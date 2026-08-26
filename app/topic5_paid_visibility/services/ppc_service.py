"""
Real parsing for Topic 5 (Paid Visibility). This topic previously had no
CSV parser at all - just a two-entry hardcoded dictionary. These two
functions read the PPC keyword-research export and the competitor-overlap
export the team actually pulls (both plain UTF-8/ASCII CSVs, unlike the
Ahrefs UTF-16 files) and turn them into the numbers the frontend expects:
keyword count, estimated spend, average CPC, click volume, and a
competitor ad-share breakdown.
"""

import io
from typing import Any, Dict

import pandas as pd


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError("Unable to decode CSV with supported encodings (utf-8, latin1).")


def _to_num(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(",", "", regex=False).replace({"-": None, "nan": None})
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def parse_ppc_keywords_csv(file_bytes: bytes, limit: int = 25) -> Dict[str, Any]:
    """Parses a PPC keyword-research export (Keyword, Search Volume, CPC/clicks/cost by match type)."""
    df = _read_csv(file_bytes)
    if "Keyword" not in df.columns:
        raise ValueError(f"CSV missing 'Keyword' column. Columns found: {list(df.columns)}")

    volume_col = "Search Volume" if "Search Volume" in df.columns else None
    clicks_col = "Total Monthly Clicks" if "Total Monthly Clicks" in df.columns else None
    cpc_cols = [c for c in ["Exact Cost Per Click", "Phrase Cost Per Click", "Broad Cost Per Click"] if c in df.columns]
    cost_cols = {"exact": "Exact Monthly Cost", "phrase": "Phrase Monthly Cost", "broad": "Broad Monthly Cost"}

    for col in [volume_col, clicks_col, *cpc_cols, *[c for c in cost_cols.values() if c in df.columns]]:
        if col:
            df[col] = _to_num(df[col])

    total_keywords = len(df)
    total_clicks = int(df[clicks_col].sum()) if clicks_col else None

    average_cpc = None
    if cpc_cols:
        nonzero_cpc = df[df[cpc_cols[0]] > 0][cpc_cols[0]]
        average_cpc = round(float(nonzero_cpc.mean()), 2) if len(nonzero_cpc) else None

    spend_by_match_type = {label: round(float(df[col].sum()), 2) for label, col in cost_cols.items() if col in df.columns}
    estimated_monthly_spend = spend_by_match_type.get("exact")

    top_keywords = []
    if volume_col:
        for _, row in df.sort_values(by=volume_col, ascending=False).head(limit).iterrows():
            entry = {"keyword": str(row["Keyword"]), "search_volume": int(row[volume_col])}
            if cpc_cols:
                entry["cpc"] = round(float(row[cpc_cols[0]]), 2)
            top_keywords.append(entry)

    return {
        "status": "success",
        "total_keywords": total_keywords,
        "estimated_monthly_spend": estimated_monthly_spend,
        "spend_by_match_type": spend_by_match_type,
        "average_cpc": average_cpc,
        "total_monthly_clicks": total_clicks,
        "top_keywords": top_keywords,
        "methodology_note": (
            "Spend/CPC use the Exact-match columns as the conservative estimate - see "
            "spend_by_match_type for Broad/Phrase/Exact individually, since the export "
            "doesn't say which match type is actually active in a live campaign."
        ),
    }


def parse_ppc_competitors_csv(file_bytes: bytes, limit: int = 10) -> Dict[str, Any]:
    """Parses a PPC competitor-overlap export (Domain Name, Common Keywords, Monthly Paid Keywords/Clicks/Budget)."""
    df = _read_csv(file_bytes)
    if "Domain Name" not in df.columns:
        raise ValueError(f"CSV missing 'Domain Name' column. Columns found: {list(df.columns)}")

    numeric_cols = ["Common Keywords", "Monthly Paid Keywords", "Monthly Paid Clicks", "Monthly Ad Budget"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = _to_num(df[col])

    df_sorted = df.sort_values(by="Monthly Ad Budget", ascending=False) if "Monthly Ad Budget" in df.columns else df

    breakdown = []
    for _, row in df_sorted.head(limit).iterrows():
        breakdown.append({
            "domain": str(row["Domain Name"]),
            "common_keywords": int(row["Common Keywords"]) if "Common Keywords" in df.columns else None,
            "monthly_paid_keywords": int(row["Monthly Paid Keywords"]) if "Monthly Paid Keywords" in df.columns else None,
            "monthly_paid_clicks": int(row["Monthly Paid Clicks"]) if "Monthly Paid Clicks" in df.columns else None,
            "monthly_ad_budget": round(float(row["Monthly Ad Budget"]), 2) if "Monthly Ad Budget" in df.columns else None,
        })

    return {
        "status": "success",
        "total_competitors_analyzed": len(df),
        "competitor_share_breakdown": breakdown,
    }
