from collections.abc import Mapping, Sequence

import numpy as np
import torch

from server.services.cov.common import select_stream_window
from server.services.cov.interface import CovarianceResult


class TorchCovariance:
    name = "torch"

    def __init__(
        self,
        stream_ids: Sequence[str],
        window_size: int,
    ) -> None:
        if not torch.backends.mps.is_available():
            raise RuntimeError("PyTorch MPS unavailable")

        self.stream_ids = list(stream_ids)
        self.window_size = window_size
        self.device = torch.device("mps")

        self._warmup()

    def _warmup(self) -> None:
        rows = min(len(self.stream_ids), 8)
        cols = min(self.window_size, 32)
        if rows < 2 or cols < 2:
            return
        values = torch.arange(
            rows * cols,
            dtype=torch.float32,
            device=self.device,
        ).reshape(rows, cols)
        for _ in range(3):
            self._compute_tensors(values)
            torch.mps.synchronize()

    def _compute_tensors(
        self,
        values: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        centered = values - values.mean(dim=1, keepdim=True)
        cov = (
            centered @ centered.T / (values.shape[1] - 1)
        )  # technically (X - mu_x)(Y - mu_y)/(n-1)

        std = torch.sqrt(torch.abs(torch.diag(cov)))
        inv_std = torch.where(std > 0.0, 1.0 / std, torch.zeros_like(std))
        corr = cov * inv_std[:, None] * inv_std[None, :]
        corr.fill_diagonal_(1.0)

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

        min_len = min(min_len, self.window_size)
        values_np = np.empty((len(streams), min_len), dtype=np.float32)
        for row, sid in enumerate(streams):
            values_np[row] = returns_map[sid][-min_len:]

        values = torch.from_numpy(values_np).to(self.device)
        cov, corr = self._compute_tensors(values)

        cov_cpu = cov.cpu().numpy()
        corr_cpu = corr.cpu().numpy()
        return CovarianceResult(
            streams=streams,
            covariance=np.round(cov_cpu, 10).tolist(),
            correlation=np.round(corr_cpu, 6).tolist(),
        )
