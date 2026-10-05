"""core.parallel — the same work for many images at once, the results in order."""
import threading
import time

import pytest

from wildintel_uploader.core import parallel


def test_the_results_come_in_the_order_of_the_items_whichever_finishes_first():
    def slow_first(n: int) -> int:
        time.sleep(0.05 if n == 0 else 0)
        return n * 2

    assert parallel.pmap(slow_first, range(8), workers=4) == [n * 2 for n in range(8)]


def test_it_really_works_on_several_at_once():
    barrier = threading.Barrier(3, timeout=5)  # only passes if three run at the same time

    assert parallel.pmap(lambda n: barrier.wait() >= 0 or n, range(3), workers=3) is not None


def test_one_worker_or_one_item_runs_in_the_calling_thread():
    threads = parallel.pmap(lambda _: threading.current_thread(), range(3), workers=1)
    assert set(threads) == {threading.current_thread()}
    assert parallel.pmap(lambda _: threading.current_thread(), [1], workers=8) == [threading.current_thread()]


def test_a_failure_is_raised_to_the_caller():
    def boom(n: int) -> int:
        if n == 3:
            raise ValueError("bad image")
        return n

    with pytest.raises(ValueError, match="bad image"):
        parallel.pmap(boom, range(6), workers=3)


def test_it_takes_the_workers_from_the_settings_by_default(monkeypatch):
    seen = []
    monkeypatch.setattr(parallel.config, "workers", lambda: seen.append("asked") or 1)

    assert parallel.pmap(lambda n: n, [1, 2]) == [1, 2]
    assert seen == ["asked"]
