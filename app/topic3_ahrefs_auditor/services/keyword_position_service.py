import io
import pandas as pd

def parse_keyword_position_csv(file_bytes: bytes) -> dict:
    """
    Parses Ahrefs Organic Keywords CSV to calculate average ranking position.
    Robustly handles UTF-16, UTF-16-LE, and UTF-8 encodings from Ahrefs exports.
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

    pos_col = next((c for c in df.columns if c in ["current_position", "position", "pos"]), None)

    if not pos_col:
        raise ValueError(f"CSV missing position column. Columns found: {list(df.columns)}")

    df[pos_col] = pd.to_numeric(df[pos_col], errors="coerce")
    df = df.dropna(subset=[pos_col])

    total_keywords = len(df)
    avg_position = round(float(df[pos_col].mean()), 2)
    top_3_count = int((df[pos_col] <= 3).sum())
    top_10_count = int((df[pos_col] <= 10).sum())
    top_50_count = int((df[pos_col] <= 50).sum())

    return {
        "status": "success",
        "metrics": {
            "average_position": avg_position,
            "total_keywords_analyzed": total_keywords,
            "top_3_count": top_3_count,
            "top_10_count": top_10_count,
            "top_50_count": top_50_count
        }
    }
