import math


def compute_covariance_matrix(
    returns_map: dict[str, list[float]],
    min_samples: int = 30,
) -> tuple[list[str], list[list[float]], list[list[float]]]:
    streams = [sid for sid, r in returns_map.items() if len(r) >= min_samples]
    n = len(streams)
    if n < 2:
        return [], [], []

    min_len = min(len(returns_map[sid]) for sid in streams)
    aligned = {sid: returns_map[sid][-min_len:] for sid in streams}

    cov: list[list[float]] = [[0.0] * n for _ in range(n)]
    corr: list[list[float]] = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            si, sj = streams[i], streams[j]
            xi, xj = aligned[si], aligned[sj]

            mean_i = sum(xi) / min_len
            mean_j = sum(xj) / min_len

            c = (
                sum(
                    (xi[k] - mean_i) * (xj[k] - mean_j)
                    for k in range(min_len)
                )
                / (min_len - 1)
            )
            cov[i][j] = round(c, 10)

            if i == j:
                corr[i][j] = 1.0
            else:
                var_i = sum((x - mean_i) ** 2 for x in xi) / (min_len - 1)
                var_j = sum((x - mean_j) ** 2 for x in xj) / (min_len - 1)
                std_i = math.sqrt(var_i)
                std_j = math.sqrt(var_j)
                if std_i > 0 and std_j > 0:
                    corr[i][j] = round(c / (std_i * std_j), 6)
                else:
                    corr[i][j] = 0.0

    return streams, cov, corr
