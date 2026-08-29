"""
Lightweight, dependency-free memory visibility for a resource-constrained
free-tier deployment (see app/common/browser_lock.py for the 512MB ceiling
this is all in service of). No extra package (no psutil) - just the
standard library's resource module, which is already always available.
"""

import resource


def log_memory(label: str) -> None:
    """
    Logs the process's peak resident memory (RSS) so far to stdout, which
    Render's log viewer captures like any other console output.

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

    On Linux, ru_maxrss is reported in kilobytes.
    """
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"[mem] {label}: peak RSS so far = {peak_mb:.0f}MB", flush=True)
