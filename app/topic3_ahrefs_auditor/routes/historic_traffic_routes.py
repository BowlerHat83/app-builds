import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.topic3_ahrefs_auditor.services.historic_traffic_service import generate_12month_historic_traffic

router = APIRouter(prefix="/api/topic3", tags=["Topic 3: Organic Analysis"])

@router.post("/historic-traffic")
async def historic_traffic_endpoint(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
    try:
        content = await file.read()
        return generate_12month_historic_traffic(content)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process Historic Traffic CSV: {err_msg}")
