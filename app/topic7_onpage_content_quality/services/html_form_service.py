"""
Lightweight form + CTA detection over plain HTTP (no browser).

The headless-browser crawl in form_detection_service.py is memory-heavy, so
it's opt-in and only needed for screenshots. This module finds forms and
CTAs on the same candidate pages by fetching their HTML (curl_cffi, Chrome
TLS impersonation) and parsing it with BeautifulSoup - a few MB of memory,
so it runs on every audit. Forms injected purely by JavaScript embeds
(HubSpot, Typeform, JotForm...) aren't in the raw HTML, so their embed
scripts are recognised and reported as embedded forms instead.
"""

import hashlib
import re
import time
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from app.topic7_onpage_content_quality.services.form_detection_service import _CTA_CLASS_RE, _CTA_TEXT_RE

_EMBEDS = [
    ("HubSpot form", re.compile(r"hbspt\.forms\.create|js\.hsforms\.net|hsforms\.com/embed", re.I)),
    ("Typeform", re.compile(r"embed\.typeform\.com|data-tf-widget|data-tf-live", re.I)),
    ("JotForm", re.compile(r"jotform\.com/(jsform|embed)|form\.jotform", re.I)),
    ("Google Form", re.compile(r"docs\.google\.com/forms", re.I)),
    ("Calendly booking", re.compile(r"assets\.calendly\.com|calendly-inline-widget", re.I)),
    ("Microsoft Form", re.compile(r"forms\.office\.com", re.I)),
    ("Zoho form", re.compile(r"forms\.zohopublic|zohoforms", re.I)),
    ("Pipedrive form", re.compile(r"webforms\.pipedrive\.com", re.I)),
]


def _is_search_form(form, fields) -> bool:
    if (form.get("role") or "").lower() == "search":
        return True
    action = (form.get("action") or "").lower()
    if "search" in action or "?s=" in action:
        return True
    names = [(f.get("name") or f.get("id") or "").lower() for f in fields]
    return len(fields) <= 2 and any(n in ("s", "q", "search", "query", "keyword") for n in names)


def _detect_sync(candidate_urls: List[str], time_budget_s: float) -> Dict[str, Any]:
    from curl_cffi import requests as curl_requests

    start = time.perf_counter()
    unique: Dict[str, Dict[str, Any]] = {}
    pages_checked: List[str] = []
    total_ctas = 0
    for url in candidate_urls:
        if time.perf_counter() - start > time_budget_s:
            break
        try:
            resp = curl_requests.get(url, impersonate="chrome120", timeout=12)
            if resp.status_code >= 400 or "html" not in (resp.headers.get("content-type") or "html"):
                continue
            html = resp.text
        except Exception:
            continue
        pages_checked.append(url)
        soup = BeautifulSoup(html, "html.parser")

        for el in soup.find_all(["a", "button"]):
            text = " ".join(el.get_text(" ", strip=True).split())[:80]
            cls = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
            if (text and _CTA_TEXT_RE.search(text)) or _CTA_CLASS_RE.search(cls):
                total_ctas += 1

        for form in soup.find_all("form"):
            fields = [
                f for f in form.find_all(["input", "textarea", "select"])
                if (f.get("type") or "text").lower() not in ("hidden", "submit", "button", "image", "reset")
            ]
            if not fields or _is_search_form(form, fields):
                continue
            names = [f.get("name") or f.get("id") or f.get("type") or f.name for f in fields]
            sig = hashlib.md5("".join(names).encode("utf-8")).hexdigest()[:8]
            if sig in unique:
                unique[sig]["occurrence_count"] += 1
                continue
            required = sum(1 for f in fields if f.has_attr("required") or f.get("aria-required") == "true")
            unique[sig] = {
                "form_id": f"form_{sig}",
                "action": form.get("action") or "N/A",
                "first_seen_url": url,
                "occurrence_count": 1,
                "total_inputs": len(fields),
                "mandatory_inputs": required,
                "sample_inputs": names[:5],
            }

        for label, pattern in _EMBEDS:
            if pattern.search(html):
                sig = hashlib.md5(label.encode("utf-8")).hexdigest()[:8]
                if sig in unique:
                    unique[sig]["occurrence_count"] += 1
                else:
                    unique[sig] = {
                        "form_id": f"embed_{sig}",
                        "action": label,
                        "first_seen_url": url,
                        "occurrence_count": 1,
                        "total_inputs": 0,
                        "mandatory_inputs": 0,
                        "sample_inputs": [f"{label} (embedded - fields load by script)"],
                    }

    n = len(pages_checked)
    return {
        "unique_forms": list(unique.values()),
        "unique_forms_count": len(unique),
        "pages_checked": pages_checked,
        "pages_checked_count": n,
        "total_ctas_found": total_ctas if n else None,
        "avg_ctas_per_page": round(total_ctas / n, 1) if n else None,
    }


async def detect_forms_http(candidate_urls: List[str], time_budget_s: float = 45) -> Dict[str, Any]:
    import asyncio
    return await asyncio.to_thread(_detect_sync, candidate_urls, time_budget_s)
