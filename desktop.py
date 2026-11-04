"""Запуск «Погодного оракула» как настольного Windows-приложения.

Внутри поднимается локальный FastAPI-сервер, а окно показывает встроенный
WebView2. Этот же файл используется как точка входа PyInstaller.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_TITLE = "Погодный оракул"


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


ROOT = application_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))


def _writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def resolve_state_dir() -> Path:
    candidates: list[Path] = []
    override = os.environ.get("WEATHER_ORACLE_HOME")
    if override:
        candidates.append(Path(override))
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "userdata")
    candidates.extend(
        [
            LOCAL_APP_DATA / "WeatherOracle",
            Path(tempfile.gettempdir()) / "WeatherOracle",
        ]
    )
    for candidate in candidates:
        if _writable(candidate):
            return candidate
    return Path(tempfile.gettempdir())


LOG_DIR = resolve_state_dir()
os.environ.setdefault("MPLCONFIGDIR", str(LOG_DIR / "matplotlib"))

# Данные на флешке должны обновляться, не меняя _internal. Копируем seed
# при первом запуске и досыпаем новые города при обновлении версии.
if not os.environ.get("ORACLE_DATA_DIR"):
    state_data = LOG_DIR / "data"
    seed_data = Path(__file__).resolve().parent / "data"
    try:
        if seed_data.exists():
            if not state_data.exists():
                shutil.copytree(seed_data, state_data)
            else:
                seed_cities = seed_data / "cities"
                state_cities = state_data / "cities"
                if seed_cities.exists():
                    state_cities.mkdir(parents=True, exist_ok=True)
                    for city_dir in seed_cities.iterdir():
                        if city_dir.is_dir() and not (state_cities / city_dir.name).exists():
                            shutil.copytree(city_dir, state_cities / city_dir.name)
        os.environ["ORACLE_DATA_DIR"] = str(state_data)
    except Exception:
        # Если FLASH/диск защищён от записи, остаёмся на встроенных данных.
        pass

try:
    (LOG_DIR / "boot.log").write_text("desktop.py entered\n", encoding="utf-8")
except Exception:
    pass

try:
    logging.basicConfig(
        filename=LOG_DIR / "oracle.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
except Exception:
    logging.basicConfig(level=logging.CRITICAL)
log = logging.getLogger("weather-oracle")
LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_SPLASH_STOP = threading.Event()
_SPLASH_IMAGE = (
    Path(getattr(sys, "_MEIPASS", ROOT)) / "build_assets" / "splash.png"
    if getattr(sys, "frozen", False)
    else ROOT / "build_assets" / "splash.png"
)


def splash_window() -> None:
    """Показывает лёгкий splash, пока импортируются pandas/sklearn."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="#101114")
        if _SPLASH_IMAGE.exists():
            image = tk.PhotoImage(file=str(_SPLASH_IMAGE))
            label = tk.Label(root, image=image, borderwidth=0, bg="#101114")
            label.image = image
        else:
            label = tk.Label(
                root,
                text="ПОГОДНЫЙ ОРАКУЛ\nЗапускаю приложение…",
                font=("Segoe UI", 20, "bold"),
                fg="#ffffff",
                bg="#101114",
                padx=70,
                pady=70,
            )
        label.pack()
        width, height = 680, 400
        x = max(0, (root.winfo_screenwidth() - width) // 2)
        y = max(0, (root.winfo_screenheight() - height) // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        def poll() -> None:
            if _SPLASH_STOP.is_set():
                root.destroy()
            else:
                root.after(80, poll)

        root.after(80, poll)
        root.mainloop()
    except Exception as exc:  # noqa: BLE001
        log.warning("Splash unavailable: %s", exc)


def splash_start() -> None:
    _SPLASH_STOP.clear()
    threading.Thread(target=splash_window, name="splash", daemon=True).start()


def splash_close() -> None:
    _SPLASH_STOP.set()
    time.sleep(0.15)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LocalServer(threading.Thread):
    def __init__(self, port: int) -> None:
        super().__init__(name="weather-oracle-uvicorn", daemon=True)
        import uvicorn
        from app.main import app as fastapi_app

        config = uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


def wait_until_ready(url: str, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with LOCAL_OPENER.open(url + "/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Локальный сервер не запустился за {timeout:.0f} секунд: {last_error}")


def message_box(text: str, *, error: bool = False) -> None:
    try:
        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, text, APP_TITLE, flags)
    except Exception:
        pass


def window_title(hwnd: int) -> str:
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    except Exception:
        return ""


def find_app_window() -> int:
    """Ищет окно Chrome/Edge в app-режиме по заголовку."""
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        found: list[int] = []

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            title = window_title(hwnd)
            if not title:
                return True
            if title.startswith("127.0.0.1"):
                found.append(hwnd)
            elif title.startswith("Погодный оракул"):
                if "DeepSeek" not in title and "ансамбль моделей" not in title:
                    found.append(hwnd)
            return True

        user32.EnumWindows(callback_type(callback), 0)
        return found[0] if found else 0
    except Exception:
        return 0


def close_stale_windows() -> None:
    """Закрывает окна предыдущего запуска, чтобы не перехватить их handle."""
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            title = window_title(hwnd)
            if title.startswith("127.0.0.1"):
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
            elif title == APP_TITLE:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
            return True

        user32.EnumWindows(callback_type(callback), 0)
    except Exception:
        pass


def run_browser_app(url: str, *, auto_close_seconds: float = 0) -> None:
    """Открывает приложение в отдельном окне Chrome или Edge без адресной строки.

    Окно запускается через shell (`start`), чтобы дочерний процесс не зависел
    от job-объекта упакованного EXE и не завершался сразу после старта.
    """
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    ]
    browser = next((path for path in candidates if path.exists()), None)
    if browser is None:
        webbrowser.open(url)
        message_box(
            "Chrome или Edge не найден. Приложение открыто в браузере.\n\n"
            "Закройте это окно, чтобы остановить локальный сервер."
        )
        return

    is_chrome = browser.name.lower() == "chrome.exe"
    profile = LOG_DIR / f"{'Chrome' if is_chrome else 'Edge'}Profile-{os.getpid()}"
    shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)
    close_stale_windows()
    time.sleep(0.5)
    log.info("Opening app window via %s", browser)

    command = [
        "cmd.exe",
        "/c",
        "start",
        "",
        str(browser),
        f"--app={url}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-mode",
        "--no-sandbox",
        "--test-type",
        "--start-maximized",
    ]
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    hwnd = 0
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        hwnd = find_app_window()
        if hwnd:
            break
        time.sleep(0.25)

    if not hwnd:
        log.warning("App window not found; opening browser")
        webbrowser.open(url)
        message_box(
            "Не удалось открыть отдельное окно приложения.\n\n"
            "Страница открыта в браузере. Закройте это окно, чтобы остановить сервер."
        )
        shutil.rmtree(profile, ignore_errors=True)
        return

    log.info("App window found: hwnd=%s", hwnd)
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetWindowTextW(hwnd, APP_TITLE)

    try:
        if auto_close_seconds:
            time.sleep(auto_close_seconds)
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            time.sleep(1)
            return

        last_seen = time.monotonic()
        while True:
            current = find_app_window()
            now = time.monotonic()
            if current:
                last_seen = now
                if window_title(current) != APP_TITLE:
                    user32.SetWindowTextW(current, APP_TITLE)
            elif now - last_seen > 4:
                log.info("App window closed")
                break
            time.sleep(0.75)
    finally:
        time.sleep(0.3)
        shutil.rmtree(profile, ignore_errors=True)


def run_window(url: str, *, auto_close_seconds: float = 0) -> None:
    run_browser_app(url, auto_close_seconds=auto_close_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--port", type=int, default=0, help="Порт локального сервера")
    parser.add_argument("--smoke-test", action="store_true", help="Проверка запуска без окна")
    parser.add_argument("--window-smoke", action="store_true", help="Открыть окно и закрыть через 6 секунд")
    parser.add_argument("--browser", action="store_true", help="Открыть в системном браузере")
    args = parser.parse_args()

    port = args.port or find_free_port()
    url = f"http://127.0.0.1:{port}/?desktop=1"
    log.info("Starting %s on %s", APP_TITLE, url)
    if not args.smoke_test:
        splash_start()

    server = LocalServer(port)
    server.start()

    try:
        wait_until_ready(f"http://127.0.0.1:{port}")
        log.info("Server ready")
        splash_close()

        if args.smoke_test:
            with LOCAL_OPENER.open(f"http://127.0.0.1:{port}/", timeout=5) as response:
                body = response.read()
            log.info("SMOKE OK status=%s bytes=%s", response.status, len(body))
            return 0

        if args.window_smoke:
            run_window(url, auto_close_seconds=6)
            log.info("WINDOW SMOKE OK")
            return 0

        if args.browser:
            webbrowser.open(url)
            message_box(
                "Приложение открыто в браузере.\n\n"
                "Закройте это окно, чтобы остановить локальный сервер."
            )
            return 0

        run_window(url)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.exception("Fatal error")
        splash_close()
        message_box(
            "Не удалось запустить приложение.\n\n"
            f"{exc}\n\nПодробности: {LOG_DIR / 'oracle.log'}",
            error=True,
        )
        return 1
    finally:
        server.stop()
        log.info("Server stopped")


if __name__ == "__main__":
    raise SystemExit(main())
