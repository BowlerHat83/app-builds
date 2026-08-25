from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic2_performance.services.page_size_auditor import audit_performance_metrics

router = APIRouter()

@router.post("/page-size", summary="Audit Page Size & Performance")
async def get_page_size(
    target_url: str = Form(...),
    screaming_frog_csv: Optional[UploadFile] = File(None)
):
    content = await screaming_frog_csv.read() if screaming_frog_csv else None
    return audit_performance_metrics(target_url, content)
