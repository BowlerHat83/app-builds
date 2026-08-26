from typing import Optional

from fastapi import APIRouter, File, UploadFile

from app.common.audit_helpers import envelope
from app.topic5_paid_visibility.services.ppc_service import parse_ppc_competitors_csv, parse_ppc_keywords_csv

router = APIRouter()


async def run_full_audit(ppc_keywords_bytes: Optional[bytes] = None, ppc_competitors_bytes: Optional[bytes] = None, **_ignored) -> dict:
    """
    Topic 5: Paid Visibility. Previously a two-entry hardcoded mock with no
    parsing at all - this now reads the two real PPC exports the team pulls.
    """
    warnings: list = []
    data = {
        "topic": "Topic 5: Paid Visibility Audit",
        "keywords": None,
        "competitor_share": None,
    }

    if ppc_keywords_bytes:
        try:
            data["keywords"] = parse_ppc_keywords_csv(ppc_keywords_bytes)
        except Exception as e:
            warnings.append(f"PPC keywords CSV parse failed: {e}")
    else:
        warnings.append("No PPC keywords CSV uploaded.")

    if ppc_competitors_bytes:
        try:
            data["competitor_share"] = parse_ppc_competitors_csv(ppc_competitors_bytes)
        except Exception as e:
            warnings.append(f"PPC competitors CSV parse failed: {e}")
    else:
        warnings.append("No PPC competitors CSV uploaded.")

    return envelope("Topic 5: Paid Visibility Audit", data, warnings)


@router.post("/audit-all", summary="Run Topic 5 Audit with PPC exports")
async def run_audit_all(
    ppc_keywords_csv: Optional[UploadFile] = File(None),
    ppc_competitors_csv: Optional[UploadFile] = File(None),
):
    return await run_full_audit(
        ppc_keywords_bytes=await ppc_keywords_csv.read() if ppc_keywords_csv else None,
        ppc_competitors_bytes=await ppc_competitors_csv.read() if ppc_competitors_csv else None,
    )
