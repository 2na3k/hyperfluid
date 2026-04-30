from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import cached_property
from typing import Any

import numpy as np

from server.services.cov.common import select_stream_window
from server.services.cov.interface import CovarianceResult


def _make_row_stats_kernel(
    rows: int,
    cols: int,
    *,
    block_rows: int,
) -> Any:
    import tilelang.language as T

    @T.prim_func
    def row_stats(
        values: T.Tensor((rows, cols), "float32"),
        means: T.Tensor((rows,), "float32"),
        inv_stds: T.Tensor((rows,), "float32"),
    )
        with T.Kernel(T.ceildiv(rows, block_rows), threads=128) as bx:
            totals = T.alloc_fragment((block_rows,), "float32")
            square_totals = T.alloc_fragment((block_rows,), "float32")
            T.clear(totals)
            T.clear(square_totals)

            for local_row in T.Parallel(block_rows):
                row = bx * block_rows + local_row
                if row < rows:
                    for col in T.serial(cols):
                        value = values[row, col]
                        totals[local_row] += value
                        square_totals[local_row] += value * value

            for local_row in T.Parallel(block_rows):
                row = bx * block_rows + local_row
                if row < rows:
                    mean = totals[local_row] / cols
                    # sample variance: sum((x - mean)^2) / (n - 1)
                    var = (square_totals[local_row] - totals[local_row] * mean) / (
                        cols - 1
                    )
                    means[row] = mean
                    inv_stds[row] = T.rsqrt(var) if var > 0.0 else 0.0

    return row_stats


def _make_cov_corr_kernel(
    rows: int,
    cols: int,
    *,
    block_m: int,
    block_n: int,
) -> Any:
    import tilelang.language as T

    @T.prim_func
    def cov_corr(
        values: T.Tensor((rows, cols), "float32"),
        means: T.Tensor((rows,), "float32"),
        inv_stds: T.Tensor((rows,), "float32"),
        covariance: T.Tensor((rows, rows), "float32"),
        correlation: T.Tensor((rows, rows), "float32"),
    ):
        with T.Kernel(
            T.ceildiv(rows, block_n),
            T.ceildiv(rows, block_m),
            threads=128,
        ) as (bx, by):
            acc = T.alloc_fragment((block_m, block_n), "float32")
            T.clear(acc)

            for col in T.serial(cols):
                for local_m, local_n in T.Parallel(block_m, block_n):
                    row_m = by * block_m + local_m
                    row_n = bx * block_n + local_n
                    if row_m < rows and row_n < rows and row_m <= row_n:
                        left = values[row_m, col] - means[row_m]
                        right = values[row_n, col] - means[row_n]
                        acc[local_m, local_n] += left * right

            for local_m, local_n in T.Parallel(block_m, block_n):
                row_m = by * block_m + local_m
                row_n = bx * block_n + local_n
                if row_m < rows and row_n < rows and row_m <= row_n:
                    cov = acc[local_m, local_n] / (cols - 1)
                    covariance[row_m, row_n] = cov
                    covariance[row_n, row_m] = cov
                    corr = (
                        1.0
                        if row_m == row_n
                        else cov * inv_stds[row_m] * inv_stds[row_n]
                    )
                    correlation[row_m, row_n] = corr
                    correlation[row_n, row_m] = corr

    return cov_corr


class TileLangCovariance:
    name = "tilelang"

    def __init__(
        self,
        stream_ids: Sequence[str],
        window_size: int,
        *,
        target: str = "auto",
        execution_backend: str = "auto",
        block_rows: int = 128,
        block_m: int = 8,
        block_n: int = 8,
    ) -> None:
        self.stream_ids = list(stream_ids)
        self.window_size = window_size
        self.target = target
        self.execution_backend = execution_backend
        self.block_rows = block_rows
        self.block_m = block_m
        self.block_n = block_n
        self._compiled_kernels: dict[tuple[int, int], tuple[Any, Any]] = {}

        self._import_runtime()

    def _import_runtime(self) -> None:
        try:
            import tilelang  # noqa: F401
            import torch  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "TileLang backend requires the optional tilelang and torch packages"
            ) from exc

    @cached_property
    def _torch(self) -> Any:
        import torch

        return torch

    @cached_property
    def _tilelang(self) -> Any:
        import tilelang

        return tilelang

    @cached_property
    def _device(self) -> Any:
        torch = self._torch
        target = self.target.split()[0]

        if target == "cuda" and torch.cuda.is_available():
            return torch.device("cuda")
        if target == "hip" and torch.cuda.is_available():
            # ROCm PyTorch exposes HIP devices through the cuda device type.
            return torch.device("cuda")
        if target == "metal" and torch.backends.mps.is_available():
            return torch.device("mps")
        if target == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            if torch.backends.mps.is_available():
                return torch.device("mps")

        return torch.device("cpu")

    def _compile_kernel(self, func: Any) -> Any:
        return self._tilelang.compile(
            func,
            target=self.target,
            execution_backend=self.execution_backend,
        )

    def _sync(self) -> None:
        torch = self._torch
        if self._device.type == "cuda":
            torch.cuda.synchronize()
        elif self._device.type == "mps":
            torch.mps.synchronize()

    def compute_arrays(self, values_np: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        values_np = np.asarray(values_np, dtype=np.float32)
        if values_np.ndim != 2:
            raise ValueError("values_np must be a 2D array")
        rows, cols = values_np.shape
        if rows < 2 or cols < 2:
            return (
                np.empty((0, 0), dtype=np.float32),
                np.empty((0, 0), dtype=np.float32),
            )

        key = (rows, cols)
        if key not in self._compiled_kernels:
            row_stats = self._compile_kernel(
                _make_row_stats_kernel(
                    rows,
                    cols,
                    block_rows=self.block_rows,
                )
            )
            cov_corr = self._compile_kernel(
                _make_cov_corr_kernel(
                    rows,
                    cols,
                    block_m=self.block_m,
                    block_n=self.block_n,
                )
            )
            self._compiled_kernels[key] = (row_stats, cov_corr)

        row_stats, cov_corr = self._compiled_kernels[key]

        torch = self._torch
        device = self._device
        values = torch.as_tensor(values_np, dtype=torch.float32, device=device)
        means = torch.empty((rows,), dtype=torch.float32, device=device)
        inv_stds = torch.empty((rows,), dtype=torch.float32, device=device)
        covariance = torch.empty((rows, rows), dtype=torch.float32, device=device)
        correlation = torch.empty((rows, rows), dtype=torch.float32, device=device)

        row_stats(values, means, inv_stds)
        cov_corr(values, means, inv_stds, covariance, correlation)
        self._sync()

        return covariance.cpu().numpy(), correlation.cpu().numpy()

    def compute(
        self,
        returns_map: Mapping[str, Sequence[float]],
        min_samples: int,
    ) -> CovarianceResult:
        streams, min_len = select_stream_window(
            returns_map,
            min_samples,
            self.stream_ids,
        )
        if not streams:
            return CovarianceResult([], [], [])

        min_len = min(min_len, self.window_size)
        values_np = np.empty((len(streams), min_len), dtype=np.float32)
        for row, sid in enumerate(streams):
            values_np[row] = returns_map[sid][-min_len:]

        covariance, correlation = self.compute_arrays(values_np)
        return CovarianceResult(
            streams=streams,
            covariance=np.round(covariance, 10).tolist(),
            correlation=np.round(correlation, 6).tolist(),
        )
