from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter_ns


class Timer:
    def __init__(self) -> None:
        self.elapsed_ms: float = 0.0


@contextmanager
def measure_ms() -> Iterator[Timer]:
    timer = Timer()
    started_at = perf_counter_ns()
    try:
        yield timer
    finally:
        timer.elapsed_ms = (perf_counter_ns() - started_at) / 1_000_000
