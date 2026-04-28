from collections.abc import Mapping, Sequence


def select_stream_window(
    returns_map: Mapping[str, Sequence[float]],
    min_samples: int,
    stream_order: Sequence[str] | None = None,
) -> tuple[list[str], int]:
    candidates = stream_order if stream_order is not None else list(returns_map.keys())
    streams = [
        sid for sid in candidates if len(returns_map.get(sid, ())) >= min_samples
    ]
    if len(streams) < 2:
        return [], 0

    min_len = min(len(returns_map[sid]) for sid in streams)
    if min_len < 2:
        return [], 0

    return streams, min_len


def prepare_returns(
    returns_map: Mapping[str, Sequence[float]],
    min_samples: int,
) -> tuple[list[str], list[list[float]]]:
    streams, min_len = select_stream_window(returns_map, min_samples)
    if not streams:
        return [], []

    values = [list(returns_map[sid][-min_len:]) for sid in streams]
    return streams, values
