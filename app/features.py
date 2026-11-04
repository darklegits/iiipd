"""Признаки для прогноза дневной максимальной температуры.

Все признаки для целевой даты t и горизонта h используют наблюдения только
до дня t - h - 1 включительно. Это соответствует прогнозу, выпущенному в
00:00 дня t - h: последний полностью известный день — предыдущий.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LEADS, TARGET_COLUMN


def _seasonal_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    day_of_year = index.dayofyear.to_numpy(dtype=float)
    angle = 2.0 * np.pi * (day_of_year - 1.0) / 365.25
    return pd.DataFrame(
        {
            "season_sin": np.sin(angle),
            "season_cos": np.cos(angle),
            "season_sin2": np.sin(2.0 * angle),
            "season_cos2": np.cos(2.0 * angle),
        },
        index=index,
    )


def build_lead_dataset(
    frame: pd.DataFrame, lead: int
) -> tuple[pd.DataFrame, pd.Series]:
    """Матрица признаков и целевая температура для одного горизонта."""

    if lead not in LEADS:
        raise ValueError(f"Неподдерживаемый горизонт: {lead}")
    if TARGET_COLUMN not in frame.columns:
        raise ValueError(f"В данных нет колонки {TARGET_COLUMN}")

    data = frame.sort_index().copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)
    data.index = data.index.normalize()

    # Самый свежий известный день: t - lead - 1.
    latest_offset = lead + 1
    latest_tmax = data["tmax"].shift(latest_offset)
    latest_tmin = data["tmin"].shift(latest_offset)
    latest_precip = data["precip"].shift(latest_offset)

    features = pd.DataFrame(index=data.index)
    for lag in range(1, 8):
        features[f"tmax_lag{lag}"] = data["tmax"].shift(lead + lag)
    for lag in range(1, 4):
        features[f"tmin_lag{lag}"] = data["tmin"].shift(lead + lag)
        features[f"precip_lag{lag}"] = data["precip"].shift(lead + lag)

    features["tmax_mean_3"] = latest_tmax.rolling(3, min_periods=3).mean()
    features["tmax_mean_7"] = latest_tmax.rolling(7, min_periods=7).mean()
    features["tmax_mean_14"] = latest_tmax.rolling(14, min_periods=14).mean()
    features["tmax_std_7"] = latest_tmax.rolling(7, min_periods=7).std()
    features["tmin_mean_3"] = latest_tmin.rolling(3, min_periods=3).mean()
    features["tmax_trend_3"] = latest_tmax - data["tmax"].shift(lead + 4)
    features["tmax_trend_7"] = latest_tmax - data["tmax"].shift(lead + 8)
    features["diurnal_range"] = latest_tmax - latest_tmin
    features["freeze_flag"] = (latest_tmin <= 0.0).astype(float)
    features["precip_sum_3"] = latest_precip.rolling(3, min_periods=3).sum()
    features["precip_sum_7"] = latest_precip.rolling(7, min_periods=7).sum()

    if "pressure" in data.columns:
        latest_pressure = data["pressure"].shift(latest_offset)
        features["pressure_lag1"] = latest_pressure
        features["pressure_delta_3"] = latest_pressure - data["pressure"].shift(lead + 4)
        features["pressure_delta_7"] = latest_pressure - data["pressure"].shift(lead + 8)
    if "humidity" in data.columns:
        features["humidity_lag1"] = data["humidity"].shift(latest_offset)
    if "cloud" in data.columns:
        features["cloud_lag1"] = data["cloud"].shift(latest_offset)
    if "dewpoint" in data.columns:
        latest_dewpoint = data["dewpoint"].shift(latest_offset)
        features["dewpoint_lag1"] = latest_dewpoint
        features["dewpoint_depression"] = latest_tmax - latest_dewpoint
    if "radiation" in data.columns:
        features["radiation_lag1"] = data["radiation"].shift(latest_offset)
    if "apparent" in data.columns:
        features["apparent_lag1"] = data["apparent"].shift(latest_offset)
    if "wind_dir" in data.columns:
        wind_radians = np.deg2rad(data["wind_dir"].shift(latest_offset))
        features["wind_dir_sin"] = np.sin(wind_radians)
        features["wind_dir_cos"] = np.cos(wind_radians)
    if "wind_max" in data.columns:
        features["wind_lag1"] = data["wind_max"].shift(latest_offset)

    features = features.join(_seasonal_features(data.index))
    target = data[TARGET_COLUMN].rename("target")
    return features.astype(float), target.astype(float)


def feature_columns() -> list[str]:
    """Единый порядок признаков, который сохраняется вместе с моделями."""

    empty = pd.DataFrame(
        {
            "tmax": np.arange(40, dtype=float),
            "tmin": np.arange(40, dtype=float) - 5,
            "precip": np.zeros(40),
            "wind_max": np.ones(40),
            "pressure": np.linspace(1000, 1010, 40),
            "humidity": np.linspace(60, 80, 40),
            "cloud": np.linspace(20, 90, 40),
            "dewpoint": np.arange(40, dtype=float) - 8,
            "radiation": np.linspace(1, 10, 40),
            "apparent": np.arange(40, dtype=float) - 3,
            "wind_dir": np.linspace(0, 350, 40),
        },
        index=pd.date_range("2025-01-01", periods=40, freq="D"),
    )
    features, _ = build_lead_dataset(empty, 1)
    return list(features.columns)


FEATURE_COLUMNS = feature_columns()


def split_dates(
    index: pd.DatetimeIndex, test_days: int, valid_days: int
) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Хронологические границы train / validation / test."""

    if len(index) == 0:
        raise ValueError("Пустой индекс дат")
    end = pd.Timestamp(index.max()).normalize()
    test_start = end - pd.Timedelta(days=test_days - 1)
    valid_end = test_start - pd.Timedelta(days=1)
    valid_start = valid_end - pd.Timedelta(days=valid_days - 1)
    train_end = valid_start - pd.Timedelta(days=1)
    return {
        "train": (pd.Timestamp(index.min()).normalize(), train_end),
        "validation": (valid_start, valid_end),
        "test": (test_start, end),
    }


def future_frame(frame: pd.DataFrame, last_date: pd.Timestamp, days: int) -> pd.DataFrame:
    """Дополняет историю пустыми строками будущих дат для расчёта признаков."""

    last_date = pd.Timestamp(last_date).normalize()
    future_index = pd.date_range(last_date + pd.Timedelta(days=1), periods=days, freq="D")
    future = pd.DataFrame(index=future_index, columns=frame.columns, dtype=float)
    return pd.concat([frame, future]).sort_index()
