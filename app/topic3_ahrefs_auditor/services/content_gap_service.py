import io
import pandas as pd

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
