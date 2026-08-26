import io
import pandas as pd

def parse_historic_traffic(csv_bytes: bytes = None):
    if not csv_bytes:
        return []
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        date_col = [c for c in df.columns if 'Date' in c or 'Month' in c]
        trf_col = [c for c in df.columns if 'Traffic' in c or 'Clicks' in c]
        
        if date_col and trf_col:
            results = []
            for _, row in df.iterrows():
                results.append({
                    "month": str(row[date_col[0]]),
                    "clicks": int(row[trf_col[0]]) if pd.notna(row[trf_col[0]]) else 0
                })
            return results
        return []
    except Exception:
        return []
