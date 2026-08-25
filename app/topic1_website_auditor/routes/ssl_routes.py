import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.topic1_website_auditor.services.ssl_service import check_ssl_certificate, SSLCertificateInfo

router = APIRouter(prefix="/api/ssl", tags=["Topic 1: Website Auditor"])

class SSLUrlRequest(BaseModel):
    url: str

@router.post("/check", response_model=SSLCertificateInfo)
async def check_ssl_endpoint(payload: SSLUrlRequest):
    try:
        return await check_ssl_certificate(payload.url)
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"SSL Check failed: {err_msg}")

