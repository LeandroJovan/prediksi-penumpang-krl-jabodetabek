import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib

from backend.app.core.errors import AppError
from krl_core.forecast import ForecastBundle


@lru_cache(maxsize=8)
def load_bundle(artifact_path: str):
    folder = Path(artifact_path)
    manifest_path = folder / "manifest.json"
    model_path = folder / "model.pkl"
    if not manifest_path.is_file() or not model_path.is_file():
        raise AppError("MODEL_NOT_AVAILABLE", 503, "Model artifact is incomplete.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest["files"]["model.pkl"]["sha256"].removeprefix("sha256:")
    actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if actual != expected:
        raise AppError("MODEL_LOAD_FAILED", 503, "Model checksum mismatch.")
    try:
        bundle = joblib.load(model_path)
    except Exception as exc:
        raise AppError("MODEL_LOAD_FAILED", 503, "Unable to load model artifact.") from exc
    if not isinstance(bundle, ForecastBundle):
        raise AppError("MODEL_LOAD_FAILED", 503, "Model does not implement ForecastBundle.")
    if bundle.run_id != manifest["run_id"] or bundle.horizon_max != manifest["horizon_max"]:
        raise AppError("MODEL_LOAD_FAILED", 503, "Model artifact metadata does not match manifest.")
    return bundle, manifest
