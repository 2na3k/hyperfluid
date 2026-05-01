from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from server.services.cov.common import select_stream_window
from server.services.cov.interface import CovarianceResult


class FftLagCovariance:
    name = "fft_lag"

    def __init__(
        self,
        stream_ids: Sequence[str],
        window_size: int,
        *,
        lag_count: int = 16,
    ) -> None:
        if lag_count < 1:
            raise ValueError("lag_count must be >= 1")

        self.stream_ids = list(stream_ids)
        self.window_size = window_size
        self.lag_count = lag_count

    def compute_arrays(self, values_np: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        values_np = np.asarray(values_np, dtype=np.float64)
        if values_np.ndim != 2:
            raise ValueError("values_np must be a 2D array")

        rows, cols = values_np.shape
        if rows < 2 or cols < max(2, self.lag_count):
            return (
                np.empty((0, 0), dtype=np.float64),
                np.empty((0, 0), dtype=np.float64),
            )

        centered = values_np - values_np.mean(axis=1, keepdims=True)
        spectrum = np.fft.fft(centered, axis=1)
        cross_corr = np.fft.ifft(
            np.conj(spectrum)[:, None, :] * spectrum[None, :, :],
            axis=2,
        ).real

        lags = np.arange(self.lag_count)
        lag_offsets = (lags[None, :] - lags[:, None]) % cols
        size = rows * self.lag_count
        covariance = np.empty((size, size), dtype=np.float64)

        for row_a in range(rows):
            start_a = row_a * self.lag_count
            end_a = start_a + self.lag_count
            for row_b in range(rows):
                start_b = row_b * self.lag_count
                end_b = start_b + self.lag_count
                covariance[start_a:end_a, start_b:end_b] = (
                    cross_corr[row_a, row_b, lag_offsets] / (cols - 1)
                )

        covariance = (covariance + covariance.T) / 2.0
        std = np.sqrt(np.diag(covariance))
        denom = np.outer(std, std)
        correlation = np.divide(
            covariance,
            denom,
            out=np.zeros_like(covariance),
            where=denom > 0,
        )
        np.fill_diagonal(correlation, 1.0)

        return covariance, correlation

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
        if min_len < max(2, self.lag_count):
            return CovarianceResult([], [], [])

        values_np = np.empty((len(streams), min_len), dtype=np.float64)
        for row, sid in enumerate(streams):
            values_np[row] = returns_map[sid][-min_len:]

        covariance, correlation = self.compute_arrays(values_np)
        feature_ids = [
            f"{stream_id}@lag{lag}"
            for stream_id in streams
            for lag in range(self.lag_count)
        ]

        return CovarianceResult(
            streams=feature_ids,
            covariance=np.round(covariance, 10).tolist(),
            correlation=np.round(correlation, 6).tolist(),
        )
