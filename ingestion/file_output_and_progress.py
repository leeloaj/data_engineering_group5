"""Atomic file output and progress messages for ingestion runs."""

import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import mkstemp
from threading import Event, Thread
from time import monotonic


PROGRESS_INTERVAL = 30


@contextmanager
def atomic_output(destination):
    """Publish a file only after its writer finishes successfully."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = mkstemp(dir=destination.parent, prefix=destination.name + ".", suffix=".tmp")
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def report_stage(name, enabled=True, detail=lambda elapsed: ""):
    """Report elapsed time even while a download or database call blocks."""
    if not enabled:
        yield
        return

    started = monotonic()
    finished = Event()

    def report(status):
        elapsed = monotonic() - started
        print(f"{name}: {status} ({elapsed:,.1f}s){detail(elapsed)}", flush=True)

    def heartbeat():
        while not finished.wait(PROGRESS_INTERVAL):
            report("running")

    print(f"{name}: starting", flush=True)
    worker = Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
    finally:
        finished.set()
        worker.join()
    report("done")
