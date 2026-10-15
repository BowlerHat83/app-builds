"""Shared Recent runs - see app/common/run_store.py."""

import re

from fastapi import APIRouter, Body, HTTPException

from app.common import run_store

router = APIRouter(prefix="/runs", tags=["Recent runs"])

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _check(run_id: str) -> None:
    if not _ID.match(run_id or ""):
        raise HTTPException(status_code=400, detail="Bad run id")


def _require() -> None:
    if not run_store.bucket():
        raise HTTPException(status_code=503, detail="Shared runs not configured (RUNS_BUCKET)")


@router.get("")
async def list_runs():
    if not run_store.bucket():
        return {"enabled": False, "runs": []}
    try:
        return {"enabled": True, "runs": await run_store.list_runs()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Run storage unavailable: {type(e).__name__}")


@router.get("/{run_id}")
async def get_run(run_id: str):
    _check(run_id)
    _require()
    run = await run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("")
async def save_run(payload: dict = Body(...)):
    _require()
    meta, audit = payload.get("meta") or {}, payload.get("audit")
    if not audit or not meta.get("id"):
        raise HTTPException(status_code=400, detail="meta.id and audit are required")
    _check(str(meta["id"]))
    return {"enabled": True, "runs": await run_store.save_run(meta, audit)}


@router.delete("/{run_id}")
async def delete_run(run_id: str):
    _check(run_id)
    _require()
    await run_store.delete_run(run_id)
    return {"ok": True}
