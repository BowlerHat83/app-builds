from fastapi import APIRouter, Query
from app.topic5_paid_visibility.services.keyword_service import KeywordService

router = APIRouter()

@router.get("/keywords/count", summary="Get count of targeted PPC keywords")
async def get_targeted_keywords_count(domain: str = Query(..., example="acme.com")):
    return KeywordService.get_targeted_keywords_count(domain)
