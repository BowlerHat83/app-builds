import asyncio
import csv
import io
import pandas as pd
import httpx
from typing import Dict, Any, List, Optional

class LocalVisibilityService:
    async def process_brightlocal_csv(self, csv_bytes: bytes) -> Dict[str, Any]:
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

    async def fetch_map_pack_position(
        self, 
        business_name: str, 
        location: str, 
        keywords: List[str], 
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pings Google Local SERP (engine=google_local) to detect map pack rank
        (1-3) across target keywords. Note: this engine's "place_id" field is
        actually a raw internal CID, not a value compatible with SerpApi's
        google_maps_reviews endpoint - reviews are resolved independently via
        engine=google_maps in gbp_review_service.py instead of reusing anything
        from here.
        """
        # Each keyword is an independent live SerpApi call - this used to run
        # them one at a time in a for loop, so with up to ~8 keywords (2 base
        # + up to 2 per topic from Topic 3/4/5's unbranded keywords) at
        # several seconds apiece, the total could easily blow past the 20s
        # budget aggregate.py gives this whole check even though no single
        # request was slow. Running them concurrently instead means the
        # total wait is roughly the slowest single request, not the sum of
        # all of them.
        async def _check_one(client: httpx.AsyncClient, kw: str) -> Dict[str, Any]:
            if not api_key:
                # No API key configured - do NOT report a rank. A fabricated number
                # that looks like a live SERP position is worse than no number at all.
                return {
                    "keyword": kw,
                    "map_pack_position": None,
                    "found": False,
                    "note": "No SerpApi key configured - live map-pack rank unavailable for this keyword."
                }
            try:
                url = "https://serpapi.com/search.json"
                params = {
                    "engine": "google_local",
                    "q": f"{kw} {location}",
                    "location": location,
                    "api_key": api_key
                }
                resp = await client.get(url, params=params)
                data = resp.json()
                local_results = data.get("local_results", [])

                rank = None
                for idx, item in enumerate(local_results, start=1):
                    if business_name.lower() in item.get("title", "").lower():
                        rank = idx
                        break

                return {"keyword": kw, "map_pack_position": rank, "found": rank is not None}
            except Exception as e:
                return {"keyword": kw, "error": str(e), "found": False}

        async with httpx.AsyncClient(timeout=10.0) as client:
            results = await asyncio.gather(*(_check_one(client, kw) for kw in keywords))

        positions = [r["map_pack_position"] for r in results if r.get("map_pack_position")]
        avg_position = round(sum(positions) / len(positions), 2) if positions else None
        data_source = "live_serpapi" if api_key else "unavailable"

        return {
            "business_name": business_name,
            "location": location,
            "data_source": data_source,
            "average_map_pack_position": avg_position,
            "total_keywords_tracked": len(keywords),
            "keywords_in_map_pack": len(positions),
            "keyword_breakdown": results,
        }
