from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.common.audit_helpers import envelope, normalize_url, safe_check
from app.topic7_onpage_content_quality.services.form_detection_service import (
    FormDetectionService,
    select_candidate_form_pages,
)
from app.topic7_onpage_content_quality.services.thin_content_service import ThinContentService

router = APIRouter()

thin_svc = ThinContentService()
form_det_svc = FormDetectionService()


async def run_full_audit(target_url: str = "https://www.bowlerhat.co.uk", csv_bytes: Optional[bytes] = None, **_ignored) -> dict:
    """
    Topic 7: On-Page Content Quality.

    Forms are now found and screenshotted across a bounded set of pages
    likely to contain them (homepage + any Screaming Frog-listed URL whose
    path matches contact/quote/audit/signup-style keywords, capped at 30
    pages) instead of just the homepage - previously a form living only on
    e.g. /contact-us/ was invisible to this audit entirely. Detection and
    screenshot capture happen in the same crawl pass (form_detection_service
    .crawl_and_capture), since a form can only be screenshotted while its
    page is still open - dedup is by an input-signature hash across every
    page visited, so the same form appearing on multiple pages is only
    reported and screenshotted once.
    """
    url = normalize_url(target_url)
    warnings: list = []

    thin_content, thin_warn = await safe_check(
        thin_svc.analyze_thin_content(url, csv_bytes), "Thin content analysis", timeout=20
    )
    if thin_warn:
        warnings.append(thin_warn)

    page_selection = select_candidate_form_pages(url, csv_bytes, max_pages=30)
    candidate_urls = page_selection["candidate_urls"]

    crawl_result, crawl_warn = await safe_check(
        form_det_svc.crawl_and_capture(candidate_urls, max_screenshots=10, time_budget_s=80),
        "Site-wide form crawl (detection + screenshots)", timeout=100,
    )
    if crawl_warn:
        warnings.append(crawl_warn)

    form_detection = None
    form_visual_breakdowns = None
    form_placement_guidance = []
    if crawl_result:
        form_placement_guidance = crawl_result.get("form_placement_guidance") or []
        form_detection = {
            "total_forms_found": sum(f["occurrence_count"] for f in crawl_result["unique_forms"]),
            "unique_forms_count": crawl_result["unique_forms_count"],
            "unique_forms": crawl_result["unique_forms"],
            "pages_checked_count": crawl_result["pages_checked_count"],
            "pages_checked": crawl_result["pages_checked"],
            "candidate_pages_selected": len(candidate_urls),
            "total_pages_discovered_in_csv": page_selection["total_pages_discovered_in_csv"],
            "form_likely_pages_matched": page_selection["form_likely_pages_matched"],
            "total_ctas_found": crawl_result.get("total_ctas_found"),
            "avg_ctas_per_page": crawl_result.get("avg_ctas_per_page"),
            "note": (
                f"Checked {crawl_result['pages_checked_count']} of {len(candidate_urls)} candidate pages "
                f"(homepage + pages matching contact/quote/audit/signup-style URL patterns out of "
                f"{page_selection['total_pages_discovered_in_csv']} total pages in the Screaming Frog export). "
                "Not every page on the site is checked - see candidate_pages_selected / total_pages_discovered_in_csv."
            ),
        }
        if crawl_result.get("time_budget_hit"):
            warnings.append(
                f"Form crawl hit its time budget before checking all {len(candidate_urls)} candidate pages - "
                f"only {crawl_result['pages_checked_count']} were checked. Results below reflect those pages only."
            )
        form_visual_breakdowns = crawl_result["form_visual_breakdowns"]

    data = {
        "topic": "Topic 7: On-Page Content Quality Audit",
        "target_url": url,
        "thin_content_analysis": thin_content,
        "form_detection": form_detection,
        "form_visual_breakdowns": form_visual_breakdowns,
        # Real per-form placement, computed from bounding-box + page height
        # during the same crawl pass form_detection_service.py already runs -
        # see _zone_for_depth / _recommendation_for_zone there. No longer a
        # static single-example stub.
        "form_placement_guidance": form_placement_guidance,
    }

    return envelope("Topic 7: On-Page Content Quality Audit", data, warnings)


@router.post("/audit-all", summary="Run Topic 7 Audit")
async def run_audit_all(
    target_url: str = Form("https://www.bowlerhat.co.uk"),
    screaming_frog_csv: Optional[UploadFile] = File(None),
):
    csv_bytes = await screaming_frog_csv.read() if screaming_frog_csv else None
    return await run_full_audit(target_url=target_url, csv_bytes=csv_bytes)
