"""Спортивные рекомендации по погодному прогнозу.

Модуль не делает сетевых запросов: он берёт уже готовый живой прогноз
(Open-Meteo или Яндекс.Погода) и превращает температуру, осадки и ветер
в понятный ответ «чем заняться и в каких условиях».

Правила намеренно консервативные: лучше честно сказать «осторожно»,
чем отправить человека на лёд или под грозу.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

# Порядок статусов от лучшего к худшему.
STATUS_LABELS = {
    "great": "Отлично",
    "ok": "Можно",
    "careful": "Осторожно",
    "no": "Не стоит",
}

LEVEL_LABELS = {
    "good": "комфортно",
    "ok": "умеренно",
    "hard": "непросто",
    "bad": "дискомфорт",
}


@dataclass(frozen=True)
class Sport:
    """Вид активности и его погодные рамки."""

    key: str
    name: str
    icon: str
    hint: str
    low: float
    high: float
    best_low: float
    best_high: float
    wind_limit: float
    precip_limit: float
    dry: bool = False
    snow: bool = False
    indoor: str = ""


SPORTS: tuple[Sport, ...] = (
    Sport(
        key="run",
        name="Бег",
        icon="run",
        hint="Кроссовки с протектором, разминка 10 минут",
        low=-16,
        high=30,
        best_low=-2,
        best_high=17,
        wind_limit=12,
        precip_limit=2,
        indoor="беговая дорожка",
    ),
    Sport(
        key="walk",
        name="Ходьба",
        icon="walk",
        hint="Самый безопасный вариант при любой погоде",
        low=-22,
        high=32,
        best_low=2,
        best_high=22,
        wind_limit=15,
        precip_limit=4,
        indoor="торговый центр или стадион",
    ),
    Sport(
        key="bike",
        name="Велосипед",
        icon="bike",
        hint="Шлем, фонарь и проверенные тормоза",
        low=1,
        high=30,
        best_low=12,
        best_high=24,
        wind_limit=9,
        precip_limit=1,
        dry=True,
        indoor="велотренажёр",
    ),
    Sport(
        key="football",
        name="Футбол и баскетбол",
        icon="ball",
        hint="Разминка и нескользящая обувь",
        low=-2,
        high=30,
        best_low=8,
        best_high=23,
        wind_limit=10,
        precip_limit=1,
        dry=True,
        indoor="зал",
    ),
    Sport(
        key="tennis",
        name="Теннис и бадминтон",
        icon="racket",
        hint="Ветер сильнее 8 м/с ломает игру",
        low=3,
        high=29,
        best_low=12,
        best_high=24,
        wind_limit=8,
        precip_limit=0.5,
        dry=True,
        indoor="крытый корт",
    ),
    Sport(
        key="workout",
        name="Воркаут и силовые",
        icon="strength",
        hint="Турники и петли, перчатки при холоде",
        low=-14,
        high=32,
        best_low=-2,
        best_high=21,
        wind_limit=12,
        precip_limit=3,
        indoor="тренажёрный зал",
    ),
    Sport(
        key="yoga",
        name="Йога на улице",
        icon="yoga",
        hint="Коврик, плед и безветренное место",
        low=6,
        high=31,
        best_low=16,
        best_high=26,
        wind_limit=6,
        precip_limit=0,
        dry=True,
        indoor="студия или дом",
    ),
    Sport(
        key="swim",
        name="Плавание в открытой воде",
        icon="swim",
        hint="Вход в воду медленный, рядом должен быть берег",
        low=17,
        high=38,
        best_low=23,
        best_high=30,
        wind_limit=6,
        precip_limit=0,
        indoor="бассейн",
    ),
    Sport(
        key="sup",
        name="SUP и каяк",
        icon="sup",
        hint="Спасжилет обязателен, следите за ветром",
        low=13,
        high=36,
        best_low=21,
        best_high=29,
        wind_limit=7,
        precip_limit=1,
        indoor="бассейн",
    ),
    Sport(
        key="ski",
        name="Лыжи и сноуборд",
        icon="ski",
        hint="Свежий снег лучше ледяной корки",
        low=-30,
        high=2,
        best_low=-14,
        best_high=-3,
        wind_limit=12,
        precip_limit=3,
        snow=True,
        indoor="крытый склон",
    ),
    Sport(
        key="skate",
        name="Коньки",
        icon="skate",
        hint="Проверьте лёд: трещины и промоины опасны",
        low=-30,
        high=1,
        best_low=-14,
        best_high=-4,
        wind_limit=10,
        precip_limit=0.5,
        indoor="крытый каток",
    ),
    Sport(
        key="climb",
        name="Скалолазание",
        icon="climb",
        hint="Скала должна быть сухой, страховка проверена",
        low=0,
        high=30,
        best_low=10,
        best_high=23,
        wind_limit=8,
        precip_limit=0.5,
        dry=True,
        indoor="скалодром",
    ),
)

SPORT_BY_KEY = {sport.key: sport for sport in SPORTS}


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _degrees(value: float) -> str:
    rounded = int(round(value))
    sign = "+" if rounded > 0 else ""
    return f"{sign}{rounded}°"


def day_conditions(row: dict[str, Any]) -> dict[str, Any]:
    """Нормализует строку прогноза в набор условий для оценки."""

    tmax = _number(row.get("ensemble_tmax"))
    if tmax is None:
        tmax = _number(row.get("official_tmax"))
    return {
        "tmax": tmax,
        "precip": _number(row.get("precip_mm")),
        "wind": _number(row.get("wind_ms")),
        "humidity": _number(row.get("humidity_pct")),
    }


def _weather_text(conditions: dict[str, Any]) -> str:
    tmax = conditions["tmax"]
    if tmax is None:
        return "нет данных о погоде"
    if tmax >= 28:
        base = "Жарко"
    elif tmax >= 22:
        base = "Тепло"
    elif tmax >= 14:
        base = "Комфортно"
    elif tmax >= 5:
        base = "Прохладно"
    elif tmax >= -5:
        base = "Холодно"
    else:
        base = "Морозно"

    precip = conditions["precip"]
    if precip is None:
        tail = "осадки неизвестны"
    elif precip >= 0.5 and tmax <= 0.5:
        tail = "снег"
    elif precip >= 5:
        tail = "сильные осадки"
    elif precip >= 1:
        tail = "дождь"
    elif precip >= 0.2:
        tail = "небольшой дождь"
    else:
        tail = "сухо"
    return f"{base}, {tail}"


def _surface(conditions: dict[str, Any]) -> str:
    tmax = conditions["tmax"]
    precip = conditions["precip"]
    if tmax is None:
        return "покрытие неизвестно"
    if tmax <= 1 and (precip or 0) >= 0.3:
        return "снег и наледь"
    if tmax <= 2 and (precip or 0) < 0.3:
        return "возможен гололёд"
    if (precip or 0) >= 5:
        return "сильно мокрое покрытие"
    if (precip or 0) >= 1:
        return "мокрое покрытие"
    return "сухое покрытие"


def _gear(conditions: dict[str, Any]) -> list[str]:
    tmax = conditions["tmax"]
    if tmax is None:
        return ["Уточните прогноз перед выходом"]
    if tmax >= 27:
        items = ["Футболка и шорты", "Головной убор", "Вода с собой", "Солнцезащитный крем"]
    elif tmax >= 20:
        items = ["Футболка и шорты", "Лёгкая ветровка", "Вода с собой"]
    elif tmax >= 13:
        items = ["Футболка с длинным рукавом", "Ветровка", "Кроссовки"]
    elif tmax >= 5:
        items = ["Термобельё", "Лёгкая куртка", "Перчатки"]
    elif tmax >= -6:
        items = ["Термобельё", "Зимняя куртка", "Шапка и перчатки"]
    else:
        items = ["Утеплённые слои", "Баф на лицо", "Тёплые перчатки", "Термос"]

    precip = conditions["precip"]
    if precip is not None and precip >= 1:
        items.append("Дождевик или мембрана")
    wind = conditions["wind"]
    if wind is not None and wind >= 8:
        items.append("Ветрозащитный слой")
    return items


def _cautions(conditions: dict[str, Any]) -> list[str]:
    tmax = conditions["tmax"]
    precip = conditions["precip"]
    wind = conditions["wind"]
    humidity = conditions["humidity"]
    items: list[str] = []
    if tmax is not None and tmax >= 30:
        items.append("Риск теплового удара: тренируйтесь утром или вечером")
    if tmax is not None and tmax >= 26 and humidity is not None and humidity >= 70:
        items.append("Душно: снизьте темп и пейте чаще")
    if tmax is not None and tmax <= -15:
        items.append("Риск обморожения: сократите время на улице")
    if precip is not None and precip >= 10:
        items.append("Ливень и возможная гроза: лучше перенести тренировку")
    if wind is not None and wind >= 12:
        items.append("Сильный ветер: избегайте открытых пространств")
    if tmax is not None and -2 <= tmax <= 1:
        items.append("Скользко: выбирайте обувь с протектором")
    return items


def comfort_index(conditions: dict[str, Any]) -> int:
    """Общий индекс комфорта для активности на улице, 0–100."""

    tmax = conditions["tmax"]
    if tmax is None:
        return 0
    penalty = 0.0
    if tmax > 24:
        penalty += (tmax - 24) * 4.0
    elif tmax < 14:
        penalty += (14 - tmax) * 2.6
    if 32 <= tmax <= 40:
        penalty += (tmax - 32) * 3.0

    precip = conditions["precip"]
    if precip is not None:
        if precip >= 15:
            penalty += 60
        elif precip >= 5:
            penalty += 42
        elif precip >= 1:
            penalty += 24
        elif precip >= 0.2:
            penalty += 10

    wind = conditions["wind"]
    if wind is not None and wind > 4:
        penalty += min(26, (wind - 4) * 3.2)

    humidity = conditions["humidity"]
    if humidity is not None and tmax >= 26 and humidity >= 65:
        penalty += 10

    return int(round(_clamp(100 - penalty)))


def _level(comfort: int) -> str:
    if comfort >= 75:
        return "good"
    if comfort >= 55:
        return "ok"
    if comfort >= 35:
        return "hard"
    return "bad"


def assess_sport(sport: Sport, conditions: dict[str, Any]) -> dict[str, Any] | None:
    """Оценивает один вид спорта. None — если температуры нет вовсе."""

    tmax = conditions["tmax"]
    if tmax is None:
        return None
    precip = conditions["precip"]
    wind = conditions["wind"]

    if tmax < sport.low:
        return _result(sport, "no", 0, f"Слишком холодно: {_degrees(tmax)}")
    if tmax > sport.high:
        return _result(sport, "no", 0, f"Слишком жарко: {_degrees(tmax)}")

    score = 100.0
    reasons: list[str] = []

    if tmax < sport.best_low:
        score -= min(48.0, (sport.best_low - tmax) * 4.2)
        reasons.append(f"прохладно, {_degrees(tmax)}")
    elif tmax > sport.best_high:
        score -= min(48.0, (tmax - sport.best_high) * 5.0)
        reasons.append(f"тепло, {_degrees(tmax)}")

    if precip is not None:
        if sport.snow:
            if precip >= 0.5 and tmax <= 1:
                reasons.append("есть снег")
                score = min(100.0, score + 8.0)
            elif precip >= 1:
                score -= 42.0
                reasons.append("мокрый снег")
        elif precip >= 5:
            score -= 70.0
            reasons.append("сильные осадки")
        elif precip >= 1:
            score -= 38.0
            reasons.append("осадки")
        elif precip >= 0.2:
            score -= 16.0
            reasons.append("небольшой дождь")

    if sport.dry and precip is not None and precip >= 1:
        score -= 18.0

    if wind is not None:
        if wind >= sport.wind_limit * 1.4:
            score -= 55.0
            reasons.append(f"сильный ветер {wind:.0f} м/с")
        elif wind >= sport.wind_limit:
            score -= 30.0
            reasons.append(f"ветер {wind:.0f} м/с")

    if sport.key in ("bike", "skate") and -2 <= tmax <= 1:
        score -= 20.0
        reasons.append("риск гололёда")

    if precip is None:
        # Без данных об осадках нельзя обещать «отлично» там, где важна
        # сухость покрытия или наличие снега.
        if sport.snow:
            score = min(score, 60.0)
            reasons.append("нет данных о снеге")
        elif sport.dry:
            score = min(score, 76.0)
            reasons.append("осадки неизвестны")

    score = _clamp(score)
    if score < 35:
        status = "no"
    elif score < 55:
        status = "careful"
    elif score < 78:
        status = "ok"
    else:
        status = "great"

    if reasons:
        reason = "; ".join(reasons[:2])
    else:
        reason = "условия подходящие"
    return _result(sport, status, score, reason)


def _result(sport: Sport, status: str, score: float, reason: str) -> dict[str, Any]:
    return {
        "key": sport.key,
        "name": sport.name,
        "icon": sport.icon,
        "hint": sport.hint,
        "indoor": sport.indoor,
        "status": status,
        "label": STATUS_LABELS[status],
        "score": int(round(score)),
        "reason": reason,
    }


def assess_day(row: dict[str, Any]) -> dict[str, Any] | None:
    conditions = day_conditions(row)
    if conditions["tmax"] is None:
        return None

    sports = [item for item in (assess_sport(sport, conditions) for sport in SPORTS) if item]
    sports.sort(key=lambda item: (-item["score"], item["name"]))

    comfort = comfort_index(conditions)
    level = _level(comfort)
    best = next((item for item in sports if item["status"] != "no"), None)

    return {
        "date": row.get("date"),
        "lead": row.get("lead"),
        "tmax": conditions["tmax"],
        "precip_mm": conditions["precip"],
        "wind_ms": conditions["wind"],
        "humidity_pct": conditions["humidity"],
        "comfort": comfort,
        "level": level,
        "level_label": LEVEL_LABELS[level],
        "weather": _weather_text(conditions),
        "surface": _surface(conditions),
        "gear": _gear(conditions),
        "cautions": _cautions(conditions),
        "best": best,
        "sports": sports,
    }


def _notes(forecast: dict[str, Any], days: Iterable[dict[str, Any]]) -> list[str]:
    rows = list(days)
    has_wind = any(day["wind_ms"] is not None for day in rows)
    has_precip = any(day["precip_mm"] is not None for day in rows)
    provider = forecast.get("provider_label") or "Open-Meteo"
    notes = [f"Источник прогноза: {provider}."]
    if has_precip and has_wind:
        notes.append("Учтены температура, осадки и ветер.")
    elif has_precip:
        notes.append("Учтены температура и осадки; скорость ветра источник не отдаёт.")
    else:
        notes.append(
            "Источник отдаёт только температуру, поэтому оценка осторожная: "
            "осадки и ветер не учитывались."
        )
    notes.append(
        "Это ориентир, а не медицинская рекомендация: учитывайте самочувствие, "
        "хронические заболевания и состояние покрытия."
    )
    return notes


def build_payload(forecast: dict[str, Any], city: dict[str, Any] | None = None) -> dict[str, Any]:
    """Собирает ответ для страницы «Спорт» из готового живого прогноза."""

    rows = forecast.get("rows") or []
    days = [day for day in (assess_day(row) for row in rows) if day]
    city = city or forecast.get("location") or {}

    best_day = max(days, key=lambda day: day["comfort"]) if days else None
    ranked = sorted(days, key=lambda day: (-day["comfort"], day["lead"] or 0))
    best_days = [
        {"date": day["date"], "comfort": day["comfort"], "best": day["best"]}
        for day in ranked[:3]
    ]

    return {
        "city": forecast.get("city") or city.get("slug"),
        "city_name": city.get("name"),
        "issue_date": forecast.get("issue_date"),
        "generated_at": forecast.get("generated_at"),
        "source": forecast.get("source") or "open-meteo",
        "provider_label": forecast.get("provider_label"),
        "days": days,
        "best_day": best_day,
        "best_days": best_days,
        "notes": _notes(forecast, days),
        "sports": [
            {"key": sport.key, "name": sport.name, "icon": sport.icon, "hint": sport.hint}
            for sport in SPORTS
        ],
    }
