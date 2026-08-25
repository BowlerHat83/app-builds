from fastapi import APIRouter, UploadFile, File
from typing import Optional
from app.topic3_ahrefs_auditor.services.content_gap_service import parse_content_gaps

router = APIRouter()

@router.post("/content-gap", summary="Get Content Gaps Table Data")
async def get_gaps(organic_csv: Optional[UploadFile] = File(None)):
    b = await organic_csv.read() if organic_csv else None
    return parse_content_gaps(b)
