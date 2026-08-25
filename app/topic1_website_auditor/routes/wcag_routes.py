from fastapi import APIRouter, Form
from app.topic1_website_auditor.services.wcag_service import analyze_wcag

router = APIRouter()

@router.post("/wcag", summary="Analyze WCAG Accessibility Issues")
async def get_wcag(target_url: str = Form(...)):
    return analyze_wcag(target_url)
