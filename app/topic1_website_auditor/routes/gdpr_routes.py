from fastapi import APIRouter, Form
from app.topic1_website_auditor.services.gdpr_service import check_gdpr_banner

router = APIRouter()

@router.post("/gdpr", summary="Check GDPR & Cookie Banner Status")
async def get_gdpr(target_url: str = Form(...)):
    return check_gdpr_banner(target_url)
