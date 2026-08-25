import asyncio
import hashlib
from typing import Dict, Any

class FormDetectionService:
    def _detect_forms_sync(self, target_url: str) -> Dict[str, Any]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()
            
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)

                forms = page.locator("form").all()
                form_signatures = {}

                for form in forms:
                    action = form.get_attribute("action") or "N/A"
                    inputs = form.locator("input, textarea, select").all()
                    input_names = [
                        inp.get_attribute("name") or inp.get_attribute("id") or inp.get_attribute("type") or "input" 
                        for inp in inputs
                    ]

                    # Hash inputs signature to group duplicate forms across template elements
                    sig = hashlib.md5("".join(input_names).encode('utf-8')).hexdigest()[:8]

                    if sig not in form_signatures:
                        form_signatures[sig] = {
                            "form_id": f"form_{sig}",
                            "action": action,
                            "occurrence_count": 1,
                            "total_inputs": len(input_names),
                            "sample_inputs": input_names[:5]
                        }
                    else:
                        form_signatures[sig]["occurrence_count"] += 1

                browser.close()
                return {
                    "total_forms_found": len(forms),
                    "unique_forms_count": len(form_signatures),
                    "unique_forms": list(form_signatures.values())
                }

            except Exception as e:
                browser.close()
                return {
                    "error": str(e),
                    "total_forms_found": 0,
                    "unique_forms_count": 0,
                    "unique_forms": []
                }

    async def detect_forms(self, target_url: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_forms_sync, target_url)
