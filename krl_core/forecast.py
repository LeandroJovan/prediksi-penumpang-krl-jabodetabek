from abc import ABC, abstractmethod

import pandas as pd


class ForecastBundle(ABC):
    """Stable pickle contract. See docs/artifact-contract.md."""

    schema_version = "1.0"
    run_id: str
    algorithm: str
    horizon_max: int
    target: str = "penumpang_ribu"

    @abstractmethod
    def predict(self, history: pd.Series, calendar: pd.DataFrame) -> pd.DataFrame:
        """Return period, horizon, point, lower80, upper80, lower95, upper95."""
