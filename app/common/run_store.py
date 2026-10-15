"""
Shared "Recent runs" storage in a Google Cloud Storage bucket, so finished
audits are visible from any browser or machine (previously localStorage -
one browser only).

No extra package: talks to the GCS JSON API with httpx, authenticating as
the Cloud Run service account via the metadata server. Disabled (the
endpoints report "unavailable" and the frontend falls back to this
browser's local list) when RUNS_BUCKET isn't set or there's no metadata
server (local development).

Layout in the bucket:
  meta/<id>.json  - small summary for the list (site, scores, date)
  runs/<id>.json  - the full audit result (gzip-encoded)

Only the latest run per site is kept, same as the WCAG scanner.
Cost: a bucket in a US region (us-central1 / us-east1 / us-west1) sits in
Google's Always Free tier (5 GB storage) - audits are a few hundred KB each.
"""

import gzip
import json
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

API = "https://storage.googleapis.com/storage/v1/b"
UPLOAD = "https://storage.googleapis.com/upload/storage/v1/b"
TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
MAX_RUNS = int(os.environ.get("RUNS_MAX", "60"))
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

_token: Dict[str, Any] = {"value": None, "expires": 0.0}


def bucket() -> Optional[str]:
    b = (os.environ.get("RUNS_BUCKET") or "").strip()
    return b or None


async def _auth(client: httpx.AsyncClient) -> Dict[str, str]:
    if _token["value"] and time.time() < _token["expires"] - 60:
        return {"Authorization": f"Bearer {_token['value']}"}
    resp = await client.get(TOKEN_URL, headers={"Metadata-Flavor": "Google"}, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + int(data.get("expires_in", 300))
    return {"Authorization": f"Bearer {_token['value']}"}


def site_key(url: str) -> str:
    v = (url or "").lower().split("://", 1)[-1].split("/", 1)[0]
    return v[4:] if v.startswith("www.") else v


async def _put(client, name: str, body: bytes, gz: bool = False) -> None:
    params = {"uploadType": "media", "name": name}
    headers = {**(await _auth(client)), "Content-Type": "application/json"}
    if gz:
        params["contentEncoding"] = "gzip"
    resp = await client.post(f"{UPLOAD}/{bucket()}/o", params=params, headers=headers, content=body)
    resp.raise_for_status()


async def _get(client, name: str) -> Optional[bytes]:
    resp = await client.get(f"{API}/{bucket()}/o/{quote(name, safe='')}", params={"alt": "media"},
                            headers=await _auth(client))
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content  # httpx decodes gzip Content-Encoding automatically


async def _delete(client, name: str) -> None:
    resp = await client.delete(f"{API}/{bucket()}/o/{quote(name, safe='')}", headers=await _auth(client))
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()


async def list_runs() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        names: List[str] = []
        page = None
        while True:
            params = {"prefix": "meta/", "fields": "items(name),nextPageToken"}
            if page:
                params["pageToken"] = page
            resp = await client.get(f"{API}/{bucket()}/o", params=params, headers=await _auth(client))
            resp.raise_for_status()
            body = resp.json()
            names += [i["name"] for i in body.get("items", [])]
            page = body.get("nextPageToken")
            if not page:
                break
        metas = []
        for n in names:
            raw = await _get(client, n)
            if raw:
                try:
                    metas.append(json.loads(raw))
                except Exception:
                    continue
    metas.sort(key=lambda m: m.get("saved_at") or "", reverse=True)
    return metas


async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        raw = await _get(client, f"runs/{run_id}.json")
    return json.loads(raw) if raw else None


async def save_run(meta: Dict[str, Any], audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    run_id = str(meta["id"])
    existing = await list_runs()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await _put(client, f"runs/{run_id}.json", gzip.compress(json.dumps(audit).encode("utf-8")), gz=True)
        await _put(client, f"meta/{run_id}.json", json.dumps(meta).encode("utf-8"))
        # Latest run per site only, and a cap on the total.
        key = site_key(meta.get("target_url", ""))
        stale = [m for m in existing if m.get("id") != run_id and site_key(m.get("target_url", "")) == key]
        keep = [m for m in existing if m not in stale and m.get("id") != run_id]
        stale += keep[MAX_RUNS - 1:]
        for m in stale:
            await _delete(client, f"runs/{m['id']}.json")
            await _delete(client, f"meta/{m['id']}.json")
    return await list_runs()


async def delete_run(run_id: str) -> None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await _delete(client, f"runs/{run_id}.json")
        await _delete(client, f"meta/{run_id}.json")
