import io
from typing import Optional, Tuple

import pandas as pd
from fastapi import APIRouter, File, UploadFile

from app.common.audit_helpers import envelope
from app.topic3_ahrefs_auditor.services.branded_traffic_service import calculate_branded_traffic_breakdown
from app.topic3_ahrefs_auditor.services.competitor_share_service import parse_competitor_share_csv
from app.topic3_ahrefs_auditor.services.content_gap_service import parse_content_gaps_csv
from app.topic3_ahrefs_auditor.services.domain_rating_service import parse_domain_rating_csv
from app.topic3_ahrefs_auditor.services.historic_traffic_service import generate_12month_historic_traffic
from app.topic3_ahrefs_auditor.services.keyword_position_service import parse_keyword_position_csv
from app.topic3_ahrefs_auditor.services.top_keywords_service import parse_top_keywords_csv
from app.topic3_ahrefs_auditor.services.traffic_impressions_service import parse_traffic_impressions_csv

router = APIRouter()


def _read_ahrefs_csv(csv_bytes: bytes) -> pd.DataFrame:
    """Ahrefs exports UTF-16 tab-separated files; older exports may be plain UTF-8 CSV."""
    for encoding, sep in (("utf-16", "\t"), ("utf-16-le", "\t"), ("utf-8-sig", ","), ("utf-8", ",")):
        try:
            df = pd.read_csv(io.BytesIO(csv_bytes), encoding=encoding, sep=sep, low_memory=False)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    raise ValueError("Unable to decode CSV with supported encodings (utf-16, utf-8, latin1).")


def _try(fn, *args) -> Tuple[Optional[dict], Optional[str]]:
    """Runs a sync CSV-parsing service function, converting an exception into a warning string."""
    try:
        return fn(*args), None
    except Exception as e:
        return None, f"{fn.__module__.rsplit('.', 1)[-1]} failed: {e}"


async def run_full_audit(
    backlinks_bytes: Optional[bytes] = None,
    keywords_bytes: Optional[bytes] = None,
    competitors_bytes: Optional[bytes] = None,
    business_name: Optional[str] = None,
    **_ignored,
) -> dict:
    """
    Topic 3: Ahrefs Off-Page & Organic Visibility.

    keywords_bytes (the Ahrefs "Organic Keywords" export) feeds six separate
    real analyses. competitors_bytes (Ahrefs "Organic Competitors" export -
    a different report type Ahrefs offers, not the same file as keywords/
    backlinks) is what Domain Rating and competitor share actually need; if
    it isn't uploaded those two come back None with a warning rather than
    guessing at numbers from the wrong file.
    """
    warnings: list = []
    data = {
        "topic": "Topic 3: Off-Page & Organic Visibility Audit",
        "backlinks_summary": None,
        "domain_rating": None,
        "competitor_share": None,
        "keyword_position": None,
        "top_keywords": None,
        "content_gaps": None,
        "branded_traffic": None,
        "traffic_impressions": None,
        "historic_traffic_estimate": None,
    }

    if not any([backlinks_bytes, keywords_bytes, competitors_bytes]):
        return envelope(
            "Topic 3: Off-Page & Organic Visibility Audit",
            data,
            ["No Ahrefs exports provided (backlinks / organic keywords / organic competitors)."],
        )

    if backlinks_bytes:
        try:
            df_bl = _read_ahrefs_csv(backlinks_bytes)
            total_backlinks = len(df_bl)
            ref_col = next((c for c in ["Referring domains", "Referring Domain", "Domain"] if c in df_bl.columns), None)
            ref_domains = int(df_bl[ref_col].nunique()) if ref_col else total_backlinks
            # Ahrefs' "Type" column is the link format (text/image/redirect/frame), not
            # dofollow status - that's a separate boolean "Nofollow" column. Checking
            # Type == "Dofollow" (the original logic) never matches real Ahrefs exports
            # and silently reports 0 dofollow links every time - confirmed against the
            # actual export while wiring this up.
            nofollow_col = next((c for c in ["Nofollow", "No follow"] if c in df_bl.columns), None)
            if nofollow_col:
                is_nofollow = df_bl[nofollow_col].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
                dofollow_count = int((~is_nofollow).sum())
            else:
                dofollow_count = total_backlinks
            data["backlinks_summary"] = {
                "total_backlinks": total_backlinks,
                "unique_referring_domains": ref_domains,
                "dofollow_backlinks": dofollow_count,
                "nofollow_backlinks": total_backlinks - dofollow_count,
            }
        except Exception as e:
            warnings.append(f"Backlinks CSV parse failed: {e}")
    else:
        warnings.append("No Ahrefs Backlinks CSV uploaded.")

    if keywords_bytes:
        for key, fn in (
            ("keyword_position", parse_keyword_position_csv),
            ("top_keywords", parse_top_keywords_csv),
            ("content_gaps", parse_content_gaps_csv),
            ("traffic_impressions", parse_traffic_impressions_csv),
            ("historic_traffic_estimate", generate_12month_historic_traffic),
        ):
            result, warn = _try(fn, keywords_bytes)
            data[key] = result
            if warn:
                warnings.append(warn)

        # branded_traffic needs business_name too (as a fallback classifier
        # when the CSV has no 'Branded' column of its own - see
        # branded_traffic_service.py), so it isn't part of the uniform loop
        # above.
        branded_result, branded_warn = _try(calculate_branded_traffic_breakdown, keywords_bytes, business_name)
        data["branded_traffic"] = branded_result
        if branded_warn:
            warnings.append(branded_warn)
        if data["historic_traffic_estimate"]:
            data["historic_traffic_estimate"]["methodology_note"] = (
                "Modeled from current total organic traffic using a typical seasonal curve - "
                "Ahrefs' Organic Keywords export doesn't include real month-by-month history. "
                "Use an Ahrefs 'Traffic history' export for exact monthly figures."
            )
    else:
        warnings.append("No Ahrefs Organic Keywords CSV uploaded - keyword position, top keywords, content gaps, branded traffic and traffic/impressions are unavailable.")

    if competitors_bytes:
        for key, fn in (
            ("domain_rating", parse_domain_rating_csv),
            ("competitor_share", parse_competitor_share_csv),
        ):
            result, warn = _try(fn, competitors_bytes)
            data[key] = result
            if warn:
                warnings.append(warn)
    else:
        warnings.append("No Ahrefs Organic Competitors CSV uploaded - Domain Rating and competitor share are unavailable.")

    return envelope("Topic 3: Off-Page & Organic Visibility Audit", data, warnings)


@router.post("/audit-all", summary="Run Topic 3 Audit with Ahrefs exports")
async def run_audit_all(
    ahrefs_backlinks_csv: Optional[UploadFile] = File(None),
    ahrefs_keywords_csv: Optional[UploadFile] = File(None),
    ahrefs_competitors_csv: Optional[UploadFile] = File(None),
):
    return await run_full_audit(
        backlinks_bytes=await ahrefs_backlinks_csv.read() if ahrefs_backlinks_csv else None,
        keywords_bytes=await ahrefs_keywords_csv.read() if ahrefs_keywords_csv else None,
        competitors_bytes=await ahrefs_competitors_csv.read() if ahrefs_competitors_csv else None,
    )
