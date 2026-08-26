from fastapi import APIRouter, Query
from app.topic7_onpage_content_quality.services.form_placement_service import FormPlacementService
router, svc = APIRouter(), FormPlacementService()

@router.get("/form-placement")
async def evaluate_form_placement(target_url: str = Query(...)):
    return {"status": "success", "data": await svc.calculate_placement(target_url)}
