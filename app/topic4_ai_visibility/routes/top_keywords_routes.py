from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic4_ai_visibility.services.top_keywords_service import parse_top_search_terms

router = APIRouter()

@router.post("/top-keywords", summary="Get Top Visible Search Terms")
async def get_keywords(target_url: str = Form(""), ai_csv: Optional[UploadFile] = File(None)):
    b = await ai_csv.read() if ai_csv and ai_csv.filename else None
    return parse_top_search_terms(b, target_url=target_url)
