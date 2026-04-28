from server.services.cov.interface import CovarianceCalculator


_BACKENDS: list[dict] = []


def _detect_backends() -> list[dict]:
    result: list[dict] = []

    # baseline / numpy — always available
    result.append({"name": "baseline", "available": True})
    result.append({"name": "numpy", "available": True})

    # torch
    try:
        import torch  # noqa: F401
        result.append({"name": "torch", "available": True})
    except ImportError:
        result.append({"name": "torch", "available": False, "error": "PyTorch not installed"})

    # mlx
    try:
        import mlx  # noqa: F401
        result.append({"name": "mlx", "available": True})
    except ImportError:
        result.append({"name": "mlx", "available": False, "error": "MLX not installed"})

    return result


def list_backends() -> list[dict]:
    global _BACKENDS
    if not _BACKENDS:
        _BACKENDS = _detect_backends()
    return list(_BACKENDS)


def get_covariance_calculator(name: str) -> CovarianceCalculator:
    normalized = name.lower()

    if normalized in {"baseline", "numpy"}:
        from server.services.cov.baseline import BaselineCovariance
        return BaselineCovariance()

    if normalized == "torch":
        from server.services.cov.torch import TorchCovariance
        return TorchCovariance()

    if normalized == "mlx":
        from server.services.cov.mlx import MlxCovariance
        return MlxCovariance()

    raise ValueError(f"Unknown covariance backend: {name}")


def validate_backend(name: str) -> tuple[bool, str]:
    normalized = name.lower()
    try:
        calc = get_covariance_calculator(normalized)
        result = calc.compute({}, 1)
        return True, ""
    except NotImplementedError as e:
        msg = str(e) or f"Backend '{normalized}' is not implemented yet"
        return False, msg
    except ValueError as e:
        return False, str(e)
