from fastapi import APIRouter, UploadFile, File, Form
import asyncio, importlib
from typing import Optional

router = APIRouter()

async def safe_run_topic(module_name: str, func_candidates: list, *args, **kwargs):
    try:
        mod = importlib.import_module(module_name)
        audit_func = None
        for name in func_candidates:
            if hasattr(mod, name):
                audit_func = getattr(mod, name)
                break
        
        if not audit_func:
            return {"status": "skipped", "data": "N/A", "reason": f"No valid audit function found in {module_name}"}
            
        return await audit_func(*args, **kwargs)
    except Exception as e:
        return {"status": "skipped", "data": "N/A", "error": str(e)}

@router.post("/audit-master", tags=["Master Audit"], summary="Run Complete Multi-Topic SEO Audit")
async def run_master_audit(
    target_url: str = Form(..., description="Target website URL"),
    business_name: Optional[str] = Form(None, description="Business Name for Local SEO"),
    target_location: Optional[str] = Form(None, description="City/Location for Local Rankings"),
    screaming_frog_csv: Optional[UploadFile] = File(None, description="Screaming Frog Internal HTML Export"),
    ahrefs_backlinks_csv: Optional[UploadFile] = File(None, description="Ahrefs Backlinks Export CSV"),
    ahrefs_keywords_csv: Optional[UploadFile] = File(None, description="Ahrefs Organic Keywords Export CSV"),
    waykey_csv: Optional[UploadFile] = File(None, description="Waykey Search Keywords Export CSV"),
    brightlocal_csv: Optional[UploadFile] = File(None, description="BrightLocal CSV Export")
):
    # Read CSV file contents asynchronously
    sf_bytes = await screaming_frog_csv.read() if screaming_frog_csv else None
    ahrefs_backlinks_bytes = await ahrefs_backlinks_csv.read() if ahrefs_backlinks_csv else None
    ahrefs_keywords_bytes = await ahrefs_keywords_csv.read() if ahrefs_keywords_csv else None
    waykey_bytes = await waykey_csv.read() if waykey_csv else None
    brightlocal_bytes = await brightlocal_csv.read() if brightlocal_csv else None

    func_names = ["run_topic7_full_audit", "run_topic6_audit", "run_topic_audit", "run_full_audit", "run_audit", "audit_all"]

    t1_task = safe_run_topic("app.topic1_website_auditor.aggregate", func_names, target_url=target_url)
    t2_task = safe_run_topic("app.topic2_performance.aggregate", func_names, target_url=target_url, csv_bytes=sf_bytes)
    t3_task = safe_run_topic("app.topic3_ahrefs_auditor.aggregate", func_names, backlinks_bytes=ahrefs_backlinks_bytes, keywords_bytes=ahrefs_keywords_bytes)
    t4_task = safe_run_topic("app.topic4_ai_visibility.aggregate", func_names, target_url=target_url, waykey_bytes=waykey_bytes)
    t5_task = safe_run_topic("app.topic5_paid_visibility.aggregate", func_names, target_url=target_url)
    t6_task = safe_run_topic("app.topic6_local_visibility.aggregate", func_names, business_name=business_name, target_location=target_location, brightlocal_bytes=brightlocal_bytes)
    t7_task = safe_run_topic("app.topic7_onpage_content_quality.aggregate", func_names, target_url=target_url, csv_bytes=sf_bytes)

    t1_res, t2_res, t3_res, t4_res, t5_res, t6_res, t7_res = await asyncio.gather(
        t1_task, t2_task, t3_task, t4_task, t5_task, t6_task, t7_task
    )

    return {
        "status": "success",
        "target_url": target_url,
        "provided_inputs": {
            "business_name": business_name or "N/A",
            "target_location": target_location or "N/A",
            "screaming_frog_csv": screaming_frog_csv.filename if screaming_frog_csv else "N/A",
            "ahrefs_backlinks_csv": ahrefs_backlinks_csv.filename if ahrefs_backlinks_csv else "N/A",
            "ahrefs_keywords_csv": ahrefs_keywords_csv.filename if ahrefs_keywords_csv else "N/A",
            "waykey_csv": waykey_csv.filename if waykey_csv else "N/A",
            "brightlocal_csv": brightlocal_csv.filename if brightlocal_csv else "N/A"
        },
        "master_audit_results": {
            "topic1_technical": t1_res,
            "topic2_performance": t2_res,
            "topic3_ahrefs": t3_res,
            "topic4_ai_visibility": t4_res,
            "topic5_paid_visibility": t5_res,
            "topic6_local_visibility": t6_res,
            "topic7_content_quality": t7_res
        }
    }
