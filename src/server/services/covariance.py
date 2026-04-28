import numpy as np


def compute_covariance_matrix(
    returns_map: dict[str, list[float]],
    min_samples: int = 30,
) -> tuple[list[str], list[list[float]], list[list[float]]]:
    streams = [sid for sid, r in returns_map.items() if len(r) >= min_samples]
    n = len(streams)
    if n < 2:
        return [], [], []

    min_len = min(len(returns_map[sid]) for sid in streams)
    values = np.array([returns_map[sid][-min_len:] for sid in streams], dtype=np.float64)
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

    return streams, np.round(cov_arr, 10).tolist(), np.round(corr_arr, 6).tolist()
