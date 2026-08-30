"""
Lightweight, dependency-free memory visibility for a resource-constrained
free-tier deployment (see app/common/browser_lock.py for the 512MB ceiling
this is all in service of). No extra package (no psutil) - just the
standard library's resource module plus a direct cgroup read.

resource is POSIX-only (Linux/macOS) and simply doesn't exist on Windows -
Render's production deploy runs Linux inside Docker, so this works fine
there, but importing it unconditionally crashed the whole app on startup
during local Windows development. Windows dev machines aren't
memory-constrained the same way this free-tier deploy is anyway, so
log_memory() is just a silent no-op there instead of a hard failure.
"""

try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    # Windows (or any other platform without the resource module).
    _HAS_RESOURCE = False


def _live_container_mb() -> float | None:
    """
    Real-time total memory in use by EVERYTHING in this container right
    now, read straight from the kernel's cgroup accounting - the same
    number an OOM killer acts on. This closes a specific blind spot in
    the two ru_maxrss numbers below: RUSAGE_CHILDREN only updates once a
    child process has been *reaped* (i.e. after browser.close() returns
    and the OS lets the parent collect its exit status). While a topic's
    Chromium is still running mid-crawl, it hasn't been reaped yet, so
    RUSAGE_CHILDREN is still reporting whatever a PREVIOUS, already-closed
    topic's Chromium peaked at - it cannot see the live Chromium that's
    actually running right now. This is exactly why a crash could still
    happen moments after a log line that looked fine: that line's
    "children" figure was stale by construction, not evidence memory was
    actually low at that moment.

    Reads cgroup v2 first (current Docker/Render default), falls back to
    v1. Returns None where neither path exists (local Windows/macOS dev,
    or any sandbox without /sys/fs/cgroup) - treat that as "unavailable",
    not "zero".
    """
    for path in (
        "/sys/fs/cgroup/memory.current",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes",
    ):
        try:
            with open(path) as f:
                return int(f.read().strip()) / (1024 * 1024)
        except Exception:
            continue
    return None


def log_memory(label: str) -> None:
    """
    Logs the process's peak resident memory (RSS) so far, plus a live
    whole-container reading, to stdout - which Render's log viewer
    captures like any other console output. A no-op wherever the resource
    module isn't available (see module docstring).

    Important nuance: ru_maxrss is a HIGH-WATER MARK - the largest RSS this
    process has ever reached since it started, not a live/current reading.
    It only ever goes up, even after Python's garbage collector frees
    memory a moment later. That's actually what's useful here: the question
    isn't "how much memory is in use right now" but "how close did this
    process get to the 512MB ceiling at its worst moment" - and a rising
    sequence of these log lines across a single audit run, especially
    around Chromium-heavy topics, is the concrete evidence needed to
    confirm (or rule out) memory pressure as the cause of a crash-restart,
    rather than guessing from symptoms alone.

    RUSAGE_SELF only covers this Python/uvicorn process - it does NOT
    include Playwright's Chromium, which always runs as separate child
    processes (browser + renderer, at minimum). A crash with "peak RSS"
    logs showing e.g. 146MB right before an OOM kill isn't a contradiction
    - it means the Python side was nowhere near the ceiling and whatever
    tipped the container's total memory over 512MB was in a child process
    instead, which is exactly why RUSAGE_CHILDREN is also logged below:
    it's the same high-water-mark reasoning, just for every child process
    this one has ever waited on (Chromium included), so the two numbers
    together show whether a crash was this process or a spawned Chromium
    instance. But see _live_container_mb() above - both of those numbers
    are blind to a Chromium instance that's still alive, which is the
    normal state for most of a crawl. The live container reading has no
    such gap - it's the third number to check first.

    On Linux, ru_maxrss is reported in kilobytes.
    """
    if not _HAS_RESOURCE:
        return
    self_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    children_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    live_mb = _live_container_mb()
    live_part = f", {live_mb:.0f}MB live container total right now" if live_mb is not None else ""
    print(f"[mem] {label}: peak RSS so far = {self_mb:.0f}MB self + {children_mb:.0f}MB children (Chromium etc.){live_part}", flush=True)
