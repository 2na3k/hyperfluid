import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

import websockets
from server.models.tick import Tick
from server.sources._retry import run_with_retry

logger = logging.getLogger(__name__)


class CoinbaseSource:
    def __init__(self, product_ids: list[str]) -> None:
        self.product_ids = product_ids

    async def run(self, callback: Callable[[Tick], Awaitable[None]]) -> None:
        url = "wss://ws-feed.exchange.coinbase.com"
        logger.info("Starting Coinbase source: %s", url)
        await run_with_retry(lambda: self._connect(callback, url))

    async def _connect(self, callback, url) -> None:
        async with websockets.connect(url) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "subscribe",
                        "product_ids": self.product_ids,
                        "channels": ["ticker"],
                    }
                )
            )
            async for msg in ws:
                data = json.loads(msg)
                if data.get("type") == "ticker":
                    ts_str = data.get("time", "")
                    ts = 0
                    if ts_str:
                        try:
                            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            ts = int(dt.timestamp() * 1000)
                        except ValueError:
                            ts = 0
                    await callback(
                        Tick(
                            source="coinbase",
                            symbol=data["product_id"],
                            stream_id=f"coinbase:{data['product_id']}",
                            price=float(data["price"]),
                            timestamp_ms=ts,
                        )
                    )
