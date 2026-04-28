.PHONY: install run

install:
	uv sync

run:
	PYTHONPATH=src HYPERFLUID_SOURCE_TYPE=coinbase HYPERFLUID_SYMBOLS="BTC-USD,ETH-USD" \
		uv run uvicorn server.api.v1.main:app --reload --port 3000
