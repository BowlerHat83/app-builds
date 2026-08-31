from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.common.audit_jobs import create_audit_job, get_job_status

router = APIRouter()


@router.post(
    "/audit-start",
    tags=["Master Audit"],
    summary="Start a full audit as a background job (topic-by-topic polling flow)",
)
async def start_audit_job(
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
    enable_topic6_screenshot: bool = Form(False, description="Capture a real Google Business Profile screenshot for Topic 6 (opt-in - real-browser page load, adds memory/time cost)"),
    enable_topic7_screenshots: bool = Form(False, description="Crawl for and screenshot forms for Topic 7 (opt-in - real-browser crawl across up to 30 pages, adds memory/time cost)"),
):
    """
    Starts all 7 topics running as independent background tasks and returns
    immediately with a job_id plus the initial status (every topic starts
    out "pending"). This call never waits on Chromium or any other slow
    check, so it can never itself hit a gateway timeout no matter how long
    the audit as a whole takes to finish. Poll GET /audit-status/{job_id}
    every few seconds to watch each topic fill in as it completes.
    """
    sf_bytes = await screaming_frog_csv.read() if screaming_frog_csv else None
    ahrefs_backlinks_bytes = await ahrefs_backlinks_csv.read() if ahrefs_backlinks_csv else None
    ahrefs_keywords_bytes = await ahrefs_keywords_csv.read() if ahrefs_keywords_csv else None
    ahrefs_competitors_bytes = await ahrefs_competitors_csv.read() if ahrefs_competitors_csv else None
    ai_facts_bytes = await ai_facts_csv.read() if ai_facts_csv else None
    ai_sources_bytes = await ai_sources_csv.read() if ai_sources_csv else None
    ppc_keywords_bytes = await ppc_keywords_csv.read() if ppc_keywords_csv else None
    ppc_competitors_bytes = await ppc_competitors_csv.read() if ppc_competitors_csv else None
    brightlocal_bytes = await brightlocal_csv.read() if brightlocal_csv else None

    provided_inputs = {
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
    }

    job_id = create_audit_job(
        target_url=target_url,
        business_name=business_name,
        target_location=target_location,
        provided_inputs=provided_inputs,
        sf_bytes=sf_bytes,
        ahrefs_backlinks_bytes=ahrefs_backlinks_bytes,
        ahrefs_keywords_bytes=ahrefs_keywords_bytes,
        ahrefs_competitors_bytes=ahrefs_competitors_bytes,
        ai_facts_bytes=ai_facts_bytes,
        ai_sources_bytes=ai_sources_bytes,
        ppc_keywords_bytes=ppc_keywords_bytes,
        ppc_competitors_bytes=ppc_competitors_bytes,
        brightlocal_bytes=brightlocal_bytes,
        enable_topic6_screenshot=enable_topic6_screenshot,
        enable_topic7_screenshots=enable_topic7_screenshots,
    )

    return get_job_status(job_id)


@router.get(
    "/audit-status/{job_id}",
    tags=["Master Audit"],
    summary="Poll a background audit job's progress",
)
async def audit_status(job_id: str):
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id")
    return status
