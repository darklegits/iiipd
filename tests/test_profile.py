"""Тесты сохранения профиля и любимых видов спорта."""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from app.profile import (
    ProfileError,
    delete_profile,
    load_profile,
    normalize,
    save_profile,
)


class NormalizeTests(unittest.TestCase):
    def test_unknown_sports_are_dropped_and_duplicates_removed(self) -> None:
        profile = normalize({"sports": ["run", "run", "ufo", "bike"]})
        self.assertEqual(profile["sports"], ["bike", "run"])

    def test_bad_levels_and_times_fall_back_to_defaults(self) -> None:
        profile = normalize({"level": "superstar", "goal": "money", "notifyTime": "25:99x"})
        self.assertEqual(profile["level"], "amateur")
        self.assertEqual(profile["goal"], "health")
        self.assertEqual(profile["notifyTime"], "18:00")

    def test_name_is_trimmed_and_limited(self) -> None:
        profile = normalize({"name": "  " + "я" * 100 + "  "})
        self.assertEqual(len(profile["name"]), 40)
        self.assertFalse(profile["name"].startswith(" "))

    def test_not_object_is_rejected(self) -> None:
        with self.assertRaises(ProfileError):
            normalize(["run"])

    def test_sports_must_be_list(self) -> None:
        with self.assertRaises(ProfileError):
            normalize({"sports": "run"})


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        # Временная папка внутри проекта: системный %TEMP% в этой среде
        # может быть защищён от удаления.
        self.dir = Path(".cache") / f"test-profile-{uuid.uuid4().hex}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "profile.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_save_and_load_roundtrip(self) -> None:
        saved = save_profile(
            {
                "name": "Алексей",
                "sports": ["run", "swim"],
                "level": "advanced",
                "goal": "endurance",
                "notify": True,
                "notifyTime": "7:30",
            },
            self.path,
        )
        self.assertTrue(self.path.exists())
        self.assertIn("updated_at", saved)
        self.assertEqual(saved["notifyTime"], "07:30")

        loaded = load_profile(self.path)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["name"], "Алексей")
        self.assertEqual(loaded["sports"], ["run", "swim"])
        self.assertEqual(loaded["level"], "advanced")
        self.assertTrue(loaded["notify"])

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(load_profile(self.path))

    def test_corrupted_file_returns_none(self) -> None:
        self.path.write_text("{не json", encoding="utf-8")
        self.assertIsNone(load_profile(self.path))

    def test_delete_removes_file(self) -> None:
        save_profile({"name": "Test"}, self.path)
        self.assertTrue(self.path.exists())
        delete_profile(self.path)
        self.assertFalse(self.path.exists())

    def test_saved_file_is_utf8_and_readable_json(self) -> None:
        save_profile({"name": "Ёлка", "sports": ["ski"]}, self.path)
        raw = self.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        self.assertEqual(data["name"], "Ёлка")
        self.assertIn("Ёлка", raw)


if __name__ == "__main__":
    unittest.main()
