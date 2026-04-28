import numpy as np

from server.services.cov.common import prepare_returns
from server.services.cov.interface import CovarianceResult


class BaselineCovariance:
    name = "baseline"

    def compute(
        self,
        returns_map: dict[str, list[float]],
        min_samples: int = 30,
    ) -> CovarianceResult:
        streams, aligned = prepare_returns(returns_map, min_samples)
        if not streams:
            return CovarianceResult([], [], [])

        min_len = len(aligned[0])
        values = np.array(aligned, dtype=np.float64)
        centered = values - values.mean(axis=1, keepdims=True)

        cov_arr = centered @ centered.T / (min_len - 1)
        std = np.sqrt(np.diag(cov_arr))
        denom = np.outer(std, std)
        corr_arr = np.divide(
            cov_arr,
            denom,
            out=np.zeros_like(cov_arr),
            where=denom > 0,
        )
        np.fill_diagonal(corr_arr, 1.0)

        return CovarianceResult(
            streams=streams,
            covariance=np.round(cov_arr, 10).tolist(),
            correlation=np.round(corr_arr, 6).tolist(),
        )
