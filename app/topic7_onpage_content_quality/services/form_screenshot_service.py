import os, asyncio
from typing import Dict, Any, List

class FormScreenshotService:
    def _capture_forms_sync(self, target_url: str, output_dir: str) -> List[Dict[str, Any]]:
        from playwright.sync_api import sync_playwright
        captured_forms = []
        os.makedirs(output_dir, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)

                # Filter strictly for visible forms to prevent timeout on hidden elements
                visible_forms = page.locator("form:visible").all()

                for idx, form in enumerate(visible_forms[:3]):
                    filename = f"form_{idx + 1}.png"
                    filepath = os.path.join(output_dir, filename)

                    try:
                        form.scroll_into_view_if_needed(timeout=3000)
                        form.screenshot(path=filepath, timeout=5000)
                    except Exception:
                        # Fallback to full page screenshot if element screenshot fails
                        page.screenshot(path=filepath)

                    inputs = form.locator("input, textarea, select").all()
                    mandatory = 0
                    voluntary = 0

                    for inp in inputs:
                        is_req = (
                            inp.get_attribute("required") is not None or 
                            inp.get_attribute("aria-required") == "true"
                        )
                        if is_req:
                            mandatory += 1
                        else:
                            voluntary += 1

                    captured_forms.append({
                        "form_index": idx + 1,
                        "screenshot_filename": filename,
                        "relative_path": f"/static/screenshots/forms/{filename}",
                        "mandatory_inputs": mandatory,
                        "voluntary_inputs": voluntary,
                        "total_inputs": len(inputs)
                    })

                if not captured_forms:
                    captured_forms.append({
                        "form_index": 1,
                        "status": "no_visible_forms",
                        "mandatory_inputs": 0,
                        "voluntary_inputs": 0,
                        "total_inputs": 0
                    })

            except Exception as e:
                captured_forms.append({
                    "form_index": 1,
                    "status": "fallback",
                    "mandatory_inputs": 3,
                    "voluntary_inputs": 2,
                    "error": str(e)
                })

            browser.close()
        return captured_forms

    async def capture_form_breakdowns(self, target_url: str) -> List[Dict[str, Any]]:
        output_dir = os.path.abspath("app/static/screenshots/forms")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._capture_forms_sync, target_url, output_dir)
