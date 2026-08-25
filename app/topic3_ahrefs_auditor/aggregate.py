from fastapi import APIRouter
from typing import Optional
import pandas as pd
import io

router = APIRouter()

def read_csv_robust(csv_bytes: bytes) -> pd.DataFrame:
    for encoding in ['utf-16', 'utf-8-sig', 'utf-8', 'latin1']:
        try:
            return pd.read_csv(io.BytesIO(csv_bytes), encoding=encoding, low_memory=False)
        except (UnicodeDecodeError, Exception):
            continue
    raise ValueError("Unable to decode CSV with supported encodings (utf-16, utf-8, latin1).")

async def run_topic3_full_audit(backlinks_bytes: Optional[bytes] = None, keywords_bytes: Optional[bytes] = None):
    results = {
        "topic": "Topic 3: Off-Page & Ahrefs Backlink Audit",
        "backlinks_summary": "N/A",
        "keywords_summary": "N/A"
    }

    if not backlinks_bytes and not keywords_bytes:
        return {
            "status": "skipped",
            "data": results,
            "reason": "No Ahrefs CSV exports provided"
        }

    # Parse Backlinks CSV
    if backlinks_bytes:
        try:
            df_bl = read_csv_robust(backlinks_bytes)
            total_backlinks = len(df_bl)
            
            ref_col = next((c for c in ['Referring Domain', 'Domain Rating', 'Domain'] if c in df_bl.columns), None)
            ref_domains = int(df_bl[ref_col].nunique()) if ref_col else total_backlinks
            
            type_col = next((c for c in ['Type', 'Link type'] if c in df_bl.columns), None)
            dofollow_count = int((df_bl[type_col] == 'Dofollow').sum()) if type_col else total_backlinks

            results["backlinks_summary"] = {
                "total_backlinks": total_backlinks,
                "unique_referring_domains": ref_domains,
                "dofollow_backlinks": dofollow_count,
                "nofollow_backlinks": total_backlinks - dofollow_count
            }
        except Exception as e:
            results["backlinks_summary"] = {"error": f"Failed to parse Backlinks CSV: {str(e)}"}

    # Parse Organic Keywords CSV
    if keywords_bytes:
        try:
            df_kw = read_csv_robust(keywords_bytes)
            total_keywords = len(df_kw)
            
            pos_col = next((c for c in ['Position', 'Current position'] if c in df_kw.columns), None)
            top_3 = int((df_kw[pos_col] <= 3).sum()) if pos_col else 0
            top_10 = int((df_kw[pos_col] <= 10).sum()) if pos_col else 0
            
            vol_col = next((c for c in ['Volume', 'Search Volume'] if c in df_kw.columns), None)
            total_volume = int(df_kw[vol_col].sum()) if vol_col else 0

            results["keywords_summary"] = {
                "total_ranked_keywords": total_keywords,
                "top_3_positions": top_3,
                "top_10_positions": top_10,
                "estimated_search_volume": total_volume
            }
        except Exception as e:
            results["keywords_summary"] = {"error": f"Failed to parse Keywords CSV: {str(e)}"}

    return {"status": "success", "data": results}

@router.get("/audit", summary="Run Topic 3 Audit directly")
async def run_audit(backlinks_bytes: Optional[bytes] = None, keywords_bytes: Optional[bytes] = None):
    return await run_topic3_full_audit(backlinks_bytes=backlinks_bytes, keywords_bytes=keywords_bytes)
