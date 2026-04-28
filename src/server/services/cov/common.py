from collections.abc import Mapping, Sequence


def prepare_returns(
    returns_map: Mapping[str, Sequence[float]],
    min_samples: int,
) -> tuple[list[str], list[list[float]]]:
    streams = [sid for sid, r in returns_map.items() if len(r) >= min_samples]
    n = len(streams)
    if n < 2:
        return [], []

    min_len = min(len(returns_map[sid]) for sid in streams)
    if min_len < 2:
        return [], []

    values = [list(returns_map[sid][-min_len:]) for sid in streams]
    return streams, values
