"""
Real metadata/status-code analysis of a Screaming Frog "Internal HTML" export,
plus a live page-weight/load-time check and real Lighthouse Core Web Vitals
from Google's PageSpeed Insights API when a key is configured.

Nothing in here is invented. Where a metric genuinely isn't available (no
CSV uploaded, no PSI key set, a timing curl_cffi's simple API can't expose)
the field comes back None with a note explaining what's missing - it never
gets a hardcoded stand-in number.
"""

import asyncio
import io
import os
import time
from typing import Any, Dict, Optional

import httpx
import pandas as pd

TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 120, 158


def _distribution(series: pd.Series, min_len: int, max_len: int, missing_mask: Optional[pd.Series]) -> Dict[str, int]:
    """
    Buckets real title/description lengths into under/optimal/over.

    Rows with no title or no meta description at all have no length to
    bucket - they used to get fillna(0)'d straight into "under", which
    silently inflated that bucket with pages that don't have a title/
    description to measure in the first place, skewing the distribution.
    Those rows are now split out into their own "missing" bucket instead.

    missing_mask has to come from the TITLE/DESCRIPTION column itself
    (Title 1 / Meta Description 1), not be inferred from the LENGTH
    column's own blanks - a first attempt did that (lengths.isna()) and
    came back 0 missing on a real CSV that had 29/388 actually-missing
    rows, because Screaming Frog's "Title 1 Length"/"Meta Description 1
    Length" columns export 0 for a missing tag, not a blank cell, so
    to_numeric().isna() never saw them as missing at all - they were
    silently still landing in "under" exactly as before this fix.
    """
    lengths = pd.to_numeric(series, errors="coerce")
    if missing_mask is None:
        missing_mask = lengths.isna()
    present = lengths[~missing_mask]
    return {
        "missing": int(missing_mask.sum()),
        "under": int((present < min_len).sum()),
        "optimal": int(((present >= min_len) & (present <= max_len)).sum()),
        "over": int((present > max_len).sum()),
    }


def analyze_metadata_csv(csv_bytes: bytes) -> Dict[str, Any]:
    """Parses a Screaming Frog 'Internal HTML' export for status codes, title/meta issues."""
    df = pd.read_csv(io.BytesIO(csv_bytes), encoding="utf-8-sig", low_memory=False)
    total_urls = len(df)

    status_counts = df["Status Code"].value_counts().to_dict() if "Status Code" in df.columns else {}

    title_col = "Title 1" if "Title 1" in df.columns else None
    title_len_col = "Title 1 Length" if "Title 1 Length" in df.columns else None
    desc_col = "Meta Description 1" if "Meta Description 1" in df.columns else None
    desc_len_col = "Meta Description 1 Length" if "Meta Description 1 Length" in df.columns else None
    h1_col = "H1-1" if "H1-1" in df.columns else None

    missing_titles = int(df[title_col].isna().sum()) if title_col else None
    duplicate_titles = int(df[title_col].dropna().duplicated(keep=False).sum()) if title_col else None
    multiple_titles = int(df["Title 2"].notna().sum()) if "Title 2" in df.columns else 0

    missing_descriptions = int(df[desc_col].isna().sum()) if desc_col else None
    duplicate_descriptions = int(df[desc_col].dropna().duplicated(keep=False).sum()) if desc_col else None
    multiple_descriptions = int(df["Meta Description 2"].notna().sum()) if "Meta Description 2" in df.columns else 0

    missing_h1 = int(df[h1_col].isna().sum()) if h1_col else None

    title_missing_mask = df[title_col].isna() if title_col else None
    description_missing_mask = df[desc_col].isna() if desc_col else None
    title_distribution = (
        _distribution(df[title_len_col], TITLE_MIN, TITLE_MAX, title_missing_mask) if title_len_col else None
    )
    description_distribution = (
        _distribution(df[desc_len_col], DESC_MIN, DESC_MAX, description_missing_mask) if desc_len_col else None
    )

    indexability_errors = None
    indexation_errors_by_status_code = None
    if "Indexability" in df.columns:
        non_indexable_mask = df["Indexability"] == "Non-Indexable"
        indexability_errors = int(non_indexable_mask.sum())
        # Breakdown of the non-indexable rows specifically by their HTTP
        # status code (404/429/303/etc) - status_code_breakdown above is
        # ALL crawled URLs, not just the ones flagged as indexation errors,
        # so it can't answer "what kind of indexation errors are these".
        if "Status Code" in df.columns:
            indexation_errors_by_status_code = {
                str(k): int(v)
                for k, v in df.loc[non_indexable_mask, "Status Code"].value_counts().to_dict().items()
            }

    return {
        "screaming_frog_parsed": True,
        "total_urls_analyzed": total_urls,
        "status_code_breakdown": {str(k): int(v) for k, v in status_counts.items()},
        "indexation_errors_count": indexability_errors,
        "indexation_errors_by_status_code": indexation_errors_by_status_code,
        "meta_counts": {
            "title": {"missing": missing_titles, "duplicate": duplicate_titles, "multiple": multiple_titles},
            "description": {"missing": missing_descriptions, "duplicate": duplicate_descriptions, "multiple": multiple_descriptions},
            "missing_h1": missing_h1,
        },
        "title_distribution": title_distribution,
        "description_distribution": description_distribution,
    }


def fetch_tech_metrics(target_url: str) -> Dict[str, Any]:
    """
    Live, real measurement of page size and total load time for target_url.

    This used to use plain httpx, which was getting silently blocked by
    Cloudflare/bot-protection on Cloudflare-fronted sites - confirmed against
    a real audit run, where this returned status_code 403 and a 5.4KB page
    size that was actually Cloudflare's block page, not the site. Topic 1's
    WCAG/HTML checks against the same URL succeeded because they already go
    through curl_cffi with Chrome TLS/JA3 impersonation - this now does the
    same, which is why it's a plain (not async) function: curl_cffi's simple
    request API is blocking, same as topic1's services. The caller runs this
    in a worker thread via asyncio.to_thread.

    curl_cffi's simple requests API doesn't expose a separate time-to-first-byte
    reading (that needs its lower-level Curl/pycurl-style interface, which isn't
    used here to avoid guessing at an API surface untested in this build) -
    ttfb_ms is reported as None with a note rather than a fabricated split of
    the total time.
    """
    from curl_cffi import requests as curl_requests

    start = time.perf_counter()
    response = curl_requests.get(
        target_url,
        impersonate="chrome120",
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    total_s = time.perf_counter() - start

    return {
        "status_code": response.status_code,
        "page_size_kb": round(len(response.content) / 1024, 1),
        "ttfb_ms": None,
        "ttfb_note": (
            "Not measured separately - curl_cffi's simple request API (used here "
            "specifically to get past Cloudflare/bot-protection TLS fingerprinting) "
            "doesn't expose time-to-first-byte the way a raw streaming client does. "
            "load_time_ms below is the full request time."
        ),
        "load_time_ms": round(total_s * 1000),
        "fetch_method": "curl_cffi (Chrome TLS impersonation)",
    }


# A handful of Lighthouse's "opportunity" audits worth surfacing - these
# come back inside the same lighthouseResult.audits payload already being
# fetched for the 5 headline CWV metrics above, so reading a few more keys
# out of a response already in hand costs nothing extra (no new API call).
# Each is Lighthouse's own estimate of how many milliseconds fixing that
# specific issue could save.
_OPPORTUNITY_AUDITS = [
    ("render-blocking-resources", "Render-blocking resources"),
    ("unused-css-rules", "Unused CSS"),
    ("unused-javascript", "Unused JavaScript"),
    ("modern-image-formats", "Images not served in next-gen formats (WebP/AVIF)"),
    ("uses-text-compression", "Text-based resources not compressed"),
    ("uses-responsive-images", "Images larger than their displayed size"),
    ("offscreen-images", "Offscreen images not deferred"),
]


def _extract_opportunities(audits: Dict[str, Any]) -> list:
    opportunities = []
    for audit_key, label in _OPPORTUNITY_AUDITS:
        audit = audits.get(audit_key)
        if not audit:
            continue
        savings_ms = audit.get("numericValue")
        # A present-but-zero (or null) savings figure means Lighthouse
        # checked this and found nothing worth fixing - only a genuine
        # positive number means this is really an opportunity.
        if isinstance(savings_ms, (int, float)) and savings_ms > 0:
            opportunities.append({
                "id": audit_key,
                "label": label,
                "estimated_savings_ms": round(savings_ms),
                "display_value": audit.get("displayValue"),
            })
    opportunities.sort(key=lambda o: o["estimated_savings_ms"], reverse=True)
    return opportunities


async def fetch_core_web_vitals(target_url: str, strategy: str = "MOBILE") -> Optional[Dict[str, Any]]:
    """
    Real Lighthouse Core Web Vitals via Google's PageSpeed Insights API.

    There isn't a separate standalone "Lighthouse API" from Google - the
    PageSpeed Insights API IS the API surface for running Lighthouse
    programmatically (same free-tier key, same endpoint). This reads
    lighthouseResult.audits (a real simulated Lighthouse run against
    target_url, "lab data") rather than loadingExperience (real-user CrUX
    "field data"), because CrUX field data only exists once a site has
    enough real Chrome traffic to be reported - for a small/medium business
    site this was very often just missing, so the old field-data version of
    this function returned None far more often than it should have. Lab
    data always returns as long as the Lighthouse run itself succeeds.

    Returns None (not a guess) if PAGESPEED_API_KEY isn't set - the caller
    is responsible for surfacing that as "unavailable".
    """
    api_key = os.environ.get("PAGESPEED_API_KEY")
    if not api_key:
        return None

    # A real Lighthouse run against a full page (not a synthetic test URL)
    # commonly takes 20-45s on Google's own infrastructure, and can run
    # past that under Google's own queueing/throttling - 45s here was
    # tight enough that it was firing before the aggregate.py caller's own
    # 60s safe_check timeout ever got a chance to, which meant a routine
    # slow-but-otherwise-fine run surfaced as a failure. Raised to 80s,
    # comfortably under the 90s the caller now allows for the mobile+
    # desktop pair together - this is a plain outbound HTTP wait, not a
    # local Chromium/memory-heavy operation, so a longer timeout doesn't
    # add to this process's own memory pressure the way the topic 6/7
    # crawls do.
    async with httpx.AsyncClient(timeout=80.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params={"url": target_url, "key": api_key, "category": "PERFORMANCE", "strategy": strategy},
        )
        resp.raise_for_status()
        payload = resp.json()

    lighthouse = payload.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})
    performance_score = lighthouse.get("categories", {}).get("performance", {}).get("score")

    def _metric(audit_key: str):
        return audits.get(audit_key, {}).get("numericValue")

    # Diagnostic fields - not scored metrics, just visibility into what Lighthouse
    # actually rendered. If requested_url and final_url diverge a lot, or a
    # runtime_error/run_warning is present, Lighthouse may not have measured the
    # real page (e.g. Cloudflare/bot-protection serving it a challenge/interstitial
    # instead of the site - PSI runs from Google's own infrastructure, so the
    # curl_cffi impersonation used for tech_metrics above doesn't apply here).
    requested_url = lighthouse.get("requestedUrl")
    final_url = lighthouse.get("finalUrl")
    runtime_error = lighthouse.get("runtimeError")
    run_warnings = lighthouse.get("runWarnings", [])

    return {
        "performance_score": round(performance_score * 100) if performance_score is not None else None,
        "lcp_ms": _metric("largest-contentful-paint"),
        "cls": _metric("cumulative-layout-shift"),
        "fcp_ms": _metric("first-contentful-paint"),
        "speed_index_ms": _metric("speed-index"),
        "total_blocking_time_ms": _metric("total-blocking-time"),
        "inp_ms": None,
        "inp_note": (
            "Real INP requires field data from actual user interactions, which a "
            "single simulated Lighthouse run can't produce - total_blocking_time_ms "
            "above is the standard lab-data proxy for input responsiveness."
        ),
        "source": f"Google Lighthouse (lab data, single simulated {strategy.lower()} run via PageSpeed Insights API)",
        "opportunities": _extract_opportunities(audits),
        "diagnostics": {
            "requested_url": requested_url,
            "final_url": final_url,
            "redirected": bool(requested_url and final_url and requested_url.rstrip("/") != final_url.rstrip("/")),
            "runtime_error": runtime_error if runtime_error else None,
            "run_warnings": run_warnings,
        },
    }


async def fetch_core_web_vitals_both(target_url: str) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Runs the PageSpeed Insights Lighthouse check twice - once simulating a
    mobile device, once desktop - since the two commonly produce very
    different results (mobile's throttling profile is far more aggressive,
    so a MOBILE-only figure can understate how the site actually performs
    for a desktop visitor). Both are plain HTTP calls out to Google's own
    infrastructure - PageSpeed Insights runs Lighthouse there, not locally -
    so running them concurrently here doesn't launch Chromium or add
    meaningfully to this process's own memory footprint.
    """
    mobile, desktop = await asyncio.gather(
        fetch_core_web_vitals(target_url, strategy="MOBILE"),
        fetch_core_web_vitals(target_url, strategy="DESKTOP"),
    )
    return {"mobile": mobile, "desktop": desktop}
