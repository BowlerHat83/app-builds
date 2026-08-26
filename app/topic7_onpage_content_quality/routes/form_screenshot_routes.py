from fastapi import APIRouter, Query
from app.topic7_onpage_content_quality.services.form_screenshot_service import FormScreenshotService
router, svc = APIRouter(), FormScreenshotService()

@router.get("/form-screenshots")
async def capture_form_screenshots(target_url: str = Query(...)):
    return {"status": "success", "data": await svc.capture_form_breakdowns(target_url)}
