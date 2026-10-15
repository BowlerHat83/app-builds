from typing import Optional

from fastapi import APIRouter, File, UploadFile

from app.common.audit_helpers import envelope, source, extra
from app.common.integrations.ahrefs import fetch_paid_estimate
from app.topic5_paid_visibility.services.ppc_service import parse_ppc_competitors_csv, parse_ppc_keywords_csv

router = APIRouter()


async def run_full_audit(
    ppc_keywords_bytes: Optional[bytes] = None,
    ppc_competitors_bytes: Optional[bytes] = None,
    target_url: Optional[str] = None,
    **_ignored,
) -> dict:
    """
    Topic 5: Paid Visibility. Previously a two-entry hardcoded mock with no
    parsing at all - this now reads the two real PPC exports the team pulls.
    """
    warnings: list = []
    sources, extras = [], []
    data = {
        "topic": "Topic 5: Paid Visibility Audit",
        "keywords": None,
        "competitor_share": None,
    }

    # Neither SpyFu export uploaded? Fall back to an Ahrefs-based estimate
    # (clearly labelled as such) rather than showing nothing. Only when BOTH
    # are missing - mixing SpyFu figures for one side with Ahrefs figures for
    # the other would make the client-vs-competitor comparison meaningless.
    if not ppc_keywords_bytes and not ppc_competitors_bytes:
        est, est_notes, est_detail = await fetch_paid_estimate(target_url)
        warnings.extend(est_notes)
        if est:
            data["keywords"] = est["keywords"]
            data["competitor_share"] = est["competitor_share"]
            data["data_source"] = est["data_source"]
            sources.append(source("Ahrefs API (paid search estimate)", "estimate", est_detail))
        extras.append(extra("SpyFu PPC Keywords CSV", "missing", "Upload for full paid keyword, CPC and spend-by-match-type data."))
        extras.append(extra("SpyFu PPC Competitors CSV", "missing", "Upload for true paid-search competitors (by shared ad keywords)."))
        return envelope("Topic 5: Paid Visibility Audit", data, warnings, sources=sources, extras=extras)

    if ppc_keywords_bytes:
        sources.append(source("SpyFu PPC Keywords CSV", "csv", "Uploaded export - paid keywords, CPC and spend by match type."))
        try:
            data["keywords"] = parse_ppc_keywords_csv(ppc_keywords_bytes)
        except Exception as e:
            warnings.append(f"PPC keywords CSV parse failed: {e}")
    else:
        extras.append(extra("SpyFu PPC Keywords CSV", "missing", "Needed for the client's paid keywords, clicks and spend."))

    if ppc_competitors_bytes:
        sources.append(source("SpyFu PPC Competitors CSV", "csv", "Uploaded export - paid-search competitors and their budgets."))
        try:
            data["competitor_share"] = parse_ppc_competitors_csv(ppc_competitors_bytes)
        except Exception as e:
            warnings.append(f"PPC competitors CSV parse failed: {e}")
    else:
        extras.append(extra("SpyFu PPC Competitors CSV", "missing", "Needed to compare the client against competitors' paid activity."))

    return envelope("Topic 5: Paid Visibility Audit", data, warnings, sources=sources, extras=extras)


@router.post("/audit-all", summary="Run Topic 5 Audit with PPC exports")
async def run_audit_all(
    ppc_keywords_csv: Optional[UploadFile] = File(None),
    ppc_competitors_csv: Optional[UploadFile] = File(None),
):
    return await run_full_audit(
        ppc_keywords_bytes=await ppc_keywords_csv.read() if ppc_keywords_csv else None,
        ppc_competitors_bytes=await ppc_competitors_csv.read() if ppc_competitors_csv else None,
    )
