from fastapi import APIRouter, Form
from app.topic1_website_auditor.services.sitemap_service import check_sitemap
from app.topic1_website_auditor.services.ssl_service import check_ssl
from app.topic1_website_auditor.services.html_checker_service import check_html_syntax
from app.topic1_website_auditor.services.wcag_service import analyze_wcag
from app.topic1_website_auditor.services.gdpr_service import check_gdpr_banner

router = APIRouter()

async def run_topic1_full_audit(target_url: str):
    sitemap_res = check_sitemap(target_url)
    ssl_res = check_ssl(target_url)
    html_res = check_html_syntax(target_url)
    wcag_res = analyze_wcag(target_url)
    gdpr_res = check_gdpr_banner(target_url)

    return {
        "status": "success",
        "topic": "Topic 1: Accessibility & Technical Standards",
        "target_url": target_url,
        "technical_standards": {
            "sitemap": sitemap_res,
            "ssl_certificate": ssl_res,
            "html_syntax": html_res
        },
        "wcag_accessibility_issues": wcag_res,
        "gdpr_and_cookie_banner": gdpr_res
    }

@router.post("/audit", summary="Run Topic 1 Audit directly")
async def run_audit(target_url: str = Form(...)):
    return await run_topic1_full_audit(target_url=target_url)
