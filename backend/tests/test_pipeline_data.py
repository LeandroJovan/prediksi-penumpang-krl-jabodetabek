from datetime import date

import pandas as pd
import pytest

from backend.app.core.forecast_csv import ForecastCsvError, normalize_forecast_frame
from backend.app.core.pipeline_data import data_bounds, target_periods


def _frame(**extra):
    base = {
        "horizon": [1, 2],
        "y_pred": [1.0, 2.0],
        "lower_80": [1.0, 2.0],
        "upper_80": [1.0, 2.0],
        "lower_95": [1.0, 2.0],
        "upper_95": [1.0, 2.0],
    }
    return pd.DataFrame({**base, **extra})


def test_target_periods_prefers_tanggal_target():
    frame = _frame(tanggal_target=["2027-03-01", "2027-04-01"])
    assert target_periods(frame) == [date(2027, 3, 1), date(2027, 4, 1)]


def test_target_periods_derives_from_last_actual_when_column_missing():
    assert target_periods(_frame(), last_actual=date(2027, 1, 1)) == [date(2027, 2, 1), date(2027, 3, 1)]


def test_normalize_adds_period_only_when_requested():
    frame = _frame(tanggal_target=["2027-03-01", "2027-04-01"])
    assert "period_target" in normalize_forecast_frame(frame).columns
    assert "period_target" not in normalize_forecast_frame(frame, with_period=False).columns


def test_normalize_raises_clear_error_when_period_undeterminable(monkeypatch):
    from backend.app.core import pipeline_data

    monkeypatch.setattr(pipeline_data, "data_bounds", lambda *a, **k: (None, None))
    with pytest.raises(ForecastCsvError):
        normalize_forecast_frame(_frame())


def test_data_bounds_reads_file_and_missing_returns_none(tmp_path):
    assert data_bounds(tmp_path) == (None, None)
    target = tmp_path / "data/processed"
    target.mkdir(parents=True)
    pd.DataFrame({"tanggal": ["2020-01-01", "2021-06-01"]}).to_csv(target / "data_final.csv", index=False)
    assert data_bounds(tmp_path) == (date(2020, 1, 1), date(2021, 6, 1))
