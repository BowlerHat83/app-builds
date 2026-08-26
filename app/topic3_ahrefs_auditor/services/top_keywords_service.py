import io
import pandas as pd

def parse_top_keywords_csv(file_bytes: bytes, limit: int = 25) -> dict:
    """
    Parses Ahrefs Organic Keywords CSV to extract top keywords with impressions (volume), 
    clicks (organic traffic), position, and calculated CTR.
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

    # Standardize column headers
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]

    kw_col = next((c for c in df.columns if c in ["keyword", "keywords"]), None)
    volume_col = next((c for c in df.columns if c in ["volume", "search_volume"]), None)
    traffic_col = next((c for c in df.columns if c in ["current_organic_traffic", "organic_traffic", "traffic"]), None)
    pos_col = next((c for c in df.columns if c in ["current_position", "position", "pos"]), None)

    if not kw_col or not volume_col or not traffic_col:
        raise ValueError(f"CSV missing essential keyword/volume/traffic columns. Columns found: {list(df.columns)}")

    # Clean numeric columns
    df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce").fillna(0)
    df[traffic_col] = pd.to_numeric(df[traffic_col], errors="coerce").fillna(0)
    
    if pos_col:
        df[pos_col] = pd.to_numeric(df[pos_col], errors="coerce")

    # Sort primarily by estimated traffic (clicks), secondarily by volume
    df_sorted = df.sort_values(by=[traffic_col, volume_col], ascending=[False, False]).head(limit)

    top_keywords_list = []
    for _, row in df_sorted.iterrows():
        vol = int(row[volume_col])
        clicks = float(row[traffic_col])
        pos = float(row[pos_col]) if pos_col and pd.notna(row[pos_col]) else None
        
        # CTR calculation
        ctr_pct = round((clicks / vol) * 100, 2) if vol > 0 else 0.0

        top_keywords_list.append({
            "keyword": str(row[kw_col]),
            "impressions_volume": vol,
            "estimated_clicks": round(clicks, 1),
            "average_position": round(pos, 1) if pos is not None else "N/A",
            "ctr_percent": ctr_pct
        })

    return {
        "status": "success",
        "total_keywords_returned": len(top_keywords_list),
        "top_keywords": top_keywords_list
    }
