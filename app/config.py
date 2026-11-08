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
    _city["modeled"] = True

# Города России без обученных ML-моделей. Для них доступен живой прогноз
# Яндекс.Погоды и спортивные рекомендации, но нет бэктеста и страниц
# «Сравнение»/«Модели»: для обучения нужна история Open-Meteo.
CITY_CATALOG: dict[str, dict[str, object]] = {
    "volgograd": {"name": "Волгоград", "latitude": 48.708, "longitude": 44.5133, "timezone": "Europe/Volgograd", "yandex": "volgograd"},
    "voronezh": {"name": "Воронеж", "latitude": 51.6608, "longitude": 39.2003, "timezone": "Europe/Moscow", "yandex": "voronezh"},
    "krasnodar": {"name": "Краснодар", "latitude": 45.0355, "longitude": 38.9753, "timezone": "Europe/Moscow", "yandex": "krasnodar"},
    "rostov_na_donu": {"name": "Ростов-на-Дону", "latitude": 47.2225, "longitude": 39.7188, "timezone": "Europe/Moscow", "yandex": "rostov-na-donu"},
    "krasnoyarsk": {"name": "Красноярск", "latitude": 56.0106, "longitude": 92.8526, "timezone": "Asia/Krasnoyarsk", "yandex": "krasnoyarsk"},
    "perm": {"name": "Пермь", "latitude": 58.0105, "longitude": 56.2502, "timezone": "Asia/Yekaterinburg", "yandex": "perm"},
    "saratov": {"name": "Саратов", "latitude": 51.5336, "longitude": 46.0343, "timezone": "Europe/Saratov", "yandex": "saratov"},
    "tolyatti": {"name": "Тольятти", "latitude": 53.5303, "longitude": 49.3461, "timezone": "Europe/Samara", "yandex": "tolyatti"},
    "izhevsk": {"name": "Ижевск", "latitude": 56.8527, "longitude": 53.2115, "timezone": "Europe/Samara", "yandex": "izhevsk"},
    "barnaul": {"name": "Барнаул", "latitude": 53.3548, "longitude": 83.7698, "timezone": "Asia/Barnaul", "yandex": "barnaul"},
    "ulyanovsk": {"name": "Ульяновск", "latitude": 54.3142, "longitude": 48.4031, "timezone": "Europe/Ulyanovsk", "yandex": "ulyanovsk"},
    "irkutsk": {"name": "Иркутск", "latitude": 52.2871, "longitude": 104.305, "timezone": "Asia/Irkutsk", "yandex": "irkutsk"},
    "khabarovsk": {"name": "Хабаровск", "latitude": 48.4827, "longitude": 135.0838, "timezone": "Asia/Vladivostok", "yandex": "khabarovsk"},
    "vladivostok": {"name": "Владивосток", "latitude": 43.1155, "longitude": 131.8855, "timezone": "Asia/Vladivostok", "yandex": "vladivostok"},
    "yaroslavl": {"name": "Ярославль", "latitude": 57.6261, "longitude": 39.8845, "timezone": "Europe/Moscow", "yandex": "yaroslavl"},
    "makhachkala": {"name": "Махачкала", "latitude": 42.9849, "longitude": 47.5047, "timezone": "Europe/Moscow", "yandex": "makhachkala"},
    "tomsk": {"name": "Томск", "latitude": 56.4846, "longitude": 84.9476, "timezone": "Asia/Tomsk", "yandex": "tomsk"},
    "omsk": {"name": "Омск", "latitude": 54.9885, "longitude": 73.3242, "timezone": "Asia/Omsk", "yandex": "omsk"},
    "kemerovo": {"name": "Кемерово", "latitude": 55.3547, "longitude": 86.0873, "timezone": "Asia/Novokuznetsk", "yandex": "kemerovo"},
    "novokuznetsk": {"name": "Новокузнецк", "latitude": 53.7557, "longitude": 87.1099, "timezone": "Asia/Novokuznetsk", "yandex": "novokuznetsk"},
    "ryazan": {"name": "Рязань", "latitude": 54.6269, "longitude": 39.6916, "timezone": "Europe/Moscow", "yandex": "ryazan"},
    "astrakhan": {"name": "Астрахань", "latitude": 46.3497, "longitude": 48.0408, "timezone": "Europe/Astrakhan", "yandex": "astrakhan"},
    "penza": {"name": "Пенза", "latitude": 53.1959, "longitude": 45.0183, "timezone": "Europe/Moscow", "yandex": "penza"},
    "lipetsk": {"name": "Липецк", "latitude": 52.6031, "longitude": 39.5708, "timezone": "Europe/Moscow", "yandex": "lipetsk"},
    "kirov": {"name": "Киров", "latitude": 58.6035, "longitude": 49.6679, "timezone": "Europe/Kirov", "yandex": "kirov"},
    "cheboksary": {"name": "Чебоксары", "latitude": 56.1439, "longitude": 47.2489, "timezone": "Europe/Moscow", "yandex": "cheboksary"},
    "tula": {"name": "Тула", "latitude": 54.1961, "longitude": 37.6182, "timezone": "Europe/Moscow", "yandex": "tula"},
    "kaliningrad": {"name": "Калининград", "latitude": 54.7104, "longitude": 20.4522, "timezone": "Europe/Kaliningrad", "yandex": "kaliningrad"},
    "kursk": {"name": "Курск", "latitude": 51.7304, "longitude": 36.1926, "timezone": "Europe/Moscow", "yandex": "kursk"},
    "stavropol": {"name": "Ставрополь", "latitude": 45.0428, "longitude": 41.9734, "timezone": "Europe/Moscow", "yandex": "stavropol"},
    "ulan_ude": {"name": "Улан-Удэ", "latitude": 51.8335, "longitude": 107.5841, "timezone": "Asia/Irkutsk", "yandex": "ulan-ude"},
    "tver": {"name": "Тверь", "latitude": 56.8587, "longitude": 35.9176, "timezone": "Europe/Moscow", "yandex": "tver"},
    "bryansk": {"name": "Брянск", "latitude": 53.2434, "longitude": 34.3639, "timezone": "Europe/Moscow", "yandex": "bryansk"},
    "ivanovo": {"name": "Иваново", "latitude": 57.0004, "longitude": 40.9739, "timezone": "Europe/Moscow", "yandex": "ivanovo"},
    "belgorod": {"name": "Белгород", "latitude": 50.5952, "longitude": 36.5873, "timezone": "Europe/Moscow", "yandex": "belgorod"},
    "vladimir": {"name": "Владимир", "latitude": 56.129, "longitude": 40.407, "timezone": "Europe/Moscow", "yandex": "vladimir"},
    "arkhangelsk": {"name": "Архангельск", "latitude": 64.5393, "longitude": 40.5182, "timezone": "Europe/Moscow", "yandex": "arkhangelsk"},
    "chita": {"name": "Чита", "latitude": 52.034, "longitude": 113.4994, "timezone": "Asia/Chita", "yandex": "chita"},
    "kaluga": {"name": "Калуга", "latitude": 54.5138, "longitude": 36.2612, "timezone": "Europe/Moscow", "yandex": "kaluga"},
    "smolensk": {"name": "Смоленск", "latitude": 54.7818, "longitude": 32.0401, "timezone": "Europe/Moscow", "yandex": "smolensk"},
    "volzhsky": {"name": "Волжский", "latitude": 48.7861, "longitude": 44.7797, "timezone": "Europe/Volgograd", "yandex": "volzhskiy"},
    "oryol": {"name": "Орёл", "latitude": 52.9651, "longitude": 36.0785, "timezone": "Europe/Moscow", "yandex": "oryol"},
    "cherepovets": {"name": "Череповец", "latitude": 59.1269, "longitude": 37.9098, "timezone": "Europe/Moscow", "yandex": "cherepovets"},
    "vologda": {"name": "Вологда", "latitude": 59.2205, "longitude": 39.8915, "timezone": "Europe/Moscow", "yandex": "vologda"},
    "murmansk": {"name": "Мурманск", "latitude": 68.9585, "longitude": 33.0827, "timezone": "Europe/Moscow", "yandex": "murmansk"},
    "petrozavodsk": {"name": "Петрозаводск", "latitude": 61.7849, "longitude": 34.3469, "timezone": "Europe/Moscow", "yandex": "petrozavodsk"},
    "nizhny_novgorod": {"name": "Нижний Новгород", "latitude": 56.3269, "longitude": 44.0059, "timezone": "Europe/Moscow", "yandex": "nizhniy-novgorod"},
    "samara": {"name": "Самара", "latitude": 53.1959, "longitude": 50.1002, "timezone": "Europe/Samara", "yandex": "samara"},
    "yakutsk": {"name": "Якутск", "latitude": 62.0355, "longitude": 129.6755, "timezone": "Asia/Yakutsk", "yandex": "yakutsk"},
    "norilsk": {"name": "Норильск", "latitude": 69.3535, "longitude": 88.2027, "timezone": "Asia/Krasnoyarsk", "yandex": "norilsk"},
    "yuzhno_sakhalinsk": {"name": "Южно-Сахалинск", "latitude": 46.9591, "longitude": 142.738, "timezone": "Asia/Sakhalin", "yandex": "yuzhno-sakhalinsk"},
}
for _slug, _city in CITY_CATALOG.items():
    _city["slug"] = _slug
    _city["modeled"] = False

ALL_CITIES: dict[str, dict[str, object]] = {**CITIES, **CITY_CATALOG}

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
    if key not in ALL_CITIES:
        raise ValueError(f"Неизвестный город: {slug}")
    return ALL_CITIES[key]


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
