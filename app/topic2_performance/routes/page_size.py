from fastapi import APIRouter, Query, HTTPException
from app.topic2_performance.services.page_size_auditor import analyze_page_size

router = APIRouter(prefix="/api/topic2/page-size", tags=["Topic 2 - Page Size"])

@router.post("/check", summary="Analyze Total Page Weight & Asset Breakdown (Pingdom-Style)")
async def check_page_size(
    url: str = Query(..., description="Target URL to analyze (e.g. https://example.com)")
):
    result = await analyze_page_size(url=url)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result)
    return result
