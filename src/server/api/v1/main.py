import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server import config
from server.services.broadcaster import Broadcaster
from server.services.rolling_returns import RollingReturns
from server.services.cov import get_covariance_calculator, list_backends, validate_backend
from server.services.stream_manager import StreamManager
from server.sources.binance import BinanceSource
from server.sources.coinbase import CoinbaseSource
from server.sources.hyperliquid import HyperliquidSource

broadcaster = Broadcaster()
rolling = RollingReturns(window_size=config.WINDOW_SIZE)
cov_calculator = get_covariance_calculator(config.COV_BACKEND)
manager = StreamManager(rolling, broadcaster, cov_calculator)


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

    backends = list_backends()
    await ws.send_text(json.dumps({
        "type": "config",
        "backends": backends,
        "current_backend": manager.covariance_calculator.name,
    }))

    try:
        while True:
            text = await ws.receive_text()
            data = json.loads(text)
            if data.get("action") == "set_backend":
                backend = data.get("backend", "")
                ok, msg = validate_backend(backend)
                if ok:
                    manager.set_covariance_calculator(backend)
                    await ws.send_text(
                        json.dumps({"type": "backend_switched", "backend": backend})
                    )
                else:
                    await ws.send_text(
                        json.dumps({"type": "backend_error", "backend": backend, "message": msg})
                    )
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
