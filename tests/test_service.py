"""Тесты сервисного слоя: резервный источник и сохранение истории."""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

from app.config import get_city
from app.data import DataFetchError
from app.service import CityStore


def _city_stand_in() -> SimpleNamespace:
    """Минимальный объект для вызова методов CityStore без чтения артефактов."""
    return SimpleNamespace(
        slug="ekaterinburg",
        city=get_city("ekaterinburg"),
        metrics={"generated_at": "2026-10-21T00:42:34+05:00"},
        data_paths={"actuals": Path("tests") / "no-such-actuals.csv"},
    )


class YandexFallbackTests(unittest.TestCase):
    def test_today_row_is_dropped_and_leads_start_at_one(self):
        issue = date(2026, 11, 4)
        raw = [
            {"date": (issue + timedelta(days=offset)).isoformat(), "tmax": 5 + offset}
            for offset in range(14)
        ]
        with (
            mock.patch("app.service.local_today", return_value=issue),
            mock.patch("app.service.fetch_yandex_forecast", return_value=raw),
        ):
            payload = CityStore._yandex_forecast(_city_stand_in())

        rows = payload["rows"]
        self.assertEqual(len(rows), 13)
        self.assertEqual([row["lead"] for row in rows], list(range(1, 14)))
        self.assertEqual(rows[0]["date"], "2026-11-05")
        self.assertEqual(rows[-1]["date"], "2026-11-17")
        self.assertEqual(payload["issue_date"], "2026-11-04")

    def test_short_feed_raises_clear_error(self):
        issue = date(2026, 11, 4)
        raw = [
            {"date": (issue + timedelta(days=offset)).isoformat(), "tmax": 5.0}
            for offset in range(6)
        ]
        with (
            mock.patch("app.service.local_today", return_value=issue),
            mock.patch("app.service.fetch_yandex_forecast", return_value=raw),
        ):
            with self.assertRaises(DataFetchError) as context:
                CityStore._yandex_forecast(_city_stand_in())
        self.assertIn("меньше недели", str(context.exception))


class HistoryMergeTests(unittest.TestCase):
    def test_merge_keeps_cached_days_and_prefers_fresh_values(self):
        cached = pd.DataFrame(
            {"tmax": [1.0, 2.0, 3.0]},
            index=pd.date_range("2026-11-01", periods=3, freq="D", name="date"),
        )
        fresh = pd.DataFrame(
            {"tmax": [2.5, 3.0, 4.0]},
            index=pd.date_range("2026-11-02", periods=3, freq="D", name="date"),
        )
        with (
            mock.patch("app.service.load_actuals", return_value=cached),
            mock.patch("app.service.save_actuals") as save,
        ):
            CityStore._merge_history(_city_stand_in(), fresh, {"source": "test"})

        save.assert_called_once()
        frame = save.call_args.args[0]
        meta = save.call_args.args[1]
        self.assertEqual(len(frame), 4)
        self.assertEqual(frame.loc["2026-11-02", "tmax"], 2.5)
        self.assertEqual(meta["first_date"], "2026-11-01")
        self.assertEqual(meta["last_date"], "2026-11-04")
        self.assertEqual(meta["rows"], 4)
        self.assertTrue(meta["merged_with_cache"])

    def test_merge_writes_fresh_history_when_cache_is_missing(self):
        fresh = pd.DataFrame(
            {"tmax": [7.0, 8.0]},
            index=pd.date_range("2026-11-03", periods=2, freq="D", name="date"),
        )
        with (
            mock.patch("app.service.load_actuals", side_effect=FileNotFoundError),
            mock.patch("app.service.save_actuals") as save,
        ):
            CityStore._merge_history(_city_stand_in(), fresh, {"source": "test"})

        frame = save.call_args.args[0]
        self.assertEqual(len(frame), 2)
        self.assertEqual(save.call_args.args[1]["first_date"], "2026-11-03")


if __name__ == "__main__":
    unittest.main()
