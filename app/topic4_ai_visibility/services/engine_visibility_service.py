import pandas as pd
from typing import Dict, Any, List

def normalize_engine_name(model_str: str) -> str:
    m = str(model_str).lower()
    if 'gemini' in m:
        return 'gemini'
    elif 'chatgpt' in m or 'gpt' in m:
        return 'chatgpt'
    elif 'claude' in m:
        return 'claude'
    elif 'sonar' in m or 'perplexity' in m:
        return 'sonar'
    return 'other'

def process_engine_visibility(facts_df: pd.DataFrame, sources_df: pd.DataFrame) -> Dict[str, Any]:
    engines = ['gemini', 'chatgpt', 'claude', 'sonar']
    
    # 1. Keywords / Prompts per Engine
    keywords_per_engine = {e: set() for e in engines}
    if 'LLM Model' in facts_df.columns and 'Prompt' in facts_df.columns:
        for _, row in facts_df.iterrows():
            engine = normalize_engine_name(row['LLM Model'])
            if engine in keywords_per_engine and pd.notna(row['Prompt']):
                keywords_per_engine[engine].add(row['Prompt'])
                
    # 2. Sources per Engine
    sources_per_engine = {e: set() for e in engines}
    if 'Models Breakdown' in sources_df.columns and 'Source' in sources_df.columns:
        for _, row in sources_df.iterrows():
            source = row['Source']
            mb_str = str(row['Models Breakdown']) if pd.notna(row['Models Breakdown']) else ''
            parts = mb_str.split('|')
            for part in parts:
                if ':' in part:
                    raw_model = part.split(':')[0].strip()
                    engine = normalize_engine_name(raw_model)
                    if engine in sources_per_engine and pd.notna(source):
                        sources_per_engine[engine].add(source)

    # 3. Format Breakdown
    breakdown = []
    for e in engines:
        breakdown.append({
            "engine": e.capitalize(),
            "keyword_count": len(keywords_per_engine[e]),
            "source_count": len(sources_per_engine[e])
        })
        
    return {
        "status": "success",
        "engine_visibility_breakdown": breakdown
    }
