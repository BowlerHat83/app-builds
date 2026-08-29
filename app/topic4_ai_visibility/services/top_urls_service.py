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


def process_top_target_urls(sources_df: pd.DataFrame, target_domain: str, limit: int = 15) -> Dict[str, Any]:
    """
    Ranks the TARGET domain's own individual pages by citation frequency -
    process_top_urls() above rolls everything up to one row per source
    DOMAIN (competitors included), which is the wrong shape when what's
    actually wanted is "which of our own pages get cited" (e.g.
    bowlerhat.co.uk/about-us, bowlerhat.co.uk/seo, ...).

    The export's "Total Citations (Source)" column is a domain-level total
    repeated on every row for that domain, so it can't tell two of the
    target's own pages apart. Citation count here is instead the number of
    distinct citation rows recorded against each individual URL - see
    methodology_note in the return value.
    """
    import re

    required_cols = ["Source", "URL"]
    for col in required_cols:
        if col not in sources_df.columns:
            return {"status": "error", "message": f"Missing required column '{col}' in CSV"}

    if not target_domain:
        return {"status": "error", "message": "No target domain available to filter by."}

    target_domain = target_domain.lower().lstrip(".")
    df = sources_df.copy()
    df["_source_host"] = df["Source"].astype(str).str.lower().str.replace(r"^www\.", "", regex=True)

    def _is_same_or_subdomain(host: str, domain: str) -> bool:
        # Proper hostname matching rather than raw substring containment -
        # "notexample.com" or "ample.com" both contain "example.com"/are
        # contained by it as plain substrings without being the same site,
        # which was silently pulling in false positives. A host counts as
        # the target only if it's the exact domain, or a subdomain of it
        # (e.g. "blog.example.com" for target "example.com"), or vice versa
        # (the export's "Source" column occasionally records a broader
        # domain than the exact target hostname).
        if not host:
            return False
        if host == domain:
            return True
        if host.endswith("." + domain):
            return True
        if domain.endswith("." + host):
            return True
        return False

    own_rows = df[df["_source_host"].apply(lambda h: _is_same_or_subdomain(h, target_domain))]
    own_rows = own_rows[own_rows["URL"].notna() & (own_rows["URL"].astype(str).str.strip() != "")]

    if own_rows.empty:
        return {
            "status": "success",
            "target_domain": target_domain,
            "total_citation_rows": 0,
            "total_distinct_urls": 0,
            "top_target_urls": [],
        }

    rows = []
    for url, group in own_rows.groupby("URL"):
        category = str(group["Category"].iloc[0]) if "Category" in group.columns and pd.notna(group["Category"].iloc[0]) else "Unknown"
        entities = set()
        if "Matched Entities" in group.columns:
            for val in group["Matched Entities"].dropna():
                for term in re.split(r"[|,]", str(val)):
                    cleaned = term.strip().strip(".").strip()
                    if cleaned:
                        entities.add(cleaned)
        rows.append({
            "url": str(url),
            "citations": len(group),
            "category": category,
            "matched_entities": sorted(entities)[:5],
        })

    rows.sort(key=lambda r: r["citations"], reverse=True)

    return {
        "status": "success",
        "target_domain": target_domain,
        "total_citation_rows": len(own_rows),
        "total_distinct_urls": len(rows),
        "top_target_urls": rows[:limit],
        "methodology_note": (
            "Citation count per URL is the number of distinct rows recorded for that "
            "exact URL in the AI-visibility sources export, not the domain-level "
            "'Total Citations (Source)' figure (which is identical for every page on a "
            "domain and can't distinguish one page from another)."
        ),
    }
