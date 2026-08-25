from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional

from app.topic6_local_visibility.services.brightlocal_service import process_brightlocal_csv
from app.topic6_local_visibility.services.gbp_review_service import process_gbp_reviews
from app.topic6_local_visibility.services.map_pack_service import process_map_pack

router = APIRouter()

@router.post("/brightlocal", summary="Parse BrightLocal Citation Tracker CSV")
async def parse_brightlocal(brightlocal_csv: Optional[UploadFile] = File(None)):
    content = await brightlocal_csv.read() if brightlocal_csv else None
    return process_brightlocal_csv(content) if content else "No Data"

@router.post("/gbp-reviews", summary="Fetch GBP Review Data")
async def get_gbp_reviews(
    target_url: str = Form(...),
    business_name: Optional[str] = Form(None),
    target_location: Optional[str] = Form(None)
):
    return process_gbp_reviews(target_url, business_name, target_location)

@router.post("/map-pack", summary="Check Local Map Pack Position")
async def get_map_pack(
    target_url: str = Form(...),
    business_name: Optional[str] = Form(None),
    target_location: Optional[str] = Form(None)
):
    return process_map_pack(target_url, business_name, target_location)
