# hyperfluid — Agent Guide

## Build / Run / Test

```bash
make install          # install deps (uv sync)
make install-torch    # + torch optional dep
make run              # coinbase, BTC-USD+ETH-USD+SOL-USD on port 3000
make run-binance      # binance, BTCUSDT+ETHUSDT+...
make run-hyperliquid  # hyperliquid, BTC+ETH+SOL+...
make run-hyperliquid-torch  # same with torch backend
```

Tests use `unittest` (not pytest), runnable as:

```bash
uv run python -m unittest discover tests
# or
uv run python tests/test_fft_lag_covariance.py
```

Linted with `ruff`, formatted with `ruff format`. Pre-commit hooks enforce both.

## Project Structure

```
src/server/
├── api/v1/main.py          # FastAPI app, WS endpoint, static files
├── config.py               # env-var configuration (module-level constants)
├── models/
│   ├── tick.py             # Tick dataclass
│   └── errors.py           # StreamError exception
├── services/
│   ├── broadcaster.py      # WebSocket client fan-out
│   ├── rolling_returns.py  # per-stream deque of log returns
│   ├── stream_manager.py   # orchestrator: sources → returns → cov → broadcast
│   ├── timing.py           # perf_counter_ns context timer
│   └── cov/
│       ├── interface.py    # CovarianceResult dataclass + CovarianceCalculator Protocol
│       ├── common.py       # select_stream_window, prepare_returns
│       ├── registry.py     # backend discovery + factory
│       ├── baseline.py     # NumPy backend
│       ├── mlx.py          # Apple MLX backend
│       ├── torch.py        # PyTorch MPS backend
│       ├── tilelang.py     # TileLang GPU kernel backend
│       └── fft_lag.py      # FFT-based lag-feature backend
└── sources/
    ├── binance.py
    ├── coinbase.py
    └── hyperliquid.py
tests/test_fft_lag_covariance.py   # only test file (6 test methods)
ui/
├── app.js, index.html, styles.css  # vanilla JS frontend
scripts/
├── benchmark_corr.py
└── benchmark_fft_lag.py
```

## Key Architecture

- **Entry point**: `run.py` (CLI wrapper) or `make run` → `uvicorn server.api.v1.main:app`
- **Data flow**: Exchange WS → Source adapter → `StreamManager` → `RollingReturns` (log returns) → `CovarianceCalculator.compute()` → `Broadcaster.broadcast()` → WebSocket clients
- **Backend plugin**: `CovarianceCalculator` Protocol in `interface.py`, backends registered in `registry.py`. Add a new backend by (1) implementing the Protocol, (2) adding it in `registry.py::_detect_backends`.
- **State**: Global singletons in `main.py` (`broadcaster`, `rolling`, `cov_calculator`, `manager`) — avoid adding more.

## Conventions

- **Python ≥3.12** — use `list[str]`, `deque[float]`, `float | None` syntax freely
- **FastAPI** + **uvicorn** — async endpoints, `@asynccontextmanager` lifespan
- **unittest** (not pytest) for tests
- **NumPy** for array ops — preferred over raw Python loops
- **WebSocket** message protocol: client sends `{"action": "set_backend", "backend": "mlx"}`, server pushes `{"type": "matrix", "stream_ids": [...], "covariance": [...], "correlation": [...], "timing_ms": {...}, "status": {...}}`
- **`snake_case`** for functions/variables, **`PascalCase`** for classes
- **Environment variables** use `HYPERFLUID_*` prefix, defaults in `config.py`
- **Source adapters** accept a `callback(stream_id, price, timestamp_ms)` callable

## Known Code Smells (fix these first)

1. Module-level global state in `main.py` — hard to test
2. Identical `while True: try/except Exception: sleep 5` retry loop copy-pasted in all 3 source adapters
3. Duplicated correlation formula (`cov → std → divide with where=denom>0`) across 5+ files
4. `broadcaster.py` sends to clients sequentially (should use `asyncio.gather`)
5. No logging anywhere — use `import logging`
6. MLX/Torch correlation can produce NaN for zero-variance streams (`0 * inf`)
7. TileLang variance formula (`E[X²] − E[X]²`) is numerically unstable
8. Dead code: `except StreamError: raise` in binance.py/coinbase.py, `ConnectionClosed` in hyperliquid.py

## Covariance Backends

| Backend    | Dependency | Notes |
|------------|-----------|-------|
| `baseline` | numpy     | Always available, reference impl |
| `mlx`      | mlx       | Apple Silicon only |
| `torch`    | torch     | MPS-only (hardcoded), optional |
| `tilelang` | tilelang+torch | GPU kernel, JIT compiles per shape, optional |
| `fft_lag`  | numpy     | FFT circular cross-correlation, always available |

## Edge Cases

- Zero-variance streams → correlation must set diagonal to 1.0, off-diagonal to 0.0 (no NaN)
- `min_len < 2` → return empty (`CovarianceResult([], [], [])`)
- `window_size < lag_count` (FFT lag) → return empty
- Malformed WS messages from exchange → must not crash the source loop
- Source task failure → currently kills all sources via `asyncio.wait(FIRST_COMPLETED)`

## Workflow

### Branching

- **`main`** — production-ready, protected. No direct commits.
- All work goes through feature branches forked from `main`:

  ```bash
  git checkout main && git pull
  git checkout -b feature/<name>
  # or fix/<name>, chore/<name>, bench/<name>
  ```

- Keep branches short-lived. Open a PR into `main` when ready.

### PR Description Format

```markdown
## Summary

<one or two sentences describing what this PR does>

## Changes

- <bullet point per meaningful change>
- <include file paths if relevant>

## Testing

- [ ] tests pass
- [ ] lint passes (`ruff check`)
- [ ] formatting passes (`ruff format --check`)
```

### CI

GitHub Actions runs on push to `main` and every PR:

| Step | Command |
|------|---------|
| Install | `uv sync --all-extras` |
| Lint | `ruff check src/ tests/ scripts/` |
| Format check | `ruff format --check src/ tests/ scripts/` |
| Test | `uv run python -m unittest discover tests` |

### Pre-commit

Hooks run automatically on `git commit`:

```bash
uv sync --extra dev     # one-time install of ruff + pre-commit
pre-commit install      # activate hooks
```

Includes: `ruff check --fix`, `ruff format`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`.

### Branch Protection (GitHub)

`main` requires:

- [ ] PR review before merge
- [ ] CI checks passing (lint, format, tests)
- [ ] No direct pushes
