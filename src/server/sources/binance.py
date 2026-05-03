import json
import logging
from collections.abc import Awaitable, Callable

import websockets
from server.models.tick import Tick
from server.sources._retry import run_with_retry

logger = logging.getLogger(__name__)


class BinanceSource:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = symbols

    async def run(self, callback: Callable[[Tick], Awaitable[None]]) -> None:
        streams = "/".join(f"{s.lower()}@trade" for s in self.symbols)
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        logger.info("Starting Binance source: %s", url)
        await run_with_retry(lambda: self._connect(callback, url))

    async def _connect(self, callback, url) -> None:
        async with websockets.connect(url) as ws:
            async for msg in ws:
                data = json.loads(msg)
                d = data.get("data", data)
                await callback(
                    Tick(
                        source="binance",
                        symbol=d["s"],
                        stream_id=f"binance:{d['s']}",
                        price=float(d["p"]),
                        timestamp_ms=int(d.get("E", 0)),
                    )
                )
