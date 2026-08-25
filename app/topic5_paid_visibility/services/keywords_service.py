import io
import pandas as pd
from typing import Optional, List, Dict, Any

def parse_ppc_keywords(ppc_bytes: Optional[bytes] = None, target_url: str = "") -> List[Dict[str, Any]]:
    if ppc_bytes:
        try:
            df = pd.read_csv(io.BytesIO(ppc_bytes))
            kw_col = next((c for c in df.columns if any(k in c.lower() for k in ['keyword', 'kw', 'search_term'])), None)
            vol_col = next((c for c in df.columns if any(k in c.lower() for k in ['volume', 'vol', 'search_volume'])), None)

            if kw_col:
                res = []
                for _, row in df.head(5).iterrows():
                    res.append({
                        "keyword": str(row[kw_col]),
                        "est_volume": int(pd.to_numeric(str(row[vol_col]).replace(',', ''), errors='coerce')) if vol_col and pd.notna(row[vol_col]) else 0
                    })
                return res
        except Exception as e:
            print(f"Error parsing PPC keywords: {e}")

    return []
