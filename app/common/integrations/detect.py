"""
Business detection for the intake screen.

From just the target URL, works out the three things Topic 6 needs - business
name, location and core offering - so the person running the audit only has
to confirm them (they can still override any of them). Each value comes back
with the source it was taken from, and that source is shown on Topic 6's
results as an accountability measure.

Order of preference:
  business name  - BrightLocal Citation Tracker report > the site's own
                   structured data (schema.org Organization/LocalBusiness) >
                   og:site_name > page title
  location       - BrightLocal report > the site's structured data address
  core offering  - Google Business Profile primary category (one SerpApi
                   google_maps lookup for "<name> <location>")

Nothing is ever invented: anything that can't be found comes back as None.
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.common.integrations.brightlocal import clean_report_name, find_report

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
ORG_TYPES = ("organization", "localbusiness", "corporation", "store", "professionalservice", "homeandconstructionbusiness")


def _url(u: str) -> str:
    return u if u.startswith(("http://", "https://")) else f"https://{u}"


def _walk_jsonld(node, found: list) -> None:
    if isinstance(node, list):
        for n in node:
            _walk_jsonld(n, found)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = [types] if isinstance(types, str) else (types or [])
        if any(any(o in str(t).lower() for o in ORG_TYPES) for t in types):
            found.append(node)
        for key in ("@graph", "publisher", "provider", "author", "brand"):
            if key in node:
                _walk_jsonld(node[key], found)


def _locality(org: dict) -> Optional[str]:
    addr = org.get("address")
    for a in (addr if isinstance(addr, list) else [addr]):
        if isinstance(a, dict) and a.get("addressLocality"):
            return str(a["addressLocality"]).strip()
    return None


async def _from_site(target_url: str) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {"name": None, "name_from": None, "location": None}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=UA) as client:
            resp = await client.get(_url(target_url))
        if resp.status_code != 200:
            return out
        soup = BeautifulSoup(resp.text, "html.parser")
        orgs: list = []
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                _walk_jsonld(json.loads(tag.string or ""), orgs)
            except Exception:
                continue
        for org in orgs:
            if not out["name"] and org.get("name"):
                out["name"], out["name_from"] = str(org["name"]).strip(), "website structured data"
            if not out["location"]:
                out["location"] = _locality(org)
        if not out["name"]:
            og = soup.find("meta", property="og:site_name")
            if og and og.get("content"):
                out["name"], out["name_from"] = og["content"].strip(), "website (og:site_name)"
        if not out["name"] and soup.title and soup.title.string:
            parts = [p.strip() for p in re.split(r"\s[|:\-–—]\s", soup.title.string) if p.strip()]
            if parts:
                # Brand names are usually the shortest segment of a title ("Services | Bowler Hat")
                out["name"], out["name_from"] = min(parts, key=len), "website page title"
    except Exception:
        pass
    return out


async def _gbp_category(name: str, location: Optional[str]) -> Optional[str]:
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key or not name:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://serpapi.com/search.json", params={
                "engine": "google_maps", "type": "search", "q": f"{name} {location or ''}".strip(), "api_key": api_key,
            })
        data = resp.json()
        lname = name.lower()
        candidates = [data.get("place_results") or {}] + list(data.get("local_results") or [])
        for c in candidates:
            if c and lname in str(c.get("title") or "").lower():
                cat = c.get("type") or (c.get("types") or [None])[0]
                if cat:
                    return str(cat).strip()
    except Exception:
        pass
    return None


async def detect_business(target_url: str) -> Dict[str, Any]:
    domain = urlparse(_url(target_url)).netloc.lower().removeprefix("www.")
    report, site = await asyncio.gather(find_report(target_url), _from_site(target_url))

    def field(value, source):
        return {"value": value or None, "source": source if value else None}

    if report and clean_report_name(report.get("report_name")):
        name = field(clean_report_name(report.get("report_name")), "BrightLocal Citation Tracker report")
    else:
        name = field(site["name"], site["name_from"])
    if report and report.get("business_location"):
        loc = field(str(report["business_location"]).strip(), "BrightLocal Citation Tracker report")
    else:
        loc = field(site["location"], "website structured data")

    category = await _gbp_category(name["value"], loc["value"]) if name["value"] else None
    offering = field(category, "Google Business Profile category")

    return {
        "target_url": target_url,
        "domain": domain,
        "business_name": name,
        "target_location": loc,
        "core_offering": offering,
        "brightlocal_report": (
            {"report_id": report.get("report_id"), "name": report.get("report_name"), "last_run": report.get("last_run")}
            if report else None
        ),
    }
