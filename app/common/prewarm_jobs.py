"""
In-memory store for the "pre-warm" step of the audit flow.

The frontend collects the three string inputs (target URL, business name,
location) on a first screen, then CSV uploads on a second. The moment the
first screen is submitted, this kicks off the Chromium-based checks that
only need those three strings - WCAG, GDPR, and the GBP screenshot - as
background tasks, so they run while the person is still browsing for and
uploading CSVs on the second screen. By the time the real /audit-master
request goes out, some or all of that work is already done, which shrinks
how long the final request has to stay open - the actual reason a
long-running Render free-tier request was getting killed with a 502 (see
the commit that added app/common/browser_lock.py for the full story: once
Chromium checks queue one-at-a-time instead of overlapping, a real audit's
single request could take long enough to hit Render's own gateway).

This deliberately does NOT touch Topic 7's form-detection crawl, which
depends on the Screaming Frog CSV to pick good candidate pages - running it
"blind" on Screen 1 would mean checking fewer, worse-chosen pages than
waiting for the CSV gives you.

Storage is a plain in-memory dict, not a database. That's fine here: Render
free tier runs a single instance (nothing to split state across), and a job
only ever needs to survive the few minutes between Screen 1 and Screen 2 of
one person's session - not a durable historical record.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from app.common.audit_helpers import normalize_url

_JOBS: Dict[str, Dict[str, Any]] = {}

# Screen 1 filled in, Screen 2 never reached (tab closed, browser crashed) -
# without this, an abandoned job's tasks would just sit in memory forever.
# 30 minutes is generous for someone genuinely mid-audit, short enough that
# abandoned jobs don't accumulate meaningfully over a day of real usage.
_JOB_TTL_SECONDS = 30 * 60


async def _run_safely(fn, *args) -> Optional[Any]:
    """
    Wraps a prewarm check so a failure inside the background task becomes a
    plain None result instead of an unretrieved-exception warning on the
    event loop (which asyncio logs loudly if the job is later abandoned and
    nothing ever awaits it). The final aggregate treats a None result here
    exactly like a timeout or failure would if the check had run inline -
    same degrade-gracefully behaviour as before this feature existed, just
    resolved earlier.
    """
    try:
        return await fn(*args)
    except Exception:
        return None


def create_job(target_url: str, business_name: Optional[str], target_location: Optional[str]) -> str:
    """
    Kicks off the prewarm tasks and returns a job_id immediately - this
    function itself does no waiting, so the /audit-prewarm endpoint that
    calls it responds in milliseconds regardless of how long the checks it
    just started end up taking.
    """
    _cleanup_stale()

    from app.topic1_website_auditor.services.wcag_service import fetch_and_audit_wcag
    from app.topic1_website_auditor.services.gdpr_service import run_gdpr_audit
    from app.topic6_local_visibility.services.screenshot_service import GBPScreenshotService

    job_id = uuid.uuid4().hex
    url = normalize_url(target_url)

    wcag_task = asyncio.create_task(_run_safely(fetch_and_audit_wcag, url)) if url else None
    gdpr_task = asyncio.create_task(_run_safely(run_gdpr_audit, url)) if url else None

    # The GBP screenshot needs an actual business_name + location string -
    # if either was left blank on Screen 1 for topic6's own auto-detect to
    # fill in later, there's nothing meaningful to prewarm with yet, so this
    # is simply skipped and it runs fresh at final-request time instead
    # (identical to today's behaviour - no regression, just no head start).
    screenshot_task = None
    if business_name and business_name.strip() and target_location and target_location.strip():
        screenshot_svc = GBPScreenshotService()
        screenshot_task = asyncio.create_task(
            _run_safely(screenshot_svc.capture_screenshot, business_name.strip(), target_location.strip())
        )

    _JOBS[job_id] = {
        "created_at": time.monotonic(),
        "wcag_task": wcag_task,
        "gdpr_task": gdpr_task,
        "screenshot_task": screenshot_task,
    }
    return job_id


def take_job(job_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Retrieves a job's tasks for the final /audit-master request to await,
    and removes it from the store - a job is only ever meant to be collected
    once. Returns None for a missing/expired/blank job_id, which callers
    should treat as "no prewarm happened, run everything fresh" - the same
    behaviour as before this feature existed, so a lost or expired job_id
    degrades gracefully instead of erroring the whole audit.
    """
    if not job_id:
        return None
    _cleanup_stale()
    return _JOBS.pop(job_id, None)


def _cleanup_stale() -> None:
    now = time.monotonic()
    stale_ids = [jid for jid, job in _JOBS.items() if now - job["created_at"] > _JOB_TTL_SECONDS]
    for jid in stale_ids:
        job = _JOBS.pop(jid, None)
        if not job:
            continue
        for key in ("wcag_task", "gdpr_task", "screenshot_task"):
            task = job.get(key)
            if task and not task.done():
                task.cancel()
