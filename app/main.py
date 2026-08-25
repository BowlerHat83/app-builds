from fastapi import FastAPI, Query, UploadFile, File, APIRouter
from typing import Optional, Dict, Any

from app.topic6_local_visibility.aggregate import router as t6_router, run_topic6_full_audit
from app.topic7_onpage_content_quality.aggregate import router as t7_router, run_topic7_full_audit

app = FastAPI(
    title="SEO Audit Suite Backend",
    description="Unified API backend for Topics 1-7 individual audits and Master Audit aggregation.",
    version="1.0.0"
)

# Placeholder Routers for Topics 1-5 to populate Swagger UI cleanly
t1_router = APIRouter(prefix="/topic1", tags=["Topic 1: Technical SEO"])
t2_router = APIRouter(prefix="/topic2", tags=["Topic 2: Performance & Speed"])
t3_router = APIRouter(prefix="/topic3", tags=["Topic 3: Site Architecture"])
t4_router = APIRouter(prefix="/topic4", tags=["Topic 4: Backlinks & Authority"])
t5_router = APIRouter(prefix="/topic5", tags=["Topic 5: Keywords & Content"])

@t1_router.post("/audit")
async def run_topic1_audit(target_url: str = Query(...)):
    return {"status": "success", "topic": "Topic 1: Technical SEO", "target_url": target_url, "metrics": "No Data"}

@t2_router.post("/audit")
async def run_topic2_audit(target_url: str = Query(...)):
    return {"status": "success", "topic": "Topic 2: Performance & Speed", "target_url": target_url, "metrics": "No Data"}

@t3_router.post("/audit")
async def run_topic3_audit(target_url: str = Query(...)):
    return {"status": "success", "topic": "Topic 3: Site Architecture", "target_url": target_url, "metrics": "No Data"}

@t4_router.post("/audit")
async def run_topic4_audit(target_url: str = Query(...)):
    return {"status": "success", "topic": "Topic 4: Backlinks & Authority", "target_url": target_url, "metrics": "No Data"}

@t5_router.post("/audit")
async def run_topic5_audit(target_url: str = Query(...)):
    return {"status": "success", "topic": "Topic 5: Keywords & Content", "target_url": target_url, "metrics": "No Data"}

# Register all topic routers
app.include_router(t1_router)
app.include_router(t2_router)
app.include_router(t3_router)
app.include_router(t4_router)
app.include_router(t5_router)
app.include_router(t6_router)
app.include_router(t7_router)

@app.get("/", tags=["Health Check"])
def root():
    return {"status": "online", "message": "SEO Audit Suite API is running"}

@app.post("/master-audit", tags=["Master Audit"])
async def run_master_audit(
    target_url: str = Query(..., description="Target website URL to audit"),
    brightlocal_csv: Optional[UploadFile] = File(None, description="Optional BrightLocal CSV file for Topic 6")
) -> Dict[str, Any]:
    """Runs all Topic 1-7 audits in a single master payload."""
    clean_url = target_url.strip() if target_url else ""
    csv_bytes = await brightlocal_csv.read() if brightlocal_csv else None

    # Topic 6 & 7 Execution
    t6_res = await run_topic6_full_audit(target_url=clean_url, brightlocal_csv_bytes=csv_bytes)
    t7_res = await run_topic7_full_audit(target_url=clean_url)

    return {
        "status": "success",
        "target_url": clean_url,
        "master_audit": {
            "topic1_technical": await run_topic1_audit(clean_url),
            "topic2_performance": await run_topic2_audit(clean_url),
            "topic3_architecture": await run_topic3_audit(clean_url),
            "topic4_backlinks": await run_topic4_audit(clean_url),
            "topic5_keywords": await run_topic5_audit(clean_url),
            "topic6_local_visibility": t6_res,
            "topic7_content_quality": t7_res
        }
    }
