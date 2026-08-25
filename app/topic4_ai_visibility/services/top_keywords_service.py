import pandas as pd
from typing import Dict, Any
from collections import Counter
import re

def process_top_keywords(sources_df: pd.DataFrame, limit: int = 10) -> Dict[str, Any]:
    if 'Matched Entities' not in sources_df.columns:
        return {"status": "error", "message": "Missing 'Matched Entities' column in CSV"}

    keywords_counter = Counter()

    for row in sources_df['Matched Entities'].dropna():
        # Split entities separated by '|' or ','
        raw_terms = [term.strip() for term in re.split(r'[|,]', str(row)) if term.strip()]
        
        for term in raw_terms:
            # Clean up trailing periods and extra spaces
            cleaned_term = term.strip('.').strip()
            if len(cleaned_term) > 2:  # Ignore tiny noise words
                keywords_counter[cleaned_term.title()] += 1

    top_keywords = [
        {"keyword": keyword, "occurrences": count}
        for keyword, count in keywords_counter.most_common(limit)
    ]

    return {
        "status": "success",
        "top_keywords": top_keywords
    }
