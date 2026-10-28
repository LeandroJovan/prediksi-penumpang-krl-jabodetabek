import numpy as np
import pandas as pd

from backend.app.core.errors import AppError

REQUIRED_COLUMNS = ["period", "horizon", "point", "lower80", "upper80", "lower95", "upper95"]


def validate_forecast(frame: pd.DataFrame, horizon_max: int) -> pd.DataFrame:
    if list(frame.columns) != REQUIRED_COLUMNS:
        raise AppError("INFERENCE_FAILED", 503, "Model output columns do not match the contract.")
    if len(frame) != horizon_max or frame["horizon"].tolist() != list(range(1, horizon_max + 1)):
        raise AppError("INFERENCE_FAILED", 503, "Model output horizons are invalid.")
    numeric = frame[["point", "lower80", "upper80", "lower95", "upper95"]]
    if not np.isfinite(numeric.to_numpy(dtype=float)).all() or (numeric <= 0).any().any():
        raise AppError("INFERENCE_FAILED", 503, "Model output contains invalid values.")
    valid = (
        (frame.lower95 <= frame.lower80)
        & (frame.lower80 <= frame.point)
        & (frame.point <= frame.upper80)
        & (frame.upper80 <= frame.upper95)
    )
    if not valid.all():
        raise AppError("INFERENCE_FAILED", 503, "Model output intervals are invalid.")
    return frame
