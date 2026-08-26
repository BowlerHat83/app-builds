from fastapi import APIRouter, UploadFile, File, HTTPException, Query
import pandas as pd
import io
from app.topic4_ai_visibility.services.top_urls_service import process_top_urls

router = APIRouter(tags=["Topic 4: AI Visibility"])

@router.post("/top-urls")
async def calculate_top_urls(
    sources_file: UploadFile = File(..., description="The Knowledge Sources CSV export"),
    limit: int = Query(10, description="Number of top credible brand sources to return")
):
    try:
        sources_contents = await sources_file.read()
        sources_df = pd.read_csv(io.BytesIO(sources_contents))

        result = process_top_urls(sources_df, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {str(e)}")
