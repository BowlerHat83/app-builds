from fastapi import APIRouter, Form, UploadFile, File
from typing import Optional
from app.topic3_ahrefs_auditor.services.domain_rating_service import parse_backlinks_and_dr
from app.topic3_ahrefs_auditor.services.traffic_impressions_service import parse_traffic_impressions
from app.topic3_ahrefs_auditor.services.keyword_position_service import parse_avg_position
from app.topic3_ahrefs_auditor.services.competitor_share_service import parse_competitor_share
from app.topic3_ahrefs_auditor.services.top_keywords_service import parse_top_keywords
from app.topic3_ahrefs_auditor.services.content_gap_service import parse_content_gaps
from app.topic3_ahrefs_auditor.services.historic_traffic_service import parse_historic_traffic

router = APIRouter()

async def run_topic3_full_audit(
    target_url: str = "", 
    organic_csv_bytes: Optional[bytes] = None,
    ahrefs_csv_bytes: Optional[bytes] = None
):
    primary_csv = organic_csv_bytes or ahrefs_csv_bytes
    
    backlink_data = parse_backlinks_and_dr(primary_csv, target_url=target_url)
    trf_imp = parse_traffic_impressions(primary_csv)
    avg_pos = parse_avg_position(primary_csv)
    comp_share = parse_competitor_share(primary_csv)
    keywords = parse_top_keywords(primary_csv, target_url=target_url)
    gaps = parse_content_gaps(primary_csv)
    traffic_trend = parse_historic_traffic(primary_csv)

    # Derive impression/click metrics if live URL scanned without CSV
    total_imp = trf_imp["total_imp"] if trf_imp["total_imp"] != "No Data" else (sum(k["imp"] for k in keywords) if keywords else "No Data")
    total_clicks = trf_imp["total_clicks"] if trf_imp["total_clicks"] != "No Data" else (sum(k["clicks"] for k in keywords) if keywords else "No Data")
    avg_keyword_pos = avg_pos if avg_pos != "No Data" else (round(sum(k["pos"] for k in keywords)/len(keywords), 1) if keywords else "No Data")

    return {
        "status": "success",
        "topic": "Topic 3: Organic Visibility",
        "target_url": target_url,
        "overview_cards": {
            "dr": backlink_data["dr"],
            "total_imp": total_imp,
            "total_clicks": total_clicks,
            "avg_keyword_position": avg_keyword_pos,
            "backlinks": backlink_data["total_backlinks"],
            "referring_domains": backlink_data["referring_domains"]
        },
        "competitor_breakdown": comp_share,
        "keywords": keywords,
        "content_gaps": gaps,
        "organic_traffic_trend": traffic_trend
    }

@router.post("/audit", summary="Run Topic 3 Audit directly")
async def run_audit(
    target_url: str = Form(""),
    organic_csv: Optional[UploadFile] = File(None),
    ahrefs_csv: Optional[UploadFile] = File(None)
):
    org_bytes = await organic_csv.read() if organic_csv and organic_csv.filename else None
    ahr_bytes = await ahrefs_csv.read() if ahrefs_csv and ahrefs_csv.filename else None
    
    return await run_topic3_full_audit(
        target_url=target_url, 
        organic_csv_bytes=org_bytes,
        ahrefs_csv_bytes=ahr_bytes
    )
