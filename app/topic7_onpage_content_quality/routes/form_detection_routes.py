from fastapi import APIRouter, Query
from app.topic7_onpage_content_quality.services.form_detection_service import FormDetectionService
router, svc = APIRouter(), FormDetectionService()

@router.get("/form-detection")
async def detect_forms(target_url: str = Query(...)):
    return {"status": "success", "data": await svc.detect_forms(target_url)}
