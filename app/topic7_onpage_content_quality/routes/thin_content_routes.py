from fastapi import APIRouter, Query, UploadFile, File
from typing import Optional
from app.topic7_onpage_content_quality.services.thin_content_service import ThinContentService
router, svc = APIRouter(), ThinContentService()

@router.post("/thin-content")
async def audit_thin_content(target_url: str = Query(...), file: Optional[UploadFile] = File(None)):
    csv_bytes = await file.read() if file else None
    return {"status": "success", "data": await svc.analyze_thin_content(target_url, csv_bytes)}
