import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.topic1_website_auditor.services.sitemap_service import discover_sitemap_url, fetch_sitemap_urls

router = APIRouter(prefix="/api/sitemap", tags=["Topic 1: Website Auditor"])

class SitemapUrlRequest(BaseModel):
    url: str

@router.post("/check")
async def check_sitemap(payload: SitemapUrlRequest):
    try:
        sitemap_url = await discover_sitemap_url(payload.url)
        urls = await fetch_sitemap_urls(sitemap_url) if sitemap_url else []
        return {"status": "success", "sitemap_url": sitemap_url, "urls_found": urls}
    except Exception as e:
        err_msg = str(e) if str(e) else repr(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Sitemap Audit failed: {err_msg}")

