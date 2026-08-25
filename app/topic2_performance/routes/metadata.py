from fastapi import APIRouter, UploadFile, File, HTTPException
from app.topic2_performance.services.metadata_checker import analyze_metadata_csv

router = APIRouter(prefix="/api/topic2/metadata", tags=["Topic 2 - Metadata"])

@router.post("/check", summary="Analyze Page Titles, Meta Descriptions, H1s & Word Counts (Screaming Frog CSV)")
async def check_metadata(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    contents = await file.read()
    return analyze_metadata_csv(contents)
