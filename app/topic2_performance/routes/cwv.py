from fastapi import APIRouter, Form
from app.topic2_performance.services.cwv_checker import check_cwv

router = APIRouter()

@router.post("/cwv", summary="Get Core Web Vitals")
async def get_cwv(target_url: str = Form(...)):
    return check_cwv(target_url)
