from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import torch

try:
    import mlx.core as mx
except ImportError:  # pragma: no cover - optional local benchmark dependency
    mx = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from server.services.cov.tilelang import TileLangCovariance
except ImportError:  # pragma: no cover - optional local benchmark dependency
    TileLangCovariance = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark NumPy/Torch/MLX/TileLang correlation calculation."
    )
    parser.add_argument("--entries", type=int, default=10_000)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "mps", "cuda"),
        default="auto",
    )
    parser.add_argument(
        "--tilelang-target",
        default="auto",
        help="TileLang target string, e.g. auto, cuda -arch=sm_90, metal, llvm.",
    )
    parser.add_argument(
        "--tilelang-backend",
        default="auto",
        help="TileLang execution backend. Leave as auto unless debugging.",
    )
    parser.add_argument("--tilelang-block-m", type=int, default=8)
    parser.add_argument("--tilelang-block-n", type=int, default=8)
    parser.add_argument("--tilelang-block-rows", type=int, default=128)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare TileLang output against NumPy before timing.",
    )
    return parser.parse_args()


def choose_device(name: str) -> torch.device:
    if name == "auto":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(name)


def sync(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize()


def numpy_cov_corr(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centered = values - values.mean(axis=1, keepdims=True)
    cov = centered @ centered.T / (values.shape[1] - 1)
    std = np.sqrt(np.diag(cov))
    denom = np.outer(std, std)
    corr = np.divide(cov, denom, out=np.zeros_like(cov), where=denom > 0)
    np.fill_diagonal(corr, 1.0)
    return cov, corr


def numpy_corr(values: np.ndarray) -> np.ndarray:
    _, corr = numpy_cov_corr(values)
    return corr


def torch_corr(values: torch.Tensor, eye: torch.Tensor, off_diag: torch.Tensor) -> torch.Tensor:
    centered = values - values.mean(dim=1, keepdim=True)
    cov = centered @ centered.T / (values.shape[1] - 1)
    std = torch.sqrt(torch.diag(cov))
    denom = torch.outer(std, std)
    corr = torch.where(denom > 0.0, cov / denom, torch.zeros_like(cov))
    return corr * off_diag + eye


def mlx_corr(values, eye, off_diag):
    centered = values - mx.mean(values, axis=1, keepdims=True)
    cov = centered @ centered.T / (values.shape[1] - 1)
    std = mx.sqrt(mx.diag(cov))
    denom = mx.outer(std, std)
    corr = mx.where(denom > 0.0, cov / denom, mx.zeros_like(cov))
    return corr * off_diag + eye


def bench(label: str, warmup: int, repeat: int, run) -> list[float]:
    for _ in range(warmup):
        run()

    timings = []
    for _ in range(repeat):
        start = time.perf_counter()
        run()
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
    return timings


def main() -> None:
    args = parse_args()
    device = choose_device(args.device)

    shape = (args.entries, args.samples)
    corr_gb = args.entries * args.entries * 4 / 1024**3
    values_gb = args.entries * args.samples * 4 / 1024**3

    print(f"shape: entries={args.entries:,}, samples={args.samples:,}")
    print(f"device: {device}")
    print(f"float32 values size: ~{values_gb:.2f} GiB")
    print(f"float32 one square matrix size: ~{corr_gb:.2f} GiB")
    print()

    rng = np.random.default_rng(0)
    values_np = rng.standard_normal(shape, dtype=np.float32)

    values_torch = torch.from_numpy(values_np).to(device)
    eye = torch.eye(args.entries, dtype=torch.float32, device=device)
    off_diag = 1.0 - eye

    if mx is not None:
        values_mlx = mx.array(values_np)
        mlx_eye = mx.eye(args.entries)
        mlx_off_diag = 1.0 - mlx_eye
    else:
        values_mlx = None
        mlx_eye = None
        mlx_off_diag = None

    if TileLangCovariance is not None:
        try:
            tilelang_backend = TileLangCovariance(
                [f"stream-{i}" for i in range(args.entries)],
                args.samples,
                target=args.tilelang_target,
                execution_backend=args.tilelang_backend,
                block_rows=args.tilelang_block_rows,
                block_m=args.tilelang_block_m,
                block_n=args.tilelang_block_n,
            )
        except Exception as e:  # pragma: no cover - depends on local accelerator stack
            tilelang_backend = None
            tilelang_error = str(e)
        else:
            tilelang_error = ""
    else:
        tilelang_backend = None
        tilelang_error = "server.services.cov.tilelang could not be imported"

    def run_numpy() -> None:
        corr = numpy_corr(values_np)
        # Touch one value so the result cannot be optimized away by future runtimes.
        float(corr[0, 0])

    def run_torch() -> None:
        corr = torch_corr(values_torch, eye, off_diag)
        sync(device)
        float(corr[0, 0].cpu())

    def run_mlx() -> None:
        corr = mlx_corr(values_mlx, mlx_eye, mlx_off_diag)
        mx.eval(corr)
        float(corr[0, 0])

    def run_tilelang() -> None:
        _, corr = tilelang_backend.compute_arrays(values_np)
        float(corr[0, 0])

    if args.check and tilelang_backend is not None:
        cov_np, corr_np = numpy_cov_corr(values_np)
        cov_tilelang, corr_tilelang = tilelang_backend.compute_arrays(values_np)
        print(
            "tilelang check: "
            f"cov max_abs={np.max(np.abs(cov_tilelang - cov_np)):.6g} "
            f"corr max_abs={np.max(np.abs(corr_tilelang - corr_np)):.6g}"
        )

    bench("numpy", args.warmup, args.repeat, run_numpy)
    bench(f"torch/{device.type}", args.warmup, args.repeat, run_torch)
    if mx is None:
        print("mlx: skipped because the mlx package is not installed")
    else:
        bench("mlx", args.warmup, args.repeat, run_mlx)
    if tilelang_backend is None:
        print(f"tilelang: skipped because {tilelang_error}")
    else:
        bench(
            f"tilelang/{args.tilelang_target}",
            args.warmup,
            args.repeat,
            run_tilelang,
        )


if __name__ == "__main__":
    main()
