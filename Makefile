.PHONY: install run dev run-hyperliquid

install:
	uv sync

run:
	PYTHONPATH=src HYPERFLUID_SOURCE_TYPE=coinbase HYPERFLUID_SYMBOLS="BTC-USD,ETH-USD,SOL-USD" \
		uv run uvicorn server.api.v1.main:app --reload --port 3000

run-binance:
	PYTHONPATH=src \
	HYPERFLUID_SOURCE_TYPE=binance \
	HYPERFLUID_SYMBOLS="BTCUSDT,ETHUSDT,SOLUSDT,UNIUSDT,USDCUSDT" \
	HYPERFLUID_WINDOW_SIZE=500 \
	HYPERFLUID_MIN_SAMPLES=5 \
	HYPERFLUID_BROADCAST_INTERVAL=1 \
		uv run uvicorn server.api.v1.main:app --reload --port 3000

run-hyperliquid:
	PYTHONPATH=src \
	HYPERFLUID_SOURCE_TYPE=hyperliquid \
	HYPERFLUID_SYMBOLS="BTC,ETH" \
		uv run uvicorn server.api.v1.main:app --reload --port 3000
