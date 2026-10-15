"""
BowlerHat WCAG 2.2 scanner integration (Topic 1).

The scanner is a separate Cloud Run service with its own JSON API. A full
scan takes many minutes (BowlerHat: ~17 min for 401 pages found / 39
tested), so the audit never starts one: it only reads the latest scan Jamie
has already run in the scanner. When there's no scan for the site, Topic 1
falls back to its own quick axe-core check of the homepage.

  GET /api/lookup?url=...   -> {cached: {scanId, lastScannedAt, stale, summary}}
  GET /api/scans/{id}       -> full scan: summary + 55 criteria verdicts
  GET /api/criteria         -> criterion names and levels

Results only - no screenshots or media are fetched.
"""

import os
from typing import Any, Dict, Optional, Tuple

import httpx

DEFAULT_URL = "https://wcag-scanner-f2ygmyuiea-nw.a.run.app"
TIMEOUT = httpx.Timeout(20.0, connect=8.0)

_criteria_cache: Dict[str, Dict[str, Any]] = {}


def _base() -> Optional[str]:
    url = os.environ.get("WCAG_SCANNER_URL", DEFAULT_URL).strip()
    if url.lower() in ("", "off", "none", "disabled"):
        return None
    return url.rstrip("/")


async def _criteria(client: httpx.AsyncClient, base: str) -> Dict[str, Dict[str, Any]]:
    if _criteria_cache:
        return _criteria_cache
    try:
        resp = await client.get(f"{base}/api/criteria")
        resp.raise_for_status()
        for c in resp.json() or []:
            if c.get("id"):
                _criteria_cache[str(c["id"])] = c
    except Exception:
        pass
    return _criteria_cache


async def fetch_latest_scan(target_url: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Returns (wcag_accessibility_block, note). The block uses the same
    'wcag_accessibility' shape Topic 1 already returns (so the aggregate
    weighting is untouched - it's still the one WCAG score averaged with
    GDPR), plus a 'criteria' summary. None when there's no scan to use.
    """
    base = _base()
    if not base or not target_url:
        return None, None
    headers = {}
    key = os.environ.get("WCAG_SCANNER_KEY")
    if key:
        headers["x-api-key"] = key
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, headers=headers) as client:
            look = await client.get(f"{base}/api/lookup", params={"url": target_url})
            look.raise_for_status()
            cached = (look.json() or {}).get("cached") or {}
            scan_id = cached.get("scanId")
            if not scan_id:
                return None, "No WCAG scanner results for this site yet - using the quick homepage check instead."
            resp = await client.get(f"{base}/api/scans/{scan_id}")
            resp.raise_for_status()
            scan = resp.json() or {}
            criteria = await _criteria(client, base)
    except Exception as e:
        return None, f"WCAG scanner unavailable ({type(e).__name__}) - using the quick homepage check instead."

    s = scan.get("summary") or {}
    passed, failed = int(s.get("passed") or 0), int(s.get("failed") or 0)
    inconclusive, na = int(s.get("inconclusive") or 0), int(s.get("notApplicable") or 0)
    decided = passed + failed
    # Criteria met out of criteria decided. "To confirm" (inconclusive) needs a
    # person, so it's left out rather than counted either way.
    score = round(100 * passed / decided) if decided else None

    issues = []
    for r in scan.get("results") or []:
        if r.get("verdict") != "fail":
            continue
        cid = str(r.get("criterion") or "")
        meta = criteria.get(cid, {})
        comps = r.get("components") or []
        top = max(comps, key=lambda c: c.get("instances") or 0) if comps else {}
        issues.append({
            "code": cid,
            "description": meta.get("name") or cid,
            "impact": f"Level {meta['level']}" if meta.get("level") else "",
            "element": top.get("name") or "",
            "occurrences": int(r.get("instances") or 0),
            "pages": int(r.get("pages") or 0),
            "fixes": len(comps),
        })
    issues.sort(key=lambda i: (i["impact"] != "Level A", -i["occurrences"]))

    scanned_at = scan.get("finishedAt") or cached.get("lastScannedAt")
    stale = bool(cached.get("stale"))
    date_txt = str(scanned_at or "")[:10]
    note = (
        f"From the WCAG 2.2 scanner (scan of {date_txt}{', may be out of date' if stale else ''}): "
        f"{scan.get('pagesTested', '?')} pages tested of {scan.get('pagesCrawled', '?')} found. "
        f"{passed} criteria met, {failed} not met, {inconclusive} still to confirm by hand (left out of the score), "
        f"{na} not applicable."
    )
    block = {
        "score": score,
        "total_issues": failed,
        "total_occurrences": int(s.get("instances") or 0),
        "total_checks": decided + inconclusive,
        "engine": "WCAG 2.2 scanner",
        "engine_note": note,
        "by_impact": {"critical": 0, "serious": 0, "moderate": 0, "minor": 0},
        "issues": issues,
        "criteria": {
            "passed": passed,
            "failed": failed,
            "inconclusive": inconclusive,
            "not_applicable": na,
            "components": int(s.get("components") or 0),
            "pages_tested": scan.get("pagesTested"),
            "pages_crawled": scan.get("pagesCrawled"),
            "scanned_at": scanned_at,
            "stale": stale,
            "scan_id": scan_id,
        },
    }
    return block, None
