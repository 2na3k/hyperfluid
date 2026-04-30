from collections.abc import Sequence

from server.services.cov.interface import CovarianceCalculator


_BACKENDS: list[dict] = []
_CACHED_SHAPE: tuple | None = None


def _detect_backends(
    stream_ids: Sequence[str],
    window_size: int,
) -> list[dict]:
    result: list[dict] = []

    # baseline / numpy — always available
    result.append({"name": "baseline", "available": True})
    result.append({"name": "numpy", "available": True})

    # torch (MPS-only)
    try:
        import torch  # noqa: F401
        from server.services.cov.torch import TorchCovariance

        TorchCovariance(stream_ids, window_size).compute(
            {sid: [0.1, 0.2, 0.3] for sid in stream_ids},
            2,
        )
        result.append({"name": "torch", "available": True, "device": "mps"})
    except ImportError:
        result.append(
            {"name": "torch", "available": False, "error": "PyTorch not installed"}
        )
    except Exception as e:
        result.append({"name": "torch", "available": False, "error": str(e)})

    # mlx
    try:
        import mlx  # noqa: F401
        from server.services.cov.mlx import MlxCovariance

        MlxCovariance(stream_ids, window_size).compute(
            {sid: [0.1, 0.2, 0.3] for sid in stream_ids},
            2,
        )
        result.append({"name": "mlx", "available": True})
    except ImportError:
        result.append({"name": "mlx", "available": False, "error": "MLX not installed"})
    except Exception as e:
        result.append({"name": "mlx", "available": False, "error": str(e)})

    # tilelang
    try:
        import tilelang  # noqa: F401
        import torch  # noqa: F401

        result.append({"name": "tilelang", "available": True, "target": "auto"})
    except ImportError as e:
        result.append({"name": "tilelang", "available": False, "error": str(e)})
    except Exception as e:
        result.append({"name": "tilelang", "available": False, "error": str(e)})

    return result


def list_backends(
    stream_ids: Sequence[str],
    window_size: int,
) -> list[dict]:
    global _BACKENDS, _CACHED_SHAPE
    key = (tuple(stream_ids), window_size)
    if not _BACKENDS or _CACHED_SHAPE != key:
        _BACKENDS = _detect_backends(stream_ids, window_size)
        _CACHED_SHAPE = key
    return list(_BACKENDS)


def get_covariance_calculator(
    name: str,
    *,
    stream_ids: Sequence[str] | None = None,
    window_size: int | None = None,
) -> CovarianceCalculator:
    normalized = name.lower()

    if normalized in {"baseline", "numpy"}:
        from server.services.cov.baseline import BaselineCovariance

        return BaselineCovariance()

    if normalized == "torch":
        if stream_ids is None or window_size is None:
            raise ValueError("Torch backend requires stream_ids and window_size")
        from server.services.cov.torch import TorchCovariance

        return TorchCovariance(stream_ids, window_size)

    if normalized == "mlx":
        if stream_ids is None or window_size is None:
            raise ValueError("MLX backend requires stream_ids and window_size")
        from server.services.cov.mlx import MlxCovariance

        return MlxCovariance(stream_ids, window_size)

    if normalized == "tilelang":
        if stream_ids is None or window_size is None:
            raise ValueError("TileLang backend requires stream_ids and window_size")
        from server.services.cov.tilelang import TileLangCovariance

        return TileLangCovariance(stream_ids, window_size)

    raise ValueError(f"Unknown covariance backend: {name}")
