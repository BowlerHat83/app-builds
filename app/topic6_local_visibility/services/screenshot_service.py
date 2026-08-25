import os
import asyncio
from typing import List, Dict, Any, Union
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = "static/screenshots"

def _take_local_screenshots_sync(urls: List[str]) -> List[Dict[str, Any]]:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15000)

        for idx, url in enumerate(urls):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(1000)

                filename = f"screenshot_topic6_{idx}.png"
                filepath = os.path.join(SCREENSHOT_DIR, filename)

                page.screenshot(path=filepath, full_page=True, timeout=10000)
                results.append({
                    "url": url,
                    "file_path": filepath,
                    "download_url": f"/static/screenshots/{filename}"
                })
            except Exception as e:
                results.append({"url": url, "error": str(e)})

        context.close()
        browser.close()

    return results

async def capture_local_screenshots(urls: Union[str, List[str]] = None, *args, **kwargs) -> Dict[str, Any]:
    if isinstance(urls, str):
        urls = [urls] if urls else []
    elif not urls:
        urls = []

    captured = await asyncio.to_thread(_take_local_screenshots_sync, urls)

    return {
        "status": "success",
        "screenshots": captured
    }
