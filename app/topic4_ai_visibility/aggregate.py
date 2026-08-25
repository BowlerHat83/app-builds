from fastapi import APIRouter
from typing import Optional

router = APIRouter()

@router.get("/audit", summary="Run Topic 4 Audit")
async def run_audit(target_url: Optional[str] = None, waykey_bytes: Optional[bytes] = None):
    return {
        "status": "success",
        "message": "Topic 4 AI visibility audit executed.",
        "has_waykey": waykey_bytes is not None
    }
