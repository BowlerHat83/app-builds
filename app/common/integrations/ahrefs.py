"""
Ahrefs API v3 integration (Topic 3, and Topic 6's keyword set via Topic 3).

Replaces the three Ahrefs CSV uploads when none are supplied:

  Organic Keywords export    -> /v3/site-explorer/organic-keywords
  Organic Competitors export -> /v3/site-explorer/organic-competitors
  Backlinks export           -> /v3/site-explorer/backlinks-stats (totals)
                                + /v3/site-explorer/all-backlinks (dofollow sample)

Keywords and competitors are turned back into CSV bytes using the exact
column names of Ahrefs' own exports, so every existing Topic 3 parser runs
unchanged. Backlinks are different: the CSV route counted rows in a capped
export, whereas backlinks-stats returns Ahrefs' real live totals, so the
summary is built directly (more accurate than the upload, not less).

Unit budget (Standard plan = 800,000 units/month, measured 15 Oct 2026):
organic keywords cost ~34 units per row with these fields, so they're capped
at KEYWORD_LIMIT rows (top by traffic). Worst case per audit is roughly
(250 + 100) x 34 + 25 x 5 + 1,000 x 2 + 100 = ~14,100 units (~55 audits/month).
"""

import csv
import io
import os
from datetime import date
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx
from dateutil.relativedelta import relativedelta

BASE_URL = "https://api.ahrefs.com/v3"
TIMEOUT = httpx.Timeout(45.0, connect=10.0)
KEYWORD_LIMIT = 250
GAP_KEYWORD_LIMIT = 100
COMPETITOR_LIMIT = 25
BACKLINK_SAMPLE = 1000


def _target(url: Optional[str]) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _csv(header, rows) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    w.writerows(rows)
    return out.getvalue().encode("utf-8")


async def _get(client: httpx.AsyncClient, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    resp = await client.get(f"{BASE_URL}{path}", params=params)
    resp.raise_for_status()
    return resp.json() or {}


async def fetch_ahrefs_data(
    target_url: Optional[str],
    need_keywords: bool = True,
    need_competitors: bool = True,
    need_backlinks: bool = True,
) -> Tuple[Dict[str, Any], list, Dict[str, str]]:
    """
    Returns (result, notes, sources). result may contain:
      "keywords_bytes"    - CSV bytes shaped like Ahrefs' Organic Keywords export
      "competitors_bytes" - CSV bytes shaped like Ahrefs' Organic Competitors export
      "backlinks_summary" - dict ready for data["backlinks_summary"]
    Anything that couldn't be fetched is simply absent. notes = genuine
    failures only (bad key, out of units...). sources maps "keywords" /
    "competitors" / "backlinks" to a one-line description of what was pulled,
    for the topic's Sources panel.
    """
    api_key = os.environ.get("AHREFS_API_KEY")
    target = _target(target_url)
    if not api_key or not target or not any([need_keywords, need_competitors, need_backlinks]):
        return {}, [], {}

    country = os.environ.get("AHREFS_COUNTRY", "gb")
    today = date.today()
    compared = today - relativedelta(months=3)  # 3-month lookback, matching how the CSVs are exported
    common = {"target": target, "mode": "subdomains", "date": today.isoformat()}
    result: Dict[str, Any] = {}
    notes: list = []
    pulled: Dict[str, str] = {}

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:

        if need_keywords:
            try:
                kw_select = ("keyword,volume,keyword_difficulty,best_position,best_position_prev,"
                             "sum_traffic,sum_traffic_prev,is_branded,best_position_url")
                kw_params = {**common, "country": country, "date_compared": compared.isoformat(), "select": kw_select}
                # 1) the keywords actually driving traffic (what most of Topic 3 measures)
                top = (await _get(client, "/site-explorer/organic-keywords", {
                    **kw_params, "order_by": "sum_traffic:desc", "limit": KEYWORD_LIMIT,
                })).get("keywords") or []
                # 2) page-2-to-5 keywords by search volume - content-gap candidates that a
                #    traffic-sorted pull would mostly miss on larger sites
                where = '{"and":[{"field":"best_position","is":["gte",11]},{"field":"best_position","is":["lte",50]}]}'
                gaps = (await _get(client, "/site-explorer/organic-keywords", {
                    **kw_params, "order_by": "volume:desc", "limit": GAP_KEYWORD_LIMIT, "where": where,
                })).get("keywords") or []
                seen, rows = set(), []
                for r in top + gaps:
                    k = (r.get("keyword") or "").strip().lower()
                    if k and k not in seen:
                        seen.add(k)
                        rows.append(r)

                # Only include the 3-month comparison columns when Ahrefs actually returned
                # comparison data for most rows - a column of blanks would be summed as 0
                # and show a fake traffic jump in the historic-traffic chart.
                has_prev = rows and sum(1 for r in rows if r.get("sum_traffic_prev") is not None) >= len(rows) / 2
                header = ["Keyword", "Volume", "KD", "Current position", "Current organic traffic", "Branded", "Current URL"]
                if has_prev:
                    header += ["Previous position", "Previous organic traffic"]
                body = []
                for r in rows:
                    line = [r.get("keyword"), r.get("volume"), r.get("keyword_difficulty"), r.get("best_position"),
                            r.get("sum_traffic"), bool(r.get("is_branded")), r.get("best_position_url")]
                    if has_prev:
                        line += [r.get("best_position_prev"), r.get("sum_traffic_prev")]
                    body.append(line)
                result["keywords_bytes"] = _csv(header, body)
                pulled["keywords"] = (
                    f"{len(rows)} organic keywords for {target} ({country.upper()}): top {len(top)} by traffic "
                    f"+ {len(rows) - len(top)} ranking 11-50" + ("; vs 3 months ago" if has_prev else "")
                )
            except Exception as e:
                notes.append(f"Ahrefs API organic keywords failed ({_why(e)}).")

        if need_competitors:
            try:
                j = await _get(client, "/site-explorer/organic-competitors", {
                    **common,
                    "country": country,
                    "select": "competitor_domain,domain_rating,keywords_common,keywords_competitor,share",
                    "order_by": "share:desc",
                    "limit": COMPETITOR_LIMIT,
                })
                rows = j.get("competitors") or []
                result["competitors_bytes"] = _csv(
                    ["Domain", "DR", "Common keywords", "Competitor's keywords", "Share"],
                    [[r.get("competitor_domain"), r.get("domain_rating"), r.get("keywords_common"),
                      r.get("keywords_competitor"), f"{r.get('share') or 0}%"] for r in rows],
                )
                pulled["competitors"] = f"Top {len(rows)} organic competitors by keyword share ({country.upper()})."
            except Exception as e:
                notes.append(f"Ahrefs API organic competitors failed ({_why(e)}).")

        if need_backlinks:
            try:
                stats = (await _get(client, "/site-explorer/backlinks-stats", common)).get("metrics") or {}
                live = int(stats.get("live") or 0)
                refdomains = int(stats.get("live_refdomains") or 0)
                sample = (await _get(client, "/site-explorer/all-backlinks", {
                    "target": target, "mode": "subdomains", "select": "url_from,is_dofollow", "limit": BACKLINK_SAMPLE,
                })).get("backlinks") or []
                if sample:
                    ratio = sum(1 for b in sample if b.get("is_dofollow")) / len(sample)
                    dofollow = round(live * ratio)
                else:
                    ratio, dofollow = None, live
                result["backlinks_summary"] = {
                    "total_backlinks": live,
                    "unique_referring_domains": refdomains,
                    "dofollow_backlinks": dofollow,
                    "nofollow_backlinks": live - dofollow,
                    "data_source": "ahrefs_api",
                    "methodology_note": (
                        "Live backlink and referring-domain totals straight from Ahrefs. Dofollow/nofollow split "
                        f"estimated from a sample of {len(sample)} backlinks."
                        if sample else "Live backlink and referring-domain totals straight from Ahrefs."
                    ),
                }
                pulled["backlinks"] = (
                    f"Live totals: {live:,} backlinks from {refdomains:,} referring domains"
                    + (f"; dofollow split from a {len(sample)}-link sample." if sample else ".")
                )
            except Exception as e:
                notes.append(f"Ahrefs API backlinks failed ({_why(e)}).")

    return result, notes, pulled


USD_TO_GBP = float(os.environ.get("AHREFS_USD_TO_GBP", "0.75"))


async def fetch_paid_estimate(target_url: Optional[str], competitor_limit: int = 10) -> Tuple[Optional[Dict[str, Any]], list, str]:
    """
    Topic 5 fallback when no SpyFu exports are uploaded. Ahrefs' API has no
    paid-keyword list or paid-competitor list, so this is deliberately an
    estimate:
      - the client's paid keywords / paid traffic / paid spend come from
        site-explorer/metrics (domain-level totals)
      - 'top keywords' are the top keyword of each paid landing page
        (site-explorer/paid-pages)
      - competitors are the client's ORGANIC competitors, with each one's
        paid figures from site-explorer/metrics, keeping only those that
        actually show paid activity
    Ahrefs reports cost in USD cents; converted to GBP at AHREFS_USD_TO_GBP
    so it sits alongside the rest of Topic 5. ~600 units per audit.

    Returns (data_for_topic5 or None, failure_notes, source_detail).
    """
    api_key = os.environ.get("AHREFS_API_KEY")
    target = _target(target_url)
    if not api_key or not target:
        return None, [], ""
    country = os.environ.get("AHREFS_COUNTRY", "gb")
    today = date.today().isoformat()
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    def gbp(cents):
        return round((cents or 0) / 100 * USD_TO_GBP, 2)

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
            base = {"mode": "subdomains", "country": country, "date": today}
            m = (await _get(client, "/site-explorer/metrics", {**base, "target": target})).get("metrics") or {}
            pages = (await _get(client, "/site-explorer/paid-pages", {
                **base, "target": target, "select": "url,top_keyword,top_keyword_volume,sum_traffic,value",
                "order_by": "sum_traffic:desc", "limit": 25,
            })).get("pages") or []
            comps = (await _get(client, "/site-explorer/organic-competitors", {
                **base, "target": target, "select": "competitor_domain,keywords_common",
                "order_by": "share:desc", "limit": competitor_limit,
            })).get("competitors") or []
            breakdown = []
            for c in comps:
                dom = c.get("competitor_domain")
                if not dom:
                    continue
                cm = (await _get(client, "/site-explorer/metrics", {**base, "target": dom})).get("metrics") or {}
                if (cm.get("paid_keywords") or 0) > 0:
                    breakdown.append({
                        "domain": dom,
                        "common_keywords": c.get("keywords_common"),
                        "monthly_paid_keywords": int(cm.get("paid_keywords") or 0),
                        "monthly_paid_clicks": int(cm.get("paid_traffic") or 0),
                        "monthly_ad_budget": gbp(cm.get("paid_cost")),
                    })
            breakdown.sort(key=lambda b: b["monthly_ad_budget"], reverse=True)
    except Exception as e:
        return None, [f"Ahrefs API paid search estimate failed ({_why(e)})."], ""

    paid_kw = int(m.get("paid_keywords") or 0)
    paid_clicks = int(m.get("paid_traffic") or 0)
    spend = gbp(m.get("paid_cost"))
    seen, top_keywords = set(), []
    for p in pages:
        kw = (p.get("top_keyword") or "").strip()
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            top_keywords.append({"keyword": kw, "search_volume": int(p.get("top_keyword_volume") or 0)})

    data = {
        "keywords": {
            "status": "success",
            "total_keywords": paid_kw,
            "estimated_monthly_spend": spend,
            "spend_by_match_type": {},
            "average_cpc": round(spend / paid_clicks, 2) if paid_clicks else None,
            "total_monthly_clicks": paid_clicks,
            "top_keywords": top_keywords,
            "methodology_note": (
                "Estimated from Ahrefs' paid search data (domain totals + top keyword per paid landing page). "
                "Ahrefs tracks far fewer paid keywords than a dedicated PPC tool, so these figures usually "
                "understate real campaigns - upload SpyFu exports for a full picture. "
                f"Spend converted from USD at {USD_TO_GBP}."
            ),
        },
        "competitor_share": {
            "status": "success",
            "total_competitors_analyzed": len(comps),
            "competitor_share_breakdown": breakdown,
        },
        "data_source": "ahrefs_estimate",
    }
    detail = (
        f"Estimate for {target}: {paid_kw} paid keywords, ~{paid_clicks:,} paid clicks/month, ~£{spend:,.0f}/month. "
        f"Competitors = organic competitors with paid activity ({len(breakdown)} of {len(comps)}). "
        "Ahrefs tracks limited paid data, so this usually understates real campaigns."
    )
    return data, [], detail


def _why(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        return {401: "invalid API key", 402: "out of API units", 403: "no API access on this plan", 429: "rate limited"}.get(code, f"HTTP {code}")
    return type(e).__name__
