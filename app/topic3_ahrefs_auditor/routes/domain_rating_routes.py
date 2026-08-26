from fastapi import APIRouter, UploadFile, File
from typing import Optional
from app.topic3_ahrefs_auditor.services.domain_rating_service import get_domain_rating

router = APIRouter()

@router.post("/domain-rating", summary="Get Domain Rating")
async def get_dr(organic_csv: Optional[UploadFile] = File(None)):
    b = await organic_csv.read() if organic_csv else None
    return {"dr": get_domain_rating(b)}
