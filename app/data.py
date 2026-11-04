"""Загрузка открытых данных Open-Meteo и работа с локальным кэшем."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .config import (
    ACTUALS_PATH,
    ARCHIVE_URL,
    DAILY_ACTUALS,
    DEFAULT_CITY,
    DEFAULT_HISTORY_DAYS,
    FORECAST_URL,
    LOCATION,
    OFFICIAL_LEADS,
    OFFICIAL_PATH,
    PREVIOUS_RUNS_URL,
    data_paths,
)


class DataFetchError(RuntimeError):
    """Понятная ошибка загрузки внешних данных."""


def _timezone(timezone: str | None) -> str:
    return timezone or str(LOCATION["timezone"])


def local_today(timezone: str | None = None) -> date:
    return datetime.now(ZoneInfo(_timezone(timezone))).date()


def local_yesterday(timezone: str | None = None) -> date:
    return local_today(timezone) - timedelta(days=1)


def _get_json(url: str, params: dict[str, Any], timeout: int = 90, retries: int = 4) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "User-Agent": "WeatherOracle/1.0 (educational open-data project)",
            "Accept": "application/json",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            last_error = DataFetchError(f"Open-Meteo HTTP {exc.code}: {body}")
            if exc.code < 500 and exc.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = DataFetchError(f"Не удалось получить данные Open-Meteo: {exc}")
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    raise last_error or DataFetchError("Неизвестная ошибка загрузки Open-Meteo")


def fetch_actuals(
    start_date: date,
    end_date: date,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    request_timeout: int = 90,
    request_retries: int = 4,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Фактическая погода из архивного API (ERA5 / best match)."""

    lat = LOCATION["latitude"] if latitude is None else latitude
    lon = LOCATION["longitude"] if longitude is None else longitude
    tz = _timezone(timezone)
    if start_date > end_date:
        raise ValueError("start_date не может быть позже end_date")

    payload = _get_json(
        ARCHIVE_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": ",".join(DAILY_ACTUALS),
            "timezone": tz,
            "wind_speed_unit": "ms",
        },
        timeout=request_timeout,
        retries=request_retries,
    )
    daily = payload.get("daily") or {}
    if "time" not in daily:
        raise DataFetchError("В ответе архива нет дневных данных")

    frame = pd.DataFrame(daily)
    frame = frame.rename(
        columns={
            "time": "date",
            "temperature_2m_max": "tmax",
            "temperature_2m_min": "tmin",
            "temperature_2m_mean": "tmean",
            "precipitation_sum": "precip",
            "weather_code": "weather_code",
            "wind_speed_10m_max": "wind_max",
            "surface_pressure_mean": "pressure",
            "relative_humidity_2m_mean": "humidity",
            "cloud_cover_mean": "cloud",
            "dew_point_2m_mean": "dewpoint",
            "wind_direction_10m_dominant": "wind_dir",
            "shortwave_radiation_sum": "radiation",
            "apparent_temperature_mean": "apparent",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()

    full_index = pd.date_range(start_date, end_date, freq="D", name="date")
    frame = frame.reindex(full_index)
    numeric = [
        "tmax",
        "tmin",
        "tmean",
        "precip",
        "wind_max",
        "pressure",
        "humidity",
        "cloud",
        "dewpoint",
        "radiation",
        "apparent",
    ]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    frame[numeric] = frame[numeric].interpolate(limit=2, limit_direction="both")
    frame["wind_dir"] = frame["wind_dir"].interpolate(limit=2, limit_direction="both")
    frame["weather_code"] = frame["weather_code"].interpolate(limit=2).round()
    frame = frame.dropna(subset=["tmax", "tmin"])
    frame.index.name = "date"

    meta = {
        "source": "Open-Meteo Archive API (ERA5 / best match)",
        "source_url": ARCHIVE_URL,
        "downloaded_at": datetime.now(ZoneInfo(tz)).isoformat(),
        "requested_start": start_date.isoformat(),
        "requested_end": end_date.isoformat(),
        "first_date": frame.index.min().date().isoformat() if len(frame) else None,
        "last_date": frame.index.max().date().isoformat() if len(frame) else None,
        "rows": int(len(frame)),
        "latitude_requested": lat,
        "longitude_requested": lon,
        "latitude_returned": payload.get("latitude"),
        "longitude_returned": payload.get("longitude"),
        "elevation_m": payload.get("elevation"),
        "timezone": payload.get("timezone"),
    }
    if frame.empty:
        raise DataFetchError("Архив вернул пустой набор фактических данных")
    return frame, meta


def _daily_from_previous_runs(payload: dict[str, Any], lead: int) -> pd.DataFrame:
    hourly = payload.get("hourly") or {}
    time_key = "time"
    temp_key = f"temperature_2m_previous_day{lead}"
    precip_key = f"precipitation_previous_day{lead}"
    if time_key not in hourly or temp_key not in hourly:
        raise DataFetchError(f"В ответе нет прогноза previous_day{lead}")

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(hourly[time_key]).normalize(),
            "temp": pd.to_numeric(pd.Series(hourly[temp_key]), errors="coerce"),
            "precip": pd.to_numeric(
                pd.Series(hourly.get(precip_key, [None] * len(hourly[time_key]))),
                errors="coerce",
            ),
        }
    )
    grouped = frame.groupby("date").agg(
        tmax=("temp", "max"),
        n_temp=("temp", "count"),
        precip=("precip", "sum"),
        n_precip=("precip", "count"),
    )
    valid = (grouped["n_temp"] >= 18) & (grouped["n_precip"] >= 18)
    grouped = grouped.loc[valid]
    return pd.DataFrame(
        {
            f"official_tmax_h{lead}": grouped["tmax"].round(2),
            f"official_precip_h{lead}": grouped["precip"].round(2),
        }
    )


def fetch_official_forecasts(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    past_days: int = 92,
    timezone: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Архив оперативных прогнозов Open-Meteo для честного сравнения.

    Previous Runs API отдаёт значения, которые модель предсказывала за 1–7 дней
    до целевой даты. Из почасовых значений собираем дневной максимум температуры.
    """

    lat = LOCATION["latitude"] if latitude is None else latitude
    lon = LOCATION["longitude"] if longitude is None else longitude
    tz = _timezone(timezone)
    past_days = max(1, min(int(past_days), 92))
    hourly_variables = []
    for lead in OFFICIAL_LEADS:
        hourly_variables.extend(
            [
                f"temperature_2m_previous_day{lead}",
                f"precipitation_previous_day{lead}",
            ]
        )

    payload = _get_json(
        PREVIOUS_RUNS_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_variables),
            "past_days": past_days,
            "forecast_days": 1,
            "timezone": tz,
        },
    )

    result: pd.DataFrame | None = None
    for lead in OFFICIAL_LEADS:
        daily = _daily_from_previous_runs(payload, lead)
        result = daily if result is None else result.join(daily, how="outer")

    assert result is not None
    result = result.sort_index()
    yesterday = pd.Timestamp(local_yesterday(tz))
    result = result.loc[result.index <= yesterday]
    result.index.name = "date"
    if result.empty:
        raise DataFetchError("Previous Runs API не вернул полных исторических прогнозов")

    meta = {
        "source": "Open-Meteo Previous Runs API (архив оперативных прогнозов)",
        "source_url": PREVIOUS_RUNS_URL,
        "downloaded_at": datetime.now(ZoneInfo(tz)).isoformat(),
        "first_date": result.index.min().date().isoformat(),
        "last_date": result.index.max().date().isoformat(),
        "rows": int(len(result)),
        "past_days": past_days,
        "latitude_returned": payload.get("latitude"),
        "longitude_returned": payload.get("longitude"),
        "timezone": payload.get("timezone"),
        "note": (
            "Дневной максимум собран из почасовых значений previous_day1..7. "
            "Это архив прогнозов Open-Meteo, а не официальный прогноз Росгидромета."
        ),
    }
    return result, meta


def fetch_live_official_previous(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    forecast_days: int = 4,
    timezone: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Оперативный прогноз из Previous Runs API, включая будущие даты.

    Для целевой даты issue+h берём previous_day{h}: тот же тип baseline,
    что и в бэктесте, поэтому живое сравнение не меняет правила игры.
    """

    lat = LOCATION["latitude"] if latitude is None else latitude
    lon = LOCATION["longitude"] if longitude is None else longitude
    tz = _timezone(timezone)
    hourly_variables = []
    for lead in OFFICIAL_LEADS:
        hourly_variables.extend(
            [
                f"temperature_2m_previous_day{lead}",
                f"precipitation_previous_day{lead}",
            ]
        )
    payload = _get_json(
        PREVIOUS_RUNS_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_variables),
            "past_days": 0,
            "forecast_days": max(8, min(int(forecast_days), 8)),
            "timezone": tz,
        },
    )
    result: pd.DataFrame | None = None
    for lead in OFFICIAL_LEADS:
        daily = _daily_from_previous_runs(payload, lead)
        result = daily if result is None else result.join(daily, how="outer")
    assert result is not None
    result = result.sort_index()
    # Не отдаём текущий (неполный) день.
    result = result.loc[result.index > pd.Timestamp(local_yesterday(tz))]
    result.index.name = "date"
    return result, {
        "source": "Open-Meteo Previous Runs API",
        "source_url": PREVIOUS_RUNS_URL,
        "downloaded_at": datetime.now(ZoneInfo(tz)).isoformat(),
        "latitude_returned": payload.get("latitude"),
        "longitude_returned": payload.get("longitude"),
        "timezone": payload.get("timezone"),
    }


def fetch_live_official(
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    forecast_days: int = 5,
    timezone: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Текущий оперативный прогноз Open-Meteo для живого сравнения."""

    lat = LOCATION["latitude"] if latitude is None else latitude
    lon = LOCATION["longitude"] if longitude is None else longitude
    tz = _timezone(timezone)
    payload = _get_json(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": max(4, min(int(forecast_days), 15)),
            "timezone": tz,
        },
    )
    daily = payload.get("daily") or {}
    if "time" not in daily:
        raise DataFetchError("В ответе прогноза нет дневных данных")
    frame = pd.DataFrame(daily).rename(
        columns={
            "time": "date",
            "temperature_2m_max": "official_tmax",
            "temperature_2m_min": "official_tmin",
            "precipitation_sum": "official_precip",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.set_index("date").sort_index()
    return frame, {
        "source": "Open-Meteo Forecast API",
        "source_url": FORECAST_URL,
        "downloaded_at": datetime.now(ZoneInfo(tz)).isoformat(),
        "latitude_returned": payload.get("latitude"),
        "longitude_returned": payload.get("longitude"),
        "timezone": payload.get("timezone"),
    }


def save_actuals(
    frame: pd.DataFrame,
    meta: dict[str, Any],
    *,
    city_slug: str = DEFAULT_CITY,
) -> None:
    paths = data_paths(city_slug)
    paths["actuals"].parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(paths["actuals"], encoding="utf-8", date_format="%Y-%m-%d")
    _write_json(paths["actuals_meta"], meta)


def save_official(
    frame: pd.DataFrame,
    meta: dict[str, Any],
    *,
    city_slug: str = DEFAULT_CITY,
) -> None:
    paths = data_paths(city_slug)
    paths["official"].parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(paths["official"], encoding="utf-8", date_format="%Y-%m-%d")
    _write_json(paths["official_meta"], meta)


def load_actuals(path: Path | None = None) -> pd.DataFrame:
    path = ACTUALS_PATH if path is None else path
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла {path}. Сначала выполните: python scripts/fetch_data.py"
        )
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    return frame


def load_official(path: Path | None = None) -> pd.DataFrame:
    path = OFFICIAL_PATH if path is None else path
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла {path}. Сначала выполните: python scripts/fetch_data.py"
        )
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    return frame


def load_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def default_period(timezone: str | None = None) -> tuple[date, date]:
    end = local_yesterday(timezone)
    start = end - timedelta(days=DEFAULT_HISTORY_DAYS - 1)
    return start, end
