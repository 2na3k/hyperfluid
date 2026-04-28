import asyncio

from server import config
from server.models.errors import StreamError
from server.models.tick import Tick
from server.services.covariance import compute_covariance_matrix


class StreamManager:
    def __init__(self, rolling, broadcaster) -> None:
        self.rolling = rolling
        self.broadcaster = broadcaster
        self.sources: list = []

    def add_source(self, source) -> None:
        self.sources.append(source)

    async def start(self) -> None:
        source_tasks = [
            asyncio.create_task(s.run(self._on_tick)) for s in self.sources
        ]
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
            streams, cov, corr = compute_covariance_matrix(
                returns_map, config.MIN_SAMPLES
            )

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
                "streams": streams,
                "covariance": cov,
                "correlation": corr,
                "status": status,
            }
            await self.broadcaster.broadcast(payload)
