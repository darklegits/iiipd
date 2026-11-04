(function () {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const state = {
    payload: null,
    period: Number(localStorage.getItem("oracle-period")) || 14,
    view: localStorage.getItem("oracle-view") === "list" ? "list" : "cards",
    unit: localStorage.getItem("oracle-unit") === "f" ? "f" : "c",
    installPrompt: null,
    lastFocus: null,
    city: window.ORACLE_CITY || document.body.dataset.city || "ekaterinburg",
  };
  state.period = [7, 10, 14].includes(state.period) ? state.period : 14;

  const WEATHER_ICONS = {
    sun: `<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="12" fill="#ffcf5c"/><g stroke="#ffcf5c" stroke-width="2.4" stroke-linecap="round"><path d="M32 8v6M32 50v6M8 32h6M50 32h6M15 15l4 4M45 45l4 4M49 15l-4 4M19 45l-4 4"/></g></svg>`,
    cloud: `<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="43" cy="21" r="10" fill="#ffcf5c" opacity=".9"/><path d="M14 47h36a9 9 0 0 0 0-18 13 13 0 0 0-24 3.6A8 8 0 0 0 14 47Z" fill="#eef2f8"/></svg>`,
    rain: `<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M14 40h36a9 9 0 0 0 0-18 13 13 0 0 0-24 3.6A8 8 0 0 0 14 40Z" fill="#dfe5ee"/><g stroke="#8fc6ff" stroke-width="2.4" stroke-linecap="round"><path d="M22 47l-2 6M32 47l-2 6M42 47l-2 6"/></g></svg>`,
    snow: `<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M14 39h36a9 9 0 0 0 0-18 13 13 0 0 0-24 3.6A8 8 0 0 0 14 39Z" fill="#e8eef7"/><g stroke="#bfe2ff" stroke-width="1.8" stroke-linecap="round"><path d="M23 48v7M19.5 51.5h7M35 48v7M31.5 51.5h7M47 48v7M43.5 51.5h7"/></g></svg>`,
    cold: `<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="13" fill="none" stroke="#bfe2ff" stroke-width="2.4"/><g stroke="#bfe2ff" stroke-width="2" stroke-linecap="round"><path d="M32 12v8M32 44v8M12 32h8M44 32h8M18 18l6 6M40 40l6 6M46 18l-6 6M24 40l-6 6"/></g></svg>`,
  };

  const MODEL_NAMES = {
    linear: "Линейная регрессия",
    random_forest: "Случайный лес",
    gradient_boosting: "Градиентный бустинг",
  };

  const dateLong = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" });
  const dateShort = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" });
  const weekdayLong = new Intl.DateTimeFormat("ru-RU", { weekday: "long" });
  const weekdayShort = new Intl.DateTimeFormat("ru-RU", { weekday: "short" });

  function parseDate(value) {
    return new Date(value + "T12:00:00");
  }

  function capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function number(value, digits = 1) {
    return Number(value).toFixed(digits).replace(".", ",");
  }

  function convert(value) {
    return state.unit === "f" ? (Number(value) * 9) / 5 + 32 : Number(value);
  }

  function temp(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return number(convert(value), digits) + "°";
  }

  function delta(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    const converted = state.unit === "f" ? (Number(value) * 9) / 5 : Number(value);
    const sign = converted > 0 ? "+" : converted < 0 ? "−" : "";
    return sign + number(Math.abs(converted), 1) + "°";
  }

  function confidence(spread) {
    if (spread === null || spread === undefined) return { label: "нет данных", className: "" };
    if (spread <= 0.7) return { label: "высокая согласованность", className: "high" };
    if (spread <= 1.6) return { label: "средняя согласованность", className: "" };
    return { label: "низкая согласованность", className: "low" };
  }

  function condition(row) {
    const value = Number(row.ensemble_tmax ?? row.official_tmax);
    const precip = Number(row.precip_mm || 0);
    if (precip >= 1 && value <= 0.5) return { key: "snow", label: "Снег · " + number(precip) + " мм" };
    if (precip >= 1) return { key: "rain", label: "Дождь · " + number(precip) + " мм" };
    if (value <= -3) return { key: "cold", label: "Морозно" };
    if (value >= 18) return { key: "sun", label: "Малооблачно" };
    return { key: "cloud", label: "Облачно" };
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function setText(id, text) {
    const element = document.getElementById(id);
    if (element) element.textContent = text;
  }

  function showToast(message) {
    const toast = $("#toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function renderHero(row) {
    if (!row) return;
    const date = parseDate(row.date);
    const visual = condition(row);
    setText("hero-date", capitalize(dateLong.format(date)));
    setText("hero-temp", temp(row.ensemble_tmax));
    setText("hero-condition", visual.label);
    setText(
      "hero-panel-label",
      row.provider_label ? "ПРОГНОЗ НА СЕГОДНЯ" : "ПРОГНОЗ НА ЗАВТРА"
    );

    const icon = $("#hero-icon");
    if (icon) icon.innerHTML = WEATHER_ICONS[visual.key] || WEATHER_ICONS.cloud;
    setText("hero-official", temp(row.official_tmax));
    setText(
      "hero-delta",
      row.official_tmax === null || row.official_tmax === undefined
        ? "—"
        : delta(Number(row.ensemble_tmax) - Number(row.official_tmax))
    );
    setText("hero-spread", row.model_spread === undefined ? "—" : "±" + number(row.model_spread) + "°");

    const confidenceBox = $("#hero-confidence");
    if (confidenceBox) {
      confidenceBox.innerHTML = row.provider_label
        ? "<i></i> " + row.provider_label
        : "<i></i> " + confidence(row.model_spread).label;
    }
    if (state.payload) {
      setText(
        "hero-issued",
        row.provider_label
          ? row.provider_label.toLowerCase()
          : "выпуск " + dateShort.format(parseDate(state.payload.issue_date))
      );
    }
  }

  function cardMarkup(row) {
    const date = parseDate(row.date);
    const visual = condition(row);
    const info = confidence(row.model_spread);
    const officialOnly = row.ensemble_tmax === null || row.ensemble_tmax === undefined;
    const sourceLabel = row.provider_label || null;
    const shownTemp = officialOnly ? row.official_tmax : row.ensemble_tmax;
    const official = temp(row.official_tmax);
    const difference =
      officialOnly || row.official_tmax === null || row.official_tmax === undefined
        ? "—"
        : delta(Number(row.ensemble_tmax) - Number(row.official_tmax));
    return `
      <div class="forecast-visual">
        <div>
          <span class="forecast-weekday">${capitalize(weekdayLong.format(date))}</span>
          <span class="forecast-date">${capitalize(dateLong.format(date))}</span>
        </div>
        <span class="forecast-lead-badge">h=${row.lead}</span>
        <div class="weather-art">${WEATHER_ICONS[visual.key] || WEATHER_ICONS.cloud}</div>
      </div>
      <div class="forecast-body">
        <div class="forecast-temp-row">
          <div>
            <strong class="forecast-temp">${number(convert(shownTemp))}<span>°${state.unit.toUpperCase()}</span></strong>
            <span class="forecast-label">${sourceLabel || (officialOnly ? "официальный прогноз" : "прогноз ансамбля")}</span>
          </div>
          <span class="condition-pill">${visual.label}</span>
        </div>
        <div class="forecast-compare">
          ${
            sourceLabel
              ? `<div><span>Источник</span><b>${sourceLabel}</b></div><div><span>Горизонт</span><b>14 дней</b></div>`
              : officialOnly
              ? `<div><span>Ансамбль</span><b>—</b></div><div><span>Источник</span><b>Open-Meteo</b></div>`
              : `<div><span>Официальный</span><b class="official-value">${official}</b></div><div><span>Разница</span><b>${difference}</b></div>`
          }
        </div>
        <div class="forecast-spread">
          ${
            sourceLabel
              ? `<span>Данные ${sourceLabel}</span><span class="confidence-badge"><i></i>живой прогноз</span>`
              : officialOnly
              ? `<span>Дни 8–14</span><span class="confidence-badge"><i></i>без ансамбля</span>`
              : `<span>Разброс моделей ${row.model_spread === undefined ? "—" : "±" + number(row.model_spread) + "°"}</span><span class="confidence-badge ${info.className}"><i></i>${info.label}</span>`
          }
        </div>
        <button class="forecast-btn" type="button" data-open="${row.lead}">Подробнее <span aria-hidden="true">→</span></button>
      </div>
    `;
  }

  function visibleRows() {
    if (!state.payload) return [];
    return state.payload.rows.filter((row) => Number(row.lead) <= state.period);
  }

  function renderCards() {
    const grid = $("#forecast-grid");
    if (!grid || !state.payload) return;
    grid.replaceChildren();

    visibleRows().forEach((row) => {
      const card = document.createElement("article");
      card.className = "forecast-card";
      card.dataset.lead = String(row.lead);
      card.innerHTML = cardMarkup(row);
      grid.appendChild(card);
    });

    $$("[data-open]", grid).forEach((button) => {
      button.addEventListener("click", () => {
        const row = state.payload.rows.find((item) => String(item.lead) === button.dataset.open);
        if (row) openModal(row);
      });
    });
  }

  function renderList() {
    const list = $("#forecast-list");
    if (!list || !state.payload) return;
    const rows = visibleRows();
    const sourceLabel = state.payload.provider_label || null;
    const heading = `
      <div class="forecast-list-head">
        <span>День</span><span>Погода</span><span>${sourceLabel ? "Прогноз" : "Ансамбль"}</span><span>${sourceLabel ? "Источник" : "Официальный"}</span><span>${sourceLabel ? "Горизонт" : "Разница"}</span><span>${sourceLabel ? "" : "Разброс"}</span><span></span>
      </div>`;
    const body = rows
      .map((row) => {
        const date = parseDate(row.date);
        const visual = condition(row);
        const official = row.official_tmax === null || row.official_tmax === undefined ? "—" : temp(row.official_tmax);
        const difference =
          row.official_tmax === null || row.official_tmax === undefined || row.ensemble_tmax === null
            ? "—"
            : delta(Number(row.ensemble_tmax) - Number(row.official_tmax));
        const spread = row.model_spread === null || row.model_spread === undefined ? "—" : "±" + number(row.model_spread) + "°";
        const shown = row.ensemble_tmax ?? row.official_tmax;
        return `
          <div class="forecast-list-row">
            <div class="forecast-list-date">
              <div><b>${capitalize(weekdayShort.format(date))}</b><span>${dateShort.format(date)}</span></div>
            </div>
            <div class="forecast-list-condition">${WEATHER_ICONS[visual.key] || WEATHER_ICONS.cloud}<span>${visual.label}</span></div>
            <div class="forecast-list-temp">${temp(shown)}</div>
            <div class="forecast-list-meta forecast-list-official">${sourceLabel || official}</div>
            <div class="forecast-list-meta">${sourceLabel ? `${row.lead} дн.` : difference}</div>
            <div class="forecast-list-meta">${sourceLabel ? "" : spread}</div>
            <button class="forecast-list-open" type="button" data-open="${row.lead}">→</button>
          </div>`;
      })
      .join("");
    list.innerHTML = heading + body;
    $$("[data-open]", list).forEach((button) => {
      button.addEventListener("click", () => {
        const row = state.payload.rows.find((item) => String(item.lead) === button.dataset.open);
        if (row) openModal(row);
      });
    });
  }

  function applyView() {
    const grid = $("#forecast-grid");
    const list = $("#forecast-list");
    if (!grid || !list) return;
    grid.hidden = state.view === "list";
    list.hidden = state.view !== "list";
    $$("[data-view]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === state.view);
    });
  }

  function setView(view) {
    state.view = view === "list" ? "list" : "cards";
    localStorage.setItem("oracle-view", state.view);
    applyView();
  }

  function updateLiveMeta() {
    if (!state.payload) return;
    const count = visibleRows().length;
    const n = Math.abs(count) % 100;
    const n1 = n % 10;
    const word =
      n1 === 1 && n !== 11
        ? "прогноз"
        : n1 >= 2 && n1 <= 4 && (n < 12 || n > 14)
        ? "прогноза"
        : "прогнозов";
    const source = state.payload.provider_label;
    const statusText = source
      ? "Данные актуальны · " + count + " " + word + " · " + source
      : "Данные актуальны · " + count + " " + word;
    setText("live-status", statusText);
    const status = $("#live-status");
    if (status) {
      status.innerHTML = '<i class="dot-pulse"></i> ' + statusText;
    }
    const issued = parseDate(state.payload.issue_date);
    setText(
      "live-issued",
      source
        ? "Источник: " + source
        : "Выпуск " + dateShort.format(issued) + " · Open-Meteo"
    );
    const note = $("#period-note");
    if (note) {
      note.textContent = source
        ? "Живой прогноз: " + source + ". Официальный baseline Open-Meteo недоступен."
        : "Дни 1–14 — ML-ансамбль. Официальный baseline доступен до 7 дней.";
    }
    if (source) {
      setText(
        "hero-lede",
        "Живой прогноз " + source + " на 14 дней. ML-ансамбль, честные метрики и сравнение с официальным baseline — на страницах «Сравнение» и «Модели»."
      );
      setText(
        "forecast-sub",
        "Источник живого прогноза — " + source + ". Выберите период и посмотрите температуру по дням."
      );
    }
  }

  function updateOfflineNotice() {
    const box = $("#forecast-offline");
    if (box) box.hidden = true;
  }

  function renderTrendChart() {
    const svg = $("#trend-chart");
    const wrap = $(".trend-chart-wrap");
    const tooltip = $("#trend-tooltip");
    if (!svg || !wrap || !state.payload) return;

    const rows = visibleRows();
    const sourceLabel = state.payload.provider_label;
    setText("trend-ensemble-label", sourceLabel || "Ансамбль");
    const officialLegend = $("#trend-official-legend");
    if (officialLegend) officialLegend.hidden = Boolean(sourceLabel);
    const values = [];
    rows.forEach((row) => {
      if (row.ensemble_tmax !== null && row.ensemble_tmax !== undefined) values.push(Number(row.ensemble_tmax));
      if (row.official_tmax !== null && row.official_tmax !== undefined) values.push(Number(row.official_tmax));
    });
    if (!values.length) {
      svg.innerHTML = "";
      return;
    }

    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const padding = Math.max(1.5, (maxValue - minValue) * 0.16);
    const low = Math.floor(minValue - padding);
    const high = Math.ceil(maxValue + padding);
    const W = 1000;
    const H = 320;
    const left = 54;
    const right = 22;
    const top = 22;
    const bottom = 38;
    const plotW = W - left - right;
    const plotH = H - top - bottom;
    const x = (index) => left + (rows.length <= 1 ? plotW / 2 : (index / (rows.length - 1)) * plotW);
    const y = (value) => top + ((high - value) / (high - low)) * plotH;

    const grid = [];
    for (let step = 0; step <= 4; step += 1) {
      const value = low + ((high - low) * step) / 4;
      const gy = y(value);
      grid.push(
        `<line class="trend-grid-line" x1="${left}" y1="${gy}" x2="${W - right}" y2="${gy}"></line>`,
        `<text class="trend-y-label" x="${left - 10}" y="${gy + 3}" text-anchor="end">${number(convert(value), 0)}°</text>`
      );
    }

    const xLabels = [];
    const step = Math.max(1, Math.ceil(rows.length / 7));
    rows.forEach((row, index) => {
      if (index % step !== 0 && index !== rows.length - 1) return;
      xLabels.push(
        `<text class="trend-axis-label" x="${x(index)}" y="${H - 12}" text-anchor="middle">${dateShort.format(parseDate(row.date))}</text>`
      );
    });

    const ensemble = rows
      .map((row, index) => ({ row, index, value: row.ensemble_tmax }))
      .filter((point) => point.value !== null && point.value !== undefined);
    const official = rows
      .map((row, index) => ({ row, index, value: row.official_tmax }))
      .filter((point) => point.value !== null && point.value !== undefined);

    const linePath = (points) =>
      points.length
        ? points.map((point, i) => `${i === 0 ? "M" : "L"}${x(point.index).toFixed(1)},${y(Number(point.value)).toFixed(1)}`).join(" ")
        : "";
    const areaPath = ensemble.length
      ? `${linePath(ensemble)} L${x(ensemble[ensemble.length - 1].index).toFixed(1)},${top + plotH} L${x(ensemble[0].index).toFixed(1)},${top + plotH} Z`
      : "";

    const dots = ensemble
      .map(
        (point) =>
          `<circle class="trend-point" cx="${x(point.index)}" cy="${y(Number(point.value))}" r="3.6" data-index="${point.index}" data-date="${point.row.date}" data-ensemble="${point.value}" data-official="${point.row.official_tmax ?? ""}" data-spread="${point.row.model_spread ?? ""}"></circle>`
      )
      .join("");
    const officialDots = official
      .map(
        (point) =>
          `<circle class="trend-point trend-point-official" cx="${x(point.index)}" cy="${y(Number(point.value))}" r="2.8" data-index="${point.index}" data-date="${point.row.date}" data-ensemble="${point.row.ensemble_tmax ?? ""}" data-official="${point.value}" data-spread="${point.row.model_spread ?? ""}"></circle>`
      )
      .join("");

    svg.innerHTML = `
      ${grid.join("")}
      ${areaPath ? `<path class="trend-area" d="${areaPath}"></path>` : ""}
      ${linePath(ensemble) ? `<path class="trend-line" d="${linePath(ensemble)}"></path>` : ""}
      ${linePath(official) ? `<path class="trend-line-official" d="${linePath(official)}"></path>` : ""}
      ${xLabels.join("")}
      ${dots}
      ${officialDots}
    `;

    const hideTooltip = () => {
      if (tooltip) tooltip.hidden = true;
      $$(".trend-point", svg).forEach((point) => point.classList.remove("is-active"));
    };

    $$(".trend-point", svg).forEach((point) => {
      point.addEventListener("mouseenter", () => {
        if (!tooltip) return;
        hideTooltip();
        point.classList.add("is-active");
        const date = parseDate(point.dataset.date);
        const officialValue = point.dataset.official;
        const spread = point.dataset.spread;
        tooltip.innerHTML = `<b>${capitalize(weekdayShort.format(date))}, ${dateLong.format(date)}</b>
          <span>${sourceLabel || "Ансамбль"} <em>${temp(point.dataset.ensemble)}</em></span>
          <span>Официальный <em>${officialValue === "" ? "—" : temp(officialValue)}</em></span>
          <span>Разброс <em>${spread === "" ? "—" : "±" + number(spread) + "°"}</em></span>`;
        tooltip.hidden = false;
        const pointRect = point.getBoundingClientRect();
        const wrapRect = wrap.getBoundingClientRect();
        const leftPos = pointRect.left - wrapRect.left + pointRect.width / 2;
        const topPos = pointRect.top - wrapRect.top;
        tooltip.style.left = `${Math.max(8, Math.min(wrapRect.width - 170, leftPos - 75))}px`;
        tooltip.style.top = `${Math.max(8, topPos - tooltip.offsetHeight - 12)}px`;
      });
      point.addEventListener("mouseleave", hideTooltip);
    });
  }

  function render() {
    if (!state.payload) return;
    if (document.body.dataset.page && document.body.dataset.page !== "forecast") return;
    renderHero(state.payload.rows[0]);
    renderCards();
    renderList();
    applyView();
    updateLiveMeta();
    updateUnitButtons();
    renderPeriodButtons();
    renderTrendChart();
    updateOfflineNotice();
  }

  function normalizePeriod(value) {
    const number = Number(value);
    return [7, 10, 14].includes(number) ? number : 7;
  }

  function renderPeriodButtons() {
    $$("[data-period]").forEach((button) => {
      button.classList.toggle("is-active", Number(button.dataset.period) === state.period);
    });
  }

  function setPeriod(value) {
    state.period = normalizePeriod(value);
    localStorage.setItem("oracle-period", String(state.period));
    renderPeriodButtons();
    if (state.payload) {
      renderCards();
      renderList();
      updateLiveMeta();
      renderTrendChart();
    }
  }

  function updateUnitButtons() {
    $$("[data-unit]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.unit === state.unit);
    });
  }

  function setUnit(unit) {
    if (unit !== "c" && unit !== "f") return;
    state.unit = unit;
    localStorage.setItem("oracle-unit", unit);
    updateUnitButtons();
    if (state.payload) render();
    const modal = $("#forecast-modal");
    if (modal && modal.open) {
      const lead = modal.dataset.lead;
      const row = state.payload && state.payload.rows.find((item) => String(item.lead) === lead);
      if (row) openModal(row);
    }
  }

  function modelBarsMarkup(row) {
    const components = row.components || {};
    const values = Object.keys(MODEL_NAMES)
      .map((key) => ({ key, value: Number(components[key]) }))
      .filter((item) => Number.isFinite(item.value));
    if (!values.length) return "";
    const min = Math.min(...values.map((item) => item.value));
    const max = Math.max(...values.map((item) => item.value));
    return values
      .map((item) => {
        const width = max === min ? 50 : 25 + ((item.value - min) / (max - min)) * 75;
        return `
          <div class="model-bar-row">
            <span>${MODEL_NAMES[item.key]}</span>
            <div class="model-bar-track"><div class="model-bar-fill" style="width:${width}%"></div></div>
            <b>${temp(item.value)}</b>
          </div>
        `;
      })
      .join("");
  }

  function openModal(row) {
    const modal = $("#forecast-modal");
    const body = $("#modal-body");
    if (!modal || !body) return;

    const date = parseDate(row.date);
    const visual = condition(row);
    const info = confidence(row.model_spread);
    const officialOnly = row.ensemble_tmax === null || row.ensemble_tmax === undefined;
    const sourceLabel = row.provider_label || null;
    const shownTemp = officialOnly ? row.official_tmax : row.ensemble_tmax;
    const official =
      row.official_tmax === null || row.official_tmax === undefined
        ? "—"
        : temp(row.official_tmax);
    const difference =
      officialOnly || row.official_tmax === null || row.official_tmax === undefined
        ? "—"
        : delta(Number(row.ensemble_tmax) - Number(row.official_tmax));

    body.innerHTML = `
      <span class="modal-eyebrow">${sourceLabel ? "ЖИВОЙ ПРОГНОЗ · " + sourceLabel.toUpperCase() : officialOnly ? "ОФИЦИАЛЬНЫЙ ПРОГНОЗ" : "ДЕТАЛИ ПРОГНОЗА"} · H=${row.lead}</span>
      <div class="modal-head">
        <div class="modal-icon">${WEATHER_ICONS[visual.key] || WEATHER_ICONS.cloud}</div>
        <div>
          <h3 class="modal-title" id="modal-title">${capitalize(weekdayLong.format(date))}, ${dateLong.format(date)}</h3>
          <p class="modal-date">${visual.label} · ${state.unit === "c" ? "Цельсий" : "Фаренгейт"}</p>
        </div>
        <div class="modal-temp">${number(convert(shownTemp))}<small>°${state.unit.toUpperCase()}</small></div>
      </div>
      ${
        sourceLabel
          ? `<div class="modal-stats">
               <div class="modal-stat"><span>Источник</span><b>${sourceLabel}</b></div>
               <div class="modal-stat"><span>Горизонт</span><b>${row.lead} дн.</b></div>
               <div class="modal-stat"><span>Тип</span><b>оперативный</b></div>
             </div>
             <p class="modal-note">Оперативный прогноз ${sourceLabel} для текущей даты. ML-ансамбль и официальный baseline Open-Meteo сейчас недоступны.</p>`
          : officialOnly
          ? `<div class="modal-stats">
               <div class="modal-stat"><span>Источник</span><b>Open-Meteo</b></div>
               <div class="modal-stat"><span>Горизонт</span><b>${row.lead} дн.</b></div>
               <div class="modal-stat"><span>Тип</span><b>официальный</b></div>
             </div>
             <p class="modal-note">Для дней 8–14 показывается оперативный прогноз Open-Meteo: ML-ансамбль обучен до 7 дней.</p>`
          : `<div class="modal-stats">
               <div class="modal-stat"><span>Официальный</span><b>${official}</b></div>
               <div class="modal-stat"><span>Разница</span><b>${difference}</b></div>
               <div class="modal-stat"><span>Разброс</span><b>${row.model_spread === undefined ? "—" : "±" + number(row.model_spread) + "°"}</b></div>
             </div>
             <div class="modal-section-label">КАК ГОЛОСОВАЛИ МОДЕЛИ</div>
             <div class="model-bars">${modelBarsMarkup(row)}</div>
             <p class="modal-note">${info.label.charAt(0).toUpperCase() + info.label.slice(1)}. Официальный прогноз Open-Meteo — архив Previous Runs, не Росгидромет. Разброс — разница между базовыми моделями, а не доверительный интервал.</p>`
      }
      <div class="modal-actions">
        <button class="btn btn-outline" type="button" data-share>Поделиться</button>
      </div>
    `;

    modal.dataset.lead = String(row.lead);
    if (!modal.open) {
      state.lastFocus = document.activeElement;
      modal.showModal();
    }

    const share = $("[data-share]", body);
    if (share) share.addEventListener("click", () => shareForecast(row));
  }

  async function shareForecast(row) {
    const officialOnly = row.ensemble_tmax === null || row.ensemble_tmax === undefined;
    const valueText = row.provider_label
      ? `${temp(row.ensemble_tmax)} (${row.provider_label})`
      : officialOnly
      ? `${temp(row.official_tmax)} (официальный Open-Meteo)`
      : `${temp(row.ensemble_tmax)} (ансамбль), официальный ${temp(row.official_tmax)}`;
    const text = `Погодный оракул: ${capitalize(dateLong.format(parseDate(row.date)))} — ${valueText}. ${window.location.href}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "Погодный оракул", text, url: window.location.href });
        return;
      }
      await navigator.clipboard.writeText(text);
      showToast("Прогноз скопирован");
    } catch (error) {
      if (error && error.name !== "AbortError") showToast("Не удалось поделиться");
    }
  }

  function setLoading() {
    const grid = $("#forecast-grid");
    if (!grid || state.payload) return;
    grid.innerHTML = '<div class="forecast-skeleton"></div><div class="forecast-skeleton"></div><div class="forecast-skeleton"></div>';
  }

  async function loadForecast(force = false) {
    if (!$("#forecast-grid")) return;
    const status = $("#live-status");
    const errorBox = $("#forecast-error");
    const refresh = $("#refresh-forecast");
    if (status) status.innerHTML = '<i class="dot-pulse"></i> Загружаю свежий прогноз…';
    if (errorBox) errorBox.hidden = true;
    if (refresh) refresh.classList.add("is-spinning");
    if (!state.payload) setLoading();

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch(
        "/api/forecast?city=" + encodeURIComponent(state.city) + (force ? "&refresh=true" : ""),
        { headers: { Accept: "application/json" }, signal: controller.signal }
      );
      if (!response.ok) {
        let detail = "HTTP " + response.status;
        try {
          const data = await response.json();
          if (data && data.detail) detail = data.detail;
        } catch (_) { /* ignore */ }
        throw new Error(detail);
      }
      state.payload = await response.json();
      render();
      if (force) showToast("Прогноз обновлён");
    } catch (error) {
      const message = error && error.name === "AbortError"
        ? "Сервер не ответил за 30 секунд. Проверьте интернет и нажмите «Повторить»."
        : error && error.message
        ? error.message
        : "Проверьте соединение";
      if (errorBox) {
        errorBox.hidden = false;
        setText("forecast-error-text", message);
      }
      if (!state.payload) {
        const grid = $("#forecast-grid");
        if (grid) grid.innerHTML = "";
        const issued = $("#live-issued");
        if (issued) issued.textContent = "";
      }
      if (status) {
        status.innerHTML = '<i class="dot-pulse"></i> Нет свежих данных';
      }
    } finally {
      window.clearTimeout(timeout);
      if (refresh) refresh.classList.remove("is-spinning");
    }
  }

  function updateNetwork() {
    const pill = $("#network-status");
    if (!pill) return;
    const online = navigator.onLine;
    pill.classList.toggle("is-offline", !online);
    const text = pill.querySelector("span");
    if (text) text.textContent = online ? "онлайн" : "офлайн";
    if (!online) showToast("Вы офлайн — показываю последний прогноз");
  }

  function setupInstall() {
    const buttons = [$("#install-app"), $("#install-app-hero"), $("#install-tab")].filter(Boolean);
    const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
    if (standalone) {
      buttons.forEach((button) => { button.hidden = true; });
      return;
    }

    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      state.installPrompt = event;
      const button = $("#install-app");
      if (button) button.hidden = false;
    });

    buttons.forEach((button) => {
      button.addEventListener("click", async () => {
        if (state.installPrompt) {
          state.installPrompt.prompt();
          const result = await state.installPrompt.userChoice;
          if (result.outcome === "accepted") showToast("Приложение установлено");
          state.installPrompt = null;
          return;
        }
        showToast("Меню браузера → «Установить приложение» или «На экран Домой»");
      });
    });

    window.addEventListener("appinstalled", () => {
      state.installPrompt = null;
      $("#install-app")?.setAttribute("hidden", "");
      showToast("Погодный оракул установлен");
    });
  }

  function setupModal() {
    const modal = $("#forecast-modal");
    if (!modal) return;
    $$("[data-close]", modal).forEach((button) => {
      button.addEventListener("click", () => modal.close());
    });
    modal.addEventListener("click", (event) => {
      if (event.target === modal) modal.close();
    });
    modal.addEventListener("close", () => {
      if (state.lastFocus && typeof state.lastFocus.focus === "function") state.lastFocus.focus();
    });
  }

  function setupNav() {
    const header = $("#site-header");
    const onScroll = () => {
      header?.classList.toggle("is-stuck", window.scrollY > 8);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  function setupServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {
        /* офлайн-режим не критичен для работы интерфейса */
      });
    });
  }

  function setupCityPicker() {
    const picker = $("#city-picker");
    const trigger = $("#city-trigger");
    const menu = $("#city-menu");
    const search = $("#city-search");
    const empty = $("#city-empty");
    if (!picker || !trigger || !menu) return;

    const filterCities = () => {
      const query = (search?.value || "").trim().toLowerCase();
      let visible = 0;
      $$("[data-city-group]", menu).forEach((group) => {
        let groupVisible = 0;
        $$(".city-option", group).forEach((option) => {
          const match = !query || (option.dataset.cityName || "").includes(query);
          option.hidden = !match;
          if (match) groupVisible += 1;
        });
        group.hidden = groupVisible === 0;
        visible += groupVisible;
      });
      if (empty) empty.hidden = visible > 0;
    };

    const setOpen = (open) => {
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      if (open) {
        if (search) search.value = "";
        filterCities();
        menu.querySelector(".city-option.is-selected")?.scrollIntoView({ block: "nearest" });
      }
    };

    search?.addEventListener("input", filterCities);

    $("#geo-city")?.addEventListener("click", () => {
      if (!navigator.geolocation) {
        showToast("Геолокация недоступна в этом браузере");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          const options = $$(".city-option", menu);
          let nearest = null;
          let best = Infinity;
          options.forEach((option) => {
            const dLat = Number(option.dataset.lat) - lat;
            const dLon = Number(option.dataset.lon) - lon;
            const distance = dLat * dLat + dLon * dLon;
            if (distance < best) {
              best = distance;
              nearest = option;
            }
          });
          if (nearest) {
            const url = new URL(window.location.href);
            url.searchParams.set("city", nearest.dataset.city);
            window.location.href = url.toString();
          }
        },
        () => showToast("Не удалось определить город — выберите вручную"),
        { timeout: 8000, maximumAge: 600000 }
      );
    });

    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      setOpen(menu.hidden);
    });

    menu.addEventListener("click", (event) => {
      const option = event.target.closest("[data-city]");
      if (!option) return;
      const slug = option.dataset.city;
      if (slug && slug !== state.city) {
        const url = new URL(window.location.href);
        url.searchParams.set("city", slug);
        window.location.href = url.toString();
      } else {
        setOpen(false);
      }
    });

    document.addEventListener("click", (event) => {
      if (!picker.contains(event.target)) setOpen(false);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !menu.hidden) {
        setOpen(false);
        trigger.focus();
      }
      if ((event.key === "ArrowDown" || event.key === "ArrowUp") && !menu.hidden) {
        event.preventDefault();
        const options = $$(".city-option", menu).filter((option) => !option.hidden);
        const index = options.indexOf(document.activeElement);
        const next = event.key === "ArrowDown"
          ? options[Math.min(options.length - 1, index + 1)]
          : options[Math.max(0, index - 1)];
        next?.focus();
      }
    });
  }

  function downloadCsv() {
    if (!state.payload) return;
    const rows = visibleRows();
    const header = ["date", "lead", "ensemble_c", "official_c", "spread_c", "precip_mm"];
    const lines = rows.map((row) => [
      row.date,
      row.lead,
      row.ensemble_tmax ?? "",
      row.official_tmax ?? "",
      row.model_spread ?? "",
      row.precip_mm ?? "",
    ]);
    const csv = [header, ...lines]
      .map((line) => line.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(";"))
      .join("\r\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `weather-oracle-${state.city}-${state.payload.issue_date}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function setupDownload() {
    $("#download-csv")?.addEventListener("click", downloadCsv);
  }

  function setupCopyButtons() {
    $$("[data-copy]").forEach((button) => {
      button.addEventListener("click", async () => {
        const text = button.dataset.copy || "";
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          const area = document.createElement("textarea");
          area.value = text;
          area.style.position = "fixed";
          area.style.opacity = "0";
          document.body.appendChild(area);
          area.select();
          document.execCommand("copy");
          area.remove();
        }
        const label = button.textContent;
        button.textContent = "Скопировано";
        button.classList.add("is-copied");
        window.setTimeout(() => {
          button.textContent = label;
          button.classList.remove("is-copied");
        }, 1600);
      });
    });
  }

  function setupHeroSlideshow() {
    const slides = $$(".hero-slide");
    const dots = $$("[data-slide]");
    if (slides.length < 2) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let index = Math.max(0, slides.findIndex((slide) => slide.classList.contains("is-active")));
    let timer = 0;

    const show = (next) => {
      index = (next + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
      dots.forEach((dot, i) => dot.classList.toggle("is-active", i === index));
    };

    const stop = () => {
      if (timer) window.clearInterval(timer);
      timer = 0;
    };

    const start = () => {
      stop();
      if (reduceMotion || slides.length < 2) return;
      timer = window.setInterval(() => show(index + 1), 7000);
    };

    dots.forEach((dot) => {
      dot.addEventListener("click", () => {
        show(Number(dot.dataset.slide));
        start();
      });
    });

    const hero = $(".hero");
    hero?.addEventListener("mouseenter", stop);
    hero?.addEventListener("mouseleave", start);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop();
      else start();
    });
    start();
  }

  function setupControls() {
    $$("[data-period]").forEach((button) => {
      button.addEventListener("click", () => setPeriod(button.dataset.period));
    });
    $$("[data-view]").forEach((button) => {
      button.addEventListener("click", () => setView(button.dataset.view));
    });
    $$("[data-unit]").forEach((button) => {
      button.addEventListener("click", () => setUnit(button.dataset.unit));
    });
    $("#refresh-forecast")?.addEventListener("click", () => loadForecast(true));
    $("#retry-forecast")?.addEventListener("click", () => loadForecast(true));
    setupCityPicker();
    setupCopyButtons();
    setupHeroSlideshow();
    setupDownload();
  }

  function start() {
    document.body.classList.add("has-tabbar");
    if (new URLSearchParams(window.location.search).has("desktop") || window.pywebview) {
      document.documentElement.classList.add("desktop-app");
    }
    updateNetwork();
    updateUnitButtons();
    setupControls();
    setupModal();
    setupInstall();
    setupNav();
    setupServiceWorker();
    window.addEventListener("online", () => {
      updateNetwork();
      if (document.body.dataset.page === "forecast") loadForecast(true);
    });
    window.addEventListener("offline", updateNetwork);
    if (document.body.dataset.page === "forecast") {
      window.setInterval(() => {
        if (!document.hidden && navigator.onLine) loadForecast(true);
      }, 15 * 60 * 1000);
    }
    loadForecast(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
