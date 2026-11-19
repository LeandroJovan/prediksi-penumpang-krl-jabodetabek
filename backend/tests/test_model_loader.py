import asyncio
import hashlib
import hmac
import json
import threading

import joblib
import pytest

from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from backend.app.ml import inference
from backend.app.ml.inference import run_inference
from backend.app.ml.loader import clear_bundle_cache, load_bundle
from backend.tests.fake_bundle import FakeBundle


def _make_artifact(folder, *, tamper=False, signature_key=None, run_id="fake_run"):
    folder.mkdir(parents=True, exist_ok=True)
    model = folder / "model.pkl"
    joblib.dump(FakeBundle(), model)
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    manifest = {"run_id": run_id, "horizon_max": 6, "files": {"model.pkl": {"sha256": f"sha256:{digest}"}}}
    if signature_key:
        manifest["signature"] = hmac.new(signature_key.encode(), digest.encode(), hashlib.sha256).hexdigest()
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if tamper:
        model.write_bytes(model.read_bytes() + b"x")
    return folder


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    clear_bundle_cache()
    monkeypatch.setattr(get_settings(), "artifacts_dir", tmp_path)
    monkeypatch.setattr(get_settings(), "model_signing_key", None)
    yield
    clear_bundle_cache()


def test_loads_valid_artifact_and_caches(tmp_path):
    folder = _make_artifact(tmp_path / "m1")
    first = load_bundle(str(folder))
    assert first[0].run_id == "fake_run"
    assert load_bundle(str(folder))[0] is first[0]


def test_replaced_artifact_is_reloaded_without_restart(tmp_path):
    folder = _make_artifact(tmp_path / "m1")
    first = load_bundle(str(folder))
    _make_artifact(folder)  # tulis ulang -> mtime/ukuran baru
    import os
    import time

    os.utime(folder / "model.pkl", ns=(time.time_ns(), time.time_ns() + 10_000_000))
    assert load_bundle(str(folder))[0] is not first[0]


def test_rejects_checksum_mismatch(tmp_path):
    folder = _make_artifact(tmp_path / "m1", tamper=True)
    with pytest.raises(AppError) as exc:
        load_bundle(str(folder))
    assert "checksum" in exc.value.detail


def test_rejects_path_outside_artifacts_dir(tmp_path, monkeypatch):
    outside = _make_artifact(tmp_path.parent / "outside_model")
    with pytest.raises(AppError) as exc:
        load_bundle(str(outside))
    assert "outside" in exc.value.detail


def test_rejects_traversal_path(tmp_path):
    _make_artifact(tmp_path.parent / "outside_model2")
    with pytest.raises(AppError):
        load_bundle(str(tmp_path / ".." / "outside_model2"))


def test_signature_required_when_key_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "model_signing_key", "kunci-rahasia")
    unsigned = _make_artifact(tmp_path / "unsigned")
    with pytest.raises(AppError) as exc:
        load_bundle(str(unsigned))
    assert "signature" in exc.value.detail
    signed = _make_artifact(tmp_path / "signed", signature_key="kunci-rahasia")
    assert load_bundle(str(signed))[0].run_id == "fake_run"
    wrong = _make_artifact(tmp_path / "wrong", signature_key="kunci-lain")
    with pytest.raises(AppError):
        load_bundle(str(wrong))


def test_rejects_metadata_mismatch(tmp_path):
    folder = _make_artifact(tmp_path / "m1", run_id="lain")
    with pytest.raises(AppError) as exc:
        load_bundle(str(folder))
    assert "metadata" in exc.value.detail


def test_incomplete_artifact_is_503(tmp_path):
    (tmp_path / "kosong").mkdir()
    with pytest.raises(AppError) as exc:
        load_bundle(str(tmp_path / "kosong"))
    assert exc.value.code == "MODEL_NOT_AVAILABLE"


async def test_inference_timeout_does_not_free_slot_until_thread_finishes():
    release = threading.Event()

    def slow():
        release.wait(5)
        return "done"

    with pytest.raises(asyncio.TimeoutError):
        await run_inference(slow, timeout=0.05, max_concurrency=1)
    # Thread masih berjalan -> slot belum bebas -> request baru ditolak cepat.
    with pytest.raises(AppError) as exc:
        await run_inference(lambda: 1, timeout=1, max_concurrency=1)
    assert exc.value.code == "INFERENCE_BUSY"
    release.set()
    for _ in range(100):
        if inference._inflight == 0:
            break
        await asyncio.sleep(0.01)
    assert await run_inference(lambda: 7, timeout=1, max_concurrency=1) == 7


async def test_inference_returns_result():
    assert await run_inference(lambda a, b: a + b, 2, 3, timeout=1, max_concurrency=2) == 5
