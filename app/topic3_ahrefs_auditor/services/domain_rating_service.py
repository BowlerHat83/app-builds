import io
import pandas as pd

def parse_domain_rating_csv(file_bytes: bytes) -> dict:
    """
    Parses Ahrefs Organic Competitors CSV to extract Competitor Domain Rating metrics.
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

    dr_col = next((c for c in df.columns if c in ["dr", "domain_rating"]), None)
    domain_col = next((c for c in df.columns if c in ["domain", "competitor"]), None)

    if not dr_col:
        raise ValueError(f"CSV missing 'DR' column. Columns found: {list(df.columns)}")

    df[dr_col] = pd.to_numeric(df[dr_col], errors="coerce")
    df = df.dropna(subset=[dr_col])

    avg_dr = round(float(df[dr_col].mean()), 2)
    max_dr = float(df[dr_col].max())
    min_dr = float(df[dr_col].min())

    competitor_list = []
    if domain_col:
        top_comps = df[[domain_col, dr_col]].head(10)
        competitor_list = top_comps.to_dict(orient="records")

    return {
        "status": "success",
        "metrics": {
            "average_competitor_dr": avg_dr,
            "max_competitor_dr": max_dr,
            "min_competitor_dr": min_dr,
            "total_competitors_analyzed": len(df)
        },
        "top_competitors": competitor_list
    }
