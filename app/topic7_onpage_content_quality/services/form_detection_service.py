"""
Site-wide form detection + screenshot capture.

This used to only look at a single page (whatever target_url was passed in),
capped at 5 forms max - so a contact form living on /contact-us/ or a quote
form on /marketing-audit/ was never seen at all if it wasn't on the homepage.
This now crawls a bounded set of pages likely to contain forms (the homepage
plus any URL from the Screaming Frog export whose path matches a form-likely
keyword - contact, quote, audit, signup, etc.) and dedupes forms by an
input-signature hash across ALL pages visited, not just within one page, so
the same footer contact form appearing on every page only counts once.

Crawling literally every discovered URL (a site can easily have hundreds)
would make every audit take many minutes for very little extra coverage -
this caps the candidate list and the crawl itself has an internal time
budget so it returns whatever it found rather than being hard-killed and
losing everything.
"""

import asyncio
import csv
import hashlib
import io
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.common.browser_lock import CHROMIUM_SLOT, LOW_MEMORY_CHROMIUM_ARGS

# Loose call-to-action matcher used to estimate "average CTAs per page" -
# counts <a>/<button> elements whose visible text reads like an action
# prompt, or whose class/id names them as one (cta / btn-primary / etc),
# rather than trying to be a precise design-system-aware detector.
_CTA_TEXT_RE = re.compile(
    r"\b(book (a|an|now)|call (us|now)|contact us|get (a |your )?quote|"
    r"request (a )?(demo|callback|quote)|buy now|shop now|add to (cart|basket)|"
    r"learn more|find out more|sign up|get started|start (your |a )?(free )?trial|"
    r"free trial|subscribe|enquire|enrol|apply now|schedule|download|"
    r"get in touch|speak to (us|an expert)|book a (call|demo|consultation)|"
    r"claim your|reserve|order now)\b",
    re.IGNORECASE,
)
_CTA_CLASS_RE = re.compile(r"\b(cta|btn-primary|button-primary|btn--primary)\b", re.IGNORECASE)

# Cookie-consent banners intercept clicks/screenshots on whatever they sit
# on top of - a form screenshot taken while one is still up can end up
# showing the banner instead of (or on top of) the form. This mirrors the
# generic accept-button heuristic already used in topic1's GDPR check and
# topic6's Google Maps screenshot capture.
_COOKIE_ACCEPT_LABELS = ["Accept all", "Accept All", "I agree", "Allow all", "Allow All", "Got it", "OK", "Accept"]


def _dismiss_cookie_banner(page) -> None:
    try:
        for label in _COOKIE_ACCEPT_LABELS:
            btn = page.get_by_role("button", name=label, exact=False)
            if btn.count() > 0:
                btn.first.click(timeout=1500)
                page.wait_for_timeout(500)
                return
    except Exception:
        pass


# Real per-form placement guidance, replacing what used to be a single
# hardcoded example returned for every site regardless of target_url
# (form_placement_service.py's old stub). Reuses the bounding-box + page
# height already cheap to read during the crawl pass above - no extra
# network calls or browser launches needed.
def _zone_for_depth(pct: Optional[float]) -> str:
    if pct is None:
        return "Unknown"
    if pct < 25:
        return "Hero Content (Above Fold)"
    if pct < 60:
        return "Mid-Page Content"
    if pct < 90:
        return "Lower Page Content"
    return "Footer"


def _recommendation_for_zone(zone: str) -> str:
    return {
        "Hero Content (Above Fold)": "Optimal position for high conversion - visible without scrolling.",
        "Mid-Page Content": "Reasonable position, but visitors need to scroll to reach it - consider a secondary form or sticky CTA higher on the page.",
        "Lower Page Content": "Most visitors won't scroll this far - consider moving a copy of this form higher on the page.",
        "Footer": "Buried at the bottom of the page - very few visitors will ever reach it. Strongly consider promoting this form (or a shorter version) above the fold.",
        "Unknown": "Couldn't measure this form's position on the page - it may be hidden until triggered (e.g. inside a popup/modal).",
    }.get(zone, "")

# "book" and "demo" were dropped as bare substrings - they matched inside
# unrelated words ("facebook", "demographic") on this site's blog content,
# eating candidate-page slots on pages that don't actually have forms.
# Scoped variants below keep the real "book a call" / "request a demo"
# intent without the substring collision.
FORM_PAGE_KEYWORDS = [
    "contact", "quote", "audit", "signup", "sign-up", "subscribe",
    "newsletter", "request", "book-a", "book-now", "booking",
    "get-started", "getstarted", "enquir", "apply", "schedule-a-demo",
    "request-a-demo", "book-a-demo", "consult", "callback", "register",
    "download", "trial", "free-", "estimate",
]


def _extract_urls_from_csv(csv_bytes: bytes) -> List[str]:
    decoded = csv_bytes.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(decoded))
    urls = []
    for row in reader:
        url = row.get("Address") or row.get("URL") or row.get("Target URL") or row.get("Top page")
        if url and url.startswith("http"):
            urls.append(url.strip())
    return urls


def select_candidate_form_pages(target_url: str, csv_bytes: Optional[bytes], max_pages: int = 30) -> Dict[str, Any]:
    """
    Picks a bounded set of pages likely to contain forms, instead of crawling
    every URL on the site. Always includes the homepage/target_url; the rest
    is every URL from the Screaming Frog export whose path matches a
    form-likely keyword, capped at max_pages total.
    """
    candidates = [target_url]
    seen = {target_url.rstrip("/")}
    total_discovered = 0
    matched = 0

    if csv_bytes:
        try:
            all_urls = _extract_urls_from_csv(csv_bytes)
            total_discovered = len(all_urls)
            for url in all_urls:
                if len(candidates) >= max_pages:
                    break
                path = urlparse(url).path.lower()
                if any(kw in path for kw in FORM_PAGE_KEYWORDS):
                    normalized = url.rstrip("/")
                    if normalized not in seen:
                        seen.add(normalized)
                        candidates.append(url)
                        matched += 1
        except Exception:
            pass

    return {
        "candidate_urls": candidates[:max_pages],
        "total_pages_discovered_in_csv": total_discovered,
        "form_likely_pages_matched": matched,
    }


class FormDetectionService:
    def _crawl_sync(
        self,
        candidate_urls: List[str],
        output_dir: str,
        max_screenshots: int,
        time_budget_s: float,
    ) -> Dict[str, Any]:
        from playwright.sync_api import sync_playwright

        os.makedirs(output_dir, exist_ok=True)
        unique_forms: Dict[str, Dict[str, Any]] = {}
        placement_samples: Dict[str, List[float]] = {}
        screenshots: List[Dict[str, Any]] = []
        pages_checked: List[str] = []
        screenshot_count = 0
        start = time.perf_counter()
        time_budget_hit = False

        total_ctas_found = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                # No launch args at all previously - running as root with no
                # sandbox flags in a Docker container is a common cause of
                # Chromium failing to launch outright, and without
                # --disable-dev-shm-usage this is also the heaviest of the
                # four browser launches (up to 30 pages + screenshots).
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"] + LOW_MEMORY_CHROMIUM_ARGS,
            )
            try:
                context = browser.new_context(
                    viewport={"width": 1400, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = context.new_page()

                for url in candidate_urls:
                    if time.perf_counter() - start > time_budget_s:
                        time_budget_hit = True
                        break

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=12000)
                        page.wait_for_timeout(1500)
                        _dismiss_cookie_banner(page)
                    except Exception:
                        continue

                    pages_checked.append(url)

                    try:
                        page_height = page.evaluate("() => document.body.scrollHeight") or None
                    except Exception:
                        page_height = None

                    try:
                        for el in page.locator("a, button").all():
                            try:
                                text = (el.inner_text() or "").strip()
                            except Exception:
                                text = ""
                            is_cta = bool(text) and bool(_CTA_TEXT_RE.search(text))
                            if not is_cta:
                                try:
                                    cls = el.get_attribute("class") or ""
                                except Exception:
                                    cls = ""
                                is_cta = bool(_CTA_CLASS_RE.search(cls))
                            if is_cta:
                                total_ctas_found += 1
                    except Exception:
                        pass

                    try:
                        forms = page.locator("form").all()
                    except Exception:
                        forms = []

                    for form in forms:
                        try:
                            action = form.get_attribute("action") or "N/A"
                            inputs = form.locator("input, textarea, select").all()
                            input_names = [
                                inp.get_attribute("name") or inp.get_attribute("id") or inp.get_attribute("type") or "input"
                                for inp in inputs
                            ]
                            sig = hashlib.md5("".join(input_names).encode("utf-8")).hexdigest()[:8]
                        except Exception:
                            continue

                        if page_height:
                            try:
                                bbox = form.bounding_box()
                            except Exception:
                                bbox = None
                            if bbox:
                                depth_pct = max(0.0, min(100.0, (bbox["y"] / page_height) * 100))
                                placement_samples.setdefault(sig, []).append(depth_pct)

                        if sig in unique_forms:
                            unique_forms[sig]["occurrence_count"] += 1
                            continue

                        mandatory = 0
                        voluntary = 0
                        for inp in inputs:
                            try:
                                is_req = (
                                    inp.get_attribute("required") is not None
                                    or inp.get_attribute("aria-required") == "true"
                                )
                            except Exception:
                                is_req = False
                            if is_req:
                                mandatory += 1
                            else:
                                voluntary += 1

                        unique_forms[sig] = {
                            "form_id": f"form_{sig}",
                            "action": action,
                            "first_seen_url": url,
                            "occurrence_count": 1,
                            "total_inputs": len(input_names),
                            "sample_inputs": input_names[:5],
                        }

                        try:
                            is_visible = form.is_visible()
                        except Exception:
                            is_visible = False

                        if not is_visible:
                            screenshots.append({
                                "form_id": f"form_{sig}",
                                "status": "hidden_on_load",
                                "note": "Form exists in the page HTML but wasn't visible on load (e.g. a popup/modal form) - no screenshot captured for it.",
                                "screenshot_filename": None,
                                "relative_path": None,
                                "found_on_url": url,
                                "mandatory_inputs": mandatory,
                                "voluntary_inputs": voluntary,
                                "total_inputs": len(input_names),
                            })
                            continue

                        if screenshot_count >= max_screenshots:
                            screenshots.append({
                                "form_id": f"form_{sig}",
                                "status": "skipped_screenshot_cap",
                                "note": f"Screenshot cap ({max_screenshots}) reached - this form was detected but not screenshotted.",
                                "screenshot_filename": None,
                                "relative_path": None,
                                "found_on_url": url,
                                "mandatory_inputs": mandatory,
                                "voluntary_inputs": voluntary,
                                "total_inputs": len(input_names),
                            })
                            continue

                        filename = f"form_{sig}.png"
                        filepath = os.path.join(output_dir, filename)
                        try:
                            form.scroll_into_view_if_needed(timeout=3000)
                            form.screenshot(path=filepath, timeout=5000)
                            status = "captured"
                            screenshot_count += 1
                        except Exception as e:
                            status = f"screenshot_failed: {e}"
                            filename = None

                        screenshots.append({
                            "form_id": f"form_{sig}",
                            "status": status,
                            "screenshot_filename": filename,
                            "relative_path": f"/static/screenshots/forms/{filename}" if filename else None,
                            "found_on_url": url,
                            "mandatory_inputs": mandatory,
                            "voluntary_inputs": voluntary,
                            "total_inputs": len(input_names),
                        })

            finally:
                browser.close()

        form_placement_guidance = []
        for sig, info in unique_forms.items():
            samples = placement_samples.get(sig, [])
            avg_depth = round(sum(samples) / len(samples), 1) if samples else None
            zone = _zone_for_depth(avg_depth)
            form_placement_guidance.append({
                "form_id": info["form_id"],
                "average_page_depth_percentage": f"{avg_depth}%" if avg_depth is not None else None,
                "placement_zone": zone,
                "sample_count": len(samples),
                "recommendation": _recommendation_for_zone(zone),
            })

        return {
            "pages_checked": pages_checked,
            "pages_checked_count": len(pages_checked),
            "time_budget_hit": time_budget_hit,
            "unique_forms_count": len(unique_forms),
            "unique_forms": list(unique_forms.values()),
            "form_visual_breakdowns": screenshots,
            "form_placement_guidance": form_placement_guidance,
            "total_ctas_found": total_ctas_found,
            "avg_ctas_per_page": (
                round(total_ctas_found / len(pages_checked), 2) if pages_checked else None
            ),
        }

    async def crawl_and_capture(
        self,
        candidate_urls: List[str],
        output_dir: Optional[str] = None,
        max_screenshots: int = 10,
        time_budget_s: float = 80.0,
    ) -> Dict[str, Any]:
        output_dir = output_dir or os.path.abspath("app/static/screenshots/forms")
        loop = asyncio.get_event_loop()
        # Only one Chromium-based check runs at a time - see app/common/browser_lock.py
        async with CHROMIUM_SLOT:
            return await loop.run_in_executor(
                None, self._crawl_sync, candidate_urls, output_dir, max_screenshots, time_budget_s
            )
