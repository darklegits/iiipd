"""Обучение моделей по городам, ансамбли и честный бэктест."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
VENDOR = ROOT / ".vendor"
if VENDOR.exists():
    sys.path.append(str(VENDOR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.config import (  # noqa: E402
    CITIES,
    DEFAULT_CITY,
    MODEL_LABELS,
    TEST_DAYS,
    VALID_DAYS,
    data_paths,
    get_city,
)
from app.data import load_actuals, load_official  # noqa: E402
from app.training import train_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Обучение «Погодного оракула»")
    parser.add_argument("--city", choices=sorted(CITIES), help="Только один город")
    parser.add_argument("--test-days", type=int, default=TEST_DAYS)
    parser.add_argument("--valid-days", type=int, default=VALID_DAYS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slugs = [args.city] if args.city else list(CITIES)
    results = []

    for slug in slugs:
        city = get_city(slug)
        paths = data_paths(slug)
        print(f"\n=== {city['name']} ===")
        try:
            actuals = load_actuals(paths["actuals"])
            official = load_official(paths["official"])
            metrics = train_pipeline(
                actuals,
                official,
                city_slug=slug,
                test_days=args.test_days,
                valid_days=args.valid_days,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"Ошибка обучения: {exc}")
            return 1
        results.append((slug, metrics))

    print("\n" + "=" * 72)
    print("ПОГОДНЫЙ ОРАКУЛ — РЕЗУЛЬТАТЫ ПО ГОРОДАМ")
    print("=" * 72)
    print(f"{'Город':<20} {'Ансамбль':>10} {'Офиц.':>8} {'Δ':>8} {'Лучшая модель':<24}")
    for slug, metrics in results:
        h = metrics["headline"]
        off = h.get("official_mae")
        off_s = f"{off:.2f}" if off is not None else "—"
        best = MODEL_LABELS.get(h["best_model"], h["best_model"])
        print(
            f"{get_city(slug)['name']:<20} "
            f"{h['ensemble_mae']:>9.2f}° {off_s:>7} "
            f"{h['delta_mae']:>+7.2f}° {best:<24}"
        )

    first_slug = results[0][0] if results else DEFAULT_CITY
    if len(results) == 1:
        metrics = results[0][1]
        print(f"\nТест: {metrics['periods']['test']['start']} — {metrics['periods']['test']['end']}")
        for lead, data in metrics["leads"].items():
            weights = ", ".join(
                f"{MODEL_LABELS.get(name, name)} {weight:.2f}"
                for name, weight in data["weights"].items()
            )
            print(f"  h={lead}: MAE {data['models']['ensemble']['mae']:.2f} °C | веса: {weights}")
        print(f"Город: {get_city(first_slug)['name']}")

    print("\nАртефакты: artifacts/<город>/ и artifacts/models/<город>/")
    print("Запуск: .\\run.cmd  или  dist\\WeatherOracle\\WeatherOracle.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
