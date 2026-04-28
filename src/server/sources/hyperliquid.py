import asyncio
import json
from collections.abc import Awaitable, Callable

import websockets
from server.models.tick import Tick


class HyperliquidSource:
    def __init__(self, coins: list[str]) -> None:
        self.coins = coins

    async def run(self, callback: Callable[[Tick], Awaitable[None]]) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        while True:
            try:
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
            except websockets.ConnectionClosed:
                await asyncio.sleep(5)
            except Exception:
                await asyncio.sleep(5)
