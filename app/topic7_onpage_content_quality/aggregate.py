from fastapi import APIRouter, Query, UploadFile, File
from typing import Dict, Any, Optional

from app.topic7_onpage_content_quality.services.thin_content_service import ThinContentService
from app.topic7_onpage_content_quality.services.form_detection_service import FormDetectionService
from app.topic7_onpage_content_quality.services.form_screenshot_service import FormScreenshotService
from app.topic7_onpage_content_quality.services.form_placement_service import FormPlacementService

from app.topic7_onpage_content_quality.routes.thin_content_routes import router as thin_router
from app.topic7_onpage_content_quality.routes.form_detection_routes import router as form_det_router
from app.topic7_onpage_content_quality.routes.form_screenshot_routes import router as form_ss_router
from app.topic7_onpage_content_quality.routes.form_placement_routes import router as form_place_router

router = APIRouter()

# Attach individual metric routes
router.include_router(thin_router)
router.include_router(form_det_router)
router.include_router(form_ss_router)
router.include_router(form_place_router)

thin_svc = ThinContentService()
form_det_svc = FormDetectionService()
form_ss_svc = FormScreenshotService()
form_place_svc = FormPlacementService()

class Topic7Aggregator:
    async def run_full_audit(self, target_url: str, csv_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        thin_content_data = await thin_svc.analyze_thin_content(target_url, csv_bytes)
        form_detection_data = await form_det_svc.detect_forms(target_url)
        form_screenshots = await form_ss_svc.capture_form_breakdowns(target_url)
        form_placement_data = await form_place_svc.calculate_placement(target_url)

        return {
            "topic": "Topic 7: On-Page Content Quality Audit",
            "target_url": target_url,
            "thin_content_analysis": thin_content_data,
            "form_detection": form_detection_data,
            "form_visual_breakdowns": form_screenshots,
            "form_placement_guidance": form_placement_data.get("form_placement_guidance", [])
        }

aggregator = Topic7Aggregator()

@router.post("/audit-all")
async def run_topic7_full_audit(target_url: str = "https://www.bowlerhat.co.uk", csv_bytes: Optional[bytes] = None, file: Optional[UploadFile] = None):
    if file and not csv_bytes:
        csv_bytes = await file.read()
    csv_bytes = await file.read() if file else None
    data = await aggregator.run_full_audit(target_url, csv_bytes)
    return {"status": "success", "data": data}
