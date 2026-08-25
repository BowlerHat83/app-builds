import io
import pandas as pd
from typing import Optional, Dict, Any

def parse_ppc_summary(ppc_bytes: Optional[bytes] = None, target_url: str = "") -> Dict[str, Any]:
    if ppc_bytes:
        try:
            df = pd.read_csv(io.BytesIO(ppc_bytes))
            
            kw_col = next((c for c in df.columns if any(k in c.lower() for k in ['keyword', 'kw', 'term'])), None)
            spend_col = next((c for c in df.columns if any(k in c.lower() for k in ['cost', 'spend', 'budget'])), None)
            cpc_col = next((c for c in df.columns if 'cpc' in c.lower()), None)
            clicks_col = next((c for c in df.columns if any(k in c.lower() for k in ['click', 'traffic'])), None)

            no_of_keywords = len(df[kw_col].dropna().unique()) if kw_col else len(df)
            
            est_spend = 0.0
            if spend_col:
                est_spend = float(pd.to_numeric(df[spend_col].astype(str).str.replace('$', '').str.replace('£', '').str.replace(',', ''), errors='coerce').sum())
                
            avg_cpc = 0.0
            if cpc_col:
                avg_cpc = float(pd.to_numeric(df[cpc_col].astype(str).str.replace('$', '').str.replace('£', '').str.replace(',', ''), errors='coerce').mean())
                
            no_clicks = 0
            if clicks_col:
                no_clicks = int(pd.to_numeric(df[clicks_col].astype(str).str.replace(',', ''), errors='coerce').sum())

            return {
                "no_of_keywords": str(no_of_keywords),
                "est_monthly_spend": f"£{round(est_spend, 2):,}",
                "average_cpc": f"£{round(avg_cpc, 2)}",
                "no_of_clicks": f"{no_clicks:,}"
            }
        except Exception as e:
            print(f"Error parsing PPC summary: {e}")

    return {
        "no_of_keywords": "0",
        "est_monthly_spend": "£0.00",
        "average_cpc": "£0.00",
        "no_of_clicks": "0"
    }
