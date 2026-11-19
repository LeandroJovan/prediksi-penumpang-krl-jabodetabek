import hashlib
import hmac
import io
import json
import threading
from pathlib import Path

import joblib

from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from krl_core.forecast import ForecastBundle

MAX_MODEL_BYTES = 256 * 1024 * 1024
MAX_CACHED_BUNDLES = 8

_cache: dict[tuple[str, int, int], tuple[ForecastBundle, dict]] = {}
_cache_lock = threading.Lock()


def _fail(detail: str) -> AppError:
    return AppError("MODEL_LOAD_FAILED", 503, detail)


def _safe_folder(artifact_path: str) -> Path:
    """Folder artifact harus berada di bawah ARTIFACTS_DIR (cegah path traversal dari nilai di DB)."""
    base = get_settings().artifacts_dir.resolve()
    folder = Path(artifact_path).resolve()
    if not folder.is_relative_to(base):
        raise _fail("Model artifact is outside the allowed directory.")
    return folder


def _verify(model_bytes: bytes, manifest: dict) -> None:
    digest = hashlib.sha256(model_bytes).hexdigest()
    try:
        expected = manifest["files"]["model.pkl"]["sha256"].removeprefix("sha256:")
    except (KeyError, TypeError, AttributeError):
        raise _fail("Model manifest is malformed.") from None
    if not hmac.compare_digest(digest, expected):
        raise _fail("Model checksum mismatch.")

    # Checksum di folder yang sama tidak membuktikan keaslian. Jika kunci penandatanganan diatur,
    # manifest wajib memuat HMAC-SHA256 atas digest (dibuat oleh pipeline training).
    key = get_settings().model_signing_key
    if key:
        signature = manifest.get("signature", "")
        wanted = hmac.new(key.encode(), digest.encode(), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(signature, wanted):
            raise _fail("Model signature is missing or invalid.")


def load_bundle(artifact_path: str):
    """Muat (bundle, manifest). Hasil di-cache per (path, mtime, ukuran) sehingga artifact yang
    diganti otomatis dimuat ulang tanpa restart."""
    folder = _safe_folder(artifact_path)
    manifest_path = folder / "manifest.json"
    model_path = folder / "model.pkl"
    if not manifest_path.is_file() or not model_path.is_file():
        raise AppError("MODEL_NOT_AVAILABLE", 503, "Model artifact is incomplete.")

    stat = model_path.stat()
    if stat.st_size > MAX_MODEL_BYTES:
        raise _fail("Model artifact is too large.")
    cache_key = (str(model_path), stat.st_mtime_ns, stat.st_size)
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise _fail("Model manifest is unreadable.") from None
    if not isinstance(manifest, dict):
        raise _fail("Model manifest is malformed.")

    # Baca byte sekali: yang diverifikasi adalah persis yang di-unpickle (tanpa celah TOCTOU).
    model_bytes = model_path.read_bytes()
    _verify(model_bytes, manifest)
    try:
        bundle = joblib.load(io.BytesIO(model_bytes))
    except Exception as exc:
        raise _fail("Unable to load model artifact.") from exc
    if not isinstance(bundle, ForecastBundle):
        raise _fail("Model does not implement ForecastBundle.")
    if bundle.run_id != manifest.get("run_id") or bundle.horizon_max != manifest.get("horizon_max"):
        raise _fail("Model artifact metadata does not match manifest.")

    with _cache_lock:
        if len(_cache) >= MAX_CACHED_BUNDLES:
            _cache.pop(next(iter(_cache)))
        _cache[cache_key] = (bundle, manifest)
    return bundle, manifest


def clear_bundle_cache() -> None:
    with _cache_lock:
        _cache.clear()
