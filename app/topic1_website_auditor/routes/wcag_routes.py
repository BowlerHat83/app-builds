import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.topic1_website_auditor.services.wcag_service import fetch_and_audit_wcag, WCAGAuditResult

router = APIRouter(prefix="/api/wcag", tags=["Topic 1: Website Auditor"])

class WCAGUrlRequest(BaseModel):
    url: str

@router.post("/check", response_model=WCAGAuditResult)
async def check_wcag(payload: WCAGUrlRequest):
    try:
        return await fetch_and_audit_wcag(payload.url)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"WCAG Audit failed: {err_msg}")

