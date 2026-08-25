import io
import pandas as pd

def parse_metadata(csv_bytes: bytes):
    if not csv_bytes:
        return {
            "element_issues": {
                "title_tags": {"missing": "No Data", "duplicate": "No Data", "multiple": "No Data"},
                "meta_descriptions": {"missing": "No Data", "duplicate": "No Data", "multiple": "No Data"}
            },
            "title_length": {"under": "No Data", "optimal": "No Data", "over": "No Data"},
            "description_length": {"under": "No Data", "optimal": "No Data", "over": "No Data"}
        }
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        
        # Helper to find column
        def get_col(names):
            for n in names:
                matches = [c for c in df.columns if n.lower() in c.lower()]
                if matches: return matches[0]
            return None

        t_col = get_col(['Title 1', 'Title'])
        t_len_col = get_col(['Title 1 Length', 'Title Length'])
        d_col = get_col(['Meta Description 1', 'Meta Description', 'Description'])
        d_len_col = get_col(['Meta Description 1 Length', 'Description Length'])

        # Title Issues
        t_missing = int(df[t_col].isna().sum()) if t_col else 0
        t_dup = int(df.duplicated(subset=[t_col]).sum()) if t_col else 0
        
        # Meta Desc Issues
        d_missing = int(df[d_col].isna().sum()) if d_col else 0
        d_dup = int(df.duplicated(subset=[d_col]).sum()) if d_col else 0

        # Title Lengths (Optimal ~ 30-60 chars)
        t_under, t_opt, t_over = 0, 0, 0
        if t_len_col:
            lens = pd.to_numeric(df[t_len_col], errors='coerce').dropna()
            t_under = int((lens < 30).sum())
            t_opt = int(((lens >= 30) & (lens <= 60)).sum())
            t_over = int((lens > 60).sum())

        # Description Lengths (Optimal ~ 70-155 chars)
        d_under, d_opt, d_over = 0, 0, 0
        if d_len_col:
            dlens = pd.to_numeric(df[d_len_col], errors='coerce').dropna()
            d_under = int((dlens < 70).sum())
            d_opt = int(((dlens >= 70) & (dlens <= 155)).sum())
            d_over = int((dlens > 155).sum())

        return {
            "element_issues": {
                "title_tags": {"missing": t_missing, "duplicate": t_dup, "multiple": 0},
                "meta_descriptions": {"missing": d_missing, "duplicate": d_dup, "multiple": 0}
            },
            "title_length": {"under": t_under, "optimal": t_opt, "over": t_over},
            "description_length": {"under": d_under, "optimal": d_opt, "over": d_over}
        }
    except Exception:
        return {
            "element_issues": {
                "title_tags": {"missing": "No Data", "duplicate": "No Data", "multiple": "No Data"},
                "meta_descriptions": {"missing": "No Data", "duplicate": "No Data", "multiple": "No Data"}
            },
            "title_length": {"under": "No Data", "optimal": "No Data", "over": "No Data"},
            "description_length": {"under": "No Data", "optimal": "No Data", "over": "No Data"}
        }
