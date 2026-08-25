from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic4_ai_visibility.services.top_urls_service import parse_top_urls

router = APIRouter()

@router.post("/top-urls", summary="Get Top Visible URLs")
async def get_urls(target_url: str = Form(""), ai_csv: Optional[UploadFile] = File(None)):
    b = await ai_csv.read() if ai_csv and ai_csv.filename else None
    return parse_top_urls(b, target_url=target_url)
