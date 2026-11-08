"""Резервный источник живого прогноза — Яндекс.Погода.

Официальный API Яндекс.Погоды требует ключ, поэтому здесь используется
публичная страница прогноза, отрендеренная локальным Chrome. Источник
явно помечается в ответе и интерфейсе.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from .config import get_city

MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
WEEKDAYS = "Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье"
HEADER = re.compile(
    rf"^(Сегодня|Завтра|{WEEKDAYS}),?\s+(\d{{1,2}})\s+({'|'.join(MONTHS)})(?:\s+\d{{4}})?:$",
    re.MULTILINE,
)
SLUGS = {
    "spb": "saint-petersburg",
    "nizhny_tagil": "nizhniy-tagil",
}


def chrome_path() -> Path | None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
    ]
    return next((path for path in candidates if path.exists()), None)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _url_for(slug: str) -> str:
    city = get_city(slug)
    name = str(city.get("yandex") or SLUGS.get(slug, slug.replace("_", "-")))
    return (
        f"https://yandex.ru/pogoda/ru/{name}/details/14-day-weather"
        f"?lat={city['latitude']}&lon={city['longitude']}"
    )


def _parse_text(text: str, issue_date: date) -> list[dict[str, Any]]:
    lines = text.splitlines()
    result: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = HEADER.match(line.strip())
        if not match:
            continue
        day = int(match.group(2))
        month = MONTHS[match.group(3)]
        year = issue_date.year
        if month < issue_date.month - 6:
            year += 1
        for next_line in lines[index + 1 : index + 9]:
            value_match = re.match(r"^днём\s+([+−-]?\d+)°", next_line.strip())
            if not value_match:
                continue
            value = int(value_match.group(1).replace("−", "-").replace("+", ""))
            result.append({"date": date(year, month, day).isoformat(), "tmax": value})
            break
    # Убираем возможные дубли и оставляем последовательность 14 дней.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in result:
        if item["date"] in seen:
            continue
        seen.add(item["date"])
        unique.append(item)
    return unique[:14]


async def _read_page(url: str, timeout: float = 25.0) -> str:
    chrome = chrome_path()
    if chrome is None:
        raise RuntimeError("Chrome не найден")
    from websockets.asyncio.client import connect

    port = _free_port()
    profile = Path(tempfile.mkdtemp(prefix="weather-oracle-yandex-"))
    process = subprocess.Popen(
        [
            str(chrome),
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "--window-size=1280,1000",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        page = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                    targets = json.loads(response.read().decode("utf-8"))
                page = next((item for item in targets if item.get("type") == "page"), None)
                if page:
                    break
            except Exception:
                time.sleep(0.2)
        if not page:
            raise RuntimeError("Chrome DevTools не запустился")

        async with connect(page["webSocketDebuggerUrl"], max_size=20_000_000) as websocket:
            counter = 0

            async def call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
                nonlocal counter
                counter += 1
                await websocket.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
                while True:
                    message = json.loads(await websocket.recv())
                    if message.get("id") == counter:
                        return message.get("result", {})

            await call("Page.enable")
            await call("Page.navigate", {"url": url})
            text = ""
            while time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                result = await call(
                    "Runtime.evaluate",
                    {"expression": "document.body.innerText", "returnByValue": True},
                )
                text = str(result.get("result", {}).get("value") or "")
                if "Погода на 14 дней" in text and text.count("днём") >= 10:
                    break
            return text
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        import shutil

        # Chrome отпускает файлы профиля с задержкой: без повторов во временной
        # папке остаются мусорные каталоги weather-oracle-yandex-*.
        for _ in range(6):
            if not profile.exists():
                break
            shutil.rmtree(profile, ignore_errors=True)
            if profile.exists():
                time.sleep(0.3)


def fetch_yandex_forecast(slug: str, issue_date: date | None = None, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Синхронная обёртка: FastAPI может вызывать её из рабочего потока."""
    issue = issue_date or date.today()
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            box["text"] = asyncio.run(_read_page(_url_for(slug), timeout=timeout))
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=worker, name="yandex-weather", daemon=True)
    thread.start()
    thread.join(timeout + 5)
    if "error" in box:
        raise RuntimeError(f"Яндекс.Погода недоступна: {box['error']}")
    rows = _parse_text(box.get("text", ""), issue)
    if len(rows) < 7:
        raise RuntimeError("Яндекс.Погода не вернула прогноз")
    return rows
