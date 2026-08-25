from fastapi import APIRouter, Query
from app.services.topic1_service import Topic1Service

router = APIRouter(prefix="/api/v1/topic1", tags=["Topic 1 - Technical & Compliance"])
service = Topic1Service()

@router.get("/")
def get_topic1_audit(
    url: str = Query(None, description="Target URL to audit"),
    use_mock: bool = Query(True, description="Use mock data for fast testing")
):
    """Endpoint returning cleaned metrics for Technical & Compliance Audit."""
    return service.get_audit_data(url=url, use_mock=use_mock)
