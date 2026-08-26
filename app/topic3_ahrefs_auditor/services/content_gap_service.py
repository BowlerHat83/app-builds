import io
import re
import pandas as pd

# A "content gap" should be a topic the client could plausibly write about.
# Ahrefs Organic Keywords exports sometimes include bare navigational/brand
# queries for OTHER companies' domains (people searching "yell.com" itself,
# a directory's own name, etc.) where the client's page ranking for it is
# usually just a directory listing - there's no content opportunity in
# writing a page targeting someone else's domain name. These are filtered
# out below rather than surfaced as if they were real topic opportunities.
_DOMAIN_LOOKALIKE_RE = re.compile(r'^[a-z0-9-]+(\.[a-z0-9-]+)+$', re.IGNORECASE)
_KNOWN_DIRECTORY_DOMAINS = {
    "yell.com", "yelp.com", "yelp.co.uk", "thomsonlocal.com", "tripadvisor.com",
    "tripadvisor.co.uk", "facebook.com", "linkedin.com", "instagram.com",
    "twitter.com", "x.com", "google.com", "maps.google.com", "bing.com",
    "checkatrade.com", "trustpilot.com", "wikipedia.org", "indeed.com",
    "glassdoor.com", "reddit.com", "youtube.com", "crunchbase.com",
    "bloomberg.com", "companieshouse.gov.uk",
}


def _is_navigational_domain_keyword(keyword: str) -> bool:
    """True if a keyword is just a bare domain name, not a real content topic."""
    kw = str(keyword).strip().lower()
    if not kw:
        return False
    if kw in _KNOWN_DIRECTORY_DOMAINS:
        return True
    return bool(_DOMAIN_LOOKALIKE_RE.match(kw))


def parse_content_gaps_csv(file_bytes: bytes, limit: int = 25) -> dict:
    """
    Parses Ahrefs Organic Keywords CSV to identify content gap opportunities 
    (high volume keywords where target domain ranks poorly > 10 or is unranked/NA).
    """
    df = None
    encodings_to_try = [
        ("utf-16", "\t"),
        ("utf-16-le", "\t"),
        ("utf-8-sig", ","),
        ("utf-8", ",")
    ]

    for enc, sep in encodings_to_try:
        try:
            temp_df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, sep=sep)
            if len(temp_df.columns) > 1:
                df = temp_df
                break
        except Exception:
            continue

    if df is None:
        raise ValueError("Could not parse CSV file. Ensure it is a valid Ahrefs export.")

    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

    kw_col = next((c for c in df.columns if c in ["keyword", "keywords"]), None)
    vol_col = next((c for c in df.columns if c in ["volume", "search_volume"]), None)
    kd_col = next((c for c in df.columns if c in ["kd", "keyword_difficulty"]), None)
    pos_col = next((c for c in df.columns if c in ["current_position", "position", "pos"]), None)

    if not kw_col or not vol_col:
        raise ValueError(f"CSV missing essential keyword/volume columns. Columns found: {list(df.columns)}")

    df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0)
    df[kd_col] = pd.to_numeric(df[kd_col], errors="coerce").fillna(0) if kd_col else 0
    
    if pos_col:
        df[pos_col] = pd.to_numeric(df[pos_col], errors="coerce")
        # Content gap condition: Unranked (NaN) or Position > 10
        gap_condition = df[pos_col].isna() | (df[pos_col] > 10)
        gap_df = df[gap_condition].copy()
    else:
        gap_df = df.copy()

    # Drop bare-domain / directory navigational queries - see
    # _is_navigational_domain_keyword above.
    gap_df = gap_df[~gap_df[kw_col].apply(_is_navigational_domain_keyword)]

    # Sort gaps by highest potential search volume descending
    gap_df_sorted = gap_df.sort_values(by=[vol_col, kd_col], ascending=[False, True]).head(limit)

    gaps_list = []
    for _, row in gap_df_sorted.iterrows():
        vol = int(row[vol_col])
        kd = int(row[kd_col]) if kd_col else 0
        pos = float(row[pos_col]) if pos_col and pd.notna(row[pos_col]) else None
        
        # Opportunity Priority score based on high volume & low-to-medium difficulty
        if kd <= 30:
            priority = "High"
        elif kd <= 60:
            priority = "Medium"
        else:
            priority = "Low"

        gaps_list.append({
            "keyword": str(row[kw_col]),
            "search_volume": vol,
            "keyword_difficulty": kd,
            "current_position": round(pos, 1) if pos is not None else "Unranked (N/A)",
            "opportunity_priority": priority
        })

    return {
        "status": "success",
        "total_content_gaps_found": len(gaps_list),
        "content_gaps": gaps_list
    }
