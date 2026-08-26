from fastapi import APIRouter, UploadFile, File, HTTPException, Query
import pandas as pd
import io
from app.topic4_ai_visibility.services.top_keywords_service import process_top_keywords

router = APIRouter(tags=["Topic 4: AI Visibility"])

@router.post("/top-keywords")
async def calculate_top_keywords(
    sources_file: UploadFile = File(..., description="The Knowledge Sources CSV export"),
    limit: int = Query(10, description="Number of top keywords/entities to return")
):
    try:
        sources_contents = await sources_file.read()
        sources_df = pd.read_csv(io.BytesIO(sources_contents))

        result = process_top_keywords(sources_df, limit=limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV file: {str(e)}")
