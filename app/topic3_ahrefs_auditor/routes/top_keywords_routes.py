import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from app.topic3_ahrefs_auditor.services.top_keywords_service import parse_top_keywords_csv

router = APIRouter(prefix="/api/topic3", tags=["Topic 3: Organic Analysis"])

@router.post("/top-keywords")
async def top_keywords_endpoint(
    file: UploadFile = File(...),
    limit: int = Query(25, ge=1, le=100, description="Number of top keywords to return (default 25)")
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
    try:
        content = await file.read()
        return parse_top_keywords_csv(content, limit=limit)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process Top Keywords CSV: {err_msg}")
