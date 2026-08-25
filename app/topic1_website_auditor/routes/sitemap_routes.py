from fastapi import APIRouter, Form
from app.topic1_website_auditor.services.sitemap_service import check_sitemap

router = APIRouter()

@router.post("/sitemap", summary="Check Sitemap XML Availability")
async def get_sitemap(target_url: str = Form(...)):
    return {"sitemap": check_sitemap(target_url)}
