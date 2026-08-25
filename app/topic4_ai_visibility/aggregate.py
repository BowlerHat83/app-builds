from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional

from app.topic4_ai_visibility.services.engine_visibility_service import get_engine_visibility
from app.topic4_ai_visibility.services.top_competitors_service import parse_top_competitors
from app.topic4_ai_visibility.services.top_keywords_service import parse_top_search_terms
from app.topic4_ai_visibility.services.top_urls_service import parse_top_urls

router = APIRouter()

async def run_topic4_full_audit(
    target_url: str = "",
    waikay_facts_bytes: Optional[bytes] = None,
    waikay_sources_bytes: Optional[bytes] = None
):
    url_str = str(target_url or "").strip()

    engines = get_engine_visibility(
        facts_bytes=waikay_facts_bytes, 
        sources_bytes=waikay_sources_bytes, 
        target_url=url_str
    )
    
    competitors = parse_top_competitors(
        sources_bytes=waikay_sources_bytes,
        facts_bytes=waikay_facts_bytes,
        target_url=url_str
    )
    
    search_terms = parse_top_search_terms(waikay_facts_bytes, target_url=url_str)
    urls = parse_top_urls(sources_bytes=waikay_sources_bytes, target_url=url_str)

    return {
        "status": "success",
        "topic": "Topic 4: AI Visibility",
        "target_url": url_str,
        "main_visibility": engines,
        "competitor_breakdown": competitors,
        "top_visible_search_terms": search_terms,
        "top_visible_urls": urls
    }

@router.post("/audit", summary="Run Topic 4 Audit directly")
async def run_audit(
    target_url: Optional[str] = Form("https://bowlerhat.co.uk"),
    waikay_facts_csv: Optional[UploadFile] = File(None),
    waikay_sources_csv: Optional[UploadFile] = File(None)
):
    facts_bytes = await waikay_facts_csv.read() if waikay_facts_csv and waikay_facts_csv.filename else None
    sources_bytes = await waikay_sources_csv.read() if waikay_sources_csv and waikay_sources_csv.filename else None
    
    return await run_topic4_full_audit(
        target_url=target_url or "", 
        waikay_facts_bytes=facts_bytes,
        waikay_sources_bytes=sources_bytes
    )
