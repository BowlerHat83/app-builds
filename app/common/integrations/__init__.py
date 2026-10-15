"""
Live API integrations that can stand in for the CSV uploads.

Every integration follows the same rule: an uploaded CSV always wins; the
API is only used when no CSV was uploaded for that slot AND the relevant
API key is set in the environment. If the key is missing, or the call
fails, the integration returns None plus a short human-readable note, and
the topic carries on exactly as it would have with no CSV - nothing that
worked before these integrations existed is put at risk.
"""

import os


def integration_status() -> dict:
    """Which CSV slots can currently be filled automatically from an API."""
    bl = bool(os.environ.get("BRIGHTLOCAL_API_KEY"))
    ah = bool(os.environ.get("AHREFS_API_KEY"))
    return {
        "brightlocal_csv": bl,
        "ahrefs_backlinks_csv": ah,
        "ahrefs_keywords_csv": ah,
        "ahrefs_competitors_csv": ah,
        # Topic 5 falls back to an Ahrefs-based estimate when no SpyFu
        # exports are uploaded - flagged separately so the intake screen can
        # show it as partial cover rather than a full replacement.
        "ppc_keywords_csv": "estimate" if ah else False,
        "ppc_competitors_csv": "estimate" if ah else False,
    }
