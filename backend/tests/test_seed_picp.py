import pandas as pd
import pytest

from backend.cli.seed_data import load_picp


def _write(tmp_path, rows):
    path = tmp_path / "m.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _row(level, kal, h, n, picp):
    return {"level": level, "kalibrasi": kal, "horizon": h, "n_uji": n, "PICP_%": picp}


def test_load_picp_uses_only_rolling_calibration(tmp_path):
    path = _write(tmp_path, [
        _row(80, "bergulir (sahih)", 1, 10, 70.0),
        _row(80, "bergulir (sahih)", 2, 30, 50.0),
        _row(95, "bergulir (sahih)", 1, 10, 90.0),
        _row(95, "bergulir (sahih)", 2, 30, 80.0),
        _row(80, "in-sample (versi lama)", 1, 34, 100.0),
        _row(95, "in-sample (versi lama)", 1, 34, 100.0),
    ])
    per_h, overall = load_picp(path)
    assert per_h[1] == pytest.approx((0.70, 0.90))
    assert per_h[2] == pytest.approx((0.50, 0.80))
    assert overall[0] == pytest.approx((70 * 10 + 50 * 30) / 40 / 100)
    assert overall[1] == pytest.approx((90 * 10 + 80 * 30) / 40 / 100)


def test_load_picp_missing_or_incomplete_returns_none(tmp_path):
    assert load_picp(tmp_path / "tidak-ada.csv") == ({}, (None, None))
    path = _write(tmp_path, [_row(80, "bergulir (sahih)", 1, 10, 70.0)])
    assert load_picp(path) == ({}, (None, None))


def test_real_pipeline_csv_is_not_the_old_hardcoded_values():
    from backend.app.core.config import REPO_ROOT

    per_h, overall = load_picp(REPO_ROOT / "outputs/metrik_interval_conformal.csv")
    if per_h:
        assert overall[1] != 1.0 and overall[0] != 0.84
