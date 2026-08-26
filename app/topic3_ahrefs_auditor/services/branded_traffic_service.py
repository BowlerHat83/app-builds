import io
import pandas as pd

def calculate_branded_traffic_breakdown(file_bytes: bytes) -> dict:
    """
    Parses Ahrefs Organic Keywords CSV to calculate Branded vs Unbranded (Non-Branded)
    traffic, search volume, keyword counts, and percentage distribution.
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

    # Classify branded vs unbranded based on Ahrefs 'Branded' column or fallback keyword match
    if branded_col:
        is_branded = df[branded_col].astype(str).str.lower().isin(["true", "1", "yes", "branded"])
    else:
        # Fallback heuristic: check if common brand variants exist in keyword string
        is_branded = df[kw_col].astype(str).str.contains("bowler|bowlerhat", case=False, regex=True)

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
