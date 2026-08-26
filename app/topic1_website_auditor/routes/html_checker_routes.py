import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.topic1_website_auditor.services.html_checker_service import fetch_and_validate_html, HTMLValidationResult

router = APIRouter(prefix="/api/html", tags=["Topic 1: Website Auditor"])

class HTMLUrlRequest(BaseModel):
    url: str

@router.post("/check", response_model=HTMLValidationResult)
async def check_html(payload: HTMLUrlRequest):
    try:
        return await fetch_and_validate_html(payload.url)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"HTML Validation failed: {err_msg}")

