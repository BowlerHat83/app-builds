import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from app.topic3_ahrefs_auditor.services.content_gap_service import parse_content_gaps_csv

router = APIRouter(prefix="/api/topic3", tags=["Topic 3: Organic Analysis"])

@router.post("/content-gaps")
async def content_gaps_endpoint(
    file: UploadFile = File(...),
    limit: int = Query(25, ge=1, le=100, description="Number of top content gaps to return (default 25)")
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
    try:
        content = await file.read()
        return parse_content_gaps_csv(content, limit=limit)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process Content Gaps CSV: {err_msg}")
