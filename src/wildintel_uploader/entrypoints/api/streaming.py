"""What the entry points that answer as they go share: NDJSON — a JSON object a line — from work run in a thread, its progress told at most a few
times a second (and always the last of each step), or from the events of an iterator; what fails mid-way is an event of type "error"."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator

from fastapi.responses import StreamingResponse

from wildintel_uploader.core.logging_setup import debugging

logger = logging.getLogger(__name__)
# what is told while the work runs; any other event ends it
_ON_THE_WAY = ("progress", "check")


def from_work(work: Callable[[Callable[[dict], None]], dict], failure: str) -> StreamingResponse:
    """Runs work(tell) in a thread: what it tells goes out as it comes, and what it returns as {"type": "done", "result"}."""
    events: queue.Queue = queue.Queue()

    def run() -> None:
        try:
            events.put({"type": "done", "result": work(events.put)})
        except Exception as exc:  # noqa: BLE001 — told to the page, which is waiting for the end
            logger.warning("%s: %s", failure, exc, exc_info=debugging())
            events.put({"type": "error", "detail": str(exc)})

    def lines() -> Iterator[str]:
        threading.Thread(target=run, daemon=True).start()
        while True:
            event = events.get()
            yield json.dumps(event) + "\n"
            if event["type"] not in _ON_THE_WAY:
                return

    return StreamingResponse(lines(), media_type="application/x-ndjson")


def throttled(tell: Callable[[dict], None], every: float = 0.25) -> Callable[[str, int, int], None]:
    """progress(step, done, total), told as {"type": "progress"} at most every `every` seconds — and always when a step starts or ends."""
    last = {"step": None, "at": 0.0}

    def progress(step: str, done: int, total: int) -> None:
        now = time.monotonic()
        if step != last["step"] or done >= total or now - last["at"] >= every:
            last["step"], last["at"] = step, now
            tell({"type": "progress", "step": step, "done": done, "total": total})
    return progress


def checks_told(tell: Callable[[dict], None]) -> Callable[[str, str], None]:
    """on_check(check, state), told as {"type": "check"}."""
    return lambda check, state: tell({"type": "check", "check": check, "state": state})


def from_events(events: Iterator[dict], failure: str, detail: Callable[[Exception], str] = str) -> StreamingResponse:
    """The events of an iterator, a line each; one that fails ends with {"type": "error", "detail"}."""
    def lines() -> Iterator[str]:
        try:
            for event in events:
                yield json.dumps(event) + "\n"
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: %s", failure, exc, exc_info=debugging())
            yield json.dumps({"type": "error", "detail": detail(exc)}) + "\n"
    return StreamingResponse(lines(), media_type="application/x-ndjson")
