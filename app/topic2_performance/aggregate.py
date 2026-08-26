import asyncio
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.common.audit_helpers import envelope, normalize_url, safe_check
from app.topic2_performance.services.screaming_frog_service import (
    analyze_metadata_csv,
    fetch_core_web_vitals,
    fetch_tech_metrics,
)

router = APIRouter()


async def run_full_audit(target_url: str = "https://www.bowlerhat.co.uk", csv_bytes: Optional[bytes] = None, **_ignored) -> dict:
    """
    Topic 2: Performance & On-Page Metrics.

    Metadata/status-code numbers come from a real Screaming Frog CSV parse
    when one is uploaded. Page size/load time are a real live fetch of
    target_url every time, via curl_cffi (Chrome TLS impersonation) so
    Cloudflare-fronted sites don't silently return a 403 block page in
    place of real numbers - fetch_tech_metrics is a blocking call, run in
    a worker thread here. Core Web Vitals are real Lighthouse lab data via
    PageSpeed Insights, only if PAGESPEED_API_KEY is configured - otherwise
    that block comes back None with a note rather than a fabricated number.
    """
    url = normalize_url(target_url)
    warnings: list = []

    tech_metrics, tech_warn = await safe_check(
        asyncio.to_thread(fetch_tech_metrics, url), "Live page-weight/load-time check (curl_cffi)", timeout=25
    )
    if tech_warn:
        warnings.append(tech_warn)

    cwv, cwv_warn = await safe_check(
        fetch_core_web_vitals(url), "Core Web Vitals (Lighthouse via PageSpeed Insights)", timeout=50
    )
    if cwv_warn:
        warnings.append(cwv_warn)
    cwv_note = None if cwv else "PAGESPEED_API_KEY not configured - Lighthouse Core Web Vitals unavailable."

    metadata = None
    if csv_bytes:
        try:
            metadata = analyze_metadata_csv(csv_bytes)
        except Exception as e:
            warnings.append(f"Screaming Frog CSV parse failed: {e}")
    else:
        warnings.append("No Screaming Frog CSV uploaded - title/meta/status-code breakdown unavailable.")

    data = {
        "topic": "Topic 2: Performance & On-Page Metrics Audit",
        "target_url": url,
        "core_web_vitals": cwv,
        "core_web_vitals_note": cwv_note,
        "tech_metrics": tech_metrics,
        "metadata_analysis": metadata,
    }

    return envelope("Topic 2: Performance & On-Page Metrics Audit", data, warnings)


@router.get("/audit", summary="Run Topic 2 Audit directly (no CSV)")
async def run_audit(target_url: Optional[str] = None):
    return await run_full_audit(target_url=target_url or "https://www.bowlerhat.co.uk")


@router.post("/audit-all", summary="Run Topic 2 Audit with a Screaming Frog CSV")
async def run_audit_all(
    target_url: str = Form("https://www.bowlerhat.co.uk"),
    screaming_frog_csv: Optional[UploadFile] = File(None),
):
    csv_bytes = await screaming_frog_csv.read() if screaming_frog_csv else None
    return await run_full_audit(target_url=target_url, csv_bytes=csv_bytes)
