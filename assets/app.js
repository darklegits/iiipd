/* ============================================================
   DotaPicker — логика поиска и рендера контрпиков
   ============================================================ */

const ATTR_RU = { str: "Сила", agi: "Ловкость", int: "Интеллект", all: "Универсал" };
const ROLE_RU = {
  Carry: "Керри", Escape: "Побег", Nuker: "Нюкер", Support: "Саппорт",
  Disabler: "Контроль", Initiator: "Инициатор", Durable: "Танк",
  Pusher: "Пушер", Jungler: "Лесник",
};

const POPULAR = [
  "pudge", "phantom_lancer", "invoker", "anti_mage", "juggernaut",
  "sniper", "legion_commander", "medusa", "spectre", "slark",
];

/* Запасной вариант, если OpenDota недоступна: кто концептуально контрит тег. */
const TAG_COUNTERS = {
  illusions: ["sven", "earthshaker", "axe", "gyrocopter", "ember_spirit", "sand_king"],
  mana_burn: ["antimage", "nyx_assassin", "obsidian_destroyer", "invoker"],
  mana: ["antimage", "nyx_assassin", "obsidian_destroyer", "invoker"],
  escape: ["doom_bringer", "legion_commander", "spirit_breaker", "bloodseeker", "slark"],
  invis: ["slardar", "bounty_hunter", "bloodseeker", "zuus", "disruptor"],
  heal: ["ancient_apparition", "doom_bringer", "viper", "silencer"],
  lifesteal: ["ancient_apparition", "viper", "doom_bringer"],
  evasion: ["tinker", "legion_commander", "axe", "bloodseeker"],
  summon: ["axe", "sven", "earthshaker", "shredder"],
  silence: ["abaddon", "oracle", "omniknight"],
  stun: ["lifestealer", "juggernaut", "abaddon"],
  burst: ["abaddon", "oracle", "dazzle", "winter_wyvern"],
  slow: ["slark", "abaddon", "storm_spirit"],
  tank: ["ancient_apparition", "ursa", "life_stealer", "doom_bringer"],
  push: ["earthshaker", "axe", "shredder", "sven"],
  single_target: ["abaddon", "oracle", "dazzle"],
  duel: ["winter_wyvern", "oracle", "pugna"],
  kite: ["spirit_breaker", "storm_spirit", "slark", "antimage"],
  save: ["doom_bringer", "silencer", "ancient_apparition"],
  global: ["spirit_breaker", "spectre", "storm_spirit"],
  rat: ["spirit_breaker", "storm_spirit", "spectre"],
  passive: ["doom_bringer", "slark", "phantom_assassin"],
  anti_escape: ["disruptor", "legion_commander", "doom_bringer"],
  anti_int: ["nyx_assassin", "antimage", "obsidian_destroyer"],
  anti_tank: ["ancient_apparition", "ursa", "life_stealer"],
  revive: ["antimage", "nyx_assassin", "doom_bringer"],
  spin: ["doom_bringer", "ursa", "phantom_assassin"],
  trap: ["bounty_hunter", "slardar", "zuus"],
  farm: ["spirit_breaker", "bounty_hunter", "riki", "slark"],
  cleave: ["puck", "storm_spirit", "windrunner"],
  dot: ["abaddon", "oracle", "dazzle"],
  ranged: ["storm_spirit", "spirit_breaker", "slark"],
  carry: ["doom_bringer", "legion_commander", "ancient_apparition"],
  nuker: ["antimage", "nyx_assassin", "silencer"],
  initiator: ["silencer", "winter_wyvern", "nyx_assassin"],
  disable: ["lifestealer", "juggernaut", "abaddon"],
  support: ["spirit_breaker", "storm_spirit", "slark"],
};

/* Короткие фразы для авто-объяснений по тегам героя-контрпика. */
const COUNTER_TAG_PHRASE = {
  carry: "переигрывает цель в поздней игре за счёт урона",
  escape: "догоняет и не даёт уйти с линии",
  initiator: "инициирует первым и выключает цель из драки",
  nuker: "убивает с бурста раньше, чем цель успевает ответить",
  support: "даёт команде контроль и сейв в ключевой драке",
  tank: "танкует её урон и затягивает драку",
  disable: "держит цель в контроле почти без окон",
  illusions: "забивает числом и путает фокус",
  invis: "заходит неожиданно и убивает хрупкие цели",
  evasion: "уклоняется от атак и выживает под фокусом",
  summon: "закрывает карту юнитами и давление на линиях",
  heal: "перелечивает урон и вытягивает затяжные драки",
  burst: "наносит слишком много урона за короткое окно",
  global: "присутствует на карте без ходьбы",
  silence: "лишает цель способностей в нужный момент",
  stun: "не даёт цели двигаться и кастовать",
  push: "быстро сносит строения, пока цель фармит",
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  heroes: [],
  byKey: new Map(),
  counters: {},
  items: {},
  tagItems: {},
  synergies: {},
  itemCatalog: {},
  abilities: {},
  heroStats: {},
  matchups: new Map(),
  matchupSource: new Map(),
  loaded: false,
};

const norm = (s) => String(s || "")
  .toLowerCase()
  .replace(/ё/g, "е")
  .replace(/[^a-zа-я0-9]+/g, " ")
  .trim();

/* ------------------------------ данные ------------------------------ */

async function loadData() {
  const [heroes, counters, items, tagItems, heroStats, synergies, abilities, itemCatalog] = await Promise.all([
    fetch("data/heroes.json").then((r) => r.json()),
    fetch("data/counters.json").then((r) => r.json()),
    fetch("data/items.json").then((r) => r.json()),
    fetch("data/tag-items.json").then((r) => r.json()),
    fetch("data/hero-stats.json").then((r) => r.json()).catch(() => ({})),
    fetch("data/synergies.json").then((r) => r.json()).catch(() => ({})),
    fetch("data/hero-abilities.json").then((r) => r.json()).catch(() => ({})),
    fetch("data/items-full.json").then((r) => r.json()).catch(() => ({})),
  ]);
  state.heroes = heroes;
  state.counters = counters;
  state.items = items;
  state.tagItems = tagItems;
  state.heroStats = heroStats || {};
  state.synergies = synergies || {};
  state.abilities = abilities || {};
  state.itemCatalog = itemCatalog || {};
  for (const h of heroes) {
    state.byKey.set(h.key, h);
    h._fields = [h.en, h.ru, h.key.replace(/_/g, " "), ...h.alias].map(norm);
    // Картинки — локальные WebP (генерируются из CDN Steam на сервере):
    // 7 КБ вместо 78 КБ PNG, отдаются тем же доменом.
    h.img = `img/heroes/${h.key}.webp`;
    h.crop = `img/crops/${h.key}.webp`;
    h.icon = `img/heroes/${h.key}-icon.webp`;
  }
  for (const [id, item] of Object.entries(items)) {
    if (item && item.img) item.img = `img/items/${id}.webp`;
  }
  state.loaded = true;
}

const STEAM_CDN = "https://cdn.cloudflare.steamstatic.com/";
const HERO_CDN_PATH = "apps/dota2/images/dota_react/heroes/";
const ITEM_CDN_PATH = "apps/dota2/images/dota_react/items/";

// Если локального WebP нет — грузим PNG через кэширующий прокси сайта.
document.addEventListener("error", (e) => {
  const el = e.target;
  if (!(el instanceof HTMLImageElement)) return;
  const src = el.getAttribute("src") || "";
  const localCrop = src.match(/^img\/crops\/([a-z0-9_]+)\.webp$/);
  if (localCrop) {
    el.removeAttribute("src");
    el.src = `img/heroes/${localCrop[1]}.webp`;
    return;
  }
  const crop = src.match(/^\/steamimg\/.*\/heroes\/crops\/([a-z0-9_]+)\.png$/);
  if (crop) {
    el.removeAttribute("src");
    el.src = `img/heroes/${crop[1]}.webp`;
    return;
  }
  const hero = src.match(/^img\/heroes\/(.+?)(-icon)?\.webp$/);
  const item = src.match(/^img\/items\/(.+)\.webp$/);
  let fallback = null;
  if (hero) fallback = `/steamimg/${HERO_CDN_PATH}${hero[2] ? "icons/" : ""}${hero[1]}.png`;
  else if (item) fallback = `/steamimg/${ITEM_CDN_PATH}${item[1]}.png`;
  if (fallback) {
    el.removeAttribute("src");
    el.src = fallback;
  }
}, true);

/* ------------------------------ поиск ------------------------------ */

function searchHeroes(query, limit = 8) {
  const q = norm(query);
  if (!q) return [];
  const scored = [];
  for (const h of state.heroes) {
    let best = 0;
    for (const f of h._fields) {
      if (f === q) best = Math.max(best, 120);
      else if (f.startsWith(q)) best = Math.max(best, 100 - (f.length - q.length));
      else if (new RegExp(`(^| )${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`).test(f)) best = Math.max(best, 85);
      else if (f.includes(q)) best = Math.max(best, 60);
    }
    if (best > 0) scored.push({ hero: h, score: best });
  }
  scored.sort((a, b) => b.score - a.score || a.hero.en.localeCompare(b.hero.en, "en"));
  return scored.slice(0, limit).map((s) => s.hero);
}

function initCollapsibleSearch(wrapId, inputId, triggerId) {
  const wrap = document.getElementById(wrapId);
  const input = document.getElementById(inputId);
  const trigger = document.getElementById(triggerId);
  if (!wrap || !input) return;

  const open = () => {
    wrap.classList.add("is-open");
    input.focus();
  };
  const closeIfEmpty = () => {
    if (!input.value.trim()) wrap.classList.remove("is-open");
  };

  if (trigger) {
    trigger.addEventListener("click", (e) => {
      e.preventDefault();
      if (wrap.classList.contains("is-open")) input.focus();
      else open();
    });
  }
  input.addEventListener("focus", open);
  input.addEventListener("blur", () => setTimeout(closeIfEmpty, 140));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      wrap.classList.remove("is-open");
      input.blur();
    }
  });
}

function setupSearch(input, box, onSelect) {
  let items = [];
  let active = -1;

  const close = () => {
    box.hidden = true;
    box.innerHTML = "";
    active = -1;
  };

  const paint = () => {
    $$(".suggestion", box).forEach((el, i) => el.classList.toggle("is-active", i === active));
    const cur = box.children[active];
    if (cur) cur.scrollIntoView({ block: "nearest" });
  };

  const render = () => {
    const q = input.value.trim();
    if (!q) return close();
    items = searchHeroes(q, 8);
    box.innerHTML = "";
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "suggestion-empty";
      empty.textContent = `Ничего не нашлось по запросу «${q}». Попробуй «пудж», «pl» или «антимаг».`;
      box.appendChild(empty);
      box.hidden = false;
      return;
    }
    items.forEach((hero, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "suggestion";
      btn.setAttribute("role", "option");
      btn.innerHTML = `
        <img class="suggestion-img" src="${hero.img || hero.icon}" alt="" loading="lazy" width="56" height="32">
        <span class="suggestion-text">
          <span class="suggestion-ru">${escapeHtml(hero.en)}</span>
          <span class="suggestion-en">${escapeHtml(hero.ru)}</span>
        </span>
        <span class="suggestion-attr">${escapeHtml(ATTR_RU[hero.attr] || hero.attr)}</span>`;
      btn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        select(hero);
      });
      btn.addEventListener("mouseenter", () => { active = i; paint(); });
      box.appendChild(btn);
    });
    box.hidden = false;
  };

  const select = (hero) => {
    input.value = "";
    close();
    input.blur();
    if (onSelect) onSelect(hero);
    else location.hash = `#/hero/${hero.key}`;
  };

  input.addEventListener("input", render);
  input.addEventListener("focus", () => { if (input.value.trim()) render(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { close(); input.blur(); return; }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!items.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      paint();
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (items[active >= 0 ? active : 0]) select(items[active >= 0 ? active : 0]);
    }
  });
  input.addEventListener("blur", () => setTimeout(close, 120));
}

/* ------------------------------ рендер данных героя ------------------------------ */

function targetItems(hero) {
  const curated = state.counters[hero.key]?.items;
  if (curated?.length) return curated;
  return tagDerivedItems(hero);
}

function tagDerivedItems(hero) {
  const keys = [];
  for (const tag of hero.tags) {
    for (const item of state.tagItems[tag] || []) {
      if (!keys.includes(item)) keys.push(item);
      if (keys.length >= 6) return keys;
    }
  }
  return keys.slice(0, 6);
}

function tagDerivedThreat(hero) {
  const roles = hero.roles.map((r) => ROLE_RU[r] || r).join(", ");
  const detail = hero.tags.length
    ? ` Сильные стороны: ${hero.tags.map(tagRu).join(", ")}.`
    : "";
  return `Роли: ${roles}.${detail} Автоматическая сводка по роли и тегам героя.`;
}

const TAG_RU = {
  illusions: "иллюзии", mana_burn: "сжигание маны", invis: "невидимость", heal: "лечение",
  evasion: "уклонение", summon: "призывы", silence: "сайленс", stun: "станы", burst: "бурст",
  slow: "замедления", tank: "танк", push: "пуш", single_target: "игра в одну цель",
  kite: "кайт", save: "спасение союзников", global: "глобальное присутствие",
  rat: "рат-стратегия", passive: "сильная пассивка", anti_escape: "анти-побег",
  anti_int: "анти-интеллект", anti_tank: "анти-танк", revive: "возрождение",
  dot: "урон по времени", lifesteal: "вампиризм", mana: "зависимость от маны",
  spin: "магическая неуязвимость", trap: "ловушки", duel: "дуэль", farm: "быстрый фарм",
  carry: "керри-потенциал", nuker: "нюк", initiator: "инициация", disable: "контроль",
  support: "саппорт", ranged: "дальний бой", cleave: "клир", escape: "побег",
};
const tagRu = (t) => TAG_RU[t] || t;

function getWinrate(heroId, counterId) {
  const rows = state.matchups.get(heroId);
  if (!rows) return null;
  const row = rows.find((r) => r.hero_id === counterId);
  if (!row || !row.games_played) return null;
  // OpenDota отдаёт винрейт искомого героя против каждого героя,
  // поэтому сила контрпика — это 100% минус его винрейт.
  return { wr: (1 - row.wins / row.games_played) * 100, games: row.games_played };
}

async function loadMatchups(hero) {
  if (state.matchups.has(hero.id)) return state.matchups.get(hero.id);

  // 1) Локальный файл, собранный из Stratz: полная база Valve, много матчей.
  try {
    const local = await fetch(`data/matchups/${hero.id}.json`, { cache: "no-store" });
    if (local.ok) {
      const rows = await local.json();
      if (Array.isArray(rows) && rows.length >= 10) {
        state.matchups.set(hero.id, rows);
        state.matchupSource.set(hero.id, "stratz");
        return rows;
      }
    }
  } catch { /* файла нет — падаем в OpenDota */ }

  const cacheKey = `cp:matchups:${hero.id}`;
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey) || "null");
    if (cached && Date.now() - cached.t < 12 * 3600 * 1000) {
      state.matchups.set(hero.id, cached.v);
      return cached.v;
    }
  } catch { /* localStorage может быть недоступен */ }

  const res = await fetch(`https://api.opendota.com/api/heroes/${hero.id}/matchups`, { mode: "cors" });
  if (!res.ok) throw new Error(`OpenDota ${res.status}`);
  const rows = await res.json();
  state.matchups.set(hero.id, rows);
  state.matchupSource.set(hero.id, "opendota");
  try { localStorage.setItem(cacheKey, JSON.stringify({ t: Date.now(), v: rows })); } catch { /* ignore */ }
  return rows;
}

function autoCounters(hero) {
  const rows = state.matchups.get(hero.id) || [];
  // Сглаживание, чтобы 5–10 игр не выкидывали случайного героя на первое место.
  const smoothed = (wins, games) => (wins + 12.5) / (games + 25);
  const candidates = rows
    .filter((r) => r.games_played >= 30)
    .map((r) => ({ hero: state.byKey.get(keyById(r.hero_id)), ...r }));
  const known = candidates.filter((c) => c.hero);
  // Чем ниже винрейт цели против героя, тем сильнее контрпик.
  known.sort((a, b) => smoothed(a.wins, a.games_played) - smoothed(b.wins, b.games_played));
  return known.slice(0, 6).map((c) => {
    const wr = (1 - c.wins / c.games_played) * 100;
    return {
      hero: c.hero,
      why: autoWhy(c.hero, hero, wr, c.games_played),
      items: tagDerivedItems(hero),
      wr,
      games: c.games_played,
      auto: true,
    };
  });
}

function keyById(id) {
  return state.heroes.find((h) => h.id === id)?.key;
}

function autoWhy(counter, target, wr, games) {
  const phrase = counter.tags.map((t) => COUNTER_TAG_PHRASE[t]).find(Boolean)
    || "имеет удобный набор способностей против этой цели";
  return `Винрейт ${wr.toFixed(1)}% на ${games.toLocaleString("ru-RU")} матчах (OpenDota). ${counter.en} ${phrase}.`;
}

function fallbackCounters(hero) {
  const keys = [];
  for (const tag of hero.tags) {
    for (const key of TAG_COUNTERS[tag] || []) {
      const h = state.byKey.get(key);
      if (h && h.key !== hero.key && !keys.includes(key)) keys.push(key);
    }
    if (keys.length >= 6) break;
  }
  if (keys.length < 5) {
    for (const h of state.heroes) {
      if (h.key !== hero.key && !keys.includes(h.key)) keys.push(h.key);
      if (keys.length >= 6) break;
    }
  }
  return keys.slice(0, 6).map((key) => {
    const h = state.byKey.get(key);
    return {
      hero: h,
      why: `${h.en} ${(h.tags.map((t) => COUNTER_TAG_PHRASE[t]).find(Boolean)) || "хорошо отвечает на ключевые механики этой цели"}. Живая статистика OpenDota сейчас недоступна.`,
      items: tagDerivedItems(hero),
      auto: true,
    };
  });
}

/* ------------------------------ рендер страницы героя ------------------------------ */

function heroImage(hero) {
  return hero.crop || hero.img;
}

function renderItems(container, keys, targetName) {
  container.innerHTML = "";
  keys.forEach((key) => {
    const item = state.items[key];
    if (!item) return;
    const card = document.createElement("div");
    card.className = "catalog-item";
    card.title = `${item.name} — контр-предмет против выбранного героя`;
    card.innerHTML = `<img src="${item.img}" alt="${escapeHtml(item.name)}" loading="lazy" width="44" height="32"><span>${escapeHtml(item.name)}</span>`;
    container.appendChild(card);
  });
}

function itemPills(keys) {
  return keys
    .map((key) => {
      const item = state.items[key];
      if (!item) return "";
      return `<span class="item-pill" title="${escapeHtml(item.name)}"><img src="${item.img}" alt="${escapeHtml(item.name)}" loading="lazy" width="34" height="24"></span>`;
    })
    .join("");
}

function renderTargetPanel(hero, counters, source) {
  const panel = $("#targetPanel");
  const items = targetItems(hero);
  const avgWr = counters.filter((c) => c.wr).length
    ? counters.filter((c) => c.wr).reduce((s, c) => s + c.wr, 0) / counters.filter((c) => c.wr).length
    : null;

  panel.innerHTML = `
    <div class="target-image">
      <img src="${heroImage(hero)}" alt="${escapeHtml(hero.en)}" width="512" height="288">
      <div class="target-attr">
        <span class="chip">${escapeHtml(ATTR_RU[hero.attr] || hero.attr)}</span>
        <span class="chip">${hero.attack === "Melee" ? "Ближний бой" : "Дальний бой"}</span>
      </div>
    </div>
    <div class="target-body">
      <p class="target-kicker">Карточка цели</p>
      <div class="target-top">
        <div>
          <h1 class="target-title">${escapeHtml(hero.en)}</h1>
          <p class="target-sub">${escapeHtml(hero.ru)}</p>
        </div>
        ${heroPopBlock(hero)}
      </div>
      <div class="target-roles">
        ${hero.roles.map((r) => `<span class="chip">${escapeHtml(ROLE_RU[r] || r)}</span>`).join("")}
      </div>
      ${abilityRow(hero)}
      <p class="target-threat">${escapeHtml(state.counters[hero.key]?.threat || tagDerivedThreat(hero))}</p>
      <div class="stats-row">
        <div class="stat"><b>${counters.length}</b><span>контрпиков</span></div>
        <div class="stat"><b>${items.length}</b><span>предметов</span></div>
        <div class="stat"><b>${avgWr ? avgWr.toFixed(1) + "%" : "—"}</b><span>средний винрейт</span></div>
        <div class="stat"><b>${source === "curated" ? "Stratz" : "OpenDota"}</b><span>источник</span></div>
      </div>
    </div>`;
}

function counterCard(c, index, target) {
  const hero = c.hero;
  // Курируемые связки несут свою статистику (Dotabuff), авто-подбор — OpenDota.
  // Подмешивать сюда выборку OpenDota нельзя: на малых выборках она врёт.
  const wr = c.wr ?? null;
  const games = c.games ?? null;
  const showWr = wr != null;

  const article = document.createElement("article");
  article.className = "counter-card";
  article.innerHTML = `
    <div class="counter-head">
      <img class="counter-hero" src="${hero.img}" alt="${escapeHtml(hero.en)}" loading="lazy" width="76" height="43">
      <div class="counter-name">
        <h3>${escapeHtml(hero.en)}</h3>
        <span>${escapeHtml(hero.ru)}</span>
      </div>
      ${showWr ? `<span class="wr-chip ${wr >= 50 ? "is-good" : "is-bad"}" title="${games ? games.toLocaleString("ru-RU") + " матчей" : ""}">${wr.toFixed(1)}%</span>` : ""}
      <span class="counter-rank">${index + 1}</span>
    </div>
    <p class="counter-why">${escapeHtml(c.why)}</p>
    <div class="counter-items">${itemPills(c.items.slice(0, 4))}</div>
    <div class="counter-foot">
      <a href="#/hero/${hero.key}">Контрпики: ${escapeHtml(hero.en)} →</a>
      <span class="muted">${c.auto ? "авто-подбор" : "курируемая связка"}</span>
    </div>`;
  return article;
}

let navToken = 0;

const HERO_TABS = ["overview", "abilities", "counters", "builds", "matchups"];

function setHeroTab(tab) {
  const active = HERO_TABS.includes(tab) ? tab : "overview";
  state.heroTab = active;
  document.addEventListener("click", (e) => {
    const abilityBtn = e.target.closest("[data-ability-tab]");
    if (abilityBtn) setHeroTab("abilities");
  });

  document.querySelectorAll("#heroTabs button").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.tab === active);
  });
  for (const name of HERO_TABS) {
    const panel = document.getElementById("tab-" + name);
    if (panel) panel.hidden = name !== active;
  }
  if (active === "builds" && state.currentHero) {
    renderBuilds(state.currentHero, "#heroBuildResult", true);
  }
  if (state.currentHero && active === "abilities") {
    renderAbilities(state.currentHero);
    const nameEl = $("#abilityTargetName");
    if (nameEl) nameEl.textContent = state.currentHero.en;
  }
}

async function showHero(key, tab) {
  const hero = state.byKey.get(key);
  if (!hero) { showLanding(); return; }
  // Если пользователь быстро переключил героя, старый рендер не должен перетирать новый.
  const token = ++navToken;

  $("#landing").hidden = true;
  $("#heroes").hidden = true;
  setHowHidden(true);
  const view = $("#heroView");
  view.hidden = false;

  const grid = $("#counterGrid");
  const itemGrid = $("#itemGrid");
  const badge = $("#sourceBadge");
  const wrNote = $("#wrNote");
  $("#itemsTargetName").textContent = hero.en;
  $("#counterGrid").innerHTML = Array.from({ length: 3 }, () => '<div class="skeleton"></div>').join("");
  itemGrid.innerHTML = "";
  badge.className = "source-badge";
  badge.textContent = "";
  wrNote.textContent = "";
  state.currentHero = hero;
  document.title = `${hero.en} — контрпики | DotaPicker`;
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

  renderItems(itemGrid, targetItems(hero), hero.en);

  const curated = state.counters[hero.key];
  const items = targetItems(hero);

  // Сначала показываем курируемые данные (если есть), параллельно тянем живую статистику.
  let counters = curated
    ? curated.counters.map((c) => ({ ...c, hero: state.byKey.get(c.hero) })).filter((c) => c.hero)
    : [];
  let source = curated ? "curated" : "live";

  if (!curated) {
    try {
      await loadMatchups(hero);
      if (token !== navToken) return;
      counters = autoCounters(hero);
      if (!counters.length) throw new Error("мало данных");
    } catch {
      if (token !== navToken) return;
      counters = fallbackCounters(hero);
      source = "fallback";
    }
  }

  const paint = () => {
    renderTargetPanel(hero, counters, source);
    grid.innerHTML = "";
    counters.forEach((c, i) => grid.appendChild(counterCard(c, i, hero)));
    renderMatchupTable(hero);
    badge.className = `source-badge ${source === "curated" ? "is-curated" : "is-live"}`;
    badge.textContent = source === "curated" ? "Контрпики Stratz" : source === "live" ? "Живые матчапы OpenDota" : "Без статистики: логика тегов";
    wrNote.textContent = source === "live"
      ? "Отсортировано по винрейту против цели"
      : source === "fallback" ? "OpenDota недоступна — показана логика тегов" : "";
  };

  paint();

  // Курируемым связкам живой винрейт OpenDota не подмешиваем (выборка на пару
  // десятков матчей врёт сильнее, чем помогает). Матчапы тянем только для таблицы.
  if (curated) {
    try {
      await loadMatchups(hero);
      if (token !== navToken) return;
      renderMatchupTable(hero);
      wrNote.textContent = counters.some((c) => c.wr != null)
        ? "Винрейты — Stratz · порядок по силе контрпика"
        : "";
    } catch {
      if (token !== navToken) return;
      wrNote.textContent = "";
    }
  }

  setHeroTab(tab || "overview");
}

/* ------------------------------ общие блоки ------------------------------ */

function showLanding() {
  $("#landing").hidden = false;
  $("#heroes").hidden = false;
  setHowHidden(false);
  $("#heroView").hidden = true;
  const block = $("#matchupBlock");
  if (block) block.hidden = true;
  hideToolViews();
  document.title = "DotaPicker — контрпики Dota 2";
}

function renderQuickPicks() {
  const wrap = $("#quickPicks");
  wrap.innerHTML = "";
  for (const key of POPULAR) {
    const hero = state.byKey.get(key);
    if (!hero) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "quick-pick";
    btn.innerHTML = `<img src="${hero.img}" alt="" loading="lazy" width="36" height="21"><span>${escapeHtml(hero.en)}</span>`;
    btn.addEventListener("click", () => { location.hash = `#/hero/${hero.key}`; });
    wrap.appendChild(btn);
  }
}

function renderHeroGrid(filter = "") {
  const grid = $("#heroGrid");
  const q = norm(filter);
  const list = state.heroes
    .filter((h) => !q || h._fields.some((f) => f.includes(q)))
    .sort((a, b) => a.en.localeCompare(b.en, "en"));
  grid.innerHTML = "";
  for (const hero of list) {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "hero-tile";
    tile.title = `${hero.en} · ${hero.ru}`;
    const wr = state.heroStats?.[hero.id]?.win;
    const wrBadge = wr ? `<em class="tile-wr ${wr >= 50 ? "is-good" : "is-bad"}">${wr.toFixed(1)}%</em>` : "";
    tile.innerHTML = `<img src="${hero.crop || hero.img}" alt="${escapeHtml(hero.en)}" loading="lazy" width="400" height="250"><span>${escapeHtml(hero.en)}</span>${wrBadge}`;
    tile.addEventListener("click", () => { location.hash = `#/hero/${hero.key}`; });
    grid.appendChild(tile);
  }
  if (!list.length) grid.innerHTML = '<p class="empty-state" style="grid-column:1/-1">Героев по фильтру не найдено.</p>';
}

const matchupSort = { key: "winrate", dir: "desc" };
let matchupCache = { heroId: null, list: [], total: 0 };

const MATCHUP_COLUMNS = [
  { key: "hero", label: "Герой" },
  { key: "disadvantage", label: "Невыгодное положение" },
  { key: "winrate", label: "Доля побед" },
  { key: "matches", label: "Сыграно матчей" },
];

function matchupBar(value, max, tone) {
  const width = max > 0 ? Math.max(1.5, Math.min(100, (value / max) * 100)) : 0;
  return `<span class="db-track"><span class="db-fill ${tone}" style="width:${width.toFixed(1)}%"></span></span>`;
}

function renderMatchupHead() {
  const head = $("#matchupHead");
  if (!head) return;
  head.innerHTML = `<tr>${MATCHUP_COLUMNS.map((col) => {
    const sorted = matchupSort.key === col.key;
    const arrow = sorted ? (matchupSort.dir === "desc" ? "▼" : "▲") : "";
    return `<th data-sort="${col.key}" class="${sorted ? "is-sorted" : ""}" aria-sort="${sorted ? (matchupSort.dir === "desc" ? "descending" : "ascending") : "none"}">${col.label}${arrow ? `<span class="sort-arrow">${arrow}</span>` : ""}</th>`;
  }).join("")}</tr>`;

  head.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (matchupSort.key === key) {
        matchupSort.dir = matchupSort.dir === "desc" ? "asc" : "desc";
      } else {
        matchupSort.key = key;
        matchupSort.dir = key === "hero" ? "asc" : "desc";
      }
      renderMatchupRows();
    });
  });
}

function renderMatchupRows() {
  const body = $("#matchupBody");
  if (!body) return;
  const { list, total } = matchupCache;
  const maxGames = list.reduce((m, r) => Math.max(m, r.games), 0);
  const maxShare = total ? Math.max(...list.map((r) => (r.games / total) * 100)) : 0;

  const sorted = [...list].sort((a, b) => {
    const dir = matchupSort.dir === "desc" ? -1 : 1;
    if (matchupSort.key === "hero") return dir * a.hero.en.localeCompare(b.hero.en, "en");
    if (matchupSort.key === "matches") return dir * (a.games - b.games);
    if (matchupSort.key === "winrate") return dir * (a.winrate - b.winrate);
    return dir * (a.share - b.share);
  });

  body.innerHTML = sorted.map((r) => {
    const good = r.winrate >= 50;
    return `<tr>
      <td><div class="mu-hero"><img src="${r.hero.img || r.hero.icon}" alt="" loading="lazy" width="38" height="22"><span>${escapeHtml(r.hero.en)}</span></div></td>
      <td><div class="db-bar-row">${matchupBar(r.share, maxShare, "neutral")}<span class="db-num">${r.share.toFixed(2)}%</span></div></td>
      <td><div class="db-bar-row">${matchupBar(r.winrate, 100, good ? "good" : "bad")}<span class="db-num">${r.winrate.toFixed(2)}%</span></div></td>
      <td><div class="db-bar-row db-matches">${matchupBar(r.games, maxGames, "matches")}<span class="db-num">${r.games.toLocaleString("ru-RU")}</span></div></td>
    </tr>`;
  }).join("");
}

function matchupPanel(title, heroes, tone) {
  const rows = heroes.map((r) => `
    <div class="db-panel-row">
      <img src="${r.hero.img || r.hero.icon}" alt="" loading="lazy" width="38" height="22">
      <div class="db-panel-main">
        <span class="db-panel-name">${escapeHtml(r.hero.en)}</span>
        <span class="db-panel-bar"><span class="db-fill ${tone}" style="width:${Math.max(2, Math.min(100, r.winrate)).toFixed(1)}%"></span></span>
      </div>
      <b>${r.winrate.toFixed(2)}%</b>
    </div>`).join("");
  return `<section class="db-panel"><h3>${title}</h3>${rows}</section>`;
}

function renderAbilities(hero) {
  const box = $("#abilityGrid");
  if (!box) return;
  const list = state.abilities?.[hero.key] || [];
  if (!list.length) {
    box.innerHTML = '<p class="tool-empty">Для этого героя нет данных по способностям.</p>';
    return;
  }
  box.innerHTML = list.map((ab) => `
    <article class="ability-card">
      <img class="ability-icon" src="/steamimg${ab.i}" alt="" loading="lazy" width="64" height="64">
      <div class="ability-body">
        <h3>${escapeHtml(ab.n)}</h3>
        <p>${escapeHtml(ab.d)}</p>
      </div>
    </article>`).join("");
}

function renderMatchupTable(hero) {
  const block = $("#matchupBlock");
  const body = $("#matchupBody");
  if (!block || !body) return;

  const rows = state.matchups.get(hero.id) || [];
  const list = rows
    .map((r) => ({ hero: state.byKey.get(keyById(r.hero_id)), games: r.games_played || 0, wins: r.wins || 0 }))
    .filter((r) => r.hero && r.games > 0 && r.hero.id !== hero.id);

  if (list.length < 10) { block.hidden = true; return; }

  const total = list.reduce((sum, r) => sum + r.games, 0);
  const prepared = list.map((r) => ({
    ...r,
    winrate: (r.wins / r.games) * 100,
    share: (r.games / total) * 100,
  }));

  matchupCache = { heroId: hero.id, list: prepared, total };
  if (matchupSort.key === "hero") matchupSort.key = "winrate";
  matchupSort.dir = matchupSort.dir || "desc";

  renderMatchupHead();
  renderMatchupRows();

  const byWinrate = [...prepared].sort((a, b) => a.winrate - b.winrate);
  // Панели — только по героям с вменяемой выборкой, иначе 1 матч даёт «0.00%».
  const MIN_PANEL_GAMES = 30;
  let pool = byWinrate.filter((r) => r.games >= MIN_PANEL_GAMES);
  if (pool.length < 10) pool = [...byWinrate].sort((a, b) => b.games - a.games).slice(0, 20);
  const worst = pool.slice(0, 5);
  const best = pool.slice(-5).reverse();

  $("#matchupPanels").innerHTML =
    matchupPanel(`${escapeHtml(hero.en)} проигрывает`, worst, "bad") +
    matchupPanel(`${escapeHtml(hero.en)} контрит`, best, "good");

  $("#matchupTargetName").textContent = hero.en;
  const source = state.matchupSource.get(hero.id);
  $("#matchupNote").textContent = source === "stratz"
    ? `${list.length} героев · ${total.toLocaleString("ru-RU")} матчей · Stratz, полная база Valve`
    : `${list.length} героев · ${total.toLocaleString("ru-RU")} матчей · выборка OpenDota`;
  block.hidden = false;
}

function abilityRow(hero) {
  const list = state.abilities?.[hero.key] || [];
  if (!list.length) return "";
  return `<div class="hero-ability-row">${list.map((a) => `
    <button type="button" class="hero-ability" data-ability-tab title="${escapeHtml(a.n)} — ${escapeHtml(a.d)}">
      <img src="/steamimg${a.i}" alt="${escapeHtml(a.n)}" loading="lazy" width="38" height="38">
    </button>`).join("")}</div>`;
}

function heroPopBlock(hero) {
  const s = state.heroStats?.[hero.id];
  if (!s) return "";
  return `<div class="hero-pop">
    <div><b>#${s.rank}</b><span>популярность</span></div>
    <div><b>${s.win.toFixed(2)}%</b><span>винрейт</span></div>
  </div>`;
}

function statLine(hero) {
  const s = state.heroStats?.[hero.id];
  if (!s) return "";
  return ` · #${s.rank} по популярности · ${s.win.toFixed(2)}% винрейт`;
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ------------------------------ роутинг и старт ------------------------------ */

/* ------------------------------ связки героев ------------------------------ */

const SYNERGY_RULES = [
  { a: "stun", b: "burst", w: 3, why: (x, y) => `${x.en} ловит цель в контроль, а ${y.en} успевает выдать бурст.` },
  { a: "stun", b: "nuker", w: 3, why: (x, y) => `Стан ${x.en} — это окно, в которое ${y.en} бьёт магией.` },
  { a: "initiator", b: "burst", w: 3, why: (x, y) => `${x.en} начинает драку, ${y.en} добивает за секунду.` },
  { a: "disable", b: "single_target", w: 2, why: (x, y) => `${x.en} не даёт цели уйти, ${y.en} разбирает её один-в-один.` },
  { a: "disable", b: "carry", w: 2, why: (x, y) => `${x.en} держит врагов, а ${y.en} спокойно реализует урон.` },
  { a: "slow", b: "kite", w: 2, why: (x, y) => `${x.en} замедляет, ${y.en} разрывает дистанцию и добивает.` },
  { a: "heal", b: "tank", w: 2, why: (x, y) => `${x.en} отхиливает ${y.en}, который и так живёт под урон.` },
  { a: "save", b: "carry", w: 2, why: (x, y) => `${x.en} спасает ${y.en}, когда того пытаются выключить.` },
  { a: "summon", b: "push", w: 2, why: (x, y) => `Призывы ${x.en} вместе с пушем ${y.en} сносят строения.` },
  { a: "illusions", b: "push", w: 2, why: (x, y) => `Иллюзии ${x.en} разбегаются по линиям, ${y.en} давит карту.` },
  { a: "silence", b: "burst", w: 2, why: (x, y) => `${x.en} сайленсит, ${y.en} бьёт бурстом без ответа.` },
  { a: "trap", b: "single_target", w: 2, why: (x, y) => `${x.en} запирает цель, ${y.en} добивает её.` },
  { a: "global", b: "gank", w: 1, why: (x, y) => `${x.en} приходит на карту в любую точку, ${y.en} добивает.` },
];

function suggestPartners(hero, limit) {
  const results = [];
  for (const other of state.heroes) {
    if (other.key === hero.key) continue;
    let score = 0;
    const notes = [];
    for (const rule of SYNERGY_RULES) {
      const forward = hero.tags.includes(rule.a) && other.tags.includes(rule.b);
      const backward = other.tags.includes(rule.a) && hero.tags.includes(rule.b);
      if (forward) { score += rule.w; notes.push(rule.why(hero, other)); }
      else if (backward) { score += rule.w; notes.push(rule.why(other, hero)); }
    }
    if (!score) continue;
    if (hero.tags.includes("carry") && other.tags.includes("carry") && !other.tags.includes("support") && !other.tags.includes("disable")) score -= 1;
    results.push({ hero: other, score, notes });
  }
  results.sort((a, b) => b.score - a.score || a.hero.en.localeCompare(b.hero.en, "en"));
  return results.slice(0, limit);
}

function renderCombos(hero) {
  const box = $("#comboResult");
  if (!box) return;

  const curated = (state.synergies?.[hero.key] || [])
    .map((pair) => ({ mate: state.byKey.get(pair.hero), why: pair.why }))
    .filter((pair) => pair.mate);
  const curatedKeys = new Set(curated.map((p) => p.mate.key));

  const engine = suggestPartners(hero, 12)
    .filter((p) => !curatedKeys.has(p.hero.key))
    .map((p) => ({ mate: p.hero, notes: p.notes }));

  const cards = [
    ...curated.map((c) => ({ ...c, curated: true })),
    ...engine.map((e) => ({ ...e, curated: false })),
  ].slice(0, 9);

  if (!cards.length) {
    box.innerHTML = '<p class="tool-empty">Не нашёл подходящих связок для этого героя.</p>';
    return;
  }

  box.innerHTML = `
    <div class="tool-note muted small">Базовый герой: <b>${escapeHtml(hero.en)}</b> (${escapeHtml(hero.ru)}). Проверенные связки — из открытых гайдов, остальные подобраны по механике.</div>
    <div class="combo-grid">
      ${cards.map(({ mate, why, notes, curated: isCurated }) => `
        <article class="combo-card">
          <div class="combo-pair">
            <img src="${hero.img}" alt="" loading="lazy" width="56" height="32">
            <span class="combo-plus">+</span>
            <img src="${mate.img}" alt="" loading="lazy" width="56" height="32">
            <div class="combo-names">
              <b>${escapeHtml(hero.en)} + ${escapeHtml(mate.en)}</b>
              <span>${escapeHtml(mate.ru)}</span>
            </div>
          </div>
          ${(isCurated ? [why] : [...new Set(notes)]).slice(0, 2).map((n) => `<p class="combo-why">${escapeHtml(n)}</p>`).join("")}
          <div class="combo-foot">
            <span class="${isCurated ? "combo-tag is-curated" : "combo-tag"}">${isCurated ? "проверенная связка" : "по механике"}</span>
            <a href="#/builds/${mate.key}">Сборка →</a>
          </div>
        </article>`).join("")}
    </div>`;
}

/* ------------------------------ сборки ------------------------------ */

const BUILD_PHASES = [
  ["start_game_items", "Старт"],
  ["early_game_items", "Ранняя игра"],
  ["mid_game_items", "Мид"],
  ["late_game_items", "Лейт"],
];

const DAMAGE_TEXT = {
  phys: "Герой наносит урон атаками, поэтому сборка идёт через скорость атаки, криты, минус брони и предметы, которые не дают цели уйти.",
  magic: "Урон идёт способностями: важны усиление магии, снижение сопротивления цели и кулдауны, чтобы выдавать комбо чаще.",
};

const PHYS_PRIORITY = ["bfury", "desolator", "monkey_king_bar", "daedalus", "manta", "satanic", "abyssal_blade", "butterfly", "diffusal_blade", "silver_edge", "nullifier", "skadi"];
const MAGIC_PRIORITY = ["ultimate_scepter", "kaya_and_sange", "veil_of_discord", "dagon_5", "ethereal_blade", "shivas_guard", "octarine_core", "sheepstick", "aether_lens", "cyclone", "refresher", "wind_waker"];

let itemMapCache = null;
let itemTagsCache = null;
let itemTreeCache = null;
let buildToken = 0;

async function loadItemMeta() {
  if (!itemMapCache) itemMapCache = await fetch("data/item-map.json").then((r) => r.json());
  if (!itemTagsCache) itemTagsCache = await fetch("data/item-tags.json").then((r) => r.json());
  if (!itemTreeCache) itemTreeCache = await fetch("data/item-tree.json").then((r) => r.json()).catch(() => ({}));
  return { map: itemMapCache, tags: itemTagsCache, tree: itemTreeCache };
}

function itemImage(key) {
  return `/steamimg/apps/dota2/images/dota_react/items/${key}.png`;
}

function heroDamageType(hero) {
  const magic = hero.tags.includes("burst") || hero.tags.includes("nuker");
  const phys = hero.tags.includes("carry") || hero.tags.includes("cleave") || hero.tags.includes("passive");
  if (magic && !phys) return "magic";
  if (phys && !magic) return "phys";
  if (magic && phys) return hero.attr === "int" ? "magic" : "phys";
  return "phys";
}

function buildDamageBlock(hero, type, meta, popularity) {
  // Собираем реальную популярность предметов из матчей (мид + лейт), только «готовые» предметы.
  const counts = new Map();
  for (const phase of ["mid_game_items", "late_game_items", "early_game_items"]) {
    for (const [id, count] of Object.entries(popularity?.[phase] || {})) {
      const item = meta.map[id];
      if (!item) continue;
      if ((item.c || 0) < 2000) continue;
      counts.set(item.k, Math.max(counts.get(item.k) || 0, count));
    }
  }

  const MAGIC_HINTS = /spell|magic|mana|silence|hex|ethereal|scepter|kaya|veil|dagon|cyclone|orchid|bloodthorn|atos|refresher|shiva|octarine|lens|wand/i;
  const PHYS_HINTS = /attack|damage|crit|cleave|lifesteal|armor|strength|agility|bash|desolator|manta|butterfly|satanic|skadi|rapier|basher/i;

  const classify = (key, item) => {
    const tag = meta.tags[key]?.t;
    if (tag === "magic" || tag === "phys") return tag;
    const text = `${item.n} ${(item.notes || []).join(" ")} ${(item.attrib || []).join(" ")}`;
    if (MAGIC_HINTS.test(text)) return "magic";
    if (PHYS_HINTS.test(text)) return "phys";
    return "phys";
  };

  let picks = [...counts.entries()]
    .map(([key, count]) => ({ key, count, item: Object.values(meta.map).find((v) => v.k === key) }))
    .filter((row) => row.item && classify(row.key, row.item) === type)
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);

  if (!picks.length) {
    const priority = type === "phys" ? PHYS_PRIORITY : MAGIC_PRIORITY;
    picks = priority.slice(0, 6).map((key) => ({
      key,
      count: 0,
      item: Object.values(meta.map).find((v) => v.k === key),
    }));
  }

  const maxCount = Math.max(1, ...picks.map((p) => p.count));
  const items = picks
    .filter((p) => p.item)
    .map((p) => {
      const metaTag = meta.tags[p.key];
      const note = metaTag?.n || itemShortNote(p.key);
      const share = p.count ? Math.round((p.count / maxCount) * 100) : 0;
      return `<article class="dmg-item">
        <div class="di-icon"><img src="${itemImage(p.key)}" alt="" loading="lazy" width="52" height="39"></div>
        <div class="di-body">
          <div class="di-head"><b>${escapeHtml(p.item.n)}</b><span class="di-cost">${(p.item.c || 0).toLocaleString("ru-RU")}</span></div>
          <p class="di-note">${escapeHtml(note)}</p>
          ${p.count ? `<div class="di-bar"><span style="width:${share}%"></span></div><span class="di-pop">${p.count.toLocaleString("ru-RU")} матчей</span>` : ""}
        </div>
      </article>`;
    }).join("");

  return `<div class="build-block">
    <h3>Сборка на ${type === "phys" ? "физический" : "магический"} урон</h3>
    <p class="muted">${escapeHtml(DAMAGE_TEXT[type])}</p>
    <div class="build-toggle">
      <button type="button" data-dmg="phys" class="${type === "phys" ? "is-active" : ""}">Физическая</button>
      <button type="button" data-dmg="magic" class="${type === "magic" ? "is-active" : ""}">Магическая</button>
    </div>
    <div class="dmg-list">${items}</div>
  </div>`;
}

function itemShortNote(key) {
  const full = state.itemCatalog?.[key];
  const note = full?.notes?.[0] || full?.lore || "";
  return note.length > 100 ? note.slice(0, 98).trim() + "…" : note;
}

function itemStatsTable(popularity, meta) {
  if (!popularity) return "";
  const counts = new Map();
  for (const [phase] of BUILD_PHASES) {
    for (const [id, n] of Object.entries(popularity[phase] || {})) {
      counts.set(id, Math.max(counts.get(id) || 0, n));
    }
  }
  const list = [...counts.entries()]
    .map(([id, n]) => ({ item: meta.map[id], n }))
    .filter((row) => row.item)
    .sort((a, b) => b.n - a.n)
    .slice(0, 16);
  if (!list.length) return "";
  const max = list[0].n || 1;
  const rows = list.map((row) => {
    const width = Math.max(2, (row.n / max) * 100);
    return `<tr>
      <td><span class="istat-hero"><img src="${itemImage(row.item.k)}" alt="" loading="lazy" width="34" height="25">${escapeHtml(row.item.n)}</span></td>
      <td><span class="istat-bar-cell"><span class="istat-bar" style="width:${width.toFixed(1)}%"></span><b>${row.n.toLocaleString("ru-RU")}</b></span></td>
    </tr>`;
  }).join("");

  return `<div class="build-block itemstats">
    <h3>Часто используемые предметы</h3>
    <p class="muted small">Сколько раз предмет покупали в матчах с этим героем (OpenDota, по всем стадиям).</p>
    <table class="itemstats-table">
      <thead><tr><th>Предмет</th><th>Сыграно матчей</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

async function renderBuilds(hero, boxSel = "#buildResult") {
  const box = $(boxSel);
  if (!box) return;
  if (box.dataset.hero === String(hero.id)) return;
  box.dataset.hero = String(hero.id);
  const token = ++buildToken;
  box.innerHTML = '<div class="skeleton" style="height:220px"></div>';

  let meta;
  let popularity;
  try {
    const [m, p] = await Promise.all([
      loadItemMeta(),
      fetch(`https://api.opendota.com/api/heroes/${hero.id}/itemPopularity`).then((r) => (r.ok ? r.json() : null)),
    ]);
    meta = m;
    popularity = p;
  } catch {
    popularity = null;
  }
  if (token !== buildToken) return;

  const phases = popularity
    ? BUILD_PHASES.map(([key, label]) => {
        const entries = Object.entries(popularity[key] || {})
          .map(([id, count]) => ({ item: meta.map[id], count }))
          .filter((e) => e.item)
          .sort((a, b) => b.count - a.count)
          .slice(0, 7);
        return { label, entries };
      })
    : [];

  // Сборка на мид/лейт: компоненты заменяем на предметы, которые из них крафтятся.
  const allUnion = new Map();
  for (const phase of phases) {
    for (const entry of phase.entries) {
      allUnion.set(entry.item.k, Math.max(allUnion.get(entry.item.k) || 0, entry.count));
    }
  }

  const cost = new Map();
  const byKey = new Map();
  for (const item of Object.values(meta.map)) {
    cost.set(item.k, item.c || 0);
    byKey.set(item.k, item);
  }

  const ancestorsOf = (startKey) => {
    const tree = meta.tree || {};
    const seen = new Set([startKey]);
    let frontier = [startKey];
    const out = [];
    for (let depth = 0; depth < 4; depth++) {
      const next = [];
      for (const k of frontier) {
        for (const parent of tree[k] || []) {
          if (seen.has(parent)) continue;
          seen.add(parent);
          next.push(parent);
        }
      }
      if (!next.length) break;
      out.push(...next);
      frontier = next;
    }
    return out;
  };

  const bestUpgrade = (key) => {
    const options = ancestorsOf(key).filter((k) => allUnion.has(k));
    if (!options.length) return null;
    options.sort((a, b) => (cost.get(b) || 0) - (cost.get(a) || 0) || (allUnion.get(b) || 0) - (allUnion.get(a) || 0));
    return options[0];
  };

  const resolveAny = (key) => ((meta.tree?.[key] || []).length ? (bestUpgrade(key) || key) : key);

  const finishedAll = [];
  const seenFin = new Set();
  for (const [key] of allUnion) {
    const fin = resolveAny(key);
    if ((meta.tree?.[fin] || []).length && (cost.get(fin) || 0) < 3000) continue;
    if (seenFin.has(fin)) continue;
    seenFin.add(fin);
    finishedAll.push(fin);
  }
  finishedAll.sort((a, b) => (cost.get(b) || 0) - (cost.get(a) || 0));

  const finalPhases = phases.map((phase, index) => {
    if (index < 2) return phase; // старт и ранняя игра — компоненты уместны
    const used = new Set();
    const entries = [];
    const add = (key, count) => {
      if (used.has(key)) return;
      const c = cost.get(key) || 0;
      // дешёвые компоненты (Blade of Alacrity, Eaglesong и т.п.) в мид/лейте не показываем
      if ((meta.tree?.[key] || []).length && c < 3000) return;
      used.add(key);
      entries.push({ item: byKey.get(key) || { k: key, n: key }, count });
    };
    for (const entry of phase.entries) add(resolveAny(entry.item.k), allUnion.get(resolveAny(entry.item.k)) || entry.count);
    // добираем готовые предметы, чтобы блок не выглядел полупустым
    const fillOrder = index === 2
      ? [...finishedAll].sort((a, b) => (allUnion.get(b) || 0) - (allUnion.get(a) || 0))
      : finishedAll;
    for (const key of fillOrder) {
      if (entries.length >= 6) break;
      add(key, allUnion.get(key) || 0);
    }
    return { ...phase, entries };
  });

  const hasData = phases.some((p) => p.entries.length);

  const type = heroDamageType(hero);

  box.innerHTML = `
    <div class="build-hero">
      <img src="${hero.img}" alt="" width="96" height="54">
      <div>
        <h2>${escapeHtml(hero.en)}</h2>
        <p>${escapeHtml(hero.ru)} · ${escapeHtml(hero.roles.map((r) => ROLE_RU[r] || r).join(", "))}${statLine(hero)}</p>
      </div>
    </div>
    ${hasData ? `<div class="build-phases">${finalPhases.map((p) => `
      <section class="build-phase">
        <h4>${p.label}</h4>
        ${p.entries.length
          ? p.entries.map((e) => `<div class="build-item"><img src="${itemImage(e.item.k)}" alt="" loading="lazy" width="40" height="30"><span class="bi-name">${escapeHtml(e.item.n)}</span><span class="bi-count">${e.count}</span></div>`).join("")
          : '<p class="muted small">Нет данных</p>'}
      </section>`).join("")}</div>`
      : '<p class="tool-empty">OpenDota не вернула популярные предметы для этого героя.</p>'}
    ${buildDamageBlock(hero, type, meta, popularity || {})}
    ${itemStatsTable(popularity, meta)}
    <p class="muted small">Предметы и их частота — OpenDota (публичные матчи). Пояснения — по механике предметов.</p>`;

  box.onclick = (event) => {
    const btn = event.target.closest("[data-dmg]");
    if (!btn) return;
    const block = box.querySelector(".build-block");
    if (block) block.outerHTML = buildDamageBlock(hero, btn.dataset.dmg, meta, popularity || {});
  };
}

function renderHeroPicker(box, prefix) {
  if (!box) return;
  const badge = prefix === "builds" ? "Сборка" : "Связки";
  const list = state.heroes.slice().sort((a, b) => {
    const ra = state.heroStats?.[a.id]?.rank ?? 999;
    const rb = state.heroStats?.[b.id]?.rank ?? 999;
    return ra - rb;
  });
  box.innerHTML = '<div class="hero-grid picker-grid">' + list.map((h) => (
    '<button type="button" class="hero-tile picker-tile" data-hero="' + h.key + '">' +
      '<img src="' + h.img + '" alt="' + escapeHtml(h.en) + '" loading="lazy" width="256" height="144">' +
      '<span>' + escapeHtml(h.en) + '</span>' +
      '<em class="tile-badge">' + badge + '</em>' +
    '</button>'
  )).join('') + '</div>';
  box.querySelectorAll("[data-hero]").forEach((btn) => {
    btn.addEventListener("click", () => { location.hash = "#/" + prefix + "/" + btn.dataset.hero; });
  });
}

/* ------------------------------ каталог предметов ------------------------------ */

const ITEM_UPDATE = "__updated";

const ITEM_GROUPS = [
  { key: "consumable", label: "Расходники" },
  { key: "laning", label: "Расходники" },
  { key: "component", label: "Компоненты" },
  { key: "common", label: "Обычные" },
  { key: "rare", label: "Редкие" },
  { key: "epic", label: "Эпические" },
  { key: "artifact", label: "Артефакты" },
  { key: "secret_shop", label: "Тайная лавка" },
  { key: "neutral1", label: "Нейтральные · Разряд 1" },
  { key: "neutral2", label: "Нейтральные · Разряд 2" },
  { key: "neutral3", label: "Нейтральные · Разряд 3" },
  { key: "neutral4", label: "Нейтральные · Разряд 4" },
  { key: "neutral5", label: "Нейтральные · Разряд 5" },
];

function itemGroupOf(item) {
  const q = String(item.q || "common");
  if (q === "neutral") return "neutral" + (Number(item.t) || 1);
  if (q.includes("consumable")) return "consumable";
  return q;
}

function renderItemsGrid(filter) {
  const grid = $("#itemsGrid");
  if (!grid) return;
  const catalog = state.itemCatalog || {};
  const q = String(filter || "").trim().toLowerCase();
  const list = Object.entries(catalog)
    .filter(([key]) => !key.startsWith("__"))
    .map(([key, item]) => ({ key, ...item }))
    .filter((item) => !q || item.n.toLowerCase().includes(q) || item.key.includes(q.replace(/\s+/g, "_")))
    .sort((a, b) => a.c - b.c || a.n.localeCompare(b.n, "en"));

  if (!list.length) {
    grid.innerHTML = '<p class="tool-empty">Ничего не нашлось.</p>';
    return;
  }

  const groups = new Map();
  for (const item of list) {
    const g = itemGroupOf(item);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(item);
  }

  const order = ITEM_GROUPS.map((g) => g.key);
  const sections = [...groups.entries()]
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([key, items]) => {
      const label = (ITEM_GROUPS.find((g) => g.key === key) || {}).label || key;
      return `<section class="shop-group">
        <h3>${escapeHtml(label)} <span class="shop-count">${items.length}</span></h3>
        <div class="shop-grid">
          ${items.map((item) => `
            <button type="button" class="shop-item q-${itemGroupOf(item)}" data-item="${item.key}"
              title="${escapeHtml(item.n)} — ${item.c} золота&#10;${escapeHtml((item.notes && item.notes[0]) || item.lore || "")}">
              <img src="/steamimg/apps/dota2/images/dota_react/items/${item.key}.png" alt="${escapeHtml(item.n)}" loading="lazy" width="44" height="33">
            </button>`).join("")}
        </div>
      </section>`;
    }).join("");

  grid.innerHTML = `<div class="shop-layout">${sections}</div>
    <div class="shop-detail" id="shopDetail" hidden></div>`;

  grid.querySelectorAll("[data-item]").forEach((btn) => {
    btn.addEventListener("click", () => showItemDetail(btn.dataset.item));
  });

  const note = $("#itemsNote");
  if (note) {
    const updated = catalog[ITEM_UPDATE] || "";
    note.textContent = `Предметов: ${list.length} · стоимость и описание — Valve (dotaconstants)${updated ? ` · база обновлена ${updated}` : ""}`;
  }
}

function showItemDetail(key) {
  const item = state.itemCatalog?.[key];
  const box = $("#shopDetail");
  if (!item || !box) return;

  const stats = (item.attrib || []).map((line) => `<span class="item-stat">${escapeHtml(line)}</span>`).join("");
  const notes = (item.notes || []).map((line) => `<p class="item-note">${escapeHtml(line)}</p>`).join("");
  const lore = item.lore ? `<p class="item-lore">${escapeHtml(item.lore)}</p>` : "";
  const comps = item.comp?.length
    ? `<p class="item-comp">Собирается из: ${item.comp.map((c) => escapeHtml(c.n)).join(", ")}</p>`
    : "";

  box.hidden = false;
  box.innerHTML = `
    <div class="shop-detail-head">
      <img src="/steamimg/apps/dota2/images/dota_react/items/${key}.png" alt="" width="72" height="54">
      <div>
        <b>${escapeHtml(item.n)}</b>
        <span class="item-cost">${item.c > 0 ? item.c.toLocaleString("ru-RU") + " золота" : "нейтральный предмет"}</span>
      </div>
      <button type="button" class="shop-detail-close" aria-label="Закрыть">×</button>
    </div>
    ${stats ? `<div class="item-stats">${stats}</div>` : ""}
    ${notes}
    ${lore}
    ${comps}`;
  box.querySelector(".shop-detail-close").addEventListener("click", () => { box.hidden = true; });
}

function showItems(focusKey) {
  $("#landing").hidden = true;
  $("#heroes").hidden = true;
  setHowHidden(true);
  $("#heroView").hidden = true;
  hideToolViews();
  $("#itemsView").hidden = false;
  document.title = "Предметы | DotaPicker";
  renderItemsGrid($("#itemsSearch")?.value || "");
  if (focusKey && state.itemCatalog?.[focusKey]) {
    showItemDetail(focusKey);
  }
}

/* ------------------------------ киберспорт и медиа ------------------------------ */

const ESPORTS_TEAMS = [
  { n: "Team Spirit", s: "TS", r: "Россия / СНГ", d: "Двукратные чемпионы The International (2021, 2023)." },
  { n: "BetBoom Team", s: "BB", r: "Россия", d: "Одна из сильнейших команд СНГ, стабильно в топе мейджоров." },
  { n: "PARIVISION", s: "PV", r: "Россия", d: "Молодая команда с сильным составом, играет на равных с топами." },
  { n: "Team Falcons", s: "TF", r: "Ближний Восток", d: "Саудовский проект, собравший звёздный состав." },
  { n: "Tundra Esports", s: "TUN", r: "Европа", d: "Чемпионы The International 2022." },
  { n: "Gaimin Gladiators", s: "GG", r: "Европа", d: "Три мейджора подряд в 2023 году." },
  { n: "Team Liquid", s: "TL", r: "Европа", d: "Легендарная организация с чемпионским составом 2017." },
  { n: "OG", s: "OG", r: "Европа", d: "Единственные двукратные чемпионы TI подряд (2018, 2019)." },
  { n: "Xtreme Gaming", s: "XG", r: "Китай", d: "Флагман китайской сцены последних сезонов." },
  { n: "Nigma Galaxy", s: "NG", r: "Ближний Восток / Европа", d: "Команда Куро и Miracle, известная по The International 2017." },
  { n: "Aurora", s: "AUR", r: "СНГ", d: "Молодой состав из СНГ, пробившийся в топ-уровень." },
  { n: "Heroic", s: "HER", r: "Южная Америка", d: "Сильная южноамериканская организация с европейским опытом." },
];

const ESPORTS_MEDIA = [
  { n: "Cybersport.ru", u: "https://www.cybersport.ru/tags/dota-2", d: "Новости, интервью и разборы СНГ-сцены." },
  { n: "Dota2.ru", u: "https://dota2.ru/", d: "Русскоязычный портал с новостями и гайдами." },
  { n: "Reddit r/DotA2", u: "https://www.reddit.com/r/DotA2/", d: "Крупнейшее англоязычное сообщество." },
  { n: "Dot Esports", u: "https://dotesports.com/dota-2", d: "Международные новости киберспорта." },
  { n: "Escoressnews", u: "https://escorenews.com/en/dota-2", d: "Турниры, результаты и расписания матчей." },
  { n: "Steam · Dota 2", u: "https://store.steampowered.com/news/app/570", d: "Официальные новости и патчи от Valve." },
];

let esportsLoaded = false;

function renderEsportsStatic() {
  const teams = $("#esportsTeams");
  if (teams) {
    teams.innerHTML = ESPORTS_TEAMS.map((t) => `
      <article class="team-card">
        <div class="team-badge">${escapeHtml(t.s)}</div>
        <div class="team-body">
          <b>${escapeHtml(t.n)}</b>
          <span class="team-region">${escapeHtml(t.r)}</span>
          <p>${escapeHtml(t.d)}</p>
        </div>
      </article>`).join("");
  }

  const media = $("#esportsMedia");
  if (media) {
    media.innerHTML = ESPORTS_MEDIA.map((m) => `
      <a class="media-card" href="${m.u}" target="_blank" rel="noopener">
        <b>${escapeHtml(m.n)}</b>
        <p>${escapeHtml(m.d)}</p>
      </a>`).join("");
  }
}

function formatNewsDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

/* ------------------------------ киберспорт: стримы и новости ------------------------------ */

const STREAM_CHANNELS = [
  { ch: "dota2ruhub", name: "RuHub", note: "Русскоязычные трансляции турниров" },
  { ch: "dota2", name: "Dota 2 (официальный)", note: "Официальный канал Valve" },
];

let newsTimer = null;
let newsUpdatedAt = 0;

function newsKind(link) {
  const url = String(link || "").toLowerCase();
  if (url.includes("youtube.com") || url.includes("youtu.be")) return { cls: "is-video", label: "видео" };
  if (url.includes("clips.twitch.tv") || url.includes("streamable.com") || url.includes("medal.tv")) return { cls: "is-clip", label: "клип" };
  if (url.includes("twitch.tv")) return { cls: "is-stream", label: "стрим" };
  return null;
}

function youtubeId(link) {
  const m = String(link || "").match(/(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/);
  return m ? m[1] : null;
}

function renderStreams() {
  const box = $("#esportsStreams");
  if (!box) return;
  box.innerHTML = STREAM_CHANNELS.map((s) => `
    <div class="stream-card">
      <div class="stream-frame">
        <iframe
          src="https://player.twitch.tv/?channel=${encodeURIComponent(s.ch)}&parent=vast-owl.vps.ktk-45.ru&muted=true"
          allowfullscreen
          loading="lazy"
          title="${escapeHtml(s.name)}"></iframe>
      </div>
      <div class="stream-meta">
        <b>${escapeHtml(s.name)}</b>
        <span>${escapeHtml(s.note)}</span>
        <a href="https://www.twitch.tv/${encodeURIComponent(s.ch)}" target="_blank" rel="noopener">Открыть на Twitch →</a>
      </div>
    </div>`).join("");
}

async function renderEsportsNews(force) {
  const box = $("#esportsNews");
  const note = $("#esportsNewsNote");
  if (!box) return;
  if (!box.children.length || force) {
    box.innerHTML = '<div class="skeleton" style="height:140px"></div>';
  }
  try {
    const res = await fetch(`/api/news${force ? "?t=" + Date.now() : ""}`, { cache: "no-store" });
    const data = await res.json();
    const items = (data.items || []).slice(0, 24);
    box.innerHTML = items.length
      ? items.map((item) => {
          const kind = newsKind(item.link);
          const yt = youtubeId(item.link);
          const thumb = yt ? `<img class="news-thumb" src="https://img.youtube.com/vi/${yt}/mqdefault.jpg" alt="" loading="lazy" width="120" height="68">` : "";
          return `<a class="news-item${kind ? " has-kind" : ""}" href="${item.link}" target="_blank" rel="noopener">
            ${thumb}
            <span class="news-main">
              <span class="news-source">${escapeHtml(item.source)}${kind ? ` · <em class="news-kind ${kind.cls}">${kind.label}</em>` : ""}</span>
              <b>${escapeHtml(item.title)}</b>
            </span>
            <span class="news-date">${formatNewsDate(item.date)}</span>
          </a>`;
        }).join("")
      : '<p class="tool-empty">Новости сейчас недоступны.</p>';
    newsUpdatedAt = Date.now();
    if (note) note.textContent = "обновлено только что";
  } catch {
    box.innerHTML = '<p class="tool-empty">Не удалось загрузить новости.</p>';
  }
}

function startNewsTimer() {
  if (newsTimer) clearInterval(newsTimer);
  newsTimer = setInterval(() => {
    const view = document.getElementById("esportsView");
    if (!view || view.hidden) return;
    renderEsportsNews(true);
    const note = document.getElementById("esportsNewsNote");
    if (note) note.textContent = "обновлено только что";
  }, 5 * 60 * 1000);
}

function showEsports() {
  $("#landing").hidden = true;
  $("#heroes").hidden = true;
  setHowHidden(true);
  $("#heroView").hidden = true;
  hideToolViews();
  $("#esportsView").hidden = false;
  document.title = "Киберспорт | DotaPicker";
  renderEsportsStatic();
  renderStreams();
  renderEsportsNews(true);
  startNewsTimer();
  const btn = $("#newsRefresh");
  if (btn) btn.onclick = () => renderEsportsNews(true);
}

function setHowHidden(hidden) {
  const el = $("#how");
  if (el) el.hidden = hidden;
}

function hideToolViews() {
  for (const id of ["combosView", "buildsView", "cabinetView", "itemsView", "esportsView"]) {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  }
}

function showCombos(heroKey) {
  $("#landing").hidden = true;
  $("#heroes").hidden = true;
  setHowHidden(true);
  $("#heroView").hidden = true;
  hideToolViews();
  $("#buildsView").hidden = true;
  $("#combosView").hidden = false;

  if (!heroKey) {
    $("#comboResult").innerHTML = '<p class="tool-note muted small">Выбери героя — покажу, кем его дополнить.</p><div id="comboPicker"></div>';
    renderHeroPicker($("#comboPicker"), "combos");
    document.title = "Связки героев | DotaPicker";
    return;
  }
  const hero = state.byKey.get(heroKey);
  if (!hero) { $("#comboResult").innerHTML = '<p class="tool-empty">Герой не найден.</p>'; return; }
  renderCombos(hero);
  document.title = `Связки: ${hero.en} | DotaPicker`;
}

function showBuilds(heroKey) {
  $("#landing").hidden = true;
  $("#heroes").hidden = true;
  setHowHidden(true);
  $("#heroView").hidden = true;
  hideToolViews();
  $("#combosView").hidden = true;
  $("#buildsView").hidden = false;

  if (!heroKey) {
    $("#buildResult").innerHTML = '<p class="tool-note muted small">Выбери героя — покажу популярные предметы по стадиям и сборку на физ/маг урон.</p><div id="buildPicker"></div>';
    renderHeroPicker($("#buildPicker"), "builds");
    document.title = "Сборки героев | DotaPicker";
    return;
  }
  const hero = state.byKey.get(heroKey);
  if (!hero) { $("#buildResult").innerHTML = '<p class="tool-empty">Герой не найден.</p>'; return; }
  document.title = `Сборка: ${hero.en} | DotaPicker`;
  renderBuilds(hero);
}
function route() {
  if (!state.loaded) return;
  const esportsRoute = location.hash.match(/^#\/esports/i);
  if (esportsRoute) { showEsports(); return; }
  const itemsRoute = location.hash.match(/^#\/items(?:\/([a-z0-9_]+))?/i);
  if (itemsRoute) { showItems(itemsRoute[1] || null); return; }
  const cab = location.hash.match(/^#\/cabinet/i);
  if (cab) { showCabinet(); return; }
  const combos = location.hash.match(/^#\/combos(?:\/([a-z0-9_]+))?/i);
  if (combos) { showCombos(combos[1] ? combos[1].toLowerCase() : null); return; }
  const builds = location.hash.match(/^#\/builds(?:\/([a-z0-9_]+))?/i);
  if (builds) { showBuilds(builds[1] ? builds[1].toLowerCase() : null); return; }
  const player = location.hash.match(/^#\/player\/(\d+)/i);
  if (player) {
    showLanding();
    showProfile(player[1]);
    return;
  }
  const m = location.hash.match(/^#\/hero\/([a-z0-9_]+)(?:\/(overview|abilities|counters|builds|matchups))?/i);
  if (m && state.byKey.has(m[1].toLowerCase())) {
    showHero(m[1].toLowerCase(), m[2] ? m[2].toLowerCase() : null);
    return;
  }
  showLanding();
  const anchor = location.hash.slice(1);
  if (anchor && document.getElementById(anchor)) {
    requestAnimationFrame(() => document.getElementById(anchor).scrollIntoView({ behavior: "smooth" }));
  }
}

/* ------------------------------ профиль по Steam ------------------------------ */

const STEAM_ID_BASE = 76561197960265728n;

const RANK_NAMES = ["", "Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine", "Immortal"];
const GAME_MODES = {
  1: "All Pick", 2: "Captains Mode", 3: "Random Draft", 4: "Single Draft", 5: "All Random",
  12: "Least Played", 16: "Captains Draft", 18: "Ability Draft", 21: "1v1 Mid", 22: "Ranked All Pick",
  23: "Turbo",
};
const LOBBY_TYPES = { 0: "Normal", 1: "Ranked", 2: "Tournament", 4: "Battle Cup", 7: "Ranked" };

function steamAccountId(steamId64) {
  try { return (BigInt(steamId64) - STEAM_ID_BASE).toString(); } catch { return null; }
}

function rankLabel(tier) {
  if (!tier) return "—";
  const medal = Math.floor(tier / 10);
  const star = tier % 10;
  const name = RANK_NAMES[medal];
  if (!name) return "—";
  return medal >= 8 ? name : `${name} ${star}`;
}

function timeAgo(unix) {
  if (!unix) return "—";
  const diff = Math.max(0, Math.floor(Date.now() / 1000) - unix);
  const mins = Math.floor(diff / 60);
  if (mins < 1) return "только что";
  if (mins < 60) return `${mins} мин назад`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ч назад`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} дн назад`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} мес назад`;
  return `${Math.floor(months / 12)} г назад`;
}

function fmtDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function heroById(id) {
  const key = keyById(id);
  return key ? state.byKey.get(key) : null;
}

// Короткое имя /id/ник резолвим через Steam (запрос идёт через наш nginx-прокси,
// поэтому CORS не мешает).
async function resolveVanity(vanity) {
  try {
    const res = await fetch(`/steamid/id/${encodeURIComponent(vanity)}/?xml=1`, { cache: "no-store" });
    if (!res.ok) return null;
    const xml = new DOMParser().parseFromString(await res.text(), "application/xml");
    if (xml.querySelector("error")) return null;
    const id = xml.querySelector("steamID64")?.textContent?.trim();
    return id && /^\d{17}$/.test(id) ? steamAccountId(id) : null;
  } catch {
    return null;
  }
}

async function resolveAccountId(raw) {
  const value = String(raw || "").trim();
  if (!value) return null;

  const db = value.match(/dotabuff\.com\/players\/(\d+)/i);
  if (db) return db[1];

  const numeric = value.match(/\b(\d{17})\b/);
  if (numeric) return steamAccountId(numeric[1]);

  if (/^\d{1,10}$/.test(value)) return value;

  const vanity = value.match(/steamcommunity\.com\/id\/([^/?#\s]+)/i);
  if (vanity) return resolveVanity(vanity[1]);

  return null;
}

function openProfileModal() {
  const modal = $("#profileModal");
  if (!modal) return;
  modal.hidden = false;
  document.body.style.overflow = "hidden";
}

function closeProfileModal() {
  const modal = $("#profileModal");
  if (!modal) return;
  modal.hidden = true;
  document.body.style.overflow = "";
}

function profileRowHero(hero, right) {
  const img = hero ? `<img src="${hero.img || hero.icon}" alt="" loading="lazy" width="38" height="22">` : "";
  const name = hero ? escapeHtml(hero.en) : "Неизвестный герой";
  return `<div class="profile-row">${img}<span class="pr-name">${name}</span>${right}</div>`;
}

function renderProfile({ accountId, strat, od, totals, heroes }) {
  const odUser = od?.profile || {};
  const avatar = $("#profileAvatar");
  const avatarUrl = strat?.avatar || odUser.avatarfull;
  if (avatarUrl) { avatar.src = avatarUrl; avatar.hidden = false; } else { avatar.hidden = true; }

  $("#profileTitle").textContent = strat?.name || odUser.personaname || `Аккаунт ${accountId}`;
  const metaParts = [];
  if (odUser.loccountrycode) metaParts.push(odUser.loccountrycode);
  if (od?.leaderboard_rank) metaParts.push(`leaderboard #${od.leaderboard_rank}`);
  metaParts.push(`ID ${accountId}`);
  $("#profileMeta").textContent = metaParts.join(" · ");

  const wins = strat?.winCount ?? 0;
  const total = strat?.matchCount ?? 0;
  const loses = Math.max(0, total - wins);
  const wr = total ? (wins / total) * 100 : null;

  const gpm = strat?.gpm ?? null;
  const xpm = strat?.xpm ?? null;
  const sampleGames = strat?.sample || 0;
  const last = strat?.matches?.[0];

  $("#profileStats").innerHTML = `
    <div class="profile-stat"><b>${total ? `${wins}–${loses}` : "—"}</b><span>Победы–поражения</span></div>
    <div class="profile-stat"><b>${wr != null ? wr.toFixed(2) + "%" : "—"}</b><span>Винрейт</span></div>
    <div class="profile-stat"><b>${rankLabel(od?.rank_tier)}</b><span>Ранг</span></div>
    <div class="profile-stat" title="${sampleGames ? `по ${sampleGames} матчам истории` : ""}"><b>${gpm != null ? gpm : "—"}</b><span>Золото в минуту</span></div>
    <div class="profile-stat" title="${sampleGames ? `по ${sampleGames} матчам истории` : ""}"><b>${xpm != null ? xpm : "—"}</b><span>Опыт в минуту</span></div>
    <div class="profile-stat"><b>${last ? timeAgo(last.start) : "—"}</b><span>Последний матч</span></div>`;

  const heroBox = $("#profileHeroes");
  const precise = (strat?.heroes || []).slice(0, 8).map((row) => ({
    hero: heroById(row.heroId),
    games: row.games,
    win: row.wins,
  }));
  const fallback = [...(heroes || [])].sort((a, b) => b.games - a.games).slice(0, 8).map((row) => ({
    hero: heroById(row.hero_id),
    games: row.games,
    win: row.win,
  }));
  const topHeroes = precise.length ? precise : fallback;
  heroBox.innerHTML = topHeroes.length
    ? topHeroes.map((row) => {
        const share = row.games ? ((row.win / row.games) * 100).toFixed(2) : "—";
        return profileRowHero(row.hero, `<span class="pr-num">${row.games} игр · ${share}%</span>`);
      }).join("")
    : '<p class="profile-empty">Нет данных по героям.</p>';

  const matchBox = $("#profileMatches");
  const lastMatches = (strat?.matches || []).slice(0, 8);
  matchBox.innerHTML = lastMatches.length
    ? lastMatches.map((m) => {
        const hero = heroById(m.heroId);
        const mode = String(m.mode || "").replace(/_/g, " ").toLowerCase();
        const lobby = String(m.lobby || "").toLowerCase();
        const right = `<span class="pr-num">${m.win ? '<b class="pr-win">W</b>' : '<b class="pr-loss">L</b>'} · ${lobby} · ${mode} · ${fmtDuration(m.duration)} · ${m.kills}/${m.deaths}/${m.assists}</span>`;
        return profileRowHero(hero, right);
      }).join("")
    : '<p class="profile-empty">Матчи не найдены — вероятно, профиль закрыт.</p>';

  const dotabuff = $("#profileDotabuff");
  dotabuff.href = `https://www.dotabuff.com/players/${accountId}`;
}

async function showProfile(accountId) {
  openProfileModal();
  $("#profileTitle").textContent = "Загружаю профиль…";
  $("#profileMeta").textContent = `ID ${accountId}`;
  $("#profileAvatar").hidden = true;
  $("#profileStats").innerHTML = "";
  $("#profileHeroes").innerHTML = '<div class="skeleton" style="height:180px"></div>';
  $("#profileMatches").innerHTML = '<div class="skeleton" style="height:180px"></div>';
  $("#profileDotabuff").href = `https://www.dotabuff.com/players/${accountId}`;

  const odBase = `https://api.opendota.com/api/players/${accountId}`;
  const [strat, od, totalsRaw, heroes] = await Promise.all([
    fetch(`/api/player?id=${accountId}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch(odBase).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch(`${odBase}/totals`).then((r) => (r.ok ? r.json() : [])).catch(() => []),
    fetch(`${odBase}/heroes`).then((r) => (r.ok ? r.json() : [])).catch(() => []),
  ]);

  const byField = {};
  for (const row of totalsRaw || []) byField[row.field] = row;
  const totals = {
    games: byField.kills?.n || 0,
    duration: byField.gold_per_min?.sum || 0,
    gold_per_min_sum: byField.gold_per_min?.sum || 0,
    xp_per_min_sum: byField.xp_per_min?.sum || 0,
  };

  renderProfile({ accountId, strat, od, totals, heroes });
}

function setupSteamSearch() {
  const form = $("#steamForm");
  if (!form) return;
  const input = $("#steamInput");
  const hint = $("#steamHint");
  let timer = null;

  const showHint = (text, sticky) => {
    if (!hint) return;
    clearTimeout(timer);
    if (!text) { hint.hidden = true; hint.textContent = ""; return; }
    hint.textContent = text;
    hint.hidden = false;
    if (!sticky) timer = setTimeout(() => { hint.hidden = true; }, 6000);
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = input.value.trim();
    if (!raw) { showHint("Вставь ссылку на профиль Steam или SteamID64."); return; }
    showHint("Ищу профиль…", true);
    const accountId = await resolveAccountId(raw);
    if (!accountId) {
      showHint("Не понял ссылку. Нужна steamcommunity.com/profiles/765… , /id/ник или SteamID64.");
      return;
    }
    showHint("");
    showProfile(accountId);
  });

  document.querySelectorAll("[data-profile-close]").forEach((el) => {
    el.addEventListener("click", closeProfileModal);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#profileModal")?.hidden) closeProfileModal();
  });
}

/* ------------------------------ аккаунт и кабинет ------------------------------ */

let authMode = "login";

async function api(path, data) {
  const res = await fetch(`/api/${path}`, {
    method: data ? "POST" : "GET",
    headers: data ? { "Content-Type": "application/json" } : undefined,
    body: data ? JSON.stringify(data) : undefined,
    credentials: "same-origin",
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || "Ошибка сервера");
  return json;
}

function updateAccountLink() {
  const link = $("#accountLink");
  if (!link) return;
  link.textContent = state.user ? state.user.username : "Войти";
}

async function initAccount() {
  try {
    const res = await api("me");
    state.user = res.user || null;
  } catch {
    state.user = null;
  }
  updateAccountLink();
}

function openAuth(mode) {
  authMode = mode || "login";
  const modal = $("#authModal");
  if (!modal) return;
  $("#authTitle").textContent = authMode === "login" ? "Вход" : "Регистрация";
  $("#authSubmit").textContent = authMode === "login" ? "Войти" : "Создать аккаунт";
  $("#authToggle").textContent = authMode === "login" ? "Нет аккаунта? Регистрация" : "Уже есть аккаунт? Вход";
  $("#authError").hidden = true;
  modal.hidden = false;
  $("#authUser").focus();
}

function closeAuth() {
  const modal = $("#authModal");
  if (modal) modal.hidden = true;
}

function setupAccount() {
  const link = $("#accountLink");
  if (link) {
    link.addEventListener("click", (e) => {
      if (!state.user) { e.preventDefault(); openAuth("login"); }
    });
  }

  document.querySelectorAll("[data-auth-close]").forEach((el) => el.addEventListener("click", closeAuth));
  const toggle = $("#authToggle");
  if (toggle) toggle.addEventListener("click", () => openAuth(authMode === "login" ? "register" : "login"));

  const form = $("#authForm");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const username = $("#authUser").value.trim();
      const password = $("#authPass").value;
      try {
        const res = await api(authMode, { username, password });
        state.user = res.user;
        updateAccountLink();
        closeAuth();
        $("#authPass").value = "";
        if (/^#\/cabinet/.test(location.hash)) renderCabinet();
      } catch (err) {
        const box = $("#authError");
        box.textContent = err.message;
        box.hidden = false;
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#authModal")?.hidden) closeAuth();
  });
}

async function favoritesBlock() {
  let favs = [];
  try {
    favs = (await api("favorites")).favorites || [];
  } catch {
    favs = [];
  }

  const cards = favs.map((f) => {
    const hero = state.byKey.get(f.hero);
    if (!hero) return "";
    const stats = state.heroStats?.[hero.id];
    const now = stats ? stats.win : null;
    const delta = now != null && f.win_at_add != null ? now - f.win_at_add : null;
    return `<div class="fav-card">
      <img src="${hero.img || hero.icon}" alt="" loading="lazy" width="40" height="22">
      <div class="fav-card-main">
        <b>${escapeHtml(hero.en)}</b>
        <span>${now != null ? now.toFixed(2) + "%" : "—"}${delta != null ? ` <em class="${delta >= 0 ? "up" : "down"}">${delta > 0 ? "+" : ""}${delta.toFixed(2)}%</em>` : ""}</span>
      </div>
      <button type="button" class="fav-remove" data-unfav="${hero.key}" aria-label="Убрать">×</button>
    </div>`;
  }).join("");

  return `<section class="cabinet-card">
    <h3>Любимые герои</h3>
    ${cards ? `<div class="fav-grid">${cards}</div>` : '<p class="muted small">Пока ничего не добавлено.</p>'}
    <div class="cabinet-actions">
      <select id="favSelect">${state.heroes
        .slice()
        .sort((a, b) => a.en.localeCompare(b.en, "en"))
        .filter((h) => !favs.some((f) => f.hero === h.key))
        .map((h) => `<option value="${h.key}">${escapeHtml(h.en)} — ${escapeHtml(h.ru)}</option>`)
        .join("")}</select>
      <button class="btn-primary" id="favAdd" type="button">Добавить</button>
    </div>
    <p class="muted small" style="margin-top:10px">Винрейт и дельта считаются по текущей статистике Stratz/OpenDota.</p>
  </section>`;
}

async function adminBlock() {
  if (state.user.role !== "admin") return "";

  let rows = [];
  try {
    const res = await api("admin/users");
    rows = res.users || [];
  } catch {
    return '<section class="cabinet-card"><h3>Админка</h3><p class="muted small">Не удалось загрузить пользователей.</p></section>';
  }

  const dateOf = (ts) => new Date(ts * 1000).toLocaleDateString("ru-RU");
  const heroOf = (key) => (key ? state.byKey.get(key) : null);

  const body = rows.map((u) => {
    const hero = heroOf(u.favorite);
    const isSelf = u.id === state.user.id;
    const roleBadge = u.role === "admin"
      ? '<span class="role-badge is-admin">админ</span>'
      : '<span class="role-badge">пользователь</span>';
    const actions = isSelf
      ? '<span class="muted small">это вы</span>'
      : `<button class="btn-ghost btn-xs" data-role="${u.id}" data-role-val="${u.role === "admin" ? "user" : "admin"}">${u.role === "admin" ? "Снять админа" : "Выдать админа"}</button>
         <button class="btn-ghost btn-xs" data-ban="${u.id}" data-banned="${u.banned ? 1 : 0}">${u.banned ? "Разбанить" : "Забанить"}</button>`;
    return `<tr class="${u.banned ? "is-banned" : ""}">
      <td class="admin-id">${u.id}</td>
      <td><span class="admin-user">${escapeHtml(u.username)}</span></td>
      <td>${roleBadge}</td>
      <td>${hero ? `<span class="admin-hero"><img src="${hero.img || hero.icon}" alt="" loading="lazy" width="30" height="18">${escapeHtml(hero.en)}</span>` : '<span class="muted">—</span>'}</td>
      <td class="muted small">${dateOf(u.created_at)}</td>
      <td>${u.banned ? '<span class="badge-ban">забанен</span>' : '<span class="badge-ok">активен</span>'}</td>
      <td class="admin-actions">${actions}</td>
    </tr>`;
  }).join("");

  return `<section class="cabinet-card admin-card">
    <div class="admin-head">
      <h3>Админка · учетные записи</h3>
      <span class="admin-count">${rows.length} аккаунтов</span>
    </div>
    <table class="admin-table">
      <thead><tr><th>ID</th><th>Логин</th><th>Роль</th><th>Любимый герой</th><th>Регистрация</th><th>Статус</th><th>Действия</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  </section>`;
}

async function renderCabinet() {
  const box = $("#cabinetBody");
  if (!box) return;

  if (!state.user) {
    box.innerHTML = `<section class="cabinet-card"><h3>Вы не вошли</h3>
      <p class="muted small">Войдите или создайте аккаунт, чтобы сохранить любимого героя и следить за его винрейтом.</p>
      <div class="cabinet-actions"><button class="btn-primary" id="cabLogin" type="button">Войти</button>
      <button class="btn-ghost" id="cabRegister" type="button">Регистрация</button></div></section>`;
    $("#cabLogin").addEventListener("click", () => openAuth("login"));
    $("#cabRegister").addEventListener("click", () => openAuth("register"));
    return;
  }

  box.innerHTML = `<div class="cabinet-grid">${await favoritesBlock()}${await adminBlock()}</div>
    <div class="cabinet-actions"><button class="btn-ghost" id="cabLogout" type="button">Выйти</button></div>`;

  $("#favAdd").addEventListener("click", async () => {
    try {
      await api("favorites", { hero: $("#favSelect").value });
      renderCabinet();
    } catch (err) {
      console.error(err);
    }
  });

  box.querySelectorAll("[data-unfav]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api("favorites/remove", { hero: btn.dataset.unfav }).catch(() => {});
      renderCabinet();
    });
  });

  $("#cabLogout").addEventListener("click", async () => {
    await api("logout", {}).catch(() => {});
    state.user = null;
    updateAccountLink();
    renderCabinet();
  });

  box.querySelectorAll("[data-role]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api("admin/role", { id: Number(btn.dataset.role), role: btn.dataset.roleVal }).catch(() => {});
      renderCabinet();
    });
  });

  box.querySelectorAll("[data-ban]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api("admin/ban", { id: Number(btn.dataset.ban), banned: btn.dataset.banned === "0" }).catch(() => {});
      renderCabinet();
    });
  });
}

function showCabinet() {
  $("#landing").hidden = true;
  $("#heroes").hidden = true;
  setHowHidden(true);
  $("#heroView").hidden = true;
  hideToolViews();
  $("#cabinetView").hidden = false;
  document.title = "Личный кабинет | DotaPicker";
  renderCabinet();
}
/* ------------------------------ настройки и музыка ------------------------------ */

const MUSIC_ON_KEY = "cp:musicOn";
const VOLUME_KEY = "cp:volume";
const TRACK_SRC = "media/bee.mp3";

const music = {
  el: null,
  on: false,
  volume: 0.5,
  started: false,
};

function ensureTrack() {
  if (music.el) return music.el;
  const el = new Audio(TRACK_SRC);
  el.loop = true;
  el.preload = "auto";
  el.volume = music.volume;
  el.addEventListener("error", () => {
    console.warn("Не удалось загрузить трек", TRACK_SRC);
  });
  music.el = el;
  return el;
}

function updateMusicUI() {
  const btn = $("#musicToggle");
  if (btn) {
    btn.classList.toggle("is-on", music.on);
    btn.setAttribute("aria-pressed", String(music.on));
  }
}

async function playMusic() {
  const el = ensureTrack();
  try {
    await el.play();
    music.started = true;
  } catch {
    // автозапуск запрещён — попробуем после первого действия пользователя
    const once = () => {
      document.removeEventListener("pointerdown", once);
      el.play().catch(() => {});
    };
    document.addEventListener("pointerdown", once, { once: true });
  }
}

function setMusic(on) {
  music.on = on;
  try { localStorage.setItem(MUSIC_ON_KEY, on ? "1" : "0"); } catch { /* ignore */ }
  updateMusicUI();
  const el = ensureTrack();
  if (on) {
    playMusic();
  } else {
    el.pause();
  }
}

/* ------------------------------ мемы героев ------------------------------ */

function initSettings() {
  let storedVolume = 0.5;
  let storedOn = false;
  try {
    const v = Number(localStorage.getItem(VOLUME_KEY));
    if (!Number.isNaN(v) && v >= 0) storedVolume = v;
    storedOn = localStorage.getItem(MUSIC_ON_KEY) === "1";
  } catch { /* ignore */ }
  music.volume = storedVolume;
  music.on = storedOn;

  const btn = $("#settingsBtn");
  const modal = $("#settingsModal");
  const toggle = $("#musicToggle");
  const range = $("#musicVolume");
  if (!btn || !modal) return;

  if (range) range.value = String(Math.round(storedVolume * 100));
  updateMusicUI();

  const open = () => { modal.hidden = false; };
  const close = () => { modal.hidden = true; };
  btn.addEventListener("click", open);
  document.querySelectorAll("[data-settings-close]").forEach((el) => el.addEventListener("click", close));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  if (location.hash === "#settings") open();

  if (toggle) toggle.addEventListener("click", () => setMusic(!music.on));

  if (range) {
    range.addEventListener("input", () => {
      music.volume = Number(range.value) / 100;
      try { localStorage.setItem(VOLUME_KEY, String(music.volume)); } catch { /* ignore */ }
      if (music.el) music.el.volume = music.volume;
    });
  }

  // если музыка была включена, стартуем после первого действия пользователя
  if (storedOn) {
    const once = () => {
      document.removeEventListener("pointerdown", once);
      playMusic();
    };
    document.addEventListener("pointerdown", once, { once: true });
  }
}

async function init() {
  const grid = $("#heroGrid");
  grid.innerHTML = Array.from({ length: 18 }, () => '<div class="skeleton" style="height:86px"></div>').join("");


  setupSearch($("#bigSearchInput"), $("#bigSuggestions"));
  setupSteamSearch();
  document.querySelectorAll("#heroTabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      if (state.currentHero) history.replaceState(null, "", `#/hero/${state.currentHero.key}/${tab}`);
      setHeroTab(tab);
    });
  });
  setupAccount();
  const itemsSearch = $("#itemsSearch");
  if (itemsSearch) itemsSearch.addEventListener("input", (e) => renderItemsGrid(e.target.value));
  initSettings();
  initAccount();
  setupSearch($("#comboSearchInput"), $("#comboSuggestions"), (hero) => { location.hash = `#/combos/${hero.key}`; });
  setupSearch($("#buildSearchInput"), $("#buildSuggestions"), (hero) => { location.hash = `#/builds/${hero.key}`; });

  $("#gridFilter").addEventListener("input", (e) => renderHeroGrid(e.target.value));

  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
      e.preventDefault();
      $("#bigSearchInput").focus();
    }
  });

  try {
    await loadData();
    renderQuickPicks();
    renderHeroGrid();
    window.addEventListener("hashchange", route);
    route();
  } catch (err) {
    console.error(err);
    grid.innerHTML = '<p class="empty-state" style="grid-column:1/-1">Не удалось загрузить данные сайта. Проверь, что файлы из папки <code>data/</code> доступны, и обнови страницу.</p>';
  }
}

init();
