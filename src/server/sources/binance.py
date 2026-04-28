import asyncio
import json
from collections.abc import Awaitable, Callable

import websockets
from server.models.errors import StreamError
from server.models.tick import Tick


class BinanceSource:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = symbols

    async def run(self, callback: Callable[[Tick], Awaitable[None]]) -> None:
        streams = "/".join(f"{s.lower()}@trade" for s in self.symbols)
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        while True:
            try:
                async with websockets.connect(url) as ws:
                    async for msg in ws:
                        data = json.loads(msg)
                        if "error" in data:
                            raise StreamError(
                                f"binance:{self.symbols}",
                                data["error"].get("msg", "unknown error"),
                            )
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
            except StreamError:
                raise
            except Exception:
                await asyncio.sleep(5)
