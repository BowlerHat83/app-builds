import asyncio
from typing import List, Dict, Any, Union
from playwright.sync_api import sync_playwright

def _check_forms_sync(urls: List[str]) -> List[Dict[str, Any]]:
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15000)

        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                # Broader selector to include common form builders (Gravity Forms, Contact Form 7, HubSpot, iFrames)
                forms = page.query_selector_all("form, iframe[src*='form'], div.wpcf7, div.gform_wrapper, div.hs-form")
                results.append({
                    "url": url,
                    "has_form": len(forms) > 0,
                    "form_count": len(forms)
                })
            except Exception as e:
                results.append({"url": url, "error": str(e)})

        context.close()
        browser.close()

    return results

async def calculate_form_placement(urls: Union[str, List[str]] = None, *args, **kwargs) -> Dict[str, Any]:
    if isinstance(urls, str):
        urls = [urls] if urls else []
    elif not urls:
        urls = []

    placements = await asyncio.to_thread(_check_forms_sync, urls)

    return {
        "status": "success",
        "form_placement": placements
    }
