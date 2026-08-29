import traceback
from typing import Optional
from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from app.topic3_ahrefs_auditor.services.branded_traffic_service import calculate_branded_traffic_breakdown

router = APIRouter(prefix="/api/topic3", tags=["Topic 3: Organic Analysis"])

@router.post("/branded-vs-unbranded")
async def branded_vs_unbranded_endpoint(file: UploadFile = File(...), business_name: Optional[str] = Form(None)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
    try:
        content = await file.read()
        return calculate_branded_traffic_breakdown(content, business_name)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process Branded Traffic CSV: {err_msg}")
