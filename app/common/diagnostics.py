"""
Lightweight, dependency-free memory visibility for a resource-constrained
free-tier deployment (see app/common/browser_lock.py for the 512MB ceiling
this is all in service of). No extra package (no psutil) - just the
standard library's resource module.

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


def log_memory(label: str) -> None:
    """
    Logs the process's peak resident memory (RSS) so far to stdout, which
    Render's log viewer captures like any other console output. A no-op
    wherever the resource module isn't available (see module docstring).

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
    instance.

    On Linux, ru_maxrss is reported in kilobytes.
    """
    if not _HAS_RESOURCE:
        return
    self_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    children_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    print(f"[mem] {label}: peak RSS so far = {self_mb:.0f}MB self + {children_mb:.0f}MB children (Chromium etc.)", flush=True)
