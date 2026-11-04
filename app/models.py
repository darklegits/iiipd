"""Модели, ансамбль и метрики качества."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from joblib import parallel_backend
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import MODEL_ORDER, RANDOM_STATE


def make_estimator(name: str, random_state: int = RANDOM_STATE):
    if name == "linear":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LinearRegression()),
            ]
        )
    if name == "random_forest":
        return RandomForestRegressor(
            n_estimators=400,
            max_depth=12,
            min_samples_leaf=3,
            max_features=0.8,
            random_state=random_state,
            n_jobs=1,
        )
    if name == "gradient_boosting":
        return GradientBoostingRegressor(
            n_estimators=320,
            learning_rate=0.05,
            max_depth=3,
            min_samples_leaf=4,
            subsample=0.85,
            random_state=random_state,
        )
    raise ValueError(f"Неизвестная модель: {name}")


def fit_base_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    sample_weight: np.ndarray | pd.Series | None = None,
    random_state: int = RANDOM_STATE,
) -> dict[str, object]:
    models: dict[str, object] = {}
    for name in MODEL_ORDER:
        estimator = make_estimator(name, random_state=random_state)
        # Sequential backend: не создаём пулы процессов/сокеты и одинаково
        # ведём себя в обычном окружении и в ограниченной песочнице.
        with parallel_backend("sequential"):
            if sample_weight is None:
                estimator.fit(X_train, y_train)
            elif name == "linear":
                estimator.fit(X_train, y_train, model__sample_weight=sample_weight)
            else:
                estimator.fit(X_train, y_train, sample_weight=sample_weight)
        models[name] = estimator
    return models


def recency_weights(index: pd.DatetimeIndex, half_life_days: float) -> np.ndarray:
    """Экспоненциально убывающие веса: свежие наблюдения важнее старых."""

    age_days = (pd.Timestamp(index.max()) - pd.DatetimeIndex(index)).days.to_numpy(
        dtype=float
    )
    return 0.5 ** (age_days / float(half_life_days))


def predict_base_models(
    models: Mapping[str, object], X: pd.DataFrame
) -> dict[str, np.ndarray]:
    return {name: np.asarray(model.predict(X), dtype=float) for name, model in models.items()}


def optimize_weights(
    predictions: Mapping[str, np.ndarray],
    y_true: pd.Series | np.ndarray,
    *,
    step: float = 0.02,
) -> dict[str, float]:
    """Неотрицательные веса, минимизирующие MAE на validation."""

    y = np.asarray(y_true, dtype=float)
    matrix = np.column_stack([predictions[name] for name in MODEL_ORDER])
    best_weights = np.array([1.0 / len(MODEL_ORDER)] * len(MODEL_ORDER))
    best_mae = float(mean_absolute_error(y, matrix @ best_weights))

    grid = np.arange(0.0, 1.0 + step / 2.0, step)
    for first in grid:
        for second in grid:
            third = 1.0 - first - second
            if third < -1e-9:
                continue
            weights = np.array([first, second, max(0.0, third)])
            mae = float(mean_absolute_error(y, matrix @ weights))
            if mae < best_mae - 1e-9:
                best_mae = mae
                best_weights = weights

    best_weights = best_weights / best_weights.sum()
    return {
        name: round(float(weight), 4)
        for name, weight in zip(MODEL_ORDER, best_weights, strict=True)
    }


def ensemble_prediction(
    predictions: Mapping[str, np.ndarray], weights: Mapping[str, float]
) -> np.ndarray:
    result = np.zeros_like(np.asarray(next(iter(predictions.values())), dtype=float))
    for name in MODEL_ORDER:
        result += float(weights.get(name, 0.0)) * np.asarray(predictions[name], dtype=float)
    return result


def select_ensemble(
    predictions: Mapping[str, np.ndarray],
    y_true: pd.Series | np.ndarray,
) -> dict[str, object]:
    """Выбирает способ ансамблирования по validation, а не по тесту."""

    y = np.asarray(y_true, dtype=float)
    equal = {name: round(1.0 / len(MODEL_ORDER), 4) for name in MODEL_ORDER}
    maes = {
        name: float(mean_absolute_error(y, predictions[name])) for name in MODEL_ORDER
    }
    inverse_raw = {name: 1.0 / max(maes[name], 1e-6) for name in MODEL_ORDER}
    inverse_total = sum(inverse_raw.values())
    inverse = {
        name: round(value / inverse_total, 4) for name, value in inverse_raw.items()
    }
    optimized = optimize_weights(predictions, y)

    candidates = {
        "equal": equal,
        "inverse_mae": inverse,
        "optimized_mae": optimized,
    }
    scores: dict[str, float] = {}
    for method, weights in candidates.items():
        prediction = ensemble_prediction(predictions, weights)
        scores[method] = round(float(mean_absolute_error(y, prediction)), 3)
    best_method = min(scores, key=scores.get)
    return {
        "method": best_method,
        "weights": candidates[best_method],
        "validation_scores": scores,
    }


def regression_metrics(
    y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray
) -> dict[str, float | int]:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(y) & np.isfinite(p)
    y, p = y[mask], p[mask]
    if len(y) == 0:
        return {"mae": float("nan"), "rmse": float("nan"), "bias": float("nan"), "r2": float("nan"), "n": 0}
    metrics: dict[str, float | int] = {
        "mae": round(float(mean_absolute_error(y, p)), 3),
        "rmse": round(float(np.sqrt(mean_squared_error(y, p))), 3),
        "bias": round(float(np.mean(p - y)), 3),
        "n": int(len(y)),
    }
    if len(y) > 2 and np.var(y) > 1e-12:
        metrics["r2"] = round(float(r2_score(y, p)), 3)
    else:
        metrics["r2"] = None
    return metrics


def cluster_bootstrap_mae_difference(
    rows: pd.DataFrame,
    *,
    model_column: str = "ensemble",
    baseline_column: str = "official",
    iterations: int = 3000,
    seed: int = RANDOM_STATE,
) -> dict[str, float | list[float] | int]:
    """Парный bootstrap по датам: насколько MAE модели отличается от baseline.

    Отрицательная разница означает, что модель точнее. Ресемплируем целые даты,
    чтобы не терять корреляцию между тремя горизонтами одной даты.
    """

    data = rows.dropna(subset=[model_column, baseline_column, "fact"]).copy()
    if data.empty:
        return {
            "delta_mae": float("nan"),
            "ci95_low": float("nan"),
            "ci95_high": float("nan"),
            "probability_better": float("nan"),
            "n_dates": 0,
            "n_rows": 0,
            "iterations": iterations,
        }
    data["_delta_abs"] = (data[model_column] - data["fact"]).abs() - (
        data[baseline_column] - data["fact"]
    ).abs()
    grouped = data.groupby(data["date"].dt.normalize()).agg(
        delta_sum=("_delta_abs", "sum"),
        count=("_delta_abs", "size"),
    )
    observed = float(grouped["delta_sum"].sum() / grouped["count"].sum())

    rng = np.random.default_rng(seed)
    sums = grouped["delta_sum"].to_numpy(dtype=float)
    counts = grouped["count"].to_numpy(dtype=float)
    n_dates = len(grouped)
    boot = np.empty(iterations, dtype=float)
    for i in range(iterations):
        idx = rng.integers(0, n_dates, size=n_dates)
        boot[i] = sums[idx].sum() / counts[idx].sum()

    return {
        "delta_mae": round(observed, 3),
        "ci95_low": round(float(np.quantile(boot, 0.025)), 3),
        "ci95_high": round(float(np.quantile(boot, 0.975)), 3),
        "probability_better": round(float(np.mean(boot < 0.0)), 3),
        "n_dates": int(n_dates),
        "n_rows": int(len(data)),
        "iterations": iterations,
    }
