from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CovarianceResult:
    streams: list[str]
    covariance: list[list[float]]
    correlation: list[list[float]]


class CovarianceCalculator(Protocol):
    name: str

    def compute(
        self,
        returns_map: Mapping[str, Sequence[float]],
        min_samples: int,
    ) -> CovarianceResult:
        ...
