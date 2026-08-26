from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from app.routes.master_audit import router as master_router
from app.routes.audit_jobs import router as audit_jobs_router
from app.topic1_website_auditor.aggregate import router as t1_router
from app.topic2_performance.aggregate import router as t2_router
from app.topic3_ahrefs_auditor.aggregate import router as t3_router
from app.topic4_ai_visibility.aggregate import router as t4_router
from app.topic5_paid_visibility.aggregate import router as t5_router
from app.topic6_local_visibility.aggregate import router as t6_router
from app.topic7_onpage_content_quality.aggregate import router as t7_router

app = FastAPI(
    title="SEO Audit Platform API",
    description="Master backend API orchestrating Topics 1 through 7.",
    version="1.0.0"
)

# CORS - the React frontend runs on a different origin (Vite dev server on
# localhost, later a vercel.app domain) than this API, so the browser will
# block requests without these headers. Wide open (*) is fine for a small
# internal tool talking to a single client; tighten allow_origins to the
# frontend'''s real domain(s) before this is exposed more broadly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static/screenshots", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount Master Orchestrator
app.include_router(master_router)
app.include_router(audit_jobs_router)

# Mount Topic Routers
app.include_router(t1_router, prefix="/topic1", tags=["Topic 1: Technical & On-Page"])
app.include_router(t2_router, prefix="/topic2", tags=["Topic 2: Performance"])
app.include_router(t3_router, prefix="/topic3", tags=["Topic 3: Off-Page & Backlinks"])
app.include_router(t4_router, prefix="/topic4", tags=["Topic 4: AI Visibility"])
app.include_router(t5_router, prefix="/topic5", tags=["Topic 5: Paid Visibility"])
app.include_router(t6_router, prefix="/topic6", tags=["Topic 6: Local Visibility"])
app.include_router(t7_router, prefix="/topic7", tags=["Topic 7: Content Quality"])

@app.get("/", tags=["System"])
async def root():
    return {"message": "SEO Audit Master API Server is Live"}
