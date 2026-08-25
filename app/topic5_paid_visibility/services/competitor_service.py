import io
import pandas as pd
from typing import Optional, List, Dict, Any

def parse_ppc_competitors(
    ppc_bytes: Optional[bytes] = None, 
    ppc_competitor_bytes: Optional[bytes] = None, 
    target_url: str = ""
) -> List[Dict[str, Any]]:
    data_bytes = ppc_competitor_bytes or ppc_bytes
    if not data_bytes:
        return []

    try:
        df = pd.read_csv(io.BytesIO(data_bytes))
        clean_target = target_url.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")

        dom_col = next((c for c in df.columns if any(k in c.lower() for k in ['domain', 'competitor', 'ad_domain'])), None)
        share_col = next((c for c in df.columns if any(k in c.lower() for k in ['overlap', 'share', 'coverage', 'visibility', 'common keywords'])), None)

        if dom_col:
            res = []
            for _, row in df.iterrows():
                dom = str(row[dom_col]).strip()
                # Exclude target domain self-row
                if clean_target and clean_target in dom.lower():
                    continue

                share_val = 0.0
                if share_col and pd.notna(row[share_col]):
                    try:
                        share_val = float(str(row[share_col]).replace('%', '').strip())
                    except ValueError:
                        share_val = 0.0

                res.append({
                    "domain": dom,
                    "share_percentage": round(share_val, 2)
                })
            return res[:5]
    except Exception as e:
        print(f"Error parsing PPC competitors: {e}")

    return []
