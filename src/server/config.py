import os

PORT: int = 3000
WINDOW_SIZE: int = int(os.getenv("HYPERFLUID_WINDOW_SIZE", "300"))
MIN_SAMPLES: int = int(os.getenv("HYPERFLUID_MIN_SAMPLES", "30"))
BROADCAST_INTERVAL_SECONDS: float = float(
    os.getenv("HYPERFLUID_BROADCAST_INTERVAL", "1.0")
)
COV_BACKEND: str = os.getenv("HYPERFLUID_COV_BACKEND", "baseline")
FFT_LAG_COUNT: int = int(os.getenv("HYPERFLUID_FFT_LAG_COUNT", "16"))

SOURCE_TYPE: str = os.getenv("HYPERFLUID_SOURCE_TYPE", "coinbase")
SYMBOLS_STR: str = os.getenv("HYPERFLUID_SYMBOLS", "BTC-USDC,ETH-USDC")
SYMBOLS: list[str] = [s.strip() for s in SYMBOLS_STR.split(",")]
STREAMS: list[dict[str, str]] = [{"source": SOURCE_TYPE, "symbol": s} for s in SYMBOLS]
STREAM_IDS: list[str] = [f"{SOURCE_TYPE}:{s}" for s in SYMBOLS]
