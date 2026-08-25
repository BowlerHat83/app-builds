import io
import pandas as pd
from typing import Dict, Any

class BrightLocalService:
    async def process_csv(self, csv_bytes: bytes) -> Dict[str, Any]:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        total_citations = len(df)
        if total_citations == 0:
            return {"error": "CSV file is empty"}

        high_da_count = int((df["Domain Authority"] >= 40).sum()) if "Domain Authority" in df.columns else 0
        active_count = int((df["Status"] == "active").sum()) if "Status" in df.columns else 0

        issue_cols = ["Business Name Issue", "Address Issue", "Zip/Postcode Issue", "Phone Number Issue"]
        existing_cols = [col for col in issue_cols if col in df.columns]
        
        if existing_cols:
            clean_rows = df[df[existing_cols].isna().all(axis=1)]
            nap_score = round((len(clean_rows) / total_citations) * 100, 2)
        else:
            nap_score = 100.0

        return {
            "total_citations": total_citations,
            "active_citations": active_count,
            "high_authority_citations": high_da_count,
            "nap_consistency_score": nap_score
        }
