from fastapi import APIRouter, UploadFile, File
from typing import Optional
from app.topic2_performance.services.metadata_checker import parse_metadata

router = APIRouter()

@router.post("/metadata", summary="Analyze Metadata Issues & Lengths")
async def get_metadata(screaming_frog_csv: Optional[UploadFile] = File(None)):
    content = await screaming_frog_csv.read() if screaming_frog_csv else None
    return parse_metadata(content)
