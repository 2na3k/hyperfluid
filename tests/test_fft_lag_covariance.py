import unittest

import numpy as np

from server.services.cov.baseline import BaselineCovariance
from server.services.cov.common import correlation_from_covariance
from server.services.cov.fft_lag import FftLagCovariance
from server.services.cov.registry import get_covariance_calculator, list_backends


def brute_circular_lag_covariance(
    values: np.ndarray,
    lag_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    centered = values - values.mean(axis=1, keepdims=True)
    rows, cols = centered.shape
    features = np.empty((rows * lag_count, cols), dtype=np.float64)

    out_row = 0
    for row in range(rows):
        for lag in range(lag_count):
            features[out_row] = np.roll(centered[row], -lag)
            out_row += 1

    covariance = features @ features.T / (cols - 1)
    correlation = correlation_from_covariance(covariance)
    return covariance, correlation


class FftLagCovarianceTest(unittest.TestCase):
    def test_matches_brute_force_circular_lag_reference(self) -> None:
        values = np.array(
            [
                [1.0, 2.0, 4.0, 8.0, 16.0, 32.0],
                [2.0, 3.0, 5.0, 7.0, 11.0, 13.0],
                [3.0, 1.0, 4.0, 1.0, 5.0, 9.0],
            ],
            dtype=np.float64,
        )
        lag_count = 3
        backend = FftLagCovariance(["a", "b", "c"], 6, lag_count=lag_count)

        cov_fft, corr_fft = backend.compute_arrays(values)
        cov_brute, corr_brute = brute_circular_lag_covariance(values, lag_count)

        np.testing.assert_allclose(cov_fft, cov_brute, atol=1e-10)
        np.testing.assert_allclose(corr_fft, corr_brute, atol=1e-10)

    def test_zero_variance_features_have_safe_correlation(self) -> None:
        values = np.array(
            [
                [1.0, 1.0, 1.0, 1.0],
                [1.0, 2.0, 1.0, 2.0],
            ],
            dtype=np.float64,
        )
        backend = FftLagCovariance(["flat", "moving"], 4, lag_count=2)

        _, correlation = backend.compute_arrays(values)

        np.testing.assert_allclose(np.diag(correlation), np.ones(4))
        self.assertEqual(correlation[0, 1], 0.0)
        self.assertEqual(correlation[0, 2], 0.0)
        self.assertEqual(correlation[1, 3], 0.0)

    def test_returns_empty_for_fewer_than_two_valid_streams(self) -> None:
        backend = FftLagCovariance(["a", "b"], 10, lag_count=2)

        result = backend.compute({"a": [1.0, 2.0, 3.0], "b": [1.0]}, 2)

        self.assertEqual(result.streams, [])
        self.assertEqual(result.covariance, [])
        self.assertEqual(result.correlation, [])

    def test_returns_empty_when_window_is_shorter_than_lag_count(self) -> None:
        backend = FftLagCovariance(["a", "b"], 10, lag_count=4)

        result = backend.compute({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]}, 2)

        self.assertEqual(result.streams, [])
        self.assertEqual(result.covariance, [])
        self.assertEqual(result.correlation, [])

    def test_compute_returns_lag_feature_ids(self) -> None:
        backend = FftLagCovariance(
            ["coinbase:BTC-USD", "coinbase:ETH-USD"], 4, lag_count=2
        )

        result = backend.compute(
            {
                "coinbase:BTC-USD": [1.0, 2.0, 3.0, 4.0],
                "coinbase:ETH-USD": [2.0, 3.0, 5.0, 7.0],
            },
            2,
        )

        self.assertEqual(
            result.streams,
            [
                "coinbase:BTC-USD@lag0",
                "coinbase:BTC-USD@lag1",
                "coinbase:ETH-USD@lag0",
                "coinbase:ETH-USD@lag1",
            ],
        )
        self.assertEqual(len(result.covariance), 4)
        self.assertEqual(len(result.correlation), 4)

    def test_registry_exposes_fft_lag_backend_and_alias(self) -> None:
        backends = list_backends(["a", "b"], 10, lag_count=3)
        names = {backend["name"] for backend in backends}

        self.assertIn("fft_lag", names)
        backend = get_covariance_calculator(
            "fft-lag",
            stream_ids=["a", "b"],
            window_size=10,
            lag_count=3,
        )
        self.assertIsInstance(backend, FftLagCovariance)
        self.assertEqual(backend.lag_count, 3)

    def test_baseline_behavior_stays_zero_lag_stream_covariance(self) -> None:
        result = BaselineCovariance().compute(
            {
                "a": [1.0, 2.0, 3.0],
                "b": [2.0, 4.0, 6.0],
            },
            2,
        )

        self.assertEqual(result.streams, ["a", "b"])
        self.assertEqual(result.covariance, [[1.0, 2.0], [2.0, 4.0]])
        self.assertEqual(result.correlation, [[1.0, 1.0], [1.0, 1.0]])


if __name__ == "__main__":
    unittest.main()
