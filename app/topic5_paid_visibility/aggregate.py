from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional

from app.topic5_paid_visibility.services.summary_service import parse_ppc_summary
from app.topic5_paid_visibility.services.competitor_service import parse_ppc_competitors
from app.topic5_paid_visibility.services.keywords_service import parse_ppc_keywords

router = APIRouter()

async def run_topic5_full_audit(
    target_url: str = "",
    ppc_bytes: Optional[bytes] = None,
    ppc_competitor_bytes: Optional[bytes] = None
):
    url_str = str(target_url or "").strip()

    summary = parse_ppc_summary(ppc_bytes=ppc_bytes, target_url=url_str)
    competitors = parse_ppc_competitors(
        ppc_bytes=ppc_bytes, 
        ppc_competitor_bytes=ppc_competitor_bytes, 
        target_url=url_str
    )
    keywords = parse_ppc_keywords(ppc_bytes=ppc_bytes, target_url=url_str)

    return {
        "status": "success",
        "topic": "Topic 5: Paid Visibility",
        "target_url": url_str,
        "summary": summary,
        "competitor_share_breakdown": competitors,
        "top_keywords": keywords
    }

@router.post("/audit", summary="Run Topic 5 Audit directly")
async def run_audit(
    target_url: Optional[str] = Form("https://barrierbase.co.uk"),
    ppc_csv: Optional[UploadFile] = File(None),
    ppc_competitor_csv: Optional[UploadFile] = File(None)
):
    ppc_bytes = await ppc_csv.read() if ppc_csv and ppc_csv.filename else None
    ppc_comp_bytes = await ppc_competitor_csv.read() if ppc_competitor_csv and ppc_competitor_csv.filename else None
    
    return await run_topic5_full_audit(
        target_url=target_url or "", 
        ppc_bytes=ppc_bytes, 
        ppc_competitor_bytes=ppc_comp_bytes
    )
