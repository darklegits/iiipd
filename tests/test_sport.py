"""Тесты спортивных рекомендаций (без сети и без артефактов)."""

from __future__ import annotations

import unittest

from app.sport import SPORTS, assess_day, assess_sport, build_payload, comfort_index, day_conditions


def row(date: str = "2026-11-06", lead: int = 1, tmax=10, precip=0.0, wind=3.0, **extra):
    payload = {
        "date": date,
        "lead": lead,
        "ensemble_tmax": tmax,
        "official_tmax": None,
        "precip_mm": precip,
        "model_spread": 0.4,
        "wind_ms": wind,
    }
    payload.update(extra)
    return payload


def by_key(day: dict, key: str) -> dict:
    return next(item for item in day["sports"] if item["key"] == key)


class AssessmentTests(unittest.TestCase):
    def test_mild_dry_day_is_good_for_running_and_bad_for_swimming(self) -> None:
        day = assess_day(row(tmax=15))
        self.assertIsNotNone(day)
        self.assertEqual(by_key(day, "run")["status"], "great")
        self.assertEqual(by_key(day, "swim")["status"], "no")
        self.assertEqual(day["best"]["key"], "run")

    def test_frost_recommends_winter_sports_and_blocks_running(self) -> None:
        day = assess_day(row(tmax=-20))
        self.assertEqual(by_key(day, "ski")["status"], "ok")
        self.assertEqual(by_key(day, "skate")["status"], "ok")
        self.assertEqual(by_key(day, "run")["status"], "no")
        self.assertEqual(day["surface"], "возможен гололёд")

    def test_heat_makes_water_sports_best(self) -> None:
        day = assess_day(row(tmax=33))
        self.assertEqual(by_key(day, "run")["status"], "no")
        self.assertEqual(by_key(day, "swim")["status"], "great")
        self.assertEqual(day["best"]["key"], "swim")
        self.assertTrue(any("теплового удара" in item for item in day["cautions"]))

    def test_heavy_rain_cancels_dry_sports(self) -> None:
        day = assess_day(row(tmax=15, precip=8.0))
        self.assertEqual(by_key(day, "run")["status"], "no")
        self.assertEqual(by_key(day, "tennis")["status"], "no")
        self.assertEqual(day["surface"], "сильно мокрое покрытие")
        self.assertTrue(any("Дождевик" in item for item in day["gear"]))

    def test_wind_softens_cycling(self) -> None:
        calm = assess_day(row(tmax=16, wind=2.0))
        windy = assess_day(row(tmax=16, wind=14.0))
        self.assertEqual(by_key(calm, "bike")["status"], "great")
        self.assertIn(by_key(windy, "bike")["status"], {"careful", "no"})
        self.assertLess(by_key(windy, "bike")["score"], by_key(calm, "bike")["score"])

    def test_snow_helps_skiing(self) -> None:
        day = assess_day(row(tmax=-5, precip=2.0))
        ski = by_key(day, "ski")
        self.assertIn(ski["status"], {"great", "ok"})
        self.assertIn("снег", " ".join(day["gear"] + [day["surface"]]).lower())

    def test_missing_temperature_returns_none(self) -> None:
        self.assertIsNone(assess_day(row(tmax=None)))
        self.assertIsNone(assess_sport(SPORTS[0], {"tmax": None, "precip": None, "wind": None, "humidity": None}))

    def test_official_temperature_is_used_when_ensemble_missing(self) -> None:
        day = assess_day({"date": "2026-11-06", "lead": 1, "ensemble_tmax": None, "official_tmax": 12.0})
        self.assertEqual(day["tmax"], 12.0)
        self.assertEqual(day["best"]["key"], "run")


class ComfortTests(unittest.TestCase):
    def test_comfort_is_bounded_and_ordered(self) -> None:
        good = comfort_index({"tmax": 20.0, "precip": 0.0, "wind": 2.0, "humidity": 50.0})
        bad = comfort_index({"tmax": 38.0, "precip": 20.0, "wind": 20.0, "humidity": 90.0})
        self.assertGreaterEqual(good, 90)
        self.assertLessEqual(bad, 10)
        for value in (good, bad):
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)


class PayloadTests(unittest.TestCase):
    def test_payload_structure_and_notes(self) -> None:
        forecast = {
            "city": "ekaterinburg",
            "issue_date": "2026-11-05",
            "generated_at": "2026-11-05T08:00:00+05:00",
            "source": "open-meteo",
            "provider_label": None,
            "location": {"slug": "ekaterinburg", "name": "Екатеринбург"},
            "rows": [row(date="2026-11-06", lead=1), row(date="2026-11-07", lead=2, tmax=-10.0)],
        }
        payload = build_payload(forecast)
        self.assertEqual(payload["city_name"], "Екатеринбург")
        self.assertEqual(len(payload["days"]), 2)
        self.assertIsNotNone(payload["best_day"])
        self.assertEqual(len(payload["best_days"]), 2)
        self.assertEqual(payload["days"][0]["date"], "2026-11-06")
        self.assertTrue(payload["notes"])
        self.assertTrue(any("ветер" in note for note in payload["notes"]))
        self.assertEqual(len(payload["sports"]), len(SPORTS))
        self.assertEqual(set(payload["best_days"][0]), {"date", "comfort", "best"})

    def test_yandex_payload_mentions_limited_data(self) -> None:
        forecast = {
            "city": "ekaterinburg",
            "issue_date": "2026-11-05",
            "source": "yandex",
            "provider_label": "Яндекс.Погода",
            "rows": [
                {
                    "date": "2026-11-06",
                    "lead": 1,
                    "ensemble_tmax": 0.0,
                    "precip_mm": None,
                    "model_spread": None,
                }
            ],
        }
        payload = build_payload(forecast)
        self.assertEqual(len(payload["days"]), 1)
        self.assertTrue(any("только температуру" in note for note in payload["notes"]))
        self.assertEqual(payload["days"][0]["precip_mm"], None)
        self.assertEqual(payload["days"][0]["best"]["key"], "run")

    def test_day_conditions_reads_optional_fields(self) -> None:
        conditions = day_conditions({"ensemble_tmax": 4, "precip_mm": 1.5, "wind_ms": 7, "humidity_pct": 80})
        self.assertEqual(conditions, {"tmax": 4.0, "precip": 1.5, "wind": 7.0, "humidity": 80.0})

    def test_unknown_precipitation_blocks_confident_verdicts(self) -> None:
        day = assess_day({"date": "2026-11-06", "lead": 1, "ensemble_tmax": -1.0, "precip_mm": None})
        self.assertNotEqual(by_key(day, "ski")["status"], "great")
        self.assertIn("нет данных о снеге", by_key(day, "ski")["reason"])

        mild = assess_day({"date": "2026-11-07", "lead": 2, "ensemble_tmax": 12.0, "precip_mm": None})
        self.assertNotEqual(by_key(mild, "bike")["status"], "great")
        self.assertIn("осадки неизвестны", by_key(mild, "bike")["reason"])


if __name__ == "__main__":
    unittest.main()
