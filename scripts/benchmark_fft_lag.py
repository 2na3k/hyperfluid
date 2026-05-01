from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from server.services.cov.fft_lag import FftLagCovariance


def parse_shape(value: str) -> tuple[int, int, int]:
    parts = value.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("shape must be streams,samples,lags")

    streams, samples, lags = (int(part) for part in parts)
    if streams < 2 or samples < 2 or lags < 1:
        raise argparse.ArgumentTypeError("streams>=2, samples>=2, and lags>=1 required")
    if samples < lags:
        raise argparse.ArgumentTypeError("samples must be >= lags")
    return streams, samples, lags


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark brute-force vs FFT circular lag covariance."
    )
    parser.add_argument(
        "--shape",
        action="append",
        type=parse_shape,
        metavar="STREAMS,SAMPLES,LAGS",
        help="Benchmark shape. Can be repeated.",
    )
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare FFT covariance against brute force before timing each shape.",
    )
    return parser.parse_args()


def brute_circular_lag_covariance(values: np.ndarray, lag_count: int) -> np.ndarray:
    centered = values - values.mean(axis=1, keepdims=True)
    rows, cols = centered.shape
    features = np.empty((rows * lag_count, cols), dtype=np.float64)

    out_row = 0
    for row in range(rows):
        for lag in range(lag_count):
            features[out_row] = np.roll(centered[row], -lag)
            out_row += 1

    return features @ features.T / (cols - 1)


def bench(label: str, warmup: int, repeat: int, run: Callable[[], np.ndarray]) -> None:
    for _ in range(warmup):
        result = run()
        float(result[0, 0])

    timings = []
    for _ in range(repeat):
        start = time.perf_counter()
        result = run()
        float(result[0, 0])
        timings.append(time.perf_counter() - start)

    p50, p90, p95 = np.percentile(timings, [50, 90, 95])
    print(
        f"{label}: min={min(timings):.4f}s "
        f"avg={sum(timings) / len(timings):.4f}s "
        f"p50={p50:.4f}s "
        f"p90={p90:.4f}s "
        f"p95={p95:.4f}s "
        f"runs={[round(t, 4) for t in timings]}"
    )


def main() -> None:
    args = parse_args()
    shapes = args.shape or [(5, 500, 16), (20, 2000, 32)]
    rng = np.random.default_rng(0)

    for streams, samples, lags in shapes:
        print(f"shape: streams={streams:,}, samples={samples:,}, lags={lags:,}")
        feature_count = streams * lags
        print(f"features: {feature_count:,}")

        values = rng.standard_normal((streams, samples), dtype=np.float64)
        backend = FftLagCovariance(
            [f"stream-{idx}" for idx in range(streams)],
            samples,
            lag_count=lags,
        )

        def run_brute() -> np.ndarray:
            return brute_circular_lag_covariance(values, lags)

        def run_fft() -> np.ndarray:
            covariance, _ = backend.compute_arrays(values)
            return covariance

        if args.check:
            cov_brute = run_brute()
            cov_fft = run_fft()
            print(f"check max_abs={np.max(np.abs(cov_fft - cov_brute)):.6g}")

        bench("brute", args.warmup, args.repeat, run_brute)
        bench("fft", args.warmup, args.repeat, run_fft)
        print()


if __name__ == "__main__":
    main()
