import io
import re
from typing import Optional

import pandas as pd

def calculate_branded_traffic_breakdown(file_bytes: bytes, business_name: Optional[str] = None) -> dict:
    """
    Parses Ahrefs Organic Keywords CSV to calculate Branded vs Unbranded (Non-Branded)
    traffic, search volume, keyword counts, and percentage distribution.

    business_name is the actual client's name for this audit, used only as
    a fallback classifier when the CSV has no 'Branded' column of its own -
    see the comment below for why this can no longer default to a
    hardcoded brand name.
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
    traffic_col = next((c for c in df.columns if "current" in c and "traffic" in c), None)
    if not traffic_col:
        traffic_col = next((c for c in df.columns if "traffic" in c), None)
        
    vol_col = next((c for c in df.columns if c in ["volume", "search_volume"]), None)
    branded_col = next((c for c in df.columns if "brand" in c), None)

    if not kw_col or not traffic_col:
        raise ValueError(f"CSV missing required keyword/traffic columns. Found: {list(df.columns)}")

    df[traffic_col] = pd.to_numeric(df[traffic_col], errors="coerce").fillna(0)
    if vol_col:
        df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0)

    # Classify branded vs unbranded based on Ahrefs 'Branded' column or fallback keyword match.
    #
    # This used to hardcode "bowler|bowlerhat" as the fallback pattern
    # whenever the CSV had no 'Branded' column - meaning it silently
    # misclassified branded/unbranded traffic for every client except
    # Bowler Hat itself (AllTru included), since this app is meant to run
    # audits for more than one client. The fallback is now built from the
    # actual business_name supplied for this audit instead of a fixed
    # brand name; if neither a Branded column nor a business_name is
    # available, there's genuinely no way to classify anything, so this
    # raises rather than guessing (or, worse, matching a hardcoded
    # competitor's name against this client's keywords).
    if branded_col:
        is_branded = df[branded_col].astype(str).str.lower().isin(["true", "1", "yes", "branded"])
    elif business_name and business_name.strip():
        # Build a pattern from the business name's own significant words
        # (3+ letters, so "the"/"and"/"co" etc don't cause false matches),
        # so e.g. "Bowler Hat" matches "bowler" or "hat" in a keyword, and
        # "AllTru" matches "alltru".
        name_words = [w for w in re.findall(r"[A-Za-z0-9]+", business_name) if len(w) >= 3]
        if not name_words:
            raise ValueError(
                f"business_name '{business_name}' has no usable words to match keywords against, and this CSV "
                "has no 'Branded' column - branded/unbranded traffic can't be classified."
            )
        pattern = "|".join(re.escape(w) for w in name_words)
        is_branded = df[kw_col].astype(str).str.contains(pattern, case=False, regex=True)
    else:
        raise ValueError(
            "This CSV has no 'Branded' column and no business name was supplied to classify keywords against - "
            "branded/unbranded traffic can't be determined."
        )

    df["is_branded"] = is_branded

    branded_df = df[df["is_branded"]]
    unbranded_df = df[~df["is_branded"]]

    branded_traffic = int(round(branded_df[traffic_col].sum()))
    unbranded_traffic = int(round(unbranded_df[traffic_col].sum()))
    total_traffic = branded_traffic + unbranded_traffic

    branded_kw_count = len(branded_df)
    unbranded_kw_count = len(unbranded_df)
    total_kw_count = len(df)

    branded_pct = round((branded_traffic / total_traffic * 100), 2) if total_traffic > 0 else 0.0
    unbranded_pct = round((unbranded_traffic / total_traffic * 100), 2) if total_traffic > 0 else 0.0

    return {
        "status": "success",
        "total_organic_traffic": total_traffic,
        "total_keywords_analyzed": total_kw_count,
        "traffic_breakdown": {
            "branded": {
                "estimated_monthly_traffic": branded_traffic,
                "traffic_percentage": branded_pct,
                "keyword_count": branded_kw_count,
                "keyword_percentage": round((branded_kw_count / total_kw_count * 100), 2) if total_kw_count > 0 else 0.0
            },
            "unbranded": {
                "estimated_monthly_traffic": unbranded_traffic,
                "traffic_percentage": unbranded_pct,
                "keyword_count": unbranded_kw_count,
                "keyword_percentage": round((unbranded_kw_count / total_kw_count * 100), 2) if total_kw_count > 0 else 0.0
            }
        }
    }
