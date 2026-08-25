from fastapi import APIRouter, UploadFile, File
from typing import Optional
from app.topic3_ahrefs_auditor.services.top_keywords_service import parse_top_keywords

router = APIRouter()

@router.post("/top-keywords", summary="Get Top Keywords Table Data")
async def get_keywords(organic_csv: Optional[UploadFile] = File(None)):
    b = await organic_csv.read() if organic_csv else None
    return parse_top_keywords(b)
