from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic2_performance.services.cwv_checker import check_cwv
from app.topic2_performance.services.metadata_checker import parse_metadata
from app.topic2_performance.services.page_size_auditor import audit_performance_metrics

router = APIRouter()

async def run_topic2_full_audit(target_url: str, screaming_frog_bytes: Optional[bytes] = None):
    cwv_data = check_cwv(target_url)
    meta_data = parse_metadata(screaming_frog_bytes)
    perf_data = audit_performance_metrics(target_url, screaming_frog_bytes)

    return {
        "status": "success",
        "topic": "Topic 2: Performance Metrics",
        "target_url": target_url,
        "core_web_vitals": cwv_data,
        "element_issues": meta_data["element_issues"],
        "title_length_breakdown": meta_data["title_length"],
        "description_length_breakdown": meta_data["description_length"],
        "performance_overview": perf_data
    }

@router.post("/audit", summary="Run Topic 2 Audit directly")
async def run_audit(
    target_url: str = Form(...),
    screaming_frog_csv: Optional[UploadFile] = File(None)
):
    sf_bytes = await screaming_frog_csv.read() if screaming_frog_csv else None
    return await run_topic2_full_audit(target_url=target_url, screaming_frog_bytes=sf_bytes)
