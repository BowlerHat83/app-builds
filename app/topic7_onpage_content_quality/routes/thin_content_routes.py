from fastapi import APIRouter, UploadFile, File
from typing import Optional
from app.topic7_onpage_content_quality.services.thin_content_service import analyze_thin_content

router = APIRouter()

@router.post("/thin-content", summary="Analyze Thin Content Pages")
async def get_thin_content(screaming_frog_csv: Optional[UploadFile] = File(None)):
    content = await screaming_frog_csv.read() if screaming_frog_csv else None
    return analyze_thin_content(content) if content else "No Data"
