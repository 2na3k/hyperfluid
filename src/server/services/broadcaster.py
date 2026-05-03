import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class Broadcaster:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self.clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        if not self.clients:
            return
        msg = json.dumps(payload, default=str)

        async def _send(ws: WebSocket) -> None:
            try:
                await ws.send_text(msg)
            except Exception:
                logger.debug("Removing dead WebSocket client")
                self.clients.discard(ws)

        await asyncio.gather(*[_send(ws) for ws in list(self.clients)])
