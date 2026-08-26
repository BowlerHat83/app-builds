import io
import pandas as pd

def parse_avg_position(csv_bytes: bytes = None):
    if not csv_bytes:
        return "No Data"
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        pos_col = [c for c in df.columns if 'Position' in c or 'Pos' in c]
        if pos_col:
            avg_pos = round(float(pd.to_numeric(df[pos_col[0]], errors='coerce').mean()), 1)
            return avg_pos
        return "No Data"
    except Exception:
        return "No Data"
