import io
import pandas as pd

def parse_traffic_impressions(csv_bytes: bytes = None):
    if not csv_bytes:
        return {"total_imp": "No Data", "total_clicks": "No Data"}
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        vol_col = [c for c in df.columns if 'Volume' in c or 'Impressions' in c]
        trf_col = [c for c in df.columns if 'Traffic' in c or 'Clicks' in c]
        
        total_imp = int(df[vol_col[0]].sum()) if vol_col else 0
        total_clicks = int(df[trf_col[0]].sum()) if trf_col else 0
        return {"total_imp": total_imp, "total_clicks": total_clicks}
    except Exception:
        return {"total_imp": "No Data", "total_clicks": "No Data"}
