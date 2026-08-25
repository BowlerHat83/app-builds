import pandas as pd
from typing import Dict, Any, List

def process_top_competitors(sources_df: pd.DataFrame, limit: int = 10) -> Dict[str, Any]:
    if 'Source' not in sources_df.columns:
        return {"status": "error", "message": "Missing 'Source' column in CSV"}

    # Aggregate total citations or frequency per domain/source
    citation_col = 'Total Citations (Source)' if 'Total Citations (Source)' in sources_df.columns else None
    
    if citation_col:
        competitor_counts = sources_df.groupby('Source')[citation_col].max().reset_index()
        competitor_counts = competitor_counts.sort_values(by=citation_col, ascending=False)
        competitor_counts.rename(columns={citation_col: "citations"}, inplace=True)
    else:
        competitor_counts = sources_df['Source'].value_counts().reset_index()
        competitor_counts.columns = ['Source', 'citations']

    top_competitors = competitor_counts.head(limit).to_dict(orient='records')

    formatted_competitors = [
        {"domain": row['Source'], "citations": int(row['citations'])}
        for row in top_competitors
    ]

    return {
        "status": "success",
        "top_competitors": formatted_competitors
    }
