from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io
from app.topic4_ai_visibility.services.engine_visibility_service import process_engine_visibility

router = APIRouter(tags=["Topic 4: AI Visibility"])

@router.post("/engine-visibility-breakdown")
async def calculate_engine_visibility_breakdown(
    facts_file: UploadFile = File(..., description="The Facts CSV export"),
    sources_file: UploadFile = File(..., description="The Knowledge Sources CSV export")
):
    try:
        facts_contents = await facts_file.read()
        sources_contents = await sources_file.read()

        facts_df = pd.read_csv(io.BytesIO(facts_contents))
        sources_df = pd.read_csv(io.BytesIO(sources_contents))

        result = process_engine_visibility(facts_df, sources_df)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV files: {str(e)}")
