from collections.abc import Mapping, Sequence

from server.services.cov.interface import CovarianceCalculator, CovarianceResult


class MlxCovariance:
    name = "mlx"

    def compute(
        self,
        returns_map: Mapping[str, Sequence[float]],
        min_samples: int,
    ) -> CovarianceResult:
        ...
