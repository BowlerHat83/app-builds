from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic4_ai_visibility.services.engine_visibility_service import get_engine_visibility

router = APIRouter()

@router.post("/engine-visibility", summary="Get Engine Visibility Metrics")
async def get_engines(target_url: str = Form(""), ai_csv: Optional[UploadFile] = File(None)):
    b = await ai_csv.read() if ai_csv and ai_csv.filename else None
    return get_engine_visibility(b, target_url=target_url)
