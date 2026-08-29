import pandas as pd
from typing import Dict, Any
from collections import Counter
import re
from dateutil import parser as date_parser

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


def process_long_form_prompts(facts_df: pd.DataFrame, limit: int = 10) -> Dict[str, Any]:
    """
    The panel this feeds is "Top Visible Search Terms" - process_top_keywords()
    above extracts short root-word/entity phrases from the sources export's
    "Matched Entities" column, which is useful for topical coverage but isn't
    what a real searcher actually types. The facts export's "Prompt" column
    is the literal long-form natural-language query that was put to each AI
    engine, so this counts occurrences of each distinct prompt instead and
    returns the most frequently recurring ones.
    """
    if "Prompt" not in facts_df.columns:
        return {"status": "error", "message": "Missing 'Prompt' column in CSV"}

    prompts_counter = Counter()
    for row in facts_df["Prompt"].dropna():
        prompt = str(row).strip()
        if prompt:
            prompts_counter[prompt] += 1

    top_search_terms = [
        {"prompt": prompt, "occurrences": count}
        for prompt, count in prompts_counter.most_common(limit)
    ]

    return {
        "status": "success",
        "top_search_terms": top_search_terms,
    }


def process_facts_overview(facts_df: pd.DataFrame) -> Dict[str, Any]:
    """
    The facts export's Date and Status columns are parsed into the
    dataframe (needed just to read the CSV) but were never actually looked
    at by anything - Status most plausibly reflects whether the tracked
    fact was verified/confirmed by the AI engine, and Date lets a reader
    see what window of activity this snapshot actually covers, rather than
    treating it as a single undated point-in-time result.
    """
    overview: Dict[str, Any] = {"status_breakdown": None, "date_range": None}

    if "Status" in facts_df.columns:
        counts = facts_df["Status"].dropna().astype(str).str.strip()
        counts = counts[counts != ""]
        if len(counts):
            overview["status_breakdown"] = dict(Counter(counts).most_common())

    if "Date" in facts_df.columns:
        parsed_dates = []
        for raw in facts_df["Date"].dropna():
            try:
                parsed_dates.append(date_parser.parse(str(raw)))
            except (ValueError, OverflowError):
                continue
        if parsed_dates:
            overview["date_range"] = {
                "earliest": min(parsed_dates).date().isoformat(),
                "latest": max(parsed_dates).date().isoformat(),
                "dated_rows": len(parsed_dates),
                "total_rows": len(facts_df),
            }

    return overview
