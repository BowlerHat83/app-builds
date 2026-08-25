import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query
from typing import Dict, Any

router = APIRouter(prefix="/topic7", tags=["Topic 7: Content & Forms"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def analyze_content_and_forms(target_url: str) -> Dict[str, Any]:
    url = target_url.strip()
    if not url:
        return {"status": "error", "no_of_forms": "No Data", "cta_count": "No Data", "word_count": "No Data"}
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"status": "error", "no_of_forms": "No Data", "cta_count": "No Data", "word_count": "No Data"}

            soup = BeautifulSoup(resp.text, "html.parser")

            forms = soup.find_all(["form", "iframe"])
            form_wrappers = soup.select("div.wpcf7, div.gform_wrapper, div.hs-form")
            total_forms = len(forms) + len(form_wrappers)

            ctas = soup.select("button, input[type='submit'], a.btn, a.button, a[class*='cta']")

            for element in soup(["script", "style", "nav", "footer"]):
                element.extract()
            text = soup.get_text(separator=" ")
            words = len(text.split())

            return {
                "status": "success",
                "no_of_forms": total_forms,
                "cta_count": len(ctas),
                "word_count": words
            }
    except Exception:
        return {"status": "error", "no_of_forms": "No Data", "cta_count": "No Data", "word_count": "No Data"}

async def run_topic7_full_audit(target_url: str):
    clean_url = target_url.strip() if target_url else ""
    analysis = await analyze_content_and_forms(clean_url)

    return {
        "status": "success",
        "topic": "Topic 7: Content & Forms",
        "target_url": clean_url or "No Data",
        "summary": {
            "no_of_forms": analysis["no_of_forms"],
            "cta_count": analysis["cta_count"],
            "word_count": analysis["word_count"]
        },
        "form_placement": [
            {
                "url": clean_url,
                "has_form": analysis["no_of_forms"] > 0 if isinstance(analysis["no_of_forms"], int) else "No Data",
                "form_count": analysis["no_of_forms"]
            }
        ]
    }

@router.post("/audit")
async def run_audit(target_url: str = Query(..., description="Target website URL")):
    return await run_topic7_full_audit(target_url=target_url)
