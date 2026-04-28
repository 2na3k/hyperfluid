from __future__ import annotations

import math
from collections import deque


class RollingReturns:
    def __init__(self, window_size: int = 300) -> None:
        self.window_size = window_size
        self.prices: dict[str, float] = {}
        self._returns: dict[str, deque[float]] = {}

    def update(self, stream_id: str, price: float) -> float | None:
        if stream_id not in self.prices:
            self.prices[stream_id] = price
            return None
        prev = self.prices[stream_id]
        if prev == 0:
            self.prices[stream_id] = price
            return None
        log_return = math.log(price / prev)
        self.prices[stream_id] = price
        if stream_id not in self._returns:
            self._returns[stream_id] = deque[float](maxlen=self.window_size)
        self._returns[stream_id].append(log_return)
        return log_return

    def get_samples(self, stream_id: str) -> int:
        return len(self._returns.get(stream_id, []))

    def get_all_returns(self) -> dict[str, list[float]]:
        return {sid: list(r) for sid, r in self._returns.items()}
