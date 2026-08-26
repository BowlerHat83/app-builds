"""
In-memory job store for the full 7-topic background-job + polling audit
flow.

Earlier this session, a single held-open POST /audit-master request turned
out to be the real cause of the live "Failed to fetch" errors: Render's
free-tier 0.1-vCPU instance can take anywhere from ~25s to ~250s to finish
all 7 topics depending on real-time CPU contention, and once that request
ran long enough, Render/Cloudflare's own gateway gave up waiting on the
origin and returned a 502 - nothing wrong with the audit logic itself, just
a request held open too long.

This module fixes that at the root: POST /audit-start (see
app/routes/audit_jobs.py) kicks off all 7 topics as independent asyncio
background tasks and returns a job_id in milliseconds, never waiting on
anything slow. GET /audit-status/{job_id} is a cheap, instant read of
whichever topics have finished so far - the frontend polls this every few
seconds instead of holding one request open. No single HTTP request in this
flow ever needs to stay open more than an instant, so the gateway-timeout
failure mode this was built to fix cannot happen here, regardless of how
long the audit as a whole takes to finish.

This supersedes the two-step "pre-warm" flow (app/common/prewarm_jobs.py,
POST /audit-prewarm) for anything using this new flow, but that module and
/audit-master are deliberately left in place, untouched, alongside this one
- both work independently, so nothing that already worked is put at risk.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from app.topic1_website_auditor.aggregate import run_full_audit as run_topic1_audit
from app.topic2_performance.aggregate import run_full_audit as run_topic2_audit
from app.topic3_ahrefs_auditor.aggregate import run_full_audit as run_topic3_audit
from app.topic4_ai_visibility.aggregate import run_full_audit as run_topic4_audit
from app.topic5_paid_visibility.aggregate import run_full_audit as run_topic5_audit
from app.topic6_local_visibility.aggregate import run_full_audit as run_topic6_audit
from app.topic7_onpage_content_quality.aggregate import run_full_audit as run_topic7_audit
from app.routes.master_audit import _safe, _extract_unbranded_keywords

_JOBS: Dict[str, Dict[str, Any]] = {}

# A job needs to survive however long the slowest real audit takes to
# finish (worst case seen this session: ~250s), plus however long the
# person leaves the results tab open afterwards while still polling/
# reading. An hour is generous for both without letting abandoned jobs
# (tab closed mid-audit) accumulate meaningfully over a day of real usage -
# same reasoning as prewarm_jobs.py's own TTL, just longer since this job
# is meant to live for the whole audit, not just the gap between two
# intake screens.
_JOB_TTL_SECONDS = 60 * 60

_TOPIC_LABELS = {
    "topic1_technical": "Topic 1: Technical & On-Page",
    "topic2_performance": "Topic 2: Performance",
    "topic3_organic_visibility": "Topic 3: Off-Page & Organic Visibility",
    "topic4_ai_visibility": "Topic 4: AI Visibility",
    "topic5_paid_visibility": "Topic 5: Paid Visibility",
    "topic6_local_visibility": "Topic 6: Local Visibility",
    "topic7_content_quality": "Topic 7: Content Quality",
}


def _pending_envelope(topic_label: str) -> dict:
    """
    Placeholder envelope for a topic that hasn't finished yet. Deliberately
    shaped exactly like a real envelope (status/topic/data/warnings) with
    an empty data dict - every topic page component and scoring.ts already
    handle empty/missing data fields via optional chaining, and every topic
    page already renders envelope.warnings as a banner, so this renders
    correctly with zero frontend changes beyond adding "pending" to the
    EnvelopeStatus type.
    """
    return {"status": "pending", "topic": topic_label, "data": {}, "warnings": ["Still running..."]}


async def _run_topic6(t3_task, t4_task, t5_task, business_name, target_location, target_url, brightlocal_bytes) -> dict:
    """
    Topic 6's map-pack rank check wants top unbranded keywords pulled from
    Topics 3/4/5 (see _extract_unbranded_keywords in master_audit.py), so
    it can't be dispatched independently like the other six - it has to
    wait on those three tasks first. Awaiting an already-completed Task
    returns instantly, so this only actually waits if Topic 6 happens to
    finish computing its own business-info/screenshot work before all of
    3/4/5 are done.
    """
    t3 = await t3_task
    t4 = await t4_task
    t5 = await t5_task
    extra_keywords = _extract_unbranded_keywords(t3, t4, t5, business_name)
    return await _safe(
        run_topic6_audit(
            business_name=business_name,
            target_location=target_location,
            target_url=target_url,
            brightlocal_bytes=brightlocal_bytes,
            extra_keywords=extra_keywords,
        ),
        _TOPIC_LABELS["topic6_local_visibility"],
    )


def create_audit_job(
    target_url: str,
    business_name: Optional[str],
    target_location: Optional[str],
    provided_inputs: Dict[str, str],
    sf_bytes: Optional[bytes] = None,
    ahrefs_backlinks_bytes: Optional[bytes] = None,
    ahrefs_keywords_bytes: Optional[bytes] = None,
    ahrefs_competitors_bytes: Optional[bytes] = None,
    ai_facts_bytes: Optional[bytes] = None,
    ai_sources_bytes: Optional[bytes] = None,
    ppc_keywords_bytes: Optional[bytes] = None,
    ppc_competitors_bytes: Optional[bytes] = None,
    brightlocal_bytes: Optional[bytes] = None,
) -> str:
    """
    Kicks off all 7 topics as independent background tasks and returns a
    job_id immediately - this function itself does no waiting, so the
    /audit-start endpoint that calls it responds in milliseconds regardless
    of how long the checks it just started end up taking.
    """
    _cleanup_stale()

    t1_task = asyncio.create_task(_safe(run_topic1_audit(target_url=target_url), _TOPIC_LABELS["topic1_technical"]))
    t2_task = asyncio.create_task(
        _safe(run_topic2_audit(target_url=target_url, csv_bytes=sf_bytes), _TOPIC_LABELS["topic2_performance"])
    )
    t3_task = asyncio.create_task(
        _safe(
            run_topic3_audit(
                backlinks_bytes=ahrefs_backlinks_bytes,
                keywords_bytes=ahrefs_keywords_bytes,
                competitors_bytes=ahrefs_competitors_bytes,
            ),
            _TOPIC_LABELS["topic3_organic_visibility"],
        )
    )
    t4_task = asyncio.create_task(
        _safe(
            run_topic4_audit(facts_bytes=ai_facts_bytes, sources_bytes=ai_sources_bytes, target_url=target_url),
            _TOPIC_LABELS["topic4_ai_visibility"],
        )
    )
    t5_task = asyncio.create_task(
        _safe(
            run_topic5_audit(ppc_keywords_bytes=ppc_keywords_bytes, ppc_competitors_bytes=ppc_competitors_bytes),
            _TOPIC_LABELS["topic5_paid_visibility"],
        )
    )
    t7_task = asyncio.create_task(
        _safe(run_topic7_audit(target_url=target_url, csv_bytes=sf_bytes), _TOPIC_LABELS["topic7_content_quality"])
    )
    t6_task = asyncio.create_task(
        _run_topic6(t3_task, t4_task, t5_task, business_name, target_location, target_url, brightlocal_bytes)
    )

    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {
        "created_at": time.monotonic(),
        "target_url": target_url,
        "provided_inputs": provided_inputs,
        "tasks": {
            "topic1_technical": t1_task,
            "topic2_performance": t2_task,
            "topic3_organic_visibility": t3_task,
            "topic4_ai_visibility": t4_task,
            "topic5_paid_visibility": t5_task,
            "topic6_local_visibility": t6_task,
            "topic7_content_quality": t7_task,
        },
    }
    return job_id


def get_job_status(job_id: str) -> Optional[dict]:
    """
    Cheap, instant read of a job's current state - never awaits anything,
    just checks which of the 7 tasks are done and reports the rest as
    "pending". Returns None for an unknown/expired job_id so the route can
    404. Never removes the job from the store (unlike prewarm_jobs.take_job)
    so it stays pollable until it naturally expires via TTL.
    """
    _cleanup_stale()
    job = _JOBS.get(job_id)
    if not job:
        return None

    results: Dict[str, Any] = {}
    complete = True
    for key, task in job["tasks"].items():
        if task.done():
            try:
                results[key] = task.result()
            except Exception as e:
                results[key] = {"status": "error", "topic": _TOPIC_LABELS[key], "data": {}, "warnings": [f"Unhandled exception: {e}"]}
        else:
            complete = False
            results[key] = _pending_envelope(_TOPIC_LABELS[key])

    return {
        "status": "success",
        "target_url": job["target_url"],
        "provided_inputs": job["provided_inputs"],
        "master_audit_results": results,
        "job_id": job_id,
        "complete": complete,
    }


def _cleanup_stale() -> None:
    now = time.monotonic()
    stale_ids = [jid for jid, job in _JOBS.items() if now - job["created_at"] > _JOB_TTL_SECONDS]
    for jid in stale_ids:
        job = _JOBS.pop(jid, None)
        if not job:
            continue
        for task in job["tasks"].values():
            if task and not task.done():
                task.cancel()
