from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic7_onpage_content_quality.services.form_detection_service import detect_forms

router = APIRouter()

@router.post("/form-detection", summary="Detect Lead/Contact Forms")
async def run_form_detection(
    target_url: str = Form(...),
    screaming_frog_csv: Optional[UploadFile] = File(None)
):
    content = await screaming_frog_csv.read() if screaming_frog_csv else None
    return detect_forms(target_url, content)
