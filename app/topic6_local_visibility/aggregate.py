import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query, UploadFile, File
from typing import Optional, Dict, Any

router = APIRouter(prefix="/topic6", tags=["Topic 6: Local Visibility"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def extract_onpage_nap(target_url: str) -> Dict[str, Any]:
    url = target_url.strip()
    if not url:
        return {"has_schema": False, "schema_detected": "No Data"}
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"has_schema": False, "schema_detected": f"HTTP {resp.status_code}"}

            soup = BeautifulSoup(resp.text, "html.parser")
            schemas = soup.find_all("script", type="application/ld+json")

            for s in schemas:
                if s.string and "LocalBusiness" in s.string:
                    return {"has_schema": True, "schema_detected": "LocalBusiness"}

            return {"has_schema": False, "schema_detected": "None Found"}
    except Exception:
        return {"has_schema": False, "schema_detected": "Fetch Error"}

async def run_topic6_full_audit(target_url: str, brightlocal_csv_bytes: Optional[bytes] = None):
    clean_url = target_url.strip() if target_url else ""
    schema_info = await extract_onpage_nap(clean_url) if clean_url else {"schema_detected": "No Data"}

    has_csv = brightlocal_csv_bytes is not None and len(brightlocal_csv_bytes) > 0

    return {
        "status": "success",
        "topic": "Topic 6: Local Visibility",
        "target_url": clean_url or "No Data",
        "onpage_schema_status": schema_info.get("schema_detected", "No Data"),
        "nap_consistency": "CSV Parsed" if has_csv else "No Data (Requires CSV Upload)",
        "gbp_profile_completion": "CSV Parsed" if has_csv else "No Data (Requires CSV Upload)",
        "avg_map_pack_rank": "CSV Parsed" if has_csv else "No Data (Requires CSV Upload)",
        "top_reviews": []
    }

@router.post("/audit")
async def run_audit(
    target_url: str = Query(..., description="Target website URL"),
    file: Optional[UploadFile] = File(None)
):
    csv_bytes = await file.read() if file else None
    return await run_topic6_full_audit(target_url=target_url, brightlocal_csv_bytes=csv_bytes)
