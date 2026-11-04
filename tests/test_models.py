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

from app.models import (
    cluster_bootstrap_mae_difference,
    ensemble_prediction,
    optimize_weights,
    regression_metrics,
    select_ensemble,
)


class EnsembleTests(unittest.TestCase):
    def test_weights_follow_best_model(self) -> None:
        y = np.array([1.0, 2.0, 3.0, 4.0])
        predictions = {
            "linear": y + 0.1,
            "random_forest": y + 5.0,
            "gradient_boosting": y + 9.0,
        }
        weights = optimize_weights(predictions, y, step=0.05)
        self.assertGreater(weights["linear"], 0.8)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=3)

    def test_select_ensemble_returns_validation_method(self) -> None:
        y = np.array([1.0, 2.0, 3.0, 4.0])
        predictions = {
            "linear": y,
            "random_forest": y,
            "gradient_boosting": y,
        }
        choice = select_ensemble(predictions, y)
        self.assertIn(choice["method"], {"equal", "inverse_mae", "optimized_mae"})
        self.assertAlmostEqual(sum(choice["weights"].values()), 1.0, places=3)

    def test_ensemble_prediction(self) -> None:
        predictions = {
            "linear": np.array([1.0, 2.0]),
            "random_forest": np.array([3.0, 4.0]),
            "gradient_boosting": np.array([5.0, 6.0]),
        }
        result = ensemble_prediction(
            predictions,
            {"linear": 0.5, "random_forest": 0.5, "gradient_boosting": 0.0},
        )
        np.testing.assert_allclose(result, [2.0, 3.0])

    def test_metrics(self) -> None:
        metrics = regression_metrics([1, 2, 3], [1, 3, 4])
        self.assertAlmostEqual(metrics["mae"], 2 / 3, places=3)
        self.assertEqual(metrics["n"], 3)
        self.assertAlmostEqual(metrics["bias"], 2 / 3, places=3)

    def test_bootstrap_detects_better_model(self) -> None:
        dates = pd.date_range("2026-01-01", periods=20, freq="D")
        rows = pd.DataFrame(
            {
                "date": np.repeat(dates, 3),
                "lead": np.tile([1, 2, 3], 20),
                "fact": 10.0,
                "ensemble": 10.1,
                "official": 10.5,
            }
        )
        result = cluster_bootstrap_mae_difference(rows, iterations=300)
        self.assertLess(result["delta_mae"], 0)
        self.assertGreaterEqual(result["probability_better"], 0.95)


if __name__ == "__main__":
    unittest.main()
