from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.topic2_performance.services.cwv_checker import analyze_core_web_vitals

router = APIRouter(prefix="/api/topic2/cwv", tags=["Topic 2 - Core Web Vitals"])

@router.post("/check", summary="Analyze Core Web Vitals locally via Lighthouse Engine")
async def check_cwv(
    url: str = Query(..., description="Target URL to analyze (e.g. https://example.com)"),
    strategy: str = Query("mobile", enum=["mobile", "desktop"])
):
    result = await analyze_core_web_vitals(url=url, strategy=strategy)
    if "error" in result:
        return JSONResponse(status_code=422, content=result)
    return result
