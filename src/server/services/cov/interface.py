from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CovarianceResult:
    """Result of a covariance/correlation matrix computation.

    Attributes:
        streams: Ordered list of stream IDs included in the matrices.
            Only streams with enough samples (>= min_samples) appear here.
        covariance: Sample covariance matrix as a nested list.
            Shape is (n x n) where n = len(streams).
            Row/column order corresponds to `streams`.
            Computed with denominator (n_obs - 1).
            Each value is rounded to 10 decimal places.
        correlation: Pearson correlation matrix.
            Shape is (n x n), same ordering as covariance.
            Diagonal entries are 1.0.
            Off-diagonal entries are in [-1, 1].
            Zero-variance pairs produce 0 correlation.
            Each value is rounded to 6 decimal places.
    """

    streams: list[str]
    covariance: list[list[float]]
    correlation: list[list[float]]


class CovarianceCalculator(Protocol):
    """Protocol for pluggable covariance/correlation backends.

    Implementations compute sample covariance and Pearson correlation
    matrices from a mapping of stream IDs to their return sequences.

    All implementations must:
      - Filter out streams with fewer than `min_samples` returns.
      - Align all valid streams to the most recent common window
        (the shortest length among the valid streams).
      - Use sample covariance (divide by n-1, not n).
      - Handle the edge case of < 2 valid streams by returning
        empty lists in CovarianceResult.
      - Convert results to plain Python lists (not tensors).
      - Round covariance to 10 decimals and correlation to 6 decimals.
    """

    name: str
    """Short identifier for the backend (e.g. "baseline", "torch")."""

    def compute(
        self,
        returns_map: Mapping[str, Sequence[float]],
        min_samples: int,
    ) -> CovarianceResult:
        """Compute covariance and correlation matrices.

        Args:
            returns_map: Mapping of stream ID to its sequence of
                log returns. Sequences may differ in length.
            min_samples: Minimum number of returns a stream must have
                to be included in the computation.

        Returns:
            CovarianceResult containing:
              - streams: IDs of the included streams in order.
              - covariance: Upper-triangular sample covariance matrix.
              - correlation: Pearson correlation matrix.

        Edge cases:
          - < 2 valid streams: return CovarianceResult([], [], []).
          - Fewer than 2 observations per stream after alignment:
            return CovarianceResult([], [], []).
          - Single-stream edge (n=1): handled as < 2, returns empty.
          - Zero-variance stream: correlation off-diagonal is 0,
            diagonal is 1.
        """
        ...
