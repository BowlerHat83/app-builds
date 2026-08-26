from fastapi import APIRouter, Form
from app.topic1_website_auditor.services.ssl_service import check_ssl

router = APIRouter()

@router.post("/ssl", summary="Verify SSL Certificate Status")
async def get_ssl(target_url: str = Form(...)):
    return {"ssl_certificate": check_ssl(target_url)}
