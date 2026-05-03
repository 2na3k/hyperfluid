import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server import config
from server.services.broadcaster import Broadcaster
from server.services.rolling_returns import RollingReturns
from server.services.cov import get_covariance_calculator, list_backends
from server.services.stream_manager import StreamManager
from server.sources.binance import BinanceSource
from server.sources.coinbase import CoinbaseSource
from server.sources.hyperliquid import HyperliquidSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    broadcaster = Broadcaster()
    rolling = RollingReturns(window_size=config.WINDOW_SIZE)
    cov_calculator = get_covariance_calculator(
        config.COV_BACKEND,
        stream_ids=config.STREAM_IDS,
        window_size=config.WINDOW_SIZE,
        lag_count=config.FFT_LAG_COUNT,
    )
    manager = StreamManager(rolling, broadcaster, cov_calculator)

    app.state.broadcaster = broadcaster
    app.state.manager = manager

    source_type = config.SOURCE_TYPE
    symbols = config.SYMBOLS

    if source_type == "binance":
        manager.add_source(BinanceSource(symbols))
    elif source_type == "hyperliquid":
        manager.add_source(HyperliquidSource(symbols))
    elif source_type == "coinbase":
        manager.add_source(CoinbaseSource(symbols))

    logger.info(
        "Starting hyperfluid: source=%s symbols=%s backend=%s",
        source_type,
        symbols,
        config.COV_BACKEND,
    )
    task = asyncio.create_task(manager.start())
    yield
    task.cancel()


app = FastAPI(title="hyperfluid", lifespan=lifespan)


@app.websocket("/ws/matrix")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    broadcaster: Broadcaster = app.state.broadcaster
    manager: StreamManager = app.state.manager

    broadcaster.add(ws)

    backends = list_backends(
        config.STREAM_IDS,
        config.WINDOW_SIZE,
        config.FFT_LAG_COUNT,
    )
    await ws.send_text(
        json.dumps(
            {
                "type": "config",
                "backends": backends,
                "current_backend": manager.covariance_calculator.name,
            }
        )
    )

    try:
        while True:
            text = await ws.receive_text()
            data = json.loads(text)
            if data.get("action") == "set_backend":
                backend = data.get("backend", "")
                try:
                    calculator = get_covariance_calculator(
                        backend,
                        stream_ids=config.STREAM_IDS,
                        window_size=config.WINDOW_SIZE,
                        lag_count=config.FFT_LAG_COUNT,
                    )
                    manager.set_covariance_calculator(calculator)
                    await ws.send_text(
                        json.dumps({"type": "backend_switched", "backend": backend})
                    )
                except Exception as e:
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "backend_error",
                                "backend": backend,
                                "message": str(e),
                            }
                        )
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
