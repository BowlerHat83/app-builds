import asyncio
from typing import Optional

from fastapi import APIRouter

from app.common.audit_helpers import envelope, normalize_url, safe_check
from app.topic1_website_auditor.services.ssl_service import check_ssl_certificate
from app.topic1_website_auditor.services.sitemap_service import discover_sitemap_url, fetch_sitemap_urls
from app.topic1_website_auditor.services.wcag_service import fetch_and_audit_wcag
from app.topic1_website_auditor.services.gdpr_service import run_gdpr_audit
from app.topic1_website_auditor.services.html_checker_service import fetch_and_validate_html

router = APIRouter()


def _run_sync(coro_fn, *args):
    """Runs an async-declared-but-actually-blocking function to completion in a worker thread."""
    return asyncio.run(coro_fn(*args))


async def run_full_audit(
    target_url: str = "https://www.bowlerhat.co.uk",
    prewarm_job: Optional[dict] = None,
    **_ignored,
) -> dict:
    """
    Topic 1: Technical Standards, WCAG Accessibility, GDPR/Cookie Compliance.

    Every sub-check here is a real live check against target_url (SSL socket,
    sitemap fetch, page crawl via curl_cffi/playwright) - nothing hardcoded.
    Each is wrapped in safe_check so a single slow/broken check (GDPR's
    Playwright pass is the heaviest) degrades to a warning instead of
    failing the whole topic.

    prewarm_job, if provided, is a dict from app/common/prewarm_jobs.py -
    when its wcag_task/gdpr_task were already kicked off during the intake
    flow's first screen, this awaits those instead of launching fresh ones,
    so a request that arrives well after Screen 1 can pick up work that's
    already finished (or nearly finished) rather than starting from zero.
    """
    url = normalize_url(target_url)
    if not url:
        return envelope("Topic 1: Technical, Security & Standards Audit", {}, ["No target URL provided"])

    warnings: list = []

    # SSL is a blocking socket call - push it off the event loop.
    ssl_result, ssl_warn = await safe_check(asyncio.to_thread(check_ssl_certificate, url), "SSL certificate check", timeout=15)

    sitemap_url, sitemap_warn = await safe_check(discover_sitemap_url(url), "Sitemap discovery", timeout=15)
    sitemap_urls, sitemap_urls_warn = (None, None)
    if sitemap_url:
        sitemap_urls, sitemap_urls_warn = await safe_check(fetch_sitemap_urls(sitemap_url), "Sitemap fetch", timeout=15)

    # html_checker is declared async but calls curl_cffi synchronously inside -
    # route it through a thread so it can't block the shared event loop.
    # wcag_service is properly async now (it awaits its own Playwright work
    # via asyncio.to_thread internally, same pattern as GDPR below) and gets
    # a longer budget - it renders a real page and runs ~15 checks against
    # it (including a contrast-ratio scan), not a single curl_cffi fetch.
    #
    # Both WCAG and GDPR now share a single-slot Chromium semaphore with
    # Topic 6's screenshot capture and Topic 7's form crawl (see
    # app/common/browser_lock.py - only one headless browser runs at a time
    # across the whole audit, to stay inside free-tier RAM limits). Topic 7's
    # crawl alone can legitimately hold that slot for up to 100s, and it runs
    # concurrently with Topic 1 from master_audit.py. A 35s timeout here was
    # timing these two out just from queueing for a turn, before they ever
    # got to actually run - 90s gives enough room to wait out a worst-case
    # queue behind Topic 7 and still complete. This only affects the ceiling
    # for a slow/stuck run; a normal WCAG or GDPR pass (a handful of seconds)
    # finishes just as fast as before.
    wcag_awaitable = (prewarm_job or {}).get("wcag_task") or fetch_and_audit_wcag(url)
    wcag_result, wcag_warn = await safe_check(wcag_awaitable, "WCAG audit", timeout=90)
    html_result, html_warn = await safe_check(
        asyncio.to_thread(_run_sync, fetch_and_validate_html, url), "HTML syntax validation", timeout=20
    )

    # GDPR spins up a full headless browser - same queueing reasoning as WCAG above.
    gdpr_awaitable = (prewarm_job or {}).get("gdpr_task") or run_gdpr_audit(url)
    gdpr_result, gdpr_warn = await safe_check(gdpr_awaitable, "GDPR/cookie banner audit", timeout=90)

    for w in (ssl_warn, sitemap_warn, sitemap_urls_warn, wcag_warn, html_warn, gdpr_warn):
        if w:
            warnings.append(w)

    wcag_buckets = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    wcag_issues = []
    if wcag_result:
        for issue in wcag_result.issues:
            bucket = issue.impact.lower()
            if bucket in wcag_buckets:
                wcag_buckets[bucket] += 1
        wcag_issues = [i.model_dump() for i in wcag_result.issues]

    data = {
        "topic": "Topic 1: Technical, Security & Standards Audit",
        "target_url": url,
        "technical_standards": {
            "sitemap": {
                "found": bool(sitemap_urls),
                "sitemap_url": sitemap_url,
                "url_count": len(sitemap_urls) if sitemap_urls else 0,
            },
            "ssl_certificate": ssl_result.model_dump() if ssl_result else None,
            "html_syntax": {
                "is_valid": html_result.is_valid if html_result else None,
                "total_errors": html_result.total_errors if html_result else None,
            },
        },
        "wcag_accessibility": {
            "score": wcag_result.score if wcag_result else None,
            "total_issues": wcag_result.total_issues if wcag_result else None,
            "total_occurrences": wcag_result.total_occurrences if wcag_result else None,
            "engine": wcag_result.engine if wcag_result else None,
            "engine_note": wcag_result.engine_note if wcag_result else None,
            "by_impact": wcag_buckets,
            "issues": wcag_issues,
        },
        "gdpr_compliance": gdpr_result.model_dump() if gdpr_result else None,
    }

    return envelope("Topic 1: Technical, Security & Standards Audit", data, warnings)


@router.get("/audit", summary="Run Topic 1 Audit directly")
async def run_audit(target_url: Optional[str] = None):
    return await run_full_audit(target_url=target_url or "https://www.bowlerhat.co.uk")
