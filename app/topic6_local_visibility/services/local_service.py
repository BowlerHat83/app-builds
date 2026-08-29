import asyncio
import csv
import io
import pandas as pd
import httpx
from typing import Dict, Any, List, Optional

class LocalVisibilityService:
    async def process_brightlocal_csv(self, csv_bytes: bytes) -> Dict[str, Any]:
        df = pd.read_csv(io.BytesIO(csv_bytes))

        if len(df) == 0:
            return {"error": "CSV file is empty"}

        # BrightLocal's "Status" column mixes three very different things
        # into one export: "active" (a real, confirmed citation the
        # business actually has), "Duplicate" (also a real citation - and
        # itself a genuine local-SEO problem, since duplicate listings for
        # the same business confuse search engines), and "Potential" (a
        # directory BrightLocal is merely suggesting as an opportunity -
        # the business isn't listed there at all). Treating every row as a
        # "citation" massively overstated the citation count on a real
        # export tested against this code (918 rows, only 213 of which are
        # actual citations - the other 705 were "Potential"), and, more
        # importantly, silently inflated NAP consistency: an unclaimed
        # "Potential" row trivially has no NAP issues, because it has no
        # NAP data at all to have issues with.
        status_norm = df["Status"].astype(str).str.strip().str.lower() if "Status" in df.columns else None
        if status_norm is not None:
            is_potential = status_norm == "potential"
            citation_rows = df[~is_potential]
            potential_rows = df[is_potential]
            active_count = int((status_norm == "active").sum())
            duplicate_count = int((status_norm == "duplicate").sum())
        else:
            citation_rows = df
            potential_rows = df.iloc[0:0]
            active_count = 0
            duplicate_count = 0

        total_citations = int(len(citation_rows))
        potential_opportunities = int(len(potential_rows))

        if total_citations == 0:
            return {
                "error": "This export has no active or duplicate citations - only unclaimed 'Potential' listings "
                "(directories BrightLocal suggests but the business isn't actually listed on yet)."
            }

        high_da_count = int((citation_rows["Domain Authority"] >= 40).sum()) if "Domain Authority" in citation_rows.columns else 0
        high_da_opportunities = int((potential_rows["Domain Authority"] >= 40).sum()) if "Domain Authority" in potential_rows.columns else 0

        # NAP (Name/Address/Phone) consistency - a citation is "clean" if
        # none of BrightLocal's own per-field issue flags are set for it.
        # Matched case/whitespace-insensitively against a few real-world
        # column-naming variants, since exports differ slightly by
        # BrightLocal account/report type.
        #
        # This used to match only 4 exact hardcoded column names and, if
        # none matched, silently fell back to reporting a blanket 100%
        # ("no issues found") - even though it had never actually looked at
        # a single row to reach that conclusion. That's a false "clean"
        # result, not a real one. This now reports nap_consistency_score as
        # None with an explanatory note when the export doesn't have
        # anything to compute it from, so the frontend can show "not
        # available" instead of a fabricated perfect score.
        normalized_cols = {str(c).strip().lower(): c for c in df.columns}
        issue_field_aliases = [
            "business name issue", "name issue", "business_name_issue", "name_issue",
            "address issue", "address_issue",
            "zip/postcode issue", "zip issue", "postcode issue", "zip_issue", "postcode_issue",
            "phone number issue", "phone issue", "phone_issue", "phone_number_issue",
        ]
        existing_cols = [normalized_cols[alias] for alias in issue_field_aliases if alias in normalized_cols]

        # Broader, un-opinionated scan (substring match on "issue") purely
        # for transparency - this is what actually lets a score that looks
        # wrong get diagnosed without needing to see the raw CSV. If a real
        # export uses column names this alias list doesn't anticipate (e.g.
        # different wording, or one combined "Issues" column instead of
        # four separate ones), those columns will show up here even when
        # they didn't match above, so it's visible exactly what was and
        # wasn't looked at.
        issue_like_cols = [str(c) for c in df.columns if "issue" in str(c).strip().lower()]

        # Even among real citation rows, BrightLocal only has NAP data to
        # actually check on the ones it's deep-crawled - most rows in a
        # typical export (Potential opportunities, and some active/
        # Duplicate rows BrightLocal hasn't deep-checked yet) have no
        # Business Name/Address/Zip/Phone captured at all. Scoring those as
        # "clean" alongside genuinely-verified rows is the same fabrication
        # problem as the old 100% fallback, just smaller in magnitude - so
        # the score is scoped to only the rows BrightLocal actually
        # captured NAP data for.
        core_field_aliases = ["business name", "address", "zip/postcode", "phone number"]
        existing_core_cols = [normalized_cols[alias] for alias in core_field_aliases if alias in normalized_cols]
        checked_rows = citation_rows[citation_rows[existing_core_cols].notna().any(axis=1)] if existing_core_cols else citation_rows
        nap_sample_size = int(len(checked_rows))

        nap_consistency_note = None
        nap_score = None
        if existing_cols:
            if nap_sample_size > 0:
                clean_rows = checked_rows[checked_rows[existing_cols].isna().all(axis=1)]
                nap_score = round((len(clean_rows) / nap_sample_size) * 100, 2)
                note_parts = [
                    f"Based on the {nap_sample_size} of {total_citations} citations BrightLocal has actually "
                    f"captured Business Name/Address/Zip/Phone data for (checked against {', '.join(existing_cols)}) "
                    "- the rest are either unclaimed opportunities or citations not yet deep-checked, so they're "
                    "excluded rather than counted as automatically clean."
                ]
                unmatched_issue_like = [c for c in issue_like_cols if c not in existing_cols]
                if unmatched_issue_like:
                    # Score was computed, but there's at least one other
                    # "issue"-shaped column that wasn't part of the
                    # calculation - flag it rather than silently ignoring
                    # it, since it could be the real signal if the matched
                    # columns turn out to be unreliable.
                    note_parts.append(
                        f"This export also has {', '.join(unmatched_issue_like)}, which weren't recognized and so "
                        "weren't included - if the score above looks off, this is the most likely reason."
                    )
                nap_consistency_note = " ".join(note_parts)
            else:
                nap_consistency_note = (
                    "None of this export's citations have actual Business Name/Address/Zip/Phone data captured "
                    "yet, so NAP consistency couldn't be assessed - only unclaimed opportunities or citations "
                    "BrightLocal hasn't deep-checked are present."
                )
        else:
            if issue_like_cols:
                nap_consistency_note = (
                    "This BrightLocal export has issue-related columns "
                    f"({', '.join(issue_like_cols)}) but not the exact per-field names "
                    "(Business Name/Address/Zip/Phone Issue) this score expects, so NAP "
                    "consistency couldn't be assessed from them."
                )
            else:
                nap_consistency_note = (
                    "This BrightLocal export doesn't include the per-field issue columns "
                    "(Business Name/Address/Zip/Phone Issue) this score is calculated from, "
                    "so NAP consistency couldn't actually be assessed."
                )

        return {
            "total_citations": total_citations,
            "active_citations": active_count,
            "duplicate_citations": duplicate_count,
            "potential_citation_opportunities": potential_opportunities,
            "high_authority_citations": high_da_count,
            "high_authority_opportunities": high_da_opportunities,
            "nap_consistency_score": nap_score,
            "nap_consistency_sample_size": nap_sample_size,
            "nap_consistency_note": nap_consistency_note,
            "nap_consistency_columns_checked": existing_cols,
        }

    async def fetch_map_pack_position(
        self, 
        business_name: str, 
        location: str, 
        keywords: List[str], 
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pings Google Local SERP (engine=google_local) to detect map pack rank
        (1-3) across target keywords. Note: this engine's "place_id" field is
        actually a raw internal CID, not a value compatible with SerpApi's
        google_maps_reviews endpoint - reviews are resolved independently via
        engine=google_maps in gbp_review_service.py instead of reusing anything
        from here.
        """
        # Each keyword is an independent live SerpApi call - this used to run
        # them one at a time in a for loop, so with up to ~8 keywords (2 base
        # + up to 2 per topic from Topic 3/4/5's unbranded keywords) at
        # several seconds apiece, the total could easily blow past the 20s
        # budget aggregate.py gives this whole check even though no single
        # request was slow. Running them concurrently instead means the
        # total wait is roughly the slowest single request, not the sum of
        # all of them.
        async def _check_one(client: httpx.AsyncClient, kw: str) -> Dict[str, Any]:
            if not api_key:
                # No API key configured - do NOT report a rank. A fabricated number
                # that looks like a live SERP position is worse than no number at all.
                return {
                    "keyword": kw,
                    "map_pack_position": None,
                    "found": False,
                    "note": "No SerpApi key configured - live map-pack rank unavailable for this keyword."
                }
            try:
                url = "https://serpapi.com/search.json"
                params = {
                    "engine": "google_local",
                    "q": f"{kw} {location}",
                    "location": location,
                    "api_key": api_key
                }
                resp = await client.get(url, params=params)
                data = resp.json()
                local_results = data.get("local_results", [])

                rank = None
                for idx, item in enumerate(local_results, start=1):
                    if business_name.lower() in item.get("title", "").lower():
                        rank = idx
                        break

                # Google's real "map pack" widget only ever shows the top 3
                # local results - SerpApi's local_results list can return
                # well beyond that (position 10, 15, whatever the business
                # actually ranks at in local search), so a match found deep
                # in that list is a real local-search rank, but it is NOT
                # "in the map pack". in_map_pack is what "found"/the
                # headline stats below actually mean; local_pack_position
                # is kept as the raw rank for context even when it's beyond
                # the true 3-pack.
                in_map_pack = rank is not None and rank <= 3
                return {
                    "keyword": kw,
                    "local_pack_position": rank,
                    "in_map_pack": in_map_pack,
                    "found": rank is not None,
                }
            except Exception as e:
                return {"keyword": kw, "error": str(e), "found": False, "in_map_pack": False}

        async with httpx.AsyncClient(timeout=10.0) as client:
            results = await asyncio.gather(*(_check_one(client, kw) for kw in keywords))

        map_pack_positions = [r["local_pack_position"] for r in results if r.get("in_map_pack")]
        all_found_positions = [r["local_pack_position"] for r in results if r.get("local_pack_position")]
        avg_position = round(sum(map_pack_positions) / len(map_pack_positions), 2) if map_pack_positions else None
        avg_local_pack_position = round(sum(all_found_positions) / len(all_found_positions), 2) if all_found_positions else None
        data_source = "live_serpapi" if api_key else "unavailable"

        return {
            "business_name": business_name,
            "location": location,
            "data_source": data_source,
            # "map pack" = the real top-3 widget only, per in_map_pack above.
            "average_map_pack_position": avg_position,
            "total_keywords_tracked": len(keywords),
            "keywords_in_map_pack": len(map_pack_positions),
            # Wider local-search context (not the 3-pack, but still real
            # rank data) - a business can be found in local results without
            # making the actual map pack, and that's worth knowing too.
            "keywords_found_in_local_results": len(all_found_positions),
            "average_local_search_position": avg_local_pack_position,
            "keyword_breakdown": results,
        }
