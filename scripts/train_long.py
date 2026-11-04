"""Дообучение моделей на горизонты 8–14 дней без пересчёта бэктеста 1–7."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VENDOR = ROOT / ".vendor"
if VENDOR.exists():
    sys.path.append(str(VENDOR))

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import (  # noqa: E402
    CITIES,
    SAMPLE_WEIGHT_HALF_LIFE_DAYS,
    TEST_DAYS,
    VALID_DAYS,
    artifact_paths,
    data_paths,
    get_city,
)
from app.data import load_actuals  # noqa: E402
from app.features import build_lead_dataset, split_dates  # noqa: E402
from app.models import (  # noqa: E402
    ensemble_prediction,
    fit_base_models,
    predict_base_models,
    recency_weights,
    select_ensemble,
)
from app.training import _fit_production_model  # noqa: E402

LONG_LEADS = tuple(range(8, 15))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Дообучение на 8–14 дней")
    parser.add_argument("--city", choices=sorted(CITIES), help="Только один город")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slugs = [args.city] if args.city else list(CITIES)
    for slug in slugs:
        city = get_city(slug)
        paths = data_paths(slug)
        model_dir = artifact_paths(slug)["models"]
        actuals = load_actuals(paths["actuals"]).sort_index()
        periods = split_dates(actuals.index, TEST_DAYS, VALID_DAYS)
        train_start, train_end = periods["train"]
        valid_start, valid_end = periods["validation"]
        print(f"\n=== {city['name']} ===")
        for lead in LONG_LEADS:
            X, y = build_lead_dataset(actuals, lead)
            complete = X.notna().all(axis=1) & y.notna()
            index = X.index
            train_mask = complete & (index >= train_start) & (index <= train_end)
            valid_mask = complete & (index >= valid_start) & (index <= valid_end)
            if train_mask.sum() < 120 or valid_mask.sum() < 14:
                raise ValueError(f"Мало данных для h={lead}")
            X_train, y_train = X.loc[train_mask], y.loc[train_mask]
            X_valid, y_valid = X.loc[valid_mask], y.loc[valid_mask]
            models = fit_base_models(
                X_train,
                y_train,
                sample_weight=recency_weights(X_train.index, SAMPLE_WEIGHT_HALF_LIFE_DAYS),
            )
            predictions = predict_base_models(models, X_valid)
            choice = select_ensemble(predictions, y_valid)
            validation_mae = float(
                np.mean(np.abs(ensemble_prediction(predictions, choice["weights"]) - y_valid.to_numpy()))
            )
            path = _fit_production_model(
                X,
                y,
                weights=choice["weights"],
                lead=lead,
                validation_mae=round(validation_mae, 3),
                location=city,
                model_dir=model_dir,
            )
            print(f"  h={lead}: MAE(valid) {validation_mae:.2f} → {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
