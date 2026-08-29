import os
import urllib.parse
import asyncio
from typing import Dict, Any

from app.common.browser_lock import CHROMIUM_SLOT, LOW_MEMORY_CHROMIUM_ARGS

class GBPScreenshotService:
    def _capture_sync(self, query: str, filepath: str):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ] + LOW_MEMORY_CHROMIUM_ARGS
            )
            try:

                context = browser.new_context(
                    viewport={"width": 1400, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="en-US"
                )

                page = context.new_page()
                page.set_default_timeout(10000)
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                # This used to search DuckDuckGo ("ia=places"), which doesn't
                # carry Google Business Profile data at all - a GBP screenshot
                # can only meaningfully come from Google itself. Google Maps'
                # search results show a business's actual profile card (name,
                # rating, category, hours, photos) in the left-hand panel when a
                # single business matches, which is what "Screenshot of Profile"
                # is meant to show.
                encoded_query = urllib.parse.quote(query)
                target_url = f"https://www.google.com/maps/search/{encoded_query}"

                # A shorter per-navigation timeout than the old 30s, since this
                # whole capture has to fit inside the ~30-45s budget aggregate.py
                # gives the outer safe_check call alongside browser launch and
                # the consent-dismissal/panel waits below - a single slow step
                # eating the whole budget was leaving nothing captured at all.
                page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(1200)

                # Google shows a GDPR/cookie consent interstitial ("Before you
                # continue to Google Maps") on a first, cookie-less visit for
                # many locales - dismiss it so the captured image is the actual
                # profile card, not the consent wall. Bounded to a short total
                # so a button that never appears can't stall the capture.
                try:
                    for label in ["Accept all", "I agree", "Reject all"]:
                        btn = page.get_by_role("button", name=label)
                        if btn.count() > 0:
                            btn.first.click(timeout=2000)
                            page.wait_for_timeout(1000)
                            break
                except Exception:
                    pass

                page.wait_for_timeout(800)

                # When a single business matches the query, Maps renders its
                # profile in the left side panel (role="main"). Screenshotting
                # just that panel gives the actual GBP card instead of the whole
                # map viewport (which is mostly empty map tiles).
                try:
                    panel = page.locator('[role="main"]').first
                    panel.wait_for(state="visible", timeout=5000)
                    panel.screenshot(path=filepath, timeout=5000)
                except Exception:
                    try:
                        page.screenshot(path=filepath, full_page=False, timeout=5000)
                    except Exception:
                        pass

            finally:
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
            # Only one Chromium-based check runs at a time - see app/common/browser_lock.py
            async with CHROMIUM_SLOT:
                await loop.run_in_executor(None, self._capture_sync, query, filepath)

            return {
                "business_name": business_name,
                "location": location,
                "screenshot_filename": filename,
                "relative_path": f"/static/screenshots/{filename}",
                "full_filepath": filepath,
                "source": "Google Maps",
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
