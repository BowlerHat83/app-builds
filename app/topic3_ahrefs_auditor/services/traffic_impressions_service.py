import io
import pandas as pd

def parse_traffic_impressions_csv(file_bytes: bytes) -> dict:
    """
    Parses Ahrefs Organic Keywords CSV to calculate estimated monthly clicks and impressions.
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

    traffic_col = next((c for c in df.columns if c in ["current_organic_traffic", "organic_traffic", "traffic"]), None)
    volume_col = next((c for c in df.columns if c in ["volume", "search_volume"]), None)
    pos_col = next((c for c in df.columns if c in ["current_position", "position", "pos"]), None)

    if not traffic_col or not volume_col:
        raise ValueError(f"CSV missing traffic/volume columns. Columns found: {list(df.columns)}")

    df[traffic_col] = pd.to_numeric(df[traffic_col], errors="coerce").fillna(0)
    df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce").fillna(0)
    
    if pos_col:
        df[pos_col] = pd.to_numeric(df[pos_col], errors="coerce")

    estimated_clicks_30d = int(df[traffic_col].sum())
    
    # Calculate estimated impression potential (Volume of keywords where site ranks in Top 20)
    if pos_col:
        top_20_df = df[df[pos_col] <= 20]
        estimated_impressions_30d = int(top_20_df[volume_col].sum())
    else:
        estimated_impressions_30d = int(df[volume_col].sum())

    total_volume = int(df[volume_col].sum())

    return {
        "status": "success",
        "timeframe": "Last 30 Days",
        "metrics": {
            "estimated_organic_clicks": estimated_clicks_30d,
            "estimated_impressions_potential": estimated_impressions_30d,
            "total_search_volume_tracked": total_volume,
            "keywords_generating_traffic": int((df[traffic_col] > 0).sum())
        }
    }
