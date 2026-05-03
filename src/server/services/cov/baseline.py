import logging

import numpy as np

from server.services.cov.common import (
    correlation_from_covariance,
    prepare_returns,
)
from server.services.cov.interface import CovarianceResult

logger = logging.getLogger(__name__)


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
        corr_arr = correlation_from_covariance(cov_arr)

        return CovarianceResult(
            streams=streams,
            covariance=np.round(cov_arr, 10).tolist(),
            correlation=np.round(corr_arr, 6).tolist(),
        )
