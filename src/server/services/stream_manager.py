import asyncio
from collections import deque

from server import config
from server.models.errors import StreamError
from server.models.tick import Tick
from server.services.cov.interface import CovarianceResult
from server.services.timing import measure_ms


class StreamManager:
    def __init__(self, rolling, broadcaster, covariance_calculator) -> None:
        self.rolling = rolling
        self.broadcaster = broadcaster
        self.covariance_calculator = covariance_calculator
        self.sources: list = []
        self.matrix_timings_ms: deque[float] = deque(maxlen=500)

    def add_source(self, source) -> None:
        self.sources.append(source)

    def set_covariance_calculator(self, covariance_calculator) -> None:
        self.covariance_calculator = covariance_calculator

    async def start(self) -> None:
        source_tasks = [asyncio.create_task(s.run(self._on_tick)) for s in self.sources]
        broadcast_task = asyncio.create_task(self._broadcast_loop())

        done, pending = await asyncio.wait(
            source_tasks + [broadcast_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            exc = task.exception()
            if isinstance(exc, StreamError):
                print(f"\n*** {exc} ***\n", flush=True)

        for task in pending:
            task.cancel()

    async def _on_tick(self, tick: Tick) -> None:
        self.rolling.update(tick.stream_id, tick.price)

    async def _broadcast_loop(self) -> None:
        while True:
            await asyncio.sleep(config.BROADCAST_INTERVAL_SECONDS)
            returns_map = self.rolling.get_all_returns()
            with measure_ms() as matrix_timer:
                try:
                    result = self.covariance_calculator.compute(
                        returns_map, config.MIN_SAMPLES
                    )
                except NotImplementedError:
                    from server.services.cov import get_covariance_calculator

                    fallback = get_covariance_calculator("baseline")
                    result = fallback.compute(returns_map, config.MIN_SAMPLES)
                except Exception:
                    result = CovarianceResult([], [], [])
            self.matrix_timings_ms.append(matrix_timer.elapsed_ms)
            matrix_p50_ms = self._percentile(self.matrix_timings_ms, 50)
            matrix_p90_ms = self._percentile(self.matrix_timings_ms, 90)
            matrix_p95_ms = self._percentile(self.matrix_timings_ms, 95)

            status: dict[str, dict] = {}
            for sid in config.STREAM_IDS:
                samples = self.rolling.get_samples(sid)
                status[sid] = {
                    "connected": samples > 0,
                    "lastPrice": self.rolling.prices.get(sid),
                    "samples": samples,
                }

            payload = {
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
                "streams": result.streams,
                "covariance": result.covariance,
                "correlation": result.correlation,
                "status": status,
                "metrics": {
                    "matrixGenerationMs": round(matrix_timer.elapsed_ms, 4),
                    "matrixGenerationP50Ms": round(matrix_p50_ms, 4),
                    "matrixGenerationP90Ms": round(matrix_p90_ms, 4),
                    "matrixGenerationP95Ms": round(matrix_p95_ms, 4),
                },
            }
            await self.broadcaster.broadcast(payload)

    @staticmethod
    def _percentile(values: deque[float], percentile: int) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        idx = round((len(sorted_values) - 1) * percentile / 100)
        return sorted_values[idx]
