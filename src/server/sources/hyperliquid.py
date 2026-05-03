import json
import logging
from collections.abc import Awaitable, Callable

import websockets
from server.models.tick import Tick
from server.sources._retry import run_with_retry

logger = logging.getLogger(__name__)


class HyperliquidSource:
    def __init__(self, coins: list[str]) -> None:
        self.coins = coins

    async def run(self, callback: Callable[[Tick], Awaitable[None]]) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        logger.info("Starting Hyperliquid source: %s", url)
        await run_with_retry(lambda: self._connect(callback, url))

    async def _connect(self, callback, url) -> None:
        async with websockets.connect(url) as ws:
            for coin in self.coins:
                await ws.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "subscription": {
                                "type": "trades",
                                "coin": coin,
                            },
                        }
                    )
                )

            async for msg in ws:
                data = json.loads(msg)
                if data.get("channel") == "subscriptionResponse":
                    continue
                if data.get("channel") == "trades":
                    trades = data.get("data", [])
                    if trades:
                        t = trades[-1]
                        await callback(
                            Tick(
                                source="hyperliquid",
                                symbol=t["coin"],
                                stream_id=f"hyperliquid:{t['coin']}",
                                price=float(t["px"]),
                                timestamp_ms=int(t.get("time", 0)),
                            )
                        )
