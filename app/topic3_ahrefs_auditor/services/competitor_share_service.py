import io
import pandas as pd

def parse_competitor_share_csv(file_bytes: bytes) -> dict:
    """
    Parses Ahrefs Organic Competitors CSV to calculate competitor market share breakdown.
    Handles percentage string parsing (e.g., '22.2%').
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

    domain_col = next((c for c in df.columns if c in ["domain", "competitor"]), None)
    share_col = next((c for c in df.columns if c in ["share", "market_share"]), None)
    common_kw_col = next((c for c in df.columns if c in ["common_keywords", "common_kw"]), None)
    comp_kw_col = next((c for c in df.columns if "competitor" in c and "keyword" in c), None)

    if not domain_col or not share_col:
        raise ValueError(f"CSV missing Domain or Share columns. Columns found: {list(df.columns)}")

    # Clean percentage strings e.g. "22.2%" -> 22.2
    df[share_col] = df[share_col].astype(str).str.replace("%", "", regex=False).str.strip()
    df[share_col] = pd.to_numeric(df[share_col], errors="coerce").fillna(0)
    
    if common_kw_col:
        df[common_kw_col] = pd.to_numeric(df[common_kw_col], errors="coerce").fillna(0)
    if comp_kw_col:
        df[comp_kw_col] = pd.to_numeric(df[comp_kw_col], errors="coerce").fillna(0)

    # Sort competitors by share descending
    df_sorted = df.sort_values(by=share_col, ascending=False)

    top_share_leaders = []
    cols_to_extract = [domain_col, share_col]
    if common_kw_col: cols_to_extract.append(common_kw_col)
    if comp_kw_col: cols_to_extract.append(comp_kw_col)

    top_df = df_sorted[cols_to_extract].head(10)
    
    for _, row in top_df.iterrows():
        item = {
            "domain": str(row[domain_col]),
            "market_share_percent": round(float(row[share_col]), 2)
        }
        if common_kw_col:
            item["common_keywords"] = int(row[common_kw_col])
        if comp_kw_col:
            item["total_competitor_keywords"] = int(row[comp_kw_col])
        top_share_leaders.append(item)

    avg_share = round(float(df[share_col].mean()), 2)
    max_share = round(float(df[share_col].max()), 2)

    return {
        "status": "success",
        "metrics": {
            "average_competitor_share": avg_share,
            "max_competitor_share": max_share,
            "total_competitors_analyzed": len(df)
        },
        "market_share_breakdown": top_share_leaders
    }
