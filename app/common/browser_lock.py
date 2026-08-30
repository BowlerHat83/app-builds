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
    # Site Isolation spins up a separate OS renderer process per origin a
    # page touches (iframes, cross-origin subresources) as a security
    # boundary against one site reading another's memory - a real concern
    # for a general-purpose browser with untrusted tabs open side by side,
    # not for a single-purpose headless scrape/screenshot with nothing else
    # sharing the process. Google Maps in particular (Topic 6's screenshot
    # target) pulls in enough distinct origins that this can multiply its
    # renderer-process count, and therefore memory, well beyond what a
    # single-page capture needs. Disabling it merges everything back into
    # one renderer process per check.
    #
    # Translate and BackForwardCache are bundled into this SAME
    # --disable-features flag rather than a second one - Chromium doesn't
    # merge two separate --disable-features switches, the later one wins
    # outright, so a second entry would have silently undone the Site
    # Isolation disabling above instead of adding to it. BackForwardCache
    # in particular keeps a full in-memory snapshot of a previous page
    # alive so a back-navigation can restore it instantly - pure overhead
    # here, since nothing in this app ever navigates backward.
    "--disable-features=IsolateOrigins,site-per-process,Translate,BackForwardCache",
    # A live WCAG run showed live container memory jump from 144MB to
    # 439MB from page.goto() ALONE - before axe.min.js was even injected,
    # with image/media/font already blocked (see wcag_service.py). That
    # rules out media payload as the (sole) cause: it's the page's own
    # JS/CSS/DOM weight. --max-old-space-size caps V8's own heap so it
    # garbage-collects sooner and smaller instead of growing to whatever
    # the container happens to report as available; --disk-cache-size=0
    # and --renderer-process-limit=1 are cheap, safe insurance on top -
    # a real page's own execution cost is the one thing left that none of
    # the resource-blocking/rule-scoping changes so far have touched.
    "--js-flags=--max-old-space-size=192",
    "--disk-cache-size=0",
    "--renderer-process-limit=1",
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
# if this ever moves to a plan with more than 512MB - defaults to 1. This
# was 2 (some overlap for I/O-bound waiting like API calls) until a live
# run on Render crashed the process outright the first time a Chromium-
# heavy topic (1/6/7) came up: [mem] logging showed the Python side at a
# safe ~146MB right before the crash-restart, meaning whatever pushed the
# container over its 512MB ceiling wasn't tracked by that logging at all -
# almost certainly a Chromium child process (see diagnostics.py, which now
# also logs RUSAGE_CHILDREN to confirm this on the next run). Serializing
# topics fully removes any chance of a second topic's CSV/API work adding
# to the heap at the exact moment a ~300-500MB Chromium instance is also
# live, trading some wall-clock time for not crashing outright - a clean
# win on a plan this tight on memory, and the audit already fills in
# results topic by topic rather than waiting on all 7 before showing
# anything.
TOPIC_SLOT = asyncio.Semaphore(max(1, int(os.environ.get("TOPIC_CONCURRENCY", "1"))))
