from fastapi import APIRouter, UploadFile, File, HTTPException
from app.topic2_performance.services.breakdown_analyzer import process_seo_breakdown

router = APIRouter(prefix="/api/topic2/seo-breakdown", tags=["Topic 2 - SEO Breakdown"])

@router.post("/check", summary="Analyze HTTP Status & Canonical Alignment (Screaming Frog CSV)")
async def check_seo_breakdown(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    return process_seo_breakdown(contents)
