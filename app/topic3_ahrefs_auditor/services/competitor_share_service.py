import io
import pandas as pd

def parse_competitor_share(csv_bytes: bytes = None):
    if not csv_bytes:
        return []
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        dom_col = [c for c in df.columns if 'Domain' in c or 'Competitor' in c]
        share_col = [c for c in df.columns if 'Share' in c or 'Traffic' in c or 'Overlap' in c]
        
        if dom_col and share_col:
            results = []
            for _, row in df.head(5).iterrows():
                results.append({
                    "domain": str(row[dom_col[0]]),
                    "share_percentage": float(row[share_col[0]]) if pd.notna(row[share_col[0]]) else 0.0
                })
            return results
        return []
    except Exception:
        return []
