import io
import pandas as pd
import requests

def audit_performance_metrics(target_url: str, csv_bytes: bytes):
    page_size = "No Data"
    ttfb = "No Data"
    load_time = "No Data"
    canonicals = "No Data"
    index_errors = "No Data"

    if target_url:
        try:
            res = requests.get(target_url, timeout=5)
            ttfb = f"{round(res.elapsed.total_seconds() * 1000, 1)} ms"
            load_time = f"{round(res.elapsed.total_seconds(), 2)}s"
            page_size = f"{round(len(res.content) / 1024, 1)} KB"
        except Exception:
            pass

    if csv_bytes:
        try:
            df = pd.read_csv(io.BytesIO(csv_bytes))
            
            # Canonical Check
            can_col = [c for c in df.columns if 'Canonical' in c]
            if can_col:
                canonicals = int(df[can_col[0]].notna().sum())

            # Index Errors (Status Code != 200 or Indexability = Non-Indexable)
            idx_col = [c for c in df.columns if 'Indexability' in c]
            if idx_col:
                index_errors = int((df[idx_col[0]].astype(str).str.lower() == 'non-indexable').sum())
        except Exception:
            pass

    return {
        "page_size": page_size,
        "ttfb": ttfb,
        "load_time": load_time,
        "canonicals": canonicals,
        "index_errors": index_errors
    }
