import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime

import websockets
from server.models.errors import StreamError
from server.models.tick import Tick


class CoinbaseSource:
    def __init__(self, product_ids: list[str]) -> None:
        self.product_ids = product_ids

    async def run(self, callback: Callable[[Tick], Awaitable[None]]) -> None:
        url = "wss://ws-feed.exchange.coinbase.com"
        while True:
            try:
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
                        if data.get("type") == "error":
                            raise StreamError(
                                f"coinbase:{self.product_ids}",
                                data.get("reason", "subscription error"),
                            )
                        if data.get("type") == "ticker":
                            ts_str = data.get("time", "")
                            ts = 0
                            if ts_str:
                                try:
                                    dt = datetime.fromisoformat(
                                        ts_str.replace("Z", "+00:00")
                                    )
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
            except StreamError:
                raise
            except Exception:
                await asyncio.sleep(5)
