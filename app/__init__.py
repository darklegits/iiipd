"""Погодный оракул — ансамбль моделей прогноза температуры."""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "1.0.0"

# Локальный fallback для сред, где зависимости лежат в .vendor.
# При активном venv или обычной установке этот путь просто не используется.
_VENDOR = Path(__file__).resolve().parent.parent / ".vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.append(str(_VENDOR))
