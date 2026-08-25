from fastapi import APIRouter, File, UploadFile, Query, HTTPException, Body
from typing import List, Optional

from app.topic6_local_visibility.services.brightlocal_service import BrightLocalService
from app.topic6_local_visibility.services.map_pack_service import MapPackService
from app.topic6_local_visibility.services.gbp_review_service import GBPReviewService
from app.topic6_local_visibility.services.screenshot_service import GBPScreenshotService
from app.topic6_local_visibility.aggregate import Topic6Aggregator

router = APIRouter()

brightlocal_svc = BrightLocalService()
map_pack_svc = MapPackService()
gbp_review_svc = GBPReviewService()
screenshot_svc = GBPScreenshotService()
aggregator_svc = Topic6Aggregator()

@router.post("/upload-brightlocal")
async def upload_brightlocal_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV format.")
    
    contents = await file.read()
    metrics = await brightlocal_svc.process_csv(contents)
    return {"status": "success", "filename": file.filename, "data": metrics}

@router.post("/map-pack-position")
async def check_map_pack_position(
    business_name: str = Query(...),
    location: str = Query(...),
    keywords: List[str] = Body(...),
    api_key: Optional[str] = Query(None)
):
    if not keywords:
        raise HTTPException(status_code=400, detail="At least one keyword must be provided.")

    data = await map_pack_svc.get_positions(business_name, location, keywords, api_key)
    return {"status": "success", "data": data}

@router.get("/gbp-reviews")
async def get_gbp_reviews(
    business_name: str = Query(...),
    location: str = Query(...),
    api_key: Optional[str] = Query(None)
):
    data = await gbp_review_svc.get_reviews(business_name, location, api_key)
    return {"status": "success", "data": data}

@router.get("/gbp-screenshot")
async def get_gbp_screenshot(
    business_name: str = Query(...),
    location: str = Query(...)
):
    data = await screenshot_svc.capture_screenshot(business_name, location)
    return {"status": "success", "data": data}

@router.post("/audit-all")
async def run_topic6_full_audit(
    business_name: str = Query(...),
    location: str = Query(...),
    keywords: List[str] = Body(...),
    file: Optional[UploadFile] = File(None),
    api_key: Optional[str] = Query(None)
):
    csv_bytes = None
    if file:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Uploaded file must be a CSV.")
        csv_bytes = await file.read()

    data = await aggregator_svc.run_full_audit(
        business_name=business_name,
        location=location,
        keywords=keywords,
        csv_bytes=csv_bytes,
        api_key=api_key
    )
    return {"status": "success", "data": data}
