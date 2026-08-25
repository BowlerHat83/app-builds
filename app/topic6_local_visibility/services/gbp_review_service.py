from typing import Dict, Any

async def get_gbp_review_summary(target_url: str = "") -> Dict[str, Any]:
    return {
        "rating": 5.0,
        "review_count": 0,
        "reviews": []
    }

async def analyze_gbp_reviews(target_url: str = "") -> Dict[str, Any]:
    return await get_gbp_review_summary(target_url)
