"""Обучение моделей, честный бэктест и сохранение артефактов."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from .config import (
    ARTIFACT_DIR,
    DEFAULT_CITY,
    LEADS,
    MODEL_ORDER,
    SAMPLE_WEIGHT_HALF_LIFE_DAYS,
    TEST_DAYS,
    VALID_DAYS,
    artifact_paths,
    data_paths,
    get_city,
)
from .data import load_meta
from .features import build_lead_dataset, split_dates
from .models import (
    cluster_bootstrap_mae_difference,
    ensemble_prediction,
    fit_base_models,
    predict_base_models,
    recency_weights,
    regression_metrics,
    select_ensemble,
)
from .reporting import make_chart


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _fit_production_model(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    weights: dict[str, float],
    lead: int,
    validation_mae: float,
    location: dict[str, object],
    model_dir: Path,
) -> Path:
    mask = X.notna().all(axis=1) & y.notna()
    X_fit = X.loc[mask]
    y_fit = y.loc[mask]
    sample_weight = recency_weights(X_fit.index, SAMPLE_WEIGHT_HALF_LIFE_DAYS)
    models = fit_base_models(X_fit, y_fit, sample_weight=sample_weight)
    payload = {
        "lead": lead,
        "target": "tmax",
        "models": models,
        "weights": weights,
        "feature_columns": list(X.columns),
        "trained_from": X_fit.index.min().date().isoformat(),
        "trained_through": X_fit.index.max().date().isoformat(),
        "training_rows": int(len(X_fit)),
        "sample_weight_half_life_days": SAMPLE_WEIGHT_HALF_LIFE_DAYS,
        "validation_mae": validation_mae,
        "location": location,
        "target_definition": "Дневной максимум температуры на 2 м, °C",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / f"lead_{lead}.joblib"
    joblib.dump(payload, path, compress=3)
    return path


def train_pipeline(
    actuals: pd.DataFrame,
    official: pd.DataFrame,
    *,
    city_slug: str = DEFAULT_CITY,
    test_days: int = TEST_DAYS,
    valid_days: int = VALID_DAYS,
) -> dict[str, Any]:
    if actuals.empty:
        raise ValueError("Нет фактических данных")
    city = get_city(city_slug)
    dpaths = data_paths(city_slug)
    apaths = artifact_paths(city_slug)
    model_dir = apaths["models"]
    actuals = actuals.sort_index()
    official = official.sort_index() if not official.empty else official

    periods = split_dates(actuals.index, test_days, valid_days)
    test_start, test_end = periods["test"]
    valid_start, valid_end = periods["validation"]
    train_start, train_end = periods["train"]

    lead_results: dict[str, Any] = {}
    prediction_frames: list[pd.DataFrame] = []
    period_rows: dict[str, int] = {}
    train_target_dates: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    for lead in LEADS:
        X, y = build_lead_dataset(actuals, lead)
        complete = X.notna().all(axis=1) & y.notna()
        index = X.index

        train_mask = complete & (index >= train_start) & (index <= train_end)
        valid_mask = complete & (index >= valid_start) & (index <= valid_end)
        test_mask = complete & (index >= test_start) & (index <= test_end)
        if train_mask.sum() < 120:
            raise ValueError(
                f"Слишком мало обучающих примеров для h={lead}: {int(train_mask.sum())}. "
                "Загрузите больше истории."
            )
        if valid_mask.sum() < 14 or test_mask.sum() < 14:
            raise ValueError(
                f"Слишком короткие validation/test для h={lead}: "
                f"{int(valid_mask.sum())}/{int(test_mask.sum())}."
            )

        X_train, y_train = X.loc[train_mask], y.loc[train_mask]
        X_valid, y_valid = X.loc[valid_mask], y.loc[valid_mask]
        X_test, y_test = X.loc[test_mask], y.loc[test_mask]

        models = fit_base_models(
            X_train,
            y_train,
            sample_weight=recency_weights(
                X_train.index, SAMPLE_WEIGHT_HALF_LIFE_DAYS
            ),
        )
        valid_predictions = predict_base_models(models, X_valid)
        ensemble_choice = select_ensemble(valid_predictions, y_valid)
        weights = ensemble_choice["weights"]
        valid_ensemble = ensemble_prediction(valid_predictions, weights)
        validation_mae = float(np.mean(np.abs(valid_ensemble - y_valid.to_numpy())))

        test_predictions = predict_base_models(models, X_test)
        test_ensemble = ensemble_prediction(test_predictions, weights)

        result = pd.DataFrame({"fact": y_test.to_numpy()}, index=X_test.index)
        for name in MODEL_ORDER:
            result[name] = test_predictions[name]
        result["ensemble"] = test_ensemble
        result["persistence"] = X_test["tmax_lag1"].to_numpy()

        official_column = f"official_tmax_h{lead}"
        if official_column in official.columns:
            result["official"] = official[official_column].reindex(result.index)
        else:
            result["official"] = np.nan

        common = result.dropna(subset=["fact", "official"])
        if common.empty:
            common = result.copy()

        lead_models_metrics = {
            name: regression_metrics(common["fact"], common[name])
            for name in (*MODEL_ORDER, "ensemble", "persistence")
        }
        if common["official"].notna().any():
            lead_models_metrics["official"] = regression_metrics(
                common["fact"], common["official"]
            )
            lead_models_metrics["persistence"] = regression_metrics(
                common["fact"], common["persistence"]
            )

        lead_results[str(lead)] = {
            "n_test": int(len(result)),
            "n_common_with_official": int(len(common)),
            "test_start": result.index.min().date().isoformat(),
            "test_end": result.index.max().date().isoformat(),
            "weights": weights,
            "ensemble_method": ensemble_choice["method"],
            "ensemble_validation_scores": ensemble_choice["validation_scores"],
            "validation_mae_ensemble": round(validation_mae, 3),
            "models": lead_models_metrics,
        }

        production_path = _fit_production_model(
            X,
            y,
            weights=weights,
            lead=lead,
            validation_mae=round(validation_mae, 3),
            location=city,
            model_dir=model_dir,
        )
        lead_results[str(lead)]["production_model"] = str(
            production_path.relative_to(ARTIFACT_DIR.parent)
        )

        period_rows[f"lead_{lead}"] = {
            "train": int(train_mask.sum()),
            "validation": int(valid_mask.sum()),
            "test": int(test_mask.sum()),
        }
        train_target_dates.append(
            (index[train_mask].min(), index[train_mask].max())
        )
        prediction_frames.append(
            result.assign(date=result.index, lead=lead).reset_index(drop=True)
        )

    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions["date"] = pd.to_datetime(predictions["date"]).dt.normalize()
    predictions = predictions.sort_values(["date", "lead"]).reset_index(drop=True)
    for column in (
        "fact",
        *MODEL_ORDER,
        "ensemble",
        "persistence",
        "official",
    ):
        predictions[column] = predictions[column].astype(float).round(3)

    comparison_rows = predictions.dropna(subset=["fact", "official"]).copy()
    if comparison_rows.empty:
        comparison_rows = predictions.copy()

    overall: dict[str, dict[str, Any]] = {}
    for name in (*MODEL_ORDER, "ensemble", "persistence"):
        overall[name] = regression_metrics(
            comparison_rows["fact"], comparison_rows[name]
        )
    if comparison_rows["official"].notna().any():
        overall["official"] = regression_metrics(
            comparison_rows["fact"], comparison_rows["official"]
        )

    bootstrap = cluster_bootstrap_mae_difference(comparison_rows)
    ensemble_mae = overall["ensemble"]["mae"]
    official_mae = overall.get("official", {}).get("mae")
    skill = None
    beats = None
    if official_mae is not None and official_mae > 0:
        skill = round((official_mae - ensemble_mae) / official_mae * 100.0, 1)
        beats = bool(ensemble_mae < official_mae)

    candidates = {name: overall[name]["mae"] for name in (*MODEL_ORDER, "ensemble")}
    best_model = min(candidates, key=candidates.get)

    effective_train_dates = train_target_dates
    train_effective_start = min(item[0] for item in effective_train_dates)
    train_effective_end = max(item[1] for item in effective_train_dates)

    test_period = (
        comparison_rows["date"].min().date().isoformat(),
        comparison_rows["date"].max().date().isoformat(),
    )
    actuals_meta = load_meta(dpaths["actuals_meta"])
    official_meta = load_meta(dpaths["official_meta"])

    metrics: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "app": {
            "name": "Погодный оракул",
            "target": "Дневной максимум температуры на 2 м",
            "unit": "°C",
            "leads": list(LEADS),
        },
        "location": city,
        "data": {
            "actuals": actuals_meta,
            "official": official_meta,
            "first_actual_date": actuals.index.min().date().isoformat(),
            "last_actual_date": actuals.index.max().date().isoformat(),
            "actual_days": int(len(actuals)),
            "official_days": int(len(official)),
        },
        "periods": {
            "train": {
                "start": train_effective_start.date().isoformat(),
                "end": train_effective_end.date().isoformat(),
                "days": int((train_effective_end - train_effective_start).days + 1),
            },
            "validation": {
                "start": valid_start.date().isoformat(),
                "end": valid_end.date().isoformat(),
                "days": valid_days,
            },
            "test": {
                "start": test_start.date().isoformat(),
                "end": test_end.date().isoformat(),
                "days": test_days,
            },
            "targets_per_lead": period_rows,
        },
        "leads": lead_results,
        "overall": overall,
        "headline": {
            "ensemble_mae": ensemble_mae,
            "official_mae": official_mae,
            "delta_mae": bootstrap["delta_mae"],
            "ci95_low": bootstrap["ci95_low"],
            "ci95_high": bootstrap["ci95_high"],
            "probability_better": bootstrap["probability_better"],
            "skill_vs_official_pct": skill,
            "beats_official": beats,
            "best_model": best_model,
            "n_dates": bootstrap["n_dates"],
            "n_rows": bootstrap["n_rows"],
            "bootstrap_iterations": bootstrap["iterations"],
        },
        "methodology": {
            "split": "chronological holdout: train → validation → test",
            "sample_weighting": (
                f"экспоненциальные веса свежести, период полураспада "
                f"{SAMPLE_WEIGHT_HALF_LIFE_DAYS} дней"
            ),
            "ensemble_weights": "способ и веса выбраны только по validation",
            "test_usage": "тест не использовался для обучения и подбора весов",
            "official_baseline": (
                "Open-Meteo Previous Runs API: прогноз, выпущенный за 1–7 дней до целевой даты"
            ),
            "fair_comparison": "метрики на общих датах, где доступен официальный прогноз",
            "uncertainty": "парный cluster bootstrap по датам, 95% интервал",
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    apaths["metrics"].parent.mkdir(parents=True, exist_ok=True)
    apaths["metrics"].write_text(
        json.dumps(_json_safe(metrics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    export_columns = [
        "date",
        "lead",
        "fact",
        "linear",
        "random_forest",
        "gradient_boosting",
        "ensemble",
        "official",
        "persistence",
    ]
    predictions[export_columns].to_csv(
        apaths["predictions"],
        index=False,
        encoding="utf-8",
        date_format="%Y-%m-%d",
    )

    make_chart(
        predictions,
        overall,
        location_name=str(city["name"]),
        path=apaths["chart"],
        test_period=test_period,
    )
    return _json_safe(metrics)
