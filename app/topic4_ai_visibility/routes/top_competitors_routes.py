from fastapi import APIRouter, UploadFile, File
from typing import Optional
from app.topic4_ai_visibility.services.top_competitors_service import parse_top_competitors

router = APIRouter()

@router.post("/top-competitors", summary="Get Competitor Breakdown")
async def get_competitors(ai_csv: Optional[UploadFile] = File(None)):
    b = await ai_csv.read() if ai_csv and ai_csv.filename else None
    return parse_top_competitors(b)
