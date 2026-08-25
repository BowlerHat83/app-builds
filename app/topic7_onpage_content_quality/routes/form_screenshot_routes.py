from fastapi import APIRouter, Form
from app.topic7_onpage_content_quality.services.form_screenshot_service import capture_form_screenshots

router = APIRouter()

@router.post("/form-screenshots", summary="Capture Form Screenshots")
async def run_form_screenshots(target_url: str = Form(...)):
    return capture_form_screenshots(target_url)
