from typing import Optional

from fastapi import APIRouter, File, UploadFile

from app.common.audit_helpers import envelope, hostname_of, read_csv_robust
from app.topic4_ai_visibility.services.engine_visibility_service import process_engine_visibility
from app.topic4_ai_visibility.services.top_competitors_service import process_top_competitors
from app.topic4_ai_visibility.services.top_keywords_service import (
    process_facts_overview,
    process_long_form_prompts,
    process_top_keywords,
)
from app.topic4_ai_visibility.services.top_urls_service import process_top_target_urls, process_top_urls

router = APIRouter()

ENGINES = ["gemini", "chatgpt", "claude", "sonar"]


async def run_full_audit(
    facts_bytes: Optional[bytes] = None,
    sources_bytes: Optional[bytes] = None,
    target_url: Optional[str] = None,
    **_ignored,
) -> dict:
    """
    Topic 4: AI Visibility.

    facts_bytes is the AI-visibility tracker's "facts" export (Date, Prompt,
    Fact, LLM Model, Status). sources_bytes is that same tool's "knowledge
    sources" export (Source, Category, Matched Entities, Total Citations,
    URL, Models Breakdown). Both are needed - engine visibility needs both,
    the other three panels only need sources.
    """
    warnings: list = []
    data = {
        "topic": "Topic 4: AI Visibility Audit",
        "engine_visibility": None,
        "top_competitors": None,
        "top_keywords": None,
        "top_search_terms": None,
        "facts_overview": None,
        "top_urls": None,
        "top_target_urls": None,
        "summary": None,
    }

    facts_df = None
    sources_df = None

    if facts_bytes:
        try:
            facts_df = read_csv_robust(facts_bytes)
        except Exception as e:
            warnings.append(f"Facts CSV parse failed: {e}")
    else:
        warnings.append("No AI-visibility facts CSV uploaded.")

    if sources_bytes:
        try:
            sources_df = read_csv_robust(sources_bytes)
        except Exception as e:
            warnings.append(f"Sources CSV parse failed: {e}")
    else:
        warnings.append("No AI-visibility knowledge-sources CSV uploaded.")

    if facts_df is not None and sources_df is not None:
        result = process_engine_visibility(facts_df, sources_df)
        data["engine_visibility"] = result
    elif facts_df is None and sources_df is None:
        pass
    else:
        warnings.append("Engine visibility breakdown needs both the facts CSV and the sources CSV.")

    if facts_df is not None:
        try:
            result = process_long_form_prompts(facts_df)
            if result.get("status") == "error":
                warnings.append(f"top_search_terms: {result.get('message')}")
            else:
                data["top_search_terms"] = result
        except Exception as e:
            warnings.append(f"top_search_terms failed: {e}")

        try:
            data["facts_overview"] = process_facts_overview(facts_df)
        except Exception as e:
            warnings.append(f"facts_overview failed: {e}")

    if sources_df is not None:
        for key, fn in (
            ("top_competitors", process_top_competitors),
            ("top_keywords", process_top_keywords),
            ("top_urls", process_top_urls),
        ):
            try:
                result = fn(sources_df)
                if result.get("status") == "error":
                    warnings.append(f"{key}: {result.get('message')}")
                else:
                    data[key] = result
            except Exception as e:
                warnings.append(f"{key} failed: {e}")

        target_domain = hostname_of(target_url) if target_url else ""
        if target_domain:
            try:
                result = process_top_target_urls(sources_df, target_domain)
                if result.get("status") == "error":
                    warnings.append(f"top_target_urls: {result.get('message')}")
                else:
                    data["top_target_urls"] = result
            except Exception as e:
                warnings.append(f"top_target_urls failed: {e}")
        else:
            warnings.append("No target_url supplied - can't scope citations to the target domain's own pages.")

    engines_seen = 0
    cited_urls = 0
    cited_terms = 0
    if data["engine_visibility"]:
        breakdown = data["engine_visibility"].get("engine_visibility_breakdown", [])
        engines_seen = sum(1 for e in breakdown if e.get("keyword_count", 0) > 0 or e.get("source_count", 0) > 0)
    # cited_urls_count is scoped to the target's OWN pages (from
    # top_target_urls), not every unique URL in the sources export - the
    # export includes competitor and third-party sources too, and counting
    # those here made the figure read as "how visible is our content" when
    # it was really "how many URLs exist in this CSV at all".
    if data["top_target_urls"] is not None:
        cited_urls = int(data["top_target_urls"].get("total_distinct_urls", 0))
    if facts_df is not None and "Prompt" in facts_df.columns:
        cited_terms = int(facts_df["Prompt"].dropna().nunique())

    # Only build a summary when at least one export was actually supplied -
    # with neither facts_bytes nor sources_bytes, engines_seen/cited_urls/
    # cited_terms are all structurally 0 (nothing was ever computed), and a
    # summary built from that would read as "0/4 engines cite you" - a real,
    # bad-looking result - rather than "we don't know, nothing was
    # submitted". Leaving data["summary"] as the None it's initialized to
    # keeps that distinction, matching the same not-fabricated-when-absent
    # rule used elsewhere (e.g. Topic 6 NAP, Topic 7 thin content, Topic 3
    # traffic fallbacks) and is what lets the frontend composite score treat
    # a fully-absent Topic 4 as N/A instead of a 0.
    if facts_df is not None or sources_df is not None:
        data["summary"] = {
            "engine_visibility_ratio": f"{engines_seen}/{len(ENGINES)}",
            "cited_urls_count": cited_urls,
            "cited_search_terms_count": cited_terms,
        }

    return envelope("Topic 4: AI Visibility Audit", data, warnings)


@router.post("/audit-all", summary="Run Topic 4 Audit with AI-visibility exports")
async def run_audit_all(
    ai_facts_csv: Optional[UploadFile] = File(None),
    ai_sources_csv: Optional[UploadFile] = File(None),
    target_url: Optional[str] = None,
):
    return await run_full_audit(
        facts_bytes=await ai_facts_csv.read() if ai_facts_csv else None,
        sources_bytes=await ai_sources_csv.read() if ai_sources_csv else None,
        target_url=target_url,
    )
