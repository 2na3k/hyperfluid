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
        self.stream_index = {sid: i for i, sid in enumerate(self.stream_ids)}
        self.device = torch.device("mps")

        shape = (len(self.stream_ids), self.window_size)
        self.host_values = np.zeros(shape, dtype=np.float32)
        self.host_tensor = torch.from_numpy(self.host_values)
        self.device_values = torch.empty(
            shape, dtype=torch.float32, device=self.device
        )
        self.device_valid_len = torch.empty(
            (), dtype=torch.int64, device=self.device
        )

        self.positions = torch.arange(
            window_size, dtype=torch.int64, device=self.device
        )
        eye = torch.eye(
            len(self.stream_ids), dtype=torch.float32, device=self.device
        )
        self.eye = eye
        self.off_diag = 1.0 - eye

        self._warmup()

    def _warmup(self) -> None:
        rows, cols = self.host_values.shape
        self.host_values[:] = (
            np.arange(rows * cols, dtype=np.float32).reshape(rows, cols) / cols
        )
        self.device_values.copy_(self.host_tensor)
        self.device_valid_len.fill_(self.window_size)
        for _ in range(3):
            self._compute_tensors(self.device_values, self.device_valid_len)
            torch.mps.synchronize()

    def _compute_tensors(
        self,
        values: torch.Tensor,
        valid_len: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        start = self.positions[-1] + 1 - valid_len
        mask = (self.positions >= start).to(values.dtype).unsqueeze(0)

        masked = values * mask
        mean = masked.sum(dim=1, keepdim=True) / valid_len.to(values.dtype)
        centered = (values - mean) * mask

        cov = centered @ centered.T / (valid_len - 1.0)

        std = torch.sqrt(torch.diag(cov))
        denom = torch.outer(std, std)
        corr = torch.where(denom > 0.0, cov / denom, torch.zeros_like(cov))
        corr = corr * self.off_diag + self.eye

        return cov, corr

    def compute(
        self,
        returns_map: Mapping[str, Sequence[float]],
        min_samples: int,
    ) -> CovarianceResult:
        streams, min_len = select_stream_window(
            returns_map, min_samples, self.stream_ids,
        )
        if not streams:
            return CovarianceResult([], [], [])

        min_len = min(min_len, self.window_size)
        self.host_values.fill(0.0)

        indices: list[int] = []
        for sid in streams:
            row = self.stream_index[sid]
            indices.append(row)
            returns = returns_map[sid]
            self.host_values[row, -min_len:] = returns[-min_len:]

        self.device_values.copy_(self.host_tensor)
        self.device_valid_len.fill_(min_len)

        cov, corr = self._compute_tensors(self.device_values, self.device_valid_len)
        torch.mps.synchronize()

        cov_cpu = cov.cpu().numpy()
        corr_cpu = corr.cpu().numpy()

        ix = np.ix_(indices, indices)
        return CovarianceResult(
            streams=streams,
            covariance=np.round(cov_cpu[ix], 10).tolist(),
            correlation=np.round(corr_cpu[ix], 6).tolist(),
        )
