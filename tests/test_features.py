from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VENDOR = ROOT / ".vendor"
if VENDOR.exists():
    sys.path.append(str(VENDOR))

import numpy as np
import pandas as pd

from app.features import FEATURE_COLUMNS, build_lead_dataset, future_frame, split_dates


def sample_frame(days: int = 90) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    index = pd.date_range("2026-01-01", periods=days, freq="D")
    tmax = 5 + 10 * np.sin(np.arange(days) / 12) + rng.normal(0, 1.5, days)
    return pd.DataFrame(
        {
            "tmax": tmax,
            "tmin": tmax - 5 + rng.normal(0, 0.7, days),
            "tmean": tmax - 2,
            "precip": rng.gamma(0.4, 1.0, days),
            "weather_code": np.zeros(days),
            "wind_max": rng.uniform(0, 8, days),
            "pressure": 1005 + rng.normal(0, 5, days),
            "humidity": rng.uniform(40, 95, days),
            "cloud": rng.uniform(0, 100, days),
            "dewpoint": tmax - 7 + rng.normal(0, 1, days),
            "wind_dir": rng.uniform(0, 360, days),
            "radiation": rng.uniform(0, 25, days),
            "apparent": tmax - 2 + rng.normal(0, 1, days),
        },
        index=index,
    )


class FeatureTests(unittest.TestCase):
    def test_feature_columns_are_stable(self) -> None:
        self.assertGreater(len(FEATURE_COLUMNS), 25)
        self.assertIn("tmax_lag1", FEATURE_COLUMNS)
        self.assertIn("pressure_delta_3", FEATURE_COLUMNS)
        self.assertEqual(len(FEATURE_COLUMNS), len(set(FEATURE_COLUMNS)))

    def test_target_day_does_not_leak_into_own_features(self) -> None:
        frame = sample_frame()
        target = frame.index[60]
        X, y = build_lead_dataset(frame, 1)
        before = X.loc[target].copy()

        changed = frame.copy()
        changed.loc[target, "tmax"] = 999.0
        X2, y2 = build_lead_dataset(changed, 1)

        pd.testing.assert_series_equal(before, X2.loc[target])
        self.assertEqual(y.loc[target], frame.loc[target, "tmax"])
        self.assertEqual(y2.loc[target], 999.0)

    def test_latest_observation_is_lead_plus_one_days_old(self) -> None:
        frame = sample_frame()
        for lead in (1, 2, 3):
            X, _ = build_lead_dataset(frame, lead)
            target_position = 60
            target = frame.index[target_position]
            expected = frame["tmax"].iloc[target_position - lead - 1]
            self.assertAlmostEqual(X.loc[target, "tmax_lag1"], expected)

    def test_future_features_use_only_history(self) -> None:
        frame = sample_frame()
        future = future_frame(frame, frame.index.max(), days=4)
        X, _ = build_lead_dataset(future, 1)
        target = frame.index.max() + pd.Timedelta(days=2)
        row = X.loc[target]
        self.assertFalse(row.isna().any())
        self.assertAlmostEqual(row["tmax_lag1"], frame["tmax"].iloc[-1])

    def test_split_is_chronological(self) -> None:
        index = pd.date_range("2025-01-01", periods=365, freq="D")
        periods = split_dates(index, test_days=45, valid_days=30)
        self.assertLess(periods["train"][1], periods["validation"][0])
        self.assertLess(periods["validation"][1], periods["test"][0])
        self.assertEqual((periods["test"][1] - periods["test"][0]).days, 44)


if __name__ == "__main__":
    unittest.main()
