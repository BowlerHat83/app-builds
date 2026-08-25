import io
import pandas as pd

def parse_content_gaps(csv_bytes: bytes = None, limit: int = 5):
    if not csv_bytes:
        return []
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        kw_col = [c for c in df.columns if 'Keyword' in c][0]
        vol_col = [c for c in df.columns if 'Volume' in c][0]
        pos_col = [c for c in df.columns if 'Position' in c or 'Pos' in c][0]
        
        # Gaps: High volume keywords where position > 10
        gap_df = df[pd.to_numeric(df[pos_col], errors='coerce') > 10]
        gap_df = gap_df.sort_values(by=vol_col, ascending=False).head(limit)
        
        gaps = []
        for _, row in gap_df.iterrows():
            gaps.append({
                "topic_opportunity": str(row[kw_col]),
                "est_vol": int(row[vol_col]) if pd.notna(row[vol_col]) else 0
            })
        return gaps
    except Exception:
        return []
