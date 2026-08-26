from fastapi import APIRouter, Form
from app.topic1_website_auditor.services.html_checker_service import check_html_syntax

router = APIRouter()

@router.post("/html-checker", summary="Check HTML Syntax Status")
async def get_html(target_url: str = Form(...)):
    return {"html_syntax": check_html_syntax(target_url)}
