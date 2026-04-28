import os

PORT: int = 3000
WINDOW_SIZE: int = 300
MIN_SAMPLES: int = 30
BROADCAST_INTERVAL_SECONDS: float = 1.0

SOURCE_TYPE: str = os.getenv("HYPERFLUID_SOURCE_TYPE", "coinbase")
SYMBOLS_STR: str = os.getenv("HYPERFLUID_SYMBOLS", "BTC-USDC,ETH-USDC")
SYMBOLS: list[str] = [s.strip() for s in SYMBOLS_STR.split(",")]
STREAMS: list[dict[str, str]] = [{"source": SOURCE_TYPE, "symbol": s} for s in SYMBOLS]
STREAM_IDS: list[str] = [f"{SOURCE_TYPE}:{s}" for s in SYMBOLS]
