import io
import pandas as pd
from urllib.parse import urlparse

def parse_top_competitors(sources_bytes: bytes = None, facts_bytes: bytes = None, target_url: str = ""):
    # We parse the Sources CSV as it contains Citations, Unique URLs, and LLM Breakdowns
    csv_bytes = sources_bytes or facts_bytes
    if not csv_bytes:
        return []

    try:
        df = pd.read_csv(io.BytesIO(csv_bytes))
        
        source_col = 'Source' if 'Source' in df.columns else next((c for c in df.columns if 'source' in c.lower()), None)
        cit_col = 'Total Citations (Source)' if 'Total Citations (Source)' in df.columns else next((c for c in df.columns if 'citation' in c.lower()), None)
        urls_col = 'Unique URLs (Source)' if 'Unique URLs (Source)' in df.columns else next((c for c in df.columns if 'url' in c.lower()), None)
        model_col = 'Models Breakdown' if 'Models Breakdown' in df.columns else next((c for c in df.columns if 'model' in c.lower()), None)

        if not source_col:
            return []

        # Extract target domain to isolate competitors
        target_domain = ""
        if target_url:
            clean_t = target_url if target_url.startswith(('http://', 'https://')) else f"https://{target_url}"
            target_domain = urlparse(clean_t).netloc.replace("www.", "").lower()

        # Exclude target domain rows
        df['clean_source'] = df[source_col].astype(str).str.lower().str.strip()
        df_comp = df[~df['clean_source'].str.contains(target_domain)].copy() if target_domain else df.copy()

        # Group by competitor domain
        grouped = df_comp.groupby(source_col).agg({
            cit_col: 'first' if cit_col else lambda s: len(s),
            urls_col: 'first' if urls_col else lambda s: len(s),
            model_col: lambda s: list(s)[0] if (model_col and len(s) > 0) else ""
        }).reset_index()

        # Numeric conversions and sorting
        if cit_col:
            grouped[cit_col] = pd.to_numeric(grouped[cit_col], errors='coerce').fillna(0)
            grouped = grouped.sort_values(by=cit_col, ascending=False)

        if urls_col:
            grouped[urls_col] = pd.to_numeric(grouped[urls_col], errors='coerce').fillna(0)

        # Helper to parse engine counts from "Sonar:27 | Gemini:28 | chatGPT:3"
        def parse_llm_counts(raw_str):
            res = {"gemini": 0, "claude": 0, "sonar": 0, "gpt": 0}
            if not isinstance(raw_str, str):
                return res
            for part in raw_str.split('|'):
                if ':' in part:
                    k, v = part.split(':')
                    k_clean, v_clean = k.strip().lower(), v.strip()
                    val = int(v_clean) if v_clean.isdigit() else 0
                    if 'gemini' in k_clean: res['gemini'] += val
                    elif 'claude' in k_clean: res['claude'] += val
                    elif 'sonar' in k_clean or 'perplexity' in k_clean: res['sonar'] += val
                    elif 'gpt' in k_clean or 'openai' in k_clean or 'chatgpt' in k_clean: res['gpt'] += val
            return res

        competitors = []
        for _, row in grouped.head(5).iterrows():
            models = parse_llm_counts(row[model_col]) if model_col else {"gemini": 0, "claude": 0, "sonar": 0, "gpt": 0}
            competitors.append({
                "domain": str(row[source_col]),
                "total_citations": int(row[cit_col]) if cit_col else 0,
                "unique_urls_indexed": int(row[urls_col]) if urls_col else 0,
                "llm_breakdown": models
            })

        return competitors
    except Exception as e:
        print(f"Error parsing top competitors: {e}")
        return []
