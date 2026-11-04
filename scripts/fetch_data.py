"""Загрузка фактической погоды и архива прогнозов Open-Meteo по городам."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VENDOR = ROOT / ".vendor"
if VENDOR.exists():
    sys.path.append(str(VENDOR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import CITIES, DEFAULT_HISTORY_DAYS, get_city  # noqa: E402
from app.data import (  # noqa: E402
    DataFetchError,
    fetch_actuals,
    fetch_official_forecasts,
    local_yesterday,
    save_actuals,
    save_official,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Загрузка данных Open-Meteo")
    parser.add_argument("--city", choices=sorted(CITIES), help="Только один город")
    parser.add_argument("--days", type=int, default=DEFAULT_HISTORY_DAYS, help="Длина истории, дней")
    parser.add_argument("--start", type=date.fromisoformat, help="Начало, YYYY-MM-DD")
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        help="Конец, YYYY-MM-DD (по умолчанию вчера)",
    )
    parser.add_argument(
        "--past-days",
        type=int,
        default=92,
        help="Глубина архива оперативных прогнозов (максимум 92)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slugs = [args.city] if args.city else list(CITIES)
    if args.days < 60 and not args.start:
        print("Ошибка: нужно минимум 60 дней истории.")
        return 2

    for slug in slugs:
        city = get_city(slug)
        timezone = str(city["timezone"])
        end = args.end or local_yesterday(timezone)
        if end > local_yesterday(timezone):
            print(f"[{city['name']}] Ошибка: архив доступен только по вчерашний день.")
            return 2
        if args.start:
            start = args.start
        else:
            start = end - timedelta(days=args.days - 1)

        print(f"\n[{city['name']}] Загружаю факты: {start} — {end} ...")
        try:
            actuals, actuals_meta = fetch_actuals(
                start,
                end,
                latitude=float(city["latitude"]),
                longitude=float(city["longitude"]),
                timezone=timezone,
            )
            save_actuals(actuals, actuals_meta, city_slug=slug)
            print(f"  OK: {len(actuals)} дней, {actuals.index.min().date()} — {actuals.index.max().date()}")

            print(f"[{city['name']}] Загружаю архив прогнозов: последние {args.past_days} дней ...")
            official, official_meta = fetch_official_forecasts(
                latitude=float(city["latitude"]),
                longitude=float(city["longitude"]),
                past_days=args.past_days,
                timezone=timezone,
            )
            save_official(official, official_meta, city_slug=slug)
            print(f"  OK: {len(official)} дат, {official.index.min().date()} — {official.index.max().date()}")
        except (DataFetchError, ValueError) as exc:
            print(f"[{city['name']}] Ошибка загрузки: {exc}")
            return 1

    print("\nДанные сохранены в data/cities/<город>/")
    print("Дальше: python scripts/train.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
