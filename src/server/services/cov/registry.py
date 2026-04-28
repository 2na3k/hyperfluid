from server.services.cov.interface import CovarianceCalculator


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
