from fastapi import APIRouter

router = APIRouter(
    prefix="/api/gdpr",
    tags=["Topic 1: Website Auditor"]
)

@router.post("/check")
async def audit_gdpr_compliance():
    return {"status": "ok"}

