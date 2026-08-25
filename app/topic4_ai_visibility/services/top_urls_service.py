import pandas as pd
from typing import Dict, Any

def process_top_urls(sources_df: pd.DataFrame, limit: int = 10) -> Dict[str, Any]:
    required_cols = ['Source', 'Total Citations (Source)', 'Category', 'URL']
    for col in required_cols:
        if col not in sources_df.columns:
            return {"status": "error", "message": f"Missing required column '{col}' in CSV"}

    df = sources_df.copy()
    
    # Group by domain source to get total citations and category
    grouped = df.groupby('Source')
    
    sources_summary = []
    for source_name, group in grouped:
        total_citations = int(group['Total Citations (Source)'].iloc[0])
        category = str(group['Category'].iloc[0]) if pd.notna(group['Category'].iloc[0]) else "Unknown"
        
        # Get the individual URLs listed for this source
        sample_urls = group['URL'].dropna().tolist()[:5]
        
        sources_summary.append({
            "source_domain": source_name,
            "category": category,
            "total_citations": total_citations,
            "key_urls": sample_urls
        })

    # Rank by total citations descending
    sources_summary = sorted(sources_summary, key=lambda x: x['total_citations'], reverse=True)[:limit]

    return {
        "status": "success",
        "top_brand_sources": sources_summary
    }
