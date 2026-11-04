"""Сохранение графика «прогноз vs факт» и итоговых таблиц."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import MODEL_LABELS, MODEL_ORDER

INK = "#101114"
MUTED = "#737986"
GRID = "#eceef2"
FACT = "#101114"
ENSEMBLE = "#e30613"
OFFICIAL = "#b45309"


def make_chart(
    predictions: pd.DataFrame,
    overall: dict[str, dict],
    *,
    location_name: str,
    path: Path,
    test_period: tuple[str, str],
) -> Path:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.edgecolor": "#e1e3e8",
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.titleweight": "bold",
        }
    )
    fig = plt.figure(figsize=(12.5, 9.2), facecolor="#ffffff")
    grid = fig.add_gridspec(2, 1, height_ratios=[1.35, 1], hspace=0.34)
    ax1 = fig.add_subplot(grid[0])
    ax2 = fig.add_subplot(grid[1])
    fig.subplots_adjust(left=0.085, right=0.96, top=0.89, bottom=0.09)

    lead_one = predictions.loc[predictions["lead"] == 1].sort_values("date")
    ax1.plot(
        lead_one["date"],
        lead_one["fact"],
        color=FACT,
        linewidth=2.8,
        label="Факт",
        zorder=4,
    )
    ax1.plot(
        lead_one["date"],
        lead_one["ensemble"],
        color=ENSEMBLE,
        linewidth=2.2,
        marker="o",
        markersize=3.4,
        label="Ансамбль, h=1",
        zorder=5,
    )
    official_available = lead_one["official"].notna().any()
    if official_available:
        ax1.plot(
            lead_one["date"],
            lead_one["official"],
            color=OFFICIAL,
            linewidth=2.0,
            linestyle=(0, (5, 3)),
            marker="s",
            markersize=3.0,
            label="Официальный прогноз, h=1",
            zorder=3,
        )
    ax1.fill_between(
        lead_one["date"],
        lead_one["fact"],
        lead_one["ensemble"],
        color=ENSEMBLE,
        alpha=0.07,
        zorder=1,
    )
    ax1.set_title(
        f"Прогноз дневного максимума на 1 день вперёд · {location_name}",
        fontsize=15,
        pad=12,
    )
    ax1.set_ylabel("Температура, °C", fontsize=10)
    ax1.grid(axis="y", color=GRID, linewidth=0.8)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.legend(
        loc="upper left",
        frameon=False,
        ncol=3,
        fontsize=9.2,
        handlelength=2.4,
        columnspacing=1.5,
    )
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax1.tick_params(axis="both", labelsize=9)
    ax1.margins(x=0.015)

    names = [*MODEL_ORDER, "ensemble", "official", "persistence"]
    names = [name for name in names if name in overall and overall[name].get("mae") is not None]
    names = sorted(names, key=lambda name: overall[name]["mae"], reverse=True)
    values = [overall[name]["mae"] for name in names]
    colors = []
    for name in names:
        if name == "ensemble":
            colors.append(ENSEMBLE)
        elif name == "official":
            colors.append(OFFICIAL)
        elif name == "persistence":
            colors.append("#d4d7dd")
        else:
            colors.append("#9da3ad")
    bars = ax2.barh(
        [MODEL_LABELS.get(name, name) for name in names],
        values,
        color=colors,
        height=0.62,
        edgecolor="none",
    )
    for bar, value in zip(bars, values, strict=True):
        ax2.text(
            value + max(values) * 0.012,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.2f}°",
            va="center",
            fontsize=9.5,
            color=INK,
            fontweight="bold" if value == min(values) else "normal",
        )
    ax2.set_title(
        "MAE по всем горизонтам 1–7 дней · меньше — лучше",
        fontsize=13,
        loc="left",
        pad=10,
    )
    ax2.set_xlabel("Средняя абсолютная ошибка, °C", fontsize=10)
    ax2.grid(axis="x", color=GRID, linewidth=0.8)
    ax2.set_axisbelow(True)
    ax2.spines[["top", "right", "left"]].set_visible(False)
    ax2.tick_params(axis="y", length=0, labelsize=9.5)
    ax2.tick_params(axis="x", labelsize=9)
    ax2.set_xlim(0, max(values) * 1.16)

    fig.text(
        0.085,
        0.945,
        "ПОГОДНЫЙ ОРАКУЛ",
        fontsize=11,
        fontweight="bold",
        color=ENSEMBLE,
    )
    fig.text(
        0.985,
        0.945,
        f"Тест: {test_period[0]} — {test_period[1]}",
        fontsize=9,
        color=MUTED,
        ha="right",
    )
    fig.text(
        0.085,
        0.035,
        "Источник факта и прогнозов: Open-Meteo. Сравнение на одних и тех же датах; "
        "официальный прогноз — архив Previous Runs, не Росгидромет.",
        fontsize=8.2,
        color=MUTED,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return path
