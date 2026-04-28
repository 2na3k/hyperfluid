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
python3 run.py --source-type coinbase --symbol-list "BTC-USD,ETH-USD"
python3 run.py --source-type binance --symbol-list "BTCUSDT,ETHUSDT"
python3 run.py --source-type hyperliquid --symbol-list "BTC,ETH"
```

Open [http://localhost:3000](http://localhost:3000).

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
