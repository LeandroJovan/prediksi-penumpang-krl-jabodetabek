"""Bundle palsu yang dapat di-pickle (harus berada di modul importable agar joblib dapat memuatnya)."""
import pandas as pd

from krl_core.forecast import ForecastBundle


class FakeBundle(ForecastBundle):
    run_id = "fake_run"
    algorithm = "fake"
    horizon_max = 6

    def predict(self, history: pd.Series, calendar: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError
