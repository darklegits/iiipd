# Данные DotaPicker

Все данные лежат в `data/` статикой — сайт не ходит в сторонние API при загрузке страницы (кроме популярности предметов и ленты новостей, которые тянутся с бэкенда/OpenDota).

## Источники

| Файл | Источник | Как обновляется |
|---|---|---|
| `heroes.json` | dotaconstants + ручные имена/алиасы | `tools/build-data.mjs` |
| `counters.json` | Stratz GraphQL (матчапы по всем героям) | `tools/stratz-sync.mjs`, cron на сервере ежечасно |
| `matchups/<id>.json` | Stratz GraphQL | тот же синк, инкрементально, свежесть 3 дня |
| `hero-abilities.json` | dotaconstants `hero_abilities.json` + `abilities.json` | скрипт сборки способностей |
| `items-full.json` | dotaconstants `items.json` + переводы | скрипт сборки каталога |
| `item-map.json`, `item-tree.json` | dotaconstants | `tools/build-data.mjs` |
| `tag-items.json` | ручная таблица «тег героя → предметы против него» | правится вручную |
| `hero-stats.json` | OpenDota `heroStats` | обновляется вместе с синком |

## Каталог предметов

`items-full.json` собирается из dotaconstants и содержит:

- `n` — название (английское, как в игре);
- `c` — цена;
- `q` — категория (`consumable`, `component`, `common`, `rare`, `epic`, `artifact`, `secret_shop`, `neutral`);
- `t` — разряд для нейтральных предметов (1–5);
- `attrib` — характеристики (`+ 10 Силы`);
- `notes` — механика предмета (переведена на русский);
- `lore` — лор;
- `comp` — из чего собирается.

Устаревшие предметы (курьеры, Necronomicon, Tome of Knowledge, Quarterstaff и т.п.) из каталога удалены.

## Переводы

Тексты предметов переводятся автоматически (Google Translate endpoint) с кэшем в `data/.translate-cache.json`. Кэш в репозиторий не попадает.

На сервере раз в сутки работает `translate-items.py` (cron 03:30) — дозаполняет переводы, если появились новые предметы.

## Синк Stratz

`tools/stratz-sync.mjs` (локально) и `/opt/counterpick/stratz-sync.py` (на сервере):

1. читает токен из `/etc/counterpick/stratz.token`;
2. для каждого героя тянет `heroVsHeroMatchup`;
3. пишет `data/matchups/<heroId>.json` и агрегирует `counters.json`;
4. пропускает героя, если файл свежее 3 дней (инкрементальность).

Токен Stratz обязателен: запросы без него отдают 403.

## Профиль игрока

`/api/player?id=<steamAccountId>` — бэкенд тянет **всю историю матчей** из Stratz (по 100 за запрос), считает средние GPM/XPM с весом по длительности матча и счётчики по героям. Ответ кэшируется на 6 часов в памяти процесса.
