from collections.abc import Mapping, Sequence

import mlx.core as mx
import numpy as np

from server.services.cov.common import select_stream_window
from server.services.cov.interface import CovarianceResult


class MlxCovariance:
    name = "mlx"

    def __init__(
        self,
        stream_ids: Sequence[str] | None = None,
        window_size: int | None = None,
    ) -> None:
        self.stream_ids = list(stream_ids) if stream_ids is not None else None
        self.window_size = window_size
        self._warmup()

    def _warmup(self) -> None:
        rows = min(len(self.stream_ids or []), 8)
        cols = min(self.window_size or 0, 32)
        if rows < 2 or cols < 2:
            return
        values = mx.arange(rows * cols, dtype=mx.float32).reshape(rows, cols)
        for _ in range(3):
            cov, corr = self._compute_tensors(values)
            mx.eval(cov, corr)

    def _compute_tensors(self, values: mx.array) -> tuple[mx.array, mx.array]:
        centered = values - mx.mean(values, axis=1, keepdims=True)
        cov = centered @ centered.T / (values.shape[1] - 1)

        std = mx.sqrt(mx.abs(mx.diag(cov)))
        inv_std = mx.where(std > 0.0, 1.0 / std, mx.zeros_like(std))
        corr = cov * inv_std[:, None] * inv_std[None, :]
        eye = mx.eye(values.shape[0], dtype=corr.dtype)
        corr = corr * (1.0 - eye) + eye
        return cov, corr

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

        if self.window_size is not None:
            min_len = min(min_len, self.window_size)
        values_np = np.empty((len(streams), min_len), dtype=np.float32)
        for row, sid in enumerate(streams):
            values_np[row] = returns_map[sid][-min_len:]

        values = mx.array(values_np)
        cov, corr = self._compute_tensors(values)
        mx.eval(cov, corr)

        cov_np = np.array(cov)
        corr_np = np.array(corr)
        return CovarianceResult(
            streams=streams,
            covariance=np.round(cov_np, 10).tolist(),
            correlation=np.round(corr_np, 6).tolist(),
        )
