"""Сохранение профиля и любимых видов спорта.

Профиль лежит рядом с данными приложения (`data/profile.json`), поэтому
переживает очистку кэша браузера и переносится вместе с portable-папкой.
Данные валидируются: неизвестные виды спорта и уровни отбрасываются.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .sport import SPORTS

SPORT_KEYS = {sport.key for sport in SPORTS}
LEVELS = {"beginner", "amateur", "advanced"}
GOALS = {"health", "endurance", "strength", "weight"}
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")

DEFAULT_PROFILE: dict[str, Any] = {
    "name": "",
    "sports": [],
    "level": "amateur",
    "goal": "health",
    "notify": False,
    "notifyTime": "18:00",
    "onlyMine": False,
}


class ProfileError(ValueError):
    """Профиль не прошёл проверку."""


def profile_path() -> Path:
    override = os.environ.get("ORACLE_PROFILE_PATH")
    return Path(override) if override else DATA_DIR / "profile.json"


def normalize(data: Any) -> dict[str, Any]:
    """Приводит профиль к безопасному виду, отбрасывая мусор."""

    if not isinstance(data, dict):
        raise ProfileError("Профиль должен быть объектом JSON")
    profile = dict(DEFAULT_PROFILE)

    name = data.get("name", "")
    if not isinstance(name, str):
        raise ProfileError("Имя должно быть строкой")
    profile["name"] = name.strip()[:40]

    sports = data.get("sports", [])
    if not isinstance(sports, list):
        raise ProfileError("Список видов спорта должен быть массивом")
    profile["sports"] = sorted({key for key in sports if key in SPORT_KEYS})

    level = data.get("level", DEFAULT_PROFILE["level"])
    profile["level"] = level if level in LEVELS else DEFAULT_PROFILE["level"]

    goal = data.get("goal", DEFAULT_PROFILE["goal"])
    profile["goal"] = goal if goal in GOALS else DEFAULT_PROFILE["goal"]

    profile["notify"] = bool(data.get("notify", False))
    profile["onlyMine"] = bool(data.get("onlyMine", False))

    time_value = str(data.get("notifyTime", DEFAULT_PROFILE["notifyTime"]))
    if TIME_RE.match(time_value):
        hours, minutes = time_value.split(":")
        profile["notifyTime"] = f"{int(hours):02d}:{int(minutes):02d}"
    else:
        profile["notifyTime"] = DEFAULT_PROFILE["notifyTime"]

    return profile


def delete_profile(path: Path | None = None) -> None:
    target = path or profile_path()
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:
        raise ProfileError(f"Не удалось удалить профиль: {exc}") from exc


def load_profile(path: Path | None = None) -> dict[str, Any] | None:
    target = path or profile_path()
    if not target.exists():
        return None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        profile = normalize(raw)
    except ProfileError:
        return None
    profile["updated_at"] = raw.get("updated_at")
    return profile


def save_profile(data: Any, path: Path | None = None) -> dict[str, Any]:
    profile = normalize(data)
    profile["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    target = path or profile_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(profile, ensure_ascii=False, indent=2)
    handle, temp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".profile-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        os.replace(temp_name, target)
    except OSError as exc:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise ProfileError(f"Не удалось сохранить профиль: {exc}") from exc
    return profile
