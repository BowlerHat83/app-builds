"""
BrightLocal Citation Tracker integration (Topic 6).

Uses BrightLocal's Citation Tracker API (v2):
  GET /ct/get-all      - list every Citation Tracker report on the account
  GET /ct/get-results  - one report's results, including links to the exact
                         same CSV export the intake screen already accepts

Because get-results hands back a link to the real Citation Tracker CSV,
the preferred path downloads that file and feeds its bytes straight into
LocalVisibilityService.process_brightlocal_csv - identical parsing and
scoring to a manual upload. Only if that download fails does it fall back
to rebuilding a minimal CSV from the JSON (citations + potential
opportunities + domain authority). That fallback deliberately leaves out
the per-field NAP issue columns: their JSON shape isn't documented, and
inventing empty issue columns would make every citation look "clean" -
the same fabricated-100% problem process_brightlocal_csv was rewritten to
avoid. Without them, NAP consistency honestly reports as unavailable.
"""

import csv
import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

BASE_URL = "https://tools.brightlocal.com/seo-tools/api/v2"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _norm(text: Optional[str]) -> str:
    """Lowercase alphanumerics only - 'M2 Consulting (M2CONSULTING-B32AA)' -> 'm2consulting'."""
    if not text:
        return ""
    text = re.sub(r"\(.*?\)", "", str(text))  # drop BrightLocal's '(LOCATION-CODE)' suffix
    text = re.sub(r",\s*[A-Z0-9][A-Z0-9 .-]*$", "", text)  # ...and the older 'Name,CODE-B13HN' form
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _pick_report(
    reports: List[Dict[str, Any]], business_name: Optional[str], target_url: Optional[str], target_location: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Choose the Citation Tracker report that belongs to this audit's business.

    Matches on business name (BrightLocal report names are '<Business> (<CODE>)'),
    then on website domain where BrightLocal has one stored. If several match,
    a location match wins, then the most recently run report.
    """
    want_name = _norm(business_name)
    want_domain = _domain(target_url)
    want_loc = _norm(target_location)
    # The domain's first label is a decent stand-in for the name when no
    # business_name was supplied (bowlerhat.co.uk -> 'bowlerhat').
    domain_stub = _norm(want_domain.split(".")[0]) if want_domain else ""

    candidates = []
    for r in reports:
        rname = _norm(r.get("report_name")) or _norm(r.get("business_name"))
        rdomain = _domain(r.get("website_address"))
        score = 0
        if want_domain and rdomain and rdomain == want_domain:
            score = 3
        elif want_name and rname and (rname == want_name or (len(want_name) >= 4 and (want_name in rname or rname in want_name))):
            score = 2
        elif domain_stub and rname and len(domain_stub) >= 4 and (domain_stub == rname or domain_stub in rname or rname in domain_stub):
            score = 1
        if score:
            loc_match = 1 if want_loc and want_loc in _norm(r.get("business_location")) else 0
            candidates.append((score, loc_match, str(r.get("last_run") or ""), r))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1], c[2]), reverse=True)
    return candidates[0][3]


def _rows_from_json(results: Dict[str, Any]) -> bytes:
    """Fallback: rebuild a minimal Citation Tracker CSV from the get-results JSON."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Domain", "Status", "Domain Authority", "Business Name", "Address", "Zip/Postcode", "Phone Number", "Citation Link"])

    seen = set()
    for row in results.get("active") or []:
        domain = row.get("source") or _domain(row.get("url"))
        seen.add(domain)
        writer.writerow([
            domain,
            row.get("status") or "active",
            row.get("domain-authority"),
            row.get("business-name") or "",
            row.get("address") or "",
            row.get("postcode") or "",
            row.get("telephone") or "",
            row.get("url") or "",
        ])

    possible = results.get("possible") or {}
    if isinstance(possible, dict):
        for domain, info in possible.items():
            if domain in seen:
                continue
            da = info.get("domain-authority") if isinstance(info, dict) else None
            writer.writerow([domain, "Potential", da, "", "", "", "", ""])

    return out.getvalue().encode("utf-8")


async def fetch_citation_tracker_csv(
    business_name: Optional[str] = None,
    target_url: Optional[str] = None,
    target_location: Optional[str] = None,
    report_id: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Returns (csv_bytes, note). csv_bytes is None when nothing could be fetched;
    note is a short message for the topic's warnings banner (or None).
    """
    api_key = os.environ.get("BRIGHTLOCAL_API_KEY")
    if not api_key:
        return None, None  # integration not configured - behave exactly as before

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            report = None
            if report_id:
                report = {"report_id": report_id, "report_name": f"report {report_id}"}
            else:
                resp = await client.get(f"{BASE_URL}/ct/get-all", params={"api-key": api_key})
                resp.raise_for_status()
                reports = ((resp.json() or {}).get("response") or {}).get("results") or []
                report = _pick_report(reports, business_name, target_url, target_location)
                if not report:
                    return None, (
                        f"No BrightLocal Citation Tracker report found for '{business_name or _domain(target_url)}' "
                        f"({len(reports)} reports checked) - upload the Citation Tracker CSV instead, or check the "
                        "report name in BrightLocal matches the business name entered here."
                    )

            resp = await client.get(
                f"{BASE_URL}/ct/get-results", params={"api-key": api_key, "report-id": report["report_id"]}
            )
            resp.raise_for_status()
            results = ((resp.json() or {}).get("response") or {}).get("results") or {}
            label = f"BrightLocal report '{report.get('report_name')}'"
            if report.get("last_run"):
                label += f" (last run {str(report['last_run'])[:10]})"

            urls = results.get("urls") or {}
            for key in ("public_csv_url", "csv_url"):
                link = urls.get(key)
                if not link:
                    continue
                try:
                    csv_resp = await client.get(link)
                    body = csv_resp.content
                    looks_like_csv = csv_resp.status_code == 200 and body[:200].lstrip(b"\xef\xbb\xbf").startswith(b'"Domain"')
                    if looks_like_csv:
                        return body, f"Citation data pulled automatically from {label} via the BrightLocal API."
                except httpx.HTTPError:
                    continue

            if results.get("active") or results.get("possible"):
                return _rows_from_json(results), (
                    f"Citation data pulled from {label} via the BrightLocal API (summary data only - the full CSV "
                    "export couldn't be downloaded, so NAP consistency isn't available for this run)."
                )
            return None, f"{label} returned no citation data - upload the Citation Tracker CSV instead."

    except httpx.HTTPStatusError as e:
        return None, f"BrightLocal API error ({e.response.status_code}) - upload the Citation Tracker CSV instead."
    except Exception as e:  # network failure, bad JSON, etc. - never break the topic
        return None, f"BrightLocal API unavailable ({type(e).__name__}) - upload the Citation Tracker CSV instead."
