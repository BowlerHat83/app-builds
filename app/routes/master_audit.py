import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.topic1_website_auditor.aggregate import run_full_audit as run_topic1_audit
from app.topic2_performance.aggregate import run_full_audit as run_topic2_audit
from app.topic3_ahrefs_auditor.aggregate import run_full_audit as run_topic3_audit
from app.topic4_ai_visibility.aggregate import run_full_audit as run_topic4_audit
from app.topic5_paid_visibility.aggregate import run_full_audit as run_topic5_audit
from app.topic6_local_visibility.aggregate import run_full_audit as run_topic6_audit
from app.topic7_onpage_content_quality.aggregate import run_full_audit as run_topic7_audit
from app.common.prewarm_jobs import create_job, take_job

router = APIRouter()


@router.post(
    "/audit-prewarm",
    tags=["Master Audit"],
    summary="Pre-warm Chromium-based checks ahead of the full audit",
)
async def prewarm_audit(
    target_url: str = Form(..., description="Target website URL"),
    business_name: Optional[str] = Form(
        None, description="Business name - if supplied together with target_location, also pre-warms the GBP screenshot check"
    ),
    target_location: Optional[str] = Form(
        None, description="City/location - if supplied together with business_name, also pre-warms the GBP screenshot check"
    ),
):
    """
    Kicks off WCAG, GDPR, and (if business_name + target_location are both
    given) the GBP screenshot check in the background, and returns a job_id
    immediately - this call itself does no waiting. Intended to be called
    the moment the intake form's first screen (the three string inputs) is
    submitted, so that work is already running while the person is still on
    the CSV-upload screen. Pass the returned job_id back to /audit-master to
    pick up whatever finished in the meantime instead of starting fresh.

    Never required - /audit-master works exactly as before with no job_id
    at all, just without the head start.
    """
    job_id = create_job(target_url, business_name, target_location)
    return {"job_id": job_id}


async def _safe(coro, topic_label: str) -> dict:
    """
    Every topicN.run_full_audit() already catches its own sub-check
    failures and returns a "partial" envelope - this is the outer backstop
    for something unexpected (a bad import, a coding error) so one topic
    blowing up can never 500 the whole /audit-master call.
    """
    try:
        return await coro
    except Exception as e:
        return {"status": "error", "topic": topic_label, "data": {}, "warnings": [f"Unhandled exception: {e}"]}


def _extract_unbranded_keywords(
    t3: Dict[str, Any], t4: Dict[str, Any], t5: Dict[str, Any], business_name: Optional[str], limit_per_topic: int = 2
) -> List[str]:
    """
    Pulls a handful of top keywords from Topic 3 (organic search), Topic 4
    (AI-visibility citations) and Topic 5 (PPC) so Topic 6's map-pack rank
    check covers more than just the business name - a branded query almost
    always already ranks, so it doesn't say much about local visibility.
    "Unbranded" here means the keyword text doesn't already contain the
    business name.
    """
    business_lower = (business_name or "").strip().lower()

    def is_unbranded(kw: str) -> bool:
        kw_l = kw.strip().lower()
        if not kw_l:
            return False
        if business_lower and business_lower in kw_l:
            return False
        return True

    picked: List[str] = []

    def add_from(rows, key: str = "keyword"):
        count = 0
        for row in rows or []:
            if count >= limit_per_topic:
                break
            kw = str((row or {}).get(key, "")).strip()
            if kw and is_unbranded(kw) and kw not in picked:
                picked.append(kw)
                count += 1

    try:
        t3_top = (((t3 or {}).get("data") or {}).get("top_keywords") or {}).get("top_keywords")
        add_from(t3_top)
    except Exception:
        pass
    try:
        t4_top = (((t4 or {}).get("data") or {}).get("top_keywords") or {}).get("top_keywords")
        add_from(t4_top)
    except Exception:
        pass
    try:
        t5_top = (((t5 or {}).get("data") or {}).get("keywords") or {}).get("top_keywords")
        add_from(t5_top)
    except Exception:
        pass

    return picked


@router.post("/audit-master", tags=["Master Audit"], summary="Run Complete Multi-Topic SEO Audit")
async def run_master_audit(
    target_url: str = Form(..., description="Target website URL"),
    business_name: Optional[str] = Form(None, description="Business name for Local SEO (auto-detected from target_url if omitted)"),
    target_location: Optional[str] = Form(None, description="City/location for local rankings (auto-detected from target_url if omitted)"),
    screaming_frog_csv: Optional[UploadFile] = File(None, description="Screaming Frog 'Internal HTML' export - feeds Topic 2 and Topic 7"),
    ahrefs_backlinks_csv: Optional[UploadFile] = File(None, description="Ahrefs Backlinks export - feeds Topic 3"),
    ahrefs_keywords_csv: Optional[UploadFile] = File(None, description="Ahrefs Organic Keywords export - feeds Topic 3"),
    ahrefs_competitors_csv: Optional[UploadFile] = File(None, description="Ahrefs Organic Competitors export - feeds Topic 3 (Domain Rating, competitor share)"),
    ai_facts_csv: Optional[UploadFile] = File(None, description="AI-visibility tracker 'facts' export - feeds Topic 4"),
    ai_sources_csv: Optional[UploadFile] = File(None, description="AI-visibility tracker 'knowledge sources' export - feeds Topic 4"),
    ppc_keywords_csv: Optional[UploadFile] = File(None, description="PPC keyword-research export - feeds Topic 5"),
    ppc_competitors_csv: Optional[UploadFile] = File(None, description="PPC competitor-overlap export - feeds Topic 5"),
    brightlocal_csv: Optional[UploadFile] = File(None, description="BrightLocal Citation Tracker export - feeds Topic 6"),
    job_id: Optional[str] = Form(
        None, description="job_id returned by /audit-prewarm, if the two-step intake flow was used - omit to run everything fresh"
    ),
):
    sf_bytes = await screaming_frog_csv.read() if screaming_frog_csv else None
    ahrefs_backlinks_bytes = await ahrefs_backlinks_csv.read() if ahrefs_backlinks_csv else None
    ahrefs_keywords_bytes = await ahrefs_keywords_csv.read() if ahrefs_keywords_csv else None
    ahrefs_competitors_bytes = await ahrefs_competitors_csv.read() if ahrefs_competitors_csv else None
    ai_facts_bytes = await ai_facts_csv.read() if ai_facts_csv else None
    ai_sources_bytes = await ai_sources_csv.read() if ai_sources_csv else None
    ppc_keywords_bytes = await ppc_keywords_csv.read() if ppc_keywords_csv else None
    ppc_competitors_bytes = await ppc_competitors_csv.read() if ppc_competitors_csv else None
    brightlocal_bytes = await brightlocal_csv.read() if brightlocal_csv else None

    # Topic 6's map-pack rank check wants top unbranded keywords from Topics
    # 3/4/5 (see _extract_unbranded_keywords above), so it can't run fully in
    # parallel with them anymore - those six run together first, then Topic 6
    # runs once their keyword data is available. Everything else about the
    # request (upload parsing, error isolation via _safe) is unchanged.
    prewarm_job = take_job(job_id)

    t1, t2, t3, t4, t5, t7 = await asyncio.gather(
        _safe(run_topic1_audit(target_url=target_url, prewarm_job=prewarm_job), "Topic 1"),
        _safe(run_topic2_audit(target_url=target_url, csv_bytes=sf_bytes), "Topic 2"),
        _safe(
            run_topic3_audit(
                backlinks_bytes=ahrefs_backlinks_bytes,
                keywords_bytes=ahrefs_keywords_bytes,
                competitors_bytes=ahrefs_competitors_bytes,
                business_name=business_name,
            ),
            "Topic 3",
        ),
        _safe(run_topic4_audit(facts_bytes=ai_facts_bytes, sources_bytes=ai_sources_bytes, target_url=target_url), "Topic 4"),
        _safe(
            run_topic5_audit(ppc_keywords_bytes=ppc_keywords_bytes, ppc_competitors_bytes=ppc_competitors_bytes),
            "Topic 5",
        ),
        _safe(run_topic7_audit(target_url=target_url, csv_bytes=sf_bytes), "Topic 7"),
    )

    extra_keywords = _extract_unbranded_keywords(t3, t4, t5, business_name)

    t6 = await _safe(
        run_topic6_audit(
            business_name=business_name,
            target_location=target_location,
            target_url=target_url,
            brightlocal_bytes=brightlocal_bytes,
            extra_keywords=extra_keywords,
            prewarm_job=prewarm_job,
        ),
        "Topic 6",
    )

    return {
        "status": "success",
        "target_url": target_url,
        "provided_inputs": {
            "business_name": business_name or "N/A (auto-detected per topic if possible)",
            "target_location": target_location or "N/A (auto-detected per topic if possible)",
            "screaming_frog_csv": screaming_frog_csv.filename if screaming_frog_csv else "N/A",
            "ahrefs_backlinks_csv": ahrefs_backlinks_csv.filename if ahrefs_backlinks_csv else "N/A",
            "ahrefs_keywords_csv": ahrefs_keywords_csv.filename if ahrefs_keywords_csv else "N/A",
            "ahrefs_competitors_csv": ahrefs_competitors_csv.filename if ahrefs_competitors_csv else "N/A",
            "ai_facts_csv": ai_facts_csv.filename if ai_facts_csv else "N/A",
            "ai_sources_csv": ai_sources_csv.filename if ai_sources_csv else "N/A",
            "ppc_keywords_csv": ppc_keywords_csv.filename if ppc_keywords_csv else "N/A",
            "ppc_competitors_csv": ppc_competitors_csv.filename if ppc_competitors_csv else "N/A",
            "brightlocal_csv": brightlocal_csv.filename if brightlocal_csv else "N/A",
        },
        "master_audit_results": {
            "topic1_technical": t1,
            "topic2_performance": t2,
            "topic3_organic_visibility": t3,
            "topic4_ai_visibility": t4,
            "topic5_paid_visibility": t5,
            "topic6_local_visibility": t6,
            "topic7_content_quality": t7,
        },
    }
