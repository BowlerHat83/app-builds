import asyncio

# Free-tier hosting caps the whole backend process at roughly 512MB RAM. A
# single headless Chromium instance can use 300-500MB on its own, so any two
# of the checks below launching a browser at the same moment can push the
# process past that ceiling and get it killed outright by the OS's OOM
# killer - which surfaces to the frontend as a bare "Failed to fetch" with
# nothing in the server logs, since the process died mid-request before it
# could send any response back.
#
# This semaphore makes sure only one Chromium-based check is ever running at
# a time across the whole audit, no matter which topics or checks happen to
# overlap. Every other check (CSV parsing, API calls, non-browser scraping)
# is completely unaffected and keeps running fully in parallel - this only
# throttles the checks that actually launch a browser:
#   - Topic 1: GDPR cookie-banner audit      (gdpr_service.py)
#   - Topic 1: WCAG accessibility audit      (wcag_service.py)
#   - Topic 6: Google Business Profile shot  (screenshot_service.py)
#   - Topic 7: form detection / screenshots  (form_detection_service.py)
CHROMIUM_SLOT = asyncio.Semaphore(1)
