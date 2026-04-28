import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server import config
from server.services.broadcaster import Broadcaster
from server.services.rolling_returns import RollingReturns
from server.services.stream_manager import StreamManager
from server.sources.binance import BinanceSource
from server.sources.coinbase import CoinbaseSource
from server.sources.hyperliquid import HyperliquidSource

broadcaster = Broadcaster()
rolling = RollingReturns(window_size=config.WINDOW_SIZE)
manager = StreamManager(rolling, broadcaster)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    source_type = config.SOURCE_TYPE
    symbols = config.SYMBOLS

    if source_type == "binance":
        manager.add_source(BinanceSource(symbols))
    elif source_type == "hyperliquid":
        manager.add_source(HyperliquidSource(symbols))
    elif source_type == "coinbase":
        manager.add_source(CoinbaseSource(symbols))

    task = asyncio.create_task(manager.start())
    yield
    task.cancel()


app = FastAPI(title="hyperfluid", lifespan=lifespan)


@app.websocket("/ws/matrix")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    broadcaster.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        broadcaster.remove(ws)


ui_path: Path = Path(__file__).resolve().parents[4] / "ui"
cache_headers: dict[str, str] = {"Cache-Control": "no-cache"}


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(ui_path / "index.html", headers=cache_headers)


@app.get("/app.js")
async def serve_js() -> FileResponse:
    return FileResponse(ui_path / "app.js", headers=cache_headers)


@app.get("/styles.css")
async def serve_css() -> FileResponse:
    return FileResponse(ui_path / "styles.css", headers=cache_headers)
