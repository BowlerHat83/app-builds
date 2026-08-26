import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Dict, List, Any

class URLExtractorService:
    async def extract_business_info(self, url: str) -> Dict[str, Any]:
        """
        Parses target URL to automatically infer business name, location, and key services.
        """
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        domain = urlparse(url).netloc.replace("www.", "")
        # Fallback business name derived from domain slug
        fallback_name = domain.split(".")[0].replace("-", " ").replace("_", " ").title()
        
        extracted_name = fallback_name
        extracted_location = "London"  # Default fallback location
        extracted_keywords = [fallback_name]

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    # 1. Extract Title
                    title_text = soup.title.string if soup.title else ""
                    if title_text:
                        parts = [p.strip() for p in re.split(r"[|:\-–]", title_text) if p.strip()]
                        if parts:
                            extracted_name = parts[0]

                    # 2. Extract Location heuristics from footer/address/meta
                    text_content = soup.get_text().lower()
                    common_cities = ["birmingham", "london", "manchester", "leeds", "bristol", "glasgow", "edinburgh"]
                    for city in common_cities:
                        if city in text_content:
                            extracted_location = city.title()
                            break

                    # 3. Generate baseline keywords
                    extracted_keywords = [
                        extracted_name,
                        f"{extracted_name} {extracted_location}"
                    ]
        except Exception:
            pass # Gracefully fall back to domain-based inference

        return {
            "business_name": extracted_name,
            "location": extracted_location,
            "keywords": extracted_keywords
        }
