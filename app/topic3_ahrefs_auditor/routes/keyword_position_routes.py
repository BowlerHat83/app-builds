import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.topic3_ahrefs_auditor.services.keyword_position_service import parse_keyword_position_csv

router = APIRouter(prefix="/api/topic3", tags=["Topic 3: Organic Analysis"])

@router.post("/keyword-position")
async def keyword_position_endpoint(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
    try:
        content = await file.read()
        return parse_keyword_position_csv(content)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process Keyword Position CSV: {err_msg}")
