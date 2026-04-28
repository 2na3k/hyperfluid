# hyperfluid

Real-time price covariance/correlation dashboard. Ingests trade data from crypto exchanges and computes rolling covariance and correlation matrices, served via a minimal vanilla JS frontend.

## setup

```bash
make install   # pip install dependencies
```

## usage

```bash
make run       # defaults: coinbase, BTC-USD + ETH-USD
```

Or specify source and symbols:

```bash
make dev       # binance, BTCUSDT+ETHUSDT, fast window for iteration
```

Open [http://localhost:3000](http://localhost:3000).

## run parameters

All parameters are set via environment variables (with defaults):

| Variable                    | Default            | Description                              |
|-----------------------------|--------------------|------------------------------------------|
| `HYPERFLUID_SOURCE_TYPE`    | `coinbase`         | Exchange source (`binance`, `hyperliquid`, `coinbase`) |
| `HYPERFLUID_SYMBOLS`        | `BTC-USDC,ETH-USDC`| Comma-separated symbol list              |
| `HYPERFLUID_WINDOW_SIZE`    | `300`              | Rolling return window per stream         |
| `HYPERFLUID_MIN_SAMPLES`    | `30`               | Minimum samples before matrix is computed |
| `HYPERFLUID_BROADCAST_INTERVAL` | `1.0`          | Seconds between matrix broadcasts        |

```bash
# example: fast iteration on binance with tiny window
HYPERFLUID_SOURCE_TYPE=binance \
HYPERFLUID_SYMBOLS="BTCUSDT,ETHUSDT" \
HYPERFLUID_WINDOW_SIZE=60 \
HYPERFLUID_MIN_SAMPLES=5 \
HYPERFLUID_BROADCAST_INTERVAL=0.25 \
make run
```

## symbol format by exchange

| Source        | Symbol format     | Example                          |
|---------------|-------------------|----------------------------------|
| `coinbase`    | `BASE-QUOTE`      | `BTC-USD`, `ETH-USD`             |
| `binance`     | `BASEQUOTE`       | `BTCUSDT`, `ETHUSDT`             |
| `hyperliquid` | `COIN`            | `BTC`, `ETH`                     |

Using an invalid symbol prints nothing — the status panel shows `no data` for that stream.

## architecture

```
Exchange WS  →  Python source adapter  →  Rolling returns  →  Covariance/correlation  →  WebSocket  →  Vanilla JS dashboard
```

Three exchange sources exist: `binance`, `hyperliquid`, `coinbase`. Run with one at a time via `--source-type`.

Computed every 1s using a rolling window of 300 log returns (configurable in `src/server/config.py`). Matrices filtered client-side by toggling ticker pills.
