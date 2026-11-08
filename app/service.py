"""Сервисный слой: загрузка артефактов и живой прогноз по городам."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd

from .config import (
    CITIES,
    CITY_GROUPS,
    DEFAULT_CITY,
    LEADS,
    MODEL_LABELS,
    MODEL_ORDER,
    artifact_paths,
    data_paths,
    get_city,
)
from .data import (
    DataFetchError,
    fetch_actuals,
    fetch_live_official_previous,
    load_actuals,
    local_today,
    save_actuals,
)
from .features import build_lead_dataset, future_frame
from .models import ensemble_prediction, predict_base_models
from .yandex import fetch_yandex_forecast


class ArtifactError(RuntimeError):
    """Артефакты обучения отсутствуют или повреждены."""


class CityStore:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.city = get_city(slug)
        self.paths = artifact_paths(slug)
        self.data_paths = data_paths(slug)
        self.metrics = self._load_json(self.paths["metrics"])
        self.predictions = self._load_predictions()
        self.actuals_meta = self._load_json(self.data_paths["actuals_meta"], required=False)
        self.official_meta = self._load_json(self.data_paths["official_meta"], required=False)
        self.models: dict[int, dict[str, Any]] | None = None
        self._models_lock = threading.Lock()

        self._live_cache: dict[str, Any] | None = None
        self._live_cached_at: float = 0.0
        self._lock = threading.Lock()

    def _ensure_models(self) -> dict[int, dict[str, Any]]:
        if self.models is not None:
            return self.models
        with self._models_lock:
            if self.models is not None:
                return self.models
            loaded: dict[int, dict[str, Any]] = {}
            for lead in LEADS:
                path = self.paths["models"] / f"lead_{lead}.joblib"
                if not path.exists():
                    raise ArtifactError(
                        f"Нет модели {path}. Сначала выполните: python scripts/train.py"
                    )
                loaded[lead] = joblib.load(path)
            self.models = loaded
        return self.models

    @property
    def model_count(self) -> int:
        """Сколько моделей доступно для города (загруженных или лежащих на диске)."""
        if self.models is not None:
            return len(self.models)
        return sum(
            1 for lead in LEADS if (self.paths["models"] / f"lead_{lead}.joblib").exists()
        )

    @staticmethod
    def _load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
        if not path.exists():
            if required:
                raise ArtifactError(
                    f"Нет файла {path}. Сначала выполните: python scripts/train.py"
                )
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_predictions(self) -> pd.DataFrame:
        path = self.paths["predictions"]
        if not path.exists():
            raise ArtifactError(
                f"Нет файла {path}. Сначала выполните: python scripts/train.py"
            )
        frame = pd.read_csv(path, parse_dates=["date"])
        return frame.sort_values(["date", "lead"]).reset_index(drop=True)

    def chart_url(self) -> str:
        path = self.paths["chart"]
        version = int(path.stat().st_mtime) if path.exists() else 0
        return f"/artifacts/{self.slug}/forecast_vs_fact.png?v={version}"

    def current_weather(self) -> dict[str, Any] | None:
        try:
            frame = load_actuals(self.data_paths["actuals"])
        except (FileNotFoundError, OSError, ValueError):
            return None
        yesterday = pd.Timestamp(local_today(str(self.city["timezone"])) - timedelta(days=1))
        frame = frame.loc[frame.index <= yesterday]
        if frame.empty:
            return None
        row = frame.iloc[-1]

        def value(column: str, digits: int = 1) -> float | None:
            if column not in frame.columns or pd.isna(row[column]):
                return None
            return round(float(row[column]), digits)

        return {
            "date": frame.index[-1].date().isoformat(),
            "tmax": value("tmax"),
            "tmin": value("tmin"),
            "tmean": value("tmean"),
            "feels": value("apparent"),
            "wind": value("wind_max"),
            "humidity": value("humidity"),
            "pressure": value("pressure"),
            "pressure_mmhg": (
                round(float(row["pressure"]) * 0.75006)
                if "pressure" in frame.columns and not pd.isna(row["pressure"])
                else None
            ),
            "precip": value("precip"),
            "cloud": value("cloud"),
        }

    def live_forecast(self, *, force: bool = False, cache_seconds: int = 900) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._live_cache is not None
                and now - self._live_cached_at < cache_seconds
            ):
                return self._live_cache

        try:
            result = self._build_live_forecast()
        except DataFetchError as exc:
            try:
                result = self._yandex_forecast()
            except Exception as yandex_error:  # noqa: BLE001
                raise DataFetchError(
                    "Нет свежих данных Open-Meteo, а Яндекс.Погода сейчас недоступна. "
                    "Проверьте интернет и нажмите «Повторить»."
                ) from yandex_error
        with self._lock:
            self._live_cache = result
            self._live_cached_at = now
        return result

    def _yandex_forecast(self) -> dict[str, Any]:
        timezone = str(self.city["timezone"])
        issue_date = local_today(timezone)
        yandex_rows = fetch_yandex_forecast(self.slug, issue_date)
        # Публичная страница Яндекса начинается с сегодняшнего дня, а наши
        # горизонты считаются от завтрашнего: h=1 — это следующие сутки.
        yandex_rows = [
            item
            for item in yandex_rows
            if pd.Timestamp(item["date"]).date() > issue_date
        ]
        if len(yandex_rows) < 7:
            raise DataFetchError(
                "Яндекс.Погода вернула меньше недели прогноза — источник недоступен."
            )
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(yandex_rows, start=1):
            rows.append(
                {
                    "date": item["date"],
                    "lead": index,
                    "ensemble_tmax": float(item["tmax"]),
                    "model_spread": None,
                    "components": {},
                    "official_tmax": None,
                    "precip_mm": None,
                    "source": "yandex",
                    "provider_label": "Яндекс.Погода",
                }
            )
        return {
            "location": self.city,
            "city": self.slug,
            "issue_date": issue_date.isoformat(),
            "generated_at": datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds"),
            "target_dates": [row["date"] for row in rows],
            "rows": rows,
            "official_note": "Источник живого прогноза: Яндекс.Погода.",
            "source": "yandex",
            "provider_label": "Яндекс.Погода",
            "model_version": self.metrics.get("generated_at"),
            "cache_seconds": 900,
        }

    def _merge_history(self, history: pd.DataFrame, meta: dict[str, Any]) -> None:
        """Сохраняет свежую историю, не теряя уже накопленные дни."""
        path = self.data_paths["actuals"]
        try:
            cached = load_actuals(path)
        except (FileNotFoundError, OSError, ValueError):
            cached = None
        if cached is not None and not cached.empty:
            combined = pd.concat([cached, history])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        else:
            combined = history
        merged_meta = dict(meta)
        merged_meta["first_date"] = combined.index.min().date().isoformat()
        merged_meta["last_date"] = combined.index.max().date().isoformat()
        merged_meta["rows"] = int(len(combined))
        merged_meta["merged_with_cache"] = True
        save_actuals(combined, merged_meta, city_slug=self.slug)

    def _build_live_forecast(self) -> dict[str, Any]:
        all_models = self._ensure_models()
        timezone = str(self.city["timezone"])
        latitude = float(self.city["latitude"])
        longitude = float(self.city["longitude"])
        issue_date = local_today(timezone)
        history_end = issue_date - timedelta(days=1)
        history_start = history_end - timedelta(days=75)
        try:
            cached_history = load_actuals(self.data_paths["actuals"])
            cached_history = cached_history.loc[cached_history.index <= pd.Timestamp(history_end)]
            # Признаки любого горизонта опираются на вчерашний день (t - h - 1 = вчера),
            # поэтому кэш без вчерашних данных бесполезен — его нужно обновить.
            if cached_history.empty or cached_history.index.max() < pd.Timestamp(history_end):
                raise FileNotFoundError
            history = cached_history.tail(75)
        except (FileNotFoundError, OSError, ValueError):
            history, history_meta = fetch_actuals(
                history_start,
                history_end,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                request_timeout=5,
                request_retries=1,
            )
            try:
                self._merge_history(history, history_meta)
            except OSError:
                pass
        if history.empty or history.index.max() < pd.Timestamp(history_end):
            raise DataFetchError(
                "Open-Meteo ещё не опубликовал полные данные за "
                f"{history_end.strftime('%d.%m.%Y')}. Обновите прогноз позже."
            )
        extended = future_frame(history, history.index.max(), days=15)

        rows: list[dict[str, Any]] = []
        for lead in LEADS:
            target_date = pd.Timestamp(issue_date + timedelta(days=lead))
            X, _ = build_lead_dataset(extended, lead)
            if target_date not in X.index:
                raise DataFetchError(f"Не удалось построить признаки на {target_date.date()}")
            row = X.loc[[target_date]]
            if row.isna().any(axis=None):
                missing = row.columns[row.isna().any()].tolist()
                raise DataFetchError(
                    f"Недостаточно истории для прогноза: {', '.join(missing)}"
                )
            payload = all_models[lead]
            base_models = payload["models"]
            weights = payload["weights"]
            row = row[payload["feature_columns"]]
            predictions = predict_base_models(base_models, row)
            value = float(ensemble_prediction(predictions, weights)[0])
            all_values = np.concatenate(
                [np.asarray(values, dtype=float).ravel() for values in predictions.values()]
            )
            spread = float(np.max(all_values) - np.min(all_values))
            rows.append(
                {
                    "date": target_date.date().isoformat(),
                    "lead": lead,
                    "ensemble_tmax": round(value, 1),
                    "model_spread": round(spread, 1),
                    "components": {
                        name: round(float(predictions[name][0]), 1)
                        for name in MODEL_ORDER
                    },
                }
            )

        target_dates = [item["date"] for item in rows]
        official_note = None
        try:
            official, _ = fetch_live_official_previous(
                latitude=latitude,
                longitude=longitude,
                forecast_days=8,
                timezone=timezone,
            )
            for item in rows:
                target = pd.Timestamp(item["date"])
                column = f"official_tmax_h{item['lead']}"
                if target in official.index and column in official.columns:
                    value = official.loc[target, column]
                    item["official_tmax"] = (
                        None if pd.isna(value) else round(float(value), 1)
                    )
                    precip_column = f"official_precip_h{item['lead']}"
                    if precip_column in official.columns:
                        precip = official.loc[target, precip_column]
                        item["precip_mm"] = (
                            None if pd.isna(precip) else round(float(precip), 1)
                        )
                    else:
                        item["precip_mm"] = None
                else:
                    item["official_tmax"] = None
                    item["precip_mm"] = None
        except DataFetchError as exc:
            official_note = f"Официальный прогноз сейчас недоступен: {exc}"
            for item in rows:
                item["official_tmax"] = None
                item["precip_mm"] = None

        return {
            "location": self.city,
            "city": self.slug,
            "issue_date": issue_date.isoformat(),
            "generated_at": datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds"),
            "target_dates": target_dates,
            "rows": rows,
            "official_note": official_note,
            "model_version": self.metrics.get("generated_at"),
            "cache_seconds": 900,
        }

    def page_context(self) -> dict[str, Any]:
        metrics = self.metrics
        overall = metrics["overall"]
        headline = metrics["headline"]
        base_names = [name for name in MODEL_ORDER if name in overall]
        best_base = min(base_names, key=lambda name: overall[name]["mae"])
        best_base_mae = overall[best_base]["mae"]
        ensemble_mae = overall["ensemble"]["mae"]
        official_mae = overall.get("official", {}).get("mae")
        improvement = (
            round((best_base_mae - ensemble_mae) / best_base_mae * 100.0, 1)
            if best_base_mae
            else 0.0
        )
        improvement_abs = abs(improvement)
        if improvement > 0.05:
            improvement_sign = "+"
            improvement_label = "лучше базовой"
        elif improvement < -0.05:
            improvement_sign = "−"
            improvement_label = "хуже базовой"
        else:
            improvement_sign = ""
            improvement_label = "на уровне базовой"

        overall_rows = sorted(
            [
                {
                    "key": name,
                    "label": MODEL_LABELS.get(name, name),
                    "mae": overall[name]["mae"],
                    "rmse": overall[name]["rmse"],
                    "bias": overall[name]["bias"],
                    "n": overall[name]["n"],
                    "is_ensemble": name == "ensemble",
                    "is_official": name == "official",
                    "is_best": name == best_model_name(overall),
                }
                for name in (*MODEL_ORDER, "ensemble", "official", "persistence")
                if name in overall
            ],
            key=lambda row: row["mae"],
        )

        lead_sections = []
        metric_leads = sorted(int(key) for key in metrics["leads"])
        for lead in metric_leads:
            lead_data = metrics["leads"][str(lead)]
            models = lead_data["models"]
            rows = []
            for name in (*MODEL_ORDER, "ensemble", "official", "persistence"):
                if name not in models:
                    continue
                rows.append(
                    {
                        "label": MODEL_LABELS.get(name, name),
                        "mae": models[name]["mae"],
                        "rmse": models[name]["rmse"],
                        "bias": models[name]["bias"],
                        "is_ensemble": name == "ensemble",
                        "is_official": name == "official",
                        "is_best": name
                        == min(
                            (key for key in (*MODEL_ORDER, "ensemble") if key in models),
                            key=lambda key: models[key]["mae"],
                        ),
                        "key": name,
                    }
                )
            rows.sort(key=lambda item: item["mae"])
            weights = [
                {
                    "label": MODEL_LABELS.get(name, name),
                    "value": value,
                    "pct": round(value * 100, 0),
                }
                for name, value in lead_data["weights"].items()
            ]
            best_row = min(
                (row for row in rows if not row["is_official"]),
                key=lambda row: row["mae"],
            )
            lead_sections.append(
                {
                    "lead": lead,
                    "n": lead_data["n_common_with_official"],
                    "weights": weights,
                    "rows": rows,
                    "method": lead_data.get("ensemble_method", ""),
                    "best_label": best_row["label"],
                }
            )

        official_note = (
            "Официальный прогноз Open-Meteo в этом бэктесте точнее нашего ансамбля. "
            "Это видно в таблице и на графике — мы не подгоняем сравнение."
            if official_mae is not None and official_mae < ensemble_mae
            else "Наш ансамбль обошёл официальный прогноз на этом тестовом периоде."
        )
        current = self.current_weather()
        if current:
            current["label"] = _format_date(current["date"])

        return {
            "metrics": metrics,
            "city": self.city,
            "location": self.city,
            "headline": headline,
            "overall_rows": overall_rows,
            "leads": lead_sections,
            "chart_url": self.chart_url(),
            "current": current,
            "improvement_vs_best_base": improvement,
            "improvement_abs": improvement_abs,
            "improvement_sign": improvement_sign,
            "improvement_label": improvement_label,
            "best_base_label": MODEL_LABELS.get(best_base, best_base),
            "best_base_mae": best_base_mae,
            "official_mae": official_mae,
            "official_note": official_note,
            "generated_at": _format_datetime(metrics.get("generated_at")),
            "actuals_range": (
                f"{_format_date(metrics['data']['first_actual_date'])} — "
                f"{_format_date(metrics['data']['last_actual_date'])}"
            ),
            "test_range": (
                f"{_format_date(metrics['periods']['test']['start'])} — "
                f"{_format_date(metrics['periods']['test']['end'])}"
            ),
            "split": {
                "train": (
                    f"{_format_date(metrics['periods']['train']['start'])} — "
                    f"{_format_date(metrics['periods']['train']['end'])}"
                ),
                "validation": (
                    f"{_format_date(metrics['periods']['validation']['start'])} — "
                    f"{_format_date(metrics['periods']['validation']['end'])}"
                ),
                "test": (
                    f"{_format_date(metrics['periods']['test']['start'])} — "
                    f"{_format_date(metrics['periods']['test']['end'])}"
                ),
            },
            "official_source_note": self.official_meta.get("note", ""),
            "test_days": metrics["periods"]["test"]["days"],
            "n_rows": headline["n_rows"],
            "n_dates": headline["n_dates"],
            "beats_official": bool(headline.get("beats_official")),
            "api_example": f"/api/forecast?city={self.slug}",
        }


class WeatherOracleStore:
    """Все обученные города и их независимые модели."""

    def __init__(self) -> None:
        self.cities: dict[str, CityStore] = {}
        errors: dict[str, str] = {}
        for slug in CITIES:
            try:
                self.cities[slug] = CityStore(slug)
            except ArtifactError as exc:
                errors[slug] = str(exc)
        if not self.cities:
            raise ArtifactError(
                "Нет ни одного обученного города. Выполните: python scripts/train.py"
            )
        self.default_slug = DEFAULT_CITY if DEFAULT_CITY in self.cities else next(iter(self.cities))
        self.artifact_errors = errors

    def get(self, slug: str | None = None) -> CityStore:
        requested = (slug or self.default_slug).strip().lower()
        if requested not in self.cities:
            raise ArtifactError(
                f"Город «{requested}» не обучен. Доступны: {', '.join(self.cities)}"
            )
        return self.cities[requested]

    def page_context(self, slug: str | None = None) -> dict[str, Any]:
        context = self.get(slug).page_context()
        selected_slug = context["city"]["slug"]

        def sort_key(city: Any) -> str:
            # Ё в русском алфавите идёт после Е, а в Unicode — раньше.
            return str(city.city["name"]).replace("ё", "е").replace("Ё", "Е").casefold()

        ordered = sorted(self.cities.values(), key=sort_key)
        context["cities"] = [
            {
                "slug": city.slug,
                "name": city.city["name"],
                "selected": city.slug == selected_slug,
            }
            for city in ordered
        ]
        # Один плоский список всех городов в алфавитном порядке.
        context["city_groups"] = [
            {
                "label": "Все города",
                "cities": [
                    {
                        "slug": city.slug,
                        "name": city.city["name"],
                        "latitude": city.city["latitude"],
                        "longitude": city.city["longitude"],
                        "selected": city.slug == selected_slug,
                    }
                    for city in ordered
                ],
            }
        ]
        return context

    def live_forecast(self, slug: str | None = None, *, force: bool = False) -> dict[str, Any]:
        return self.get(slug).live_forecast(force=force)

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "slug": city.slug,
                "name": city.city["name"],
                "latitude": city.city["latitude"],
                "longitude": city.city["longitude"],
                "timezone": city.city["timezone"],
                "headline": city.metrics.get("headline", {}),
            }
            for city in self.cities.values()
        ]


def best_model_name(overall: dict[str, dict]) -> str:
    candidates = {
        name: data["mae"]
        for name, data in overall.items()
        if name in (*MODEL_ORDER, "ensemble")
    }
    return min(candidates, key=candidates.get)


def _format_date(value: str | None) -> str:
    if not value:
        return "—"
    return datetime.fromisoformat(value).strftime("%d.%m.%Y")


def _format_datetime(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y, %H:%M")
    except ValueError:
        return value
