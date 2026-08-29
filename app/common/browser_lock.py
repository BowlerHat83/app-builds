import asyncio
import os

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

# Extra launch flags every one of the 4 sites above should use on top of
# their own args, to keep each individual Chromium instance's own memory
# footprint as small as possible - CHROMIUM_SLOT above only ever allows one
# instance running at a time, it doesn't shrink how much any single one
# uses, and a single instance was already measured at 300-500MB against a
# 512MB total ceiling (see comment above). None of these change what a
# check can see or measure - they just turn off Chromium subsystems a
# headless, single-purpose scrape/screenshot has no use for, each of which
# normally runs its own background process or thread with its own memory.
# The two biggest wins are GPU compositing (there's no display in this
# container at all) and the zygote process Chromium normally pre-forks
# renderer processes from (every launch here only ever needs one renderer,
# so the zygote's standing overhead buys nothing).
LOW_MEMORY_CHROMIUM_ARGS = [
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--no-zygote",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-first-run",
    "--safebrowsing-disable-auto-update",
]

# A second, coarser cap on top of CHROMIUM_SLOT above. CHROMIUM_SLOT only
# ever allows one *browser* running at once - it says nothing about the
# other 5-6 topics' own Python-side work (pandas parsing CSV exports,
# holding API responses in memory) happening at the very same moment,
# which can pile onto the heap right alongside a 300-500MB Chromium
# instance and tip the whole process over 512MB just as easily. The
# job/polling flow (app/common/audit_jobs.py) no longer needs every topic
# racing to finish at once for the UI to feel responsive - it already
# fills in topic by topic as each one lands - so trading some of that
# parallelism for headroom is a clean win on this plan, not a real loss.
#
# Tunable via TOPIC_CONCURRENCY so it can be raised without a code change
# if this ever moves to a plan with more than 512MB - defaults to 2 (some
# overlap for I/O-bound waiting like API calls, without letting every
# CSV-parsing topic pile up in memory at the same instant).
TOPIC_SLOT = asyncio.Semaphore(max(1, int(os.environ.get("TOPIC_CONCURRENCY", "2"))))
