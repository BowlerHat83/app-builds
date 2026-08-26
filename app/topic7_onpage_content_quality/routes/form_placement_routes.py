from fastapi import APIRouter, Form
from app.topic7_onpage_content_quality.services.form_placement_service import analyze_form_placement

router = APIRouter()

@router.post("/form-placement", summary="Analyze Above/Below Fold Form Placement")
async def run_form_placement(target_url: str = Form(...)):
    return analyze_form_placement(target_url)
