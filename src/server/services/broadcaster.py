import json

from fastapi import WebSocket


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
        dead: set[WebSocket] = set()
        for ws in self.clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        self.clients -= dead
