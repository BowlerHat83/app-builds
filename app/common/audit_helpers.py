"""
Shared helpers used across all topicN aggregate.py modules.

The point of this module is to give every topic the same failure behaviour:
a slow or broken live check (SSL, Playwright, a live crawl) degrades to a
warning instead of taking down the whole /audit-master call, and every
topic's public function returns the same envelope shape so the frontend
(and the master orchestrator) only ever has to handle one response format.
"""

import asyncio
from typing import Any, Awaitable, Optional, Tuple


async def safe_check(coro: Awaitable, label: str, timeout: float = 20.0) -> Tuple[Optional[Any], Optional[str]]:
    """
    Runs a coroutine with a hard timeout and catches any exception it raises.

    Returns (result, warning). `result` is None if the check failed or timed
    out; `warning` is a short human-readable string describing what went
    wrong, or None if the check succeeded. Callers should always check for
    `warning is not None` rather than trusting `result` to be populated.
    """
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return result, None
    except asyncio.TimeoutError:
        return None, f"{label} timed out after {timeout:g}s"
    except Exception as e:  # noqa: BLE001 - intentionally broad, this is a resilience boundary
        # Some exceptions (notably httpx's timeout family - ConnectTimeout,
        # ReadTimeout, etc.) stringify to an empty message, which used to
        # produce a warning banner reading just "<label> failed: " with
        # nothing after the colon - technically present, but useless for
        # figuring out what actually went wrong without digging through
        # server logs. Fall back to the exception's class name so there's
        # always something diagnosable in the message itself.
        detail = str(e) or type(e).__name__
        return None, f"{label} failed: {detail}"


def envelope(topic: str, data: dict, warnings: Optional[list] = None) -> dict:
    """
    Standard response shape every topicN.aggregate.run_full_audit() returns.

    status is:
      - "success"  no warnings at all
      - "partial"  some sub-checks failed/degraded but at least one succeeded
      - "error"    nothing could be produced
    """
    warnings = warnings or []
    has_data = bool(data)
    if not has_data and warnings:
        status = "error"
    elif warnings:
        status = "partial"
    else:
        status = "success"

    return {
        "status": status,
        "topic": topic,
        "data": data,
        "warnings": warnings,
    }


def read_csv_robust(file_bytes: bytes):
    """
    Shared CSV reader for the plain UTF-8 / ASCII exports (Screaming Frog,
    the PPC tool, the AI-visibility tracker, BrightLocal). Ahrefs' UTF-16
    tab-separated exports use their own decoder inside topic3's services,
    since that format is specific to Ahrefs.
    """
    import io
    import pandas as pd

    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError("Unable to decode CSV with supported encodings (utf-8, latin1).")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def hostname_of(url: str) -> str:
    """Bare hostname (no scheme, no www, no path) - used to match rows in a
    CSV export against "is this actually the target site" rather than a
    competitor or third-party domain."""
    from urllib.parse import urlparse

    url = normalize_url(url)
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host
