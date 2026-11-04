"""Конфигурация проекта «Погодный оракул»."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("ORACLE_DATA_DIR", str(BASE_DIR / "data")))
RAW_DIR = DATA_DIR / "raw"
CITY_DATA_DIR = DATA_DIR / "cities"
ARTIFACT_DIR = BASE_DIR / "artifacts"
MODEL_DIR = ARTIFACT_DIR / "models"
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

APP_NAME = "Погодный оракул"
APP_SUBTITLE = "Ансамбль моделей для прогноза температуры по открытым данным"

CITIES: dict[str, dict[str, object]] = {
    "ekaterinburg": {
        "name": "Екатеринбург",
        "name_genitive": "Екатеринбурга",
        "latitude": 56.8389,
        "longitude": 60.6057,
        "timezone": "Asia/Yekaterinburg",
    },
    "chelyabinsk": {
        "name": "Челябинск",
        "name_genitive": "Челябинска",
        "latitude": 55.1644,
        "longitude": 61.4368,
        "timezone": "Asia/Yekaterinburg",
    },
    "tyumen": {
        "name": "Тюмень",
        "name_genitive": "Тюмени",
        "latitude": 57.1522,
        "longitude": 65.5272,
        "timezone": "Asia/Yekaterinburg",
    },
    "kurgan": {
        "name": "Курган",
        "name_genitive": "Кургана",
        "latitude": 55.4408,
        "longitude": 65.3411,
        "timezone": "Asia/Yekaterinburg",
    },
    "ufa": {
        "name": "Уфа",
        "name_genitive": "Уфы",
        "latitude": 54.7388,
        "longitude": 55.9721,
        "timezone": "Asia/Yekaterinburg",
    },
    "orenburg": {
        "name": "Оренбург",
        "name_genitive": "Оренбурга",
        "latitude": 51.7682,
        "longitude": 55.0979,
        "timezone": "Asia/Yekaterinburg",
    },
    "magnitogorsk": {
        "name": "Магнитогорск",
        "name_genitive": "Магнитогорска",
        "latitude": 53.4186,
        "longitude": 59.0472,
        "timezone": "Asia/Yekaterinburg",
    },
    "nizhny_tagil": {
        "name": "Нижний Тагил",
        "name_genitive": "Нижнего Тагила",
        "latitude": 57.9101,
        "longitude": 59.9813,
        "timezone": "Asia/Yekaterinburg",
    },
    "surgut": {
        "name": "Сургут",
        "name_genitive": "Сургута",
        "latitude": 61.2540,
        "longitude": 73.3962,
        "timezone": "Asia/Yekaterinburg",
    },
    "moscow": {
        "name": "Москва",
        "name_genitive": "Москвы",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "timezone": "Europe/Moscow",
    },
    "spb": {
        "name": "Санкт-Петербург",
        "name_genitive": "Санкт-Петербурга",
        "latitude": 59.9343,
        "longitude": 30.3351,
        "timezone": "Europe/Moscow",
    },
    "novosibirsk": {
        "name": "Новосибирск",
        "name_genitive": "Новосибирска",
        "latitude": 55.0084,
        "longitude": 82.9357,
        "timezone": "Asia/Novosibirsk",
    },
    "kazan": {
        "name": "Казань",
        "name_genitive": "Казани",
        "latitude": 55.7961,
        "longitude": 49.1064,
        "timezone": "Europe/Moscow",
    },
    "sochi": {
        "name": "Сочи",
        "name_genitive": "Сочи",
        "latitude": 43.5855,
        "longitude": 39.7231,
        "timezone": "Europe/Moscow",
    },
}
for _slug, _city in CITIES.items():
    _city["slug"] = _slug

CITY_GROUPS = (
    {
        "label": "Урал · МСК+2",
        "slugs": (
            "ekaterinburg",
            "chelyabinsk",
            "tyumen",
            "kurgan",
            "ufa",
            "orenburg",
            "magnitogorsk",
            "nizhny_tagil",
            "surgut",
        ),
    },
    {
        "label": "Другие города",
        "slugs": ("moscow", "spb", "novosibirsk", "kazan", "sochi"),
    },
)

DEFAULT_CITY = "ekaterinburg"
LOCATION = CITIES[DEFAULT_CITY]


def get_city(slug: str | None = None) -> dict[str, object]:
    key = (slug or DEFAULT_CITY).strip().lower()
    if key not in CITIES:
        raise ValueError(f"Неизвестный город: {slug}")
    return CITIES[key]


def city_data_dir(slug: str) -> Path:
    return CITY_DATA_DIR / slug


def city_artifact_dir(slug: str) -> Path:
    return ARTIFACT_DIR / slug


def city_model_dir(slug: str) -> Path:
    return ARTIFACT_DIR / "models" / slug


def data_paths(slug: str) -> dict[str, Path]:
    root = city_data_dir(slug)
    return {
        "actuals": root / "actuals.csv",
        "actuals_meta": root / "actuals_meta.json",
        "official": root / "official_forecasts.csv",
        "official_meta": root / "official_forecasts_meta.json",
    }


def artifact_paths(slug: str) -> dict[str, Path]:
    root = city_artifact_dir(slug)
    return {
        "metrics": root / "metrics.json",
        "predictions": root / "predictions.csv",
        "chart": root / "forecast_vs_fact.png",
        "models": city_model_dir(slug),
    }


# Совместимость с одно-городними модулями и старыми артефактами.
ACTUALS_PATH = data_paths(DEFAULT_CITY)["actuals"]
ACTUALS_META_PATH = data_paths(DEFAULT_CITY)["actuals_meta"]
OFFICIAL_PATH = data_paths(DEFAULT_CITY)["official"]
OFFICIAL_META_PATH = data_paths(DEFAULT_CITY)["official_meta"]
METRICS_PATH = artifact_paths(DEFAULT_CITY)["metrics"]
PREDICTIONS_PATH = artifact_paths(DEFAULT_CITY)["predictions"]
CHART_PATH = artifact_paths(DEFAULT_CITY)["chart"]

for _directory in (DATA_DIR, RAW_DIR, CITY_DATA_DIR, ARTIFACT_DIR, MODEL_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

LEADS = tuple(range(1, 15))
OFFICIAL_LEADS = tuple(range(1, 8))
TARGET_COLUMN = "tmax"
RANDOM_STATE = 42

# Хронологический бэктест: 45 дней теста, 30 дней валидации, остальное — обучение.
TEST_DAYS = 45
VALID_DAYS = 30
SAMPLE_WEIGHT_HALF_LIFE_DAYS = 365
DEFAULT_HISTORY_DAYS = 365

MODEL_ORDER = ("linear", "random_forest", "gradient_boosting")
MODEL_LABELS = {
    "linear": "Линейная регрессия",
    "random_forest": "Случайный лес",
    "gradient_boosting": "Градиентный бустинг",
    "ensemble": "Ансамбль",
    "official": "Официальный прогноз",
    "persistence": "Инерция",
}

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_ACTUALS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "weather_code",
    "wind_speed_10m_max",
    "surface_pressure_mean",
    "relative_humidity_2m_mean",
    "cloud_cover_mean",
    "dew_point_2m_mean",
    "wind_direction_10m_dominant",
    "shortwave_radiation_sum",
    "apparent_temperature_mean",
)
