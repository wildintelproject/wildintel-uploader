"""Doing the same thing to many images at once. The work is Pillow decoding and hashing, which let go of
Python's lock while they run, so threads use as many CPUs as there are workers — and, unlike processes,
they cost nothing to start and work the same in the packaged app."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from wildintel_uploader.core import config

T = TypeVar("T")
R = TypeVar("R")


def pmap(function: Callable[[T], R], items: Iterable[T], workers: int | None = None) -> list[R]:
    """`function` applied to each item — `workers` at a time, GENERAL.workers by default — with the results in
    the order of the items, so what is reported never depends on which finished first."""
    items = list(items)
    workers = config.workers() if workers is None else workers
    if workers <= 1 or len(items) <= 1:
        return [function(item) for item in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(function, items))
