import os
import urllib.parse
import asyncio
from typing import Dict, Any

class GBPScreenshotService:
    def _capture_sync(self, query: str, filepath: str):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox"
                ]
            )
            
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-GB"
            )
            
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            encoded_query = urllib.parse.quote(query)
            target_url = f"https://duckduckgo.com/?q={encoded_query}&ia=places"
            
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # Close/Remove DuckDuckGo promo popups via JS DOM removal
            page.evaluate("""() => {
                const promos = document.querySelectorAll('.ddg-extension-hide, [class*="badge-link"], [class*="modal"], [class*="prompt"]');
                promos.forEach(el => el.remove());
                const closeBtn = document.querySelector('button[aria-label="Close"]');
                if (closeBtn) closeBtn.click();
            }""")
            
            page.wait_for_timeout(1000)
            page.screenshot(path=filepath, full_page=False)
            browser.close()

    async def capture_screenshot(self, business_name: str, location: str) -> Dict[str, Any]:
        output_dir = os.path.abspath("app/static/screenshots")
        os.makedirs(output_dir, exist_ok=True)
        
        safe_name = business_name.lower().replace(" ", "_").replace("/", "_")
        filename = f"gbp_{safe_name}_{location.lower()}.png"
        filepath = os.path.join(output_dir, filename)
        
        query = f"{business_name} {location}"

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._capture_sync, query, filepath)
                
            return {
                "business_name": business_name,
                "location": location,
                "screenshot_filename": filename,
                "relative_path": f"/static/screenshots/{filename}",
                "full_filepath": filepath,
                "status": "captured"
            }
        except Exception as e:
            return {
                "business_name": business_name,
                "location": location,
                "screenshot_filename": filename,
                "relative_path": f"/static/screenshots/{filename}",
                "status": "error",
                "error_details": str(e)
            }
