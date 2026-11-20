# CounterPick — контрпики Dota 2

Одностраничное приложение: вводишь героя — получаешь 5–7 контрпиков, контр-предметы и короткое объяснение, почему это работает. Тёмная тема в духе DotaBuff, без бэкенда и сборки.

**Живая версия:** https://closed-star.vps.ktk-45.ru/counterpick/ — сайт развёрнут на учебном VPS `debian13-client` и отдаётся nginx'ом напрямую (без туннелей).

![Скриншот](shot-hero2.png)

## Что умеет

- **Поиск с автодополнением** по русским и английским именам, никам и сокращениям: `пудж`, `Pudge`, `pl`, `ам`, `антимаг`, `qop`. Работает и в шапке, и в большом поле на главной, с клавиатурой (↑/↓/Enter/Esc, `/` — фокус в поиск).
- **Карточка цели**: большая картинка героя, роли, атрибут, тип атаки, краткое описание угрозы.
- **Контр-предметы**: сетка иконок предметов против выбранного героя.
- **Контрпики**: карточки с иконкой, именем, пояснением, предметами и живым винрейтом (OpenDota).
- **18 героев с ручной подборкой** (Phantom Lancer, Anti-Mage, Pudge, Sniper, Invoker, Juggernaut, PA, Medusa, Spectre, Storm Spirit, Tinker, Bristleback, Huskar, Slark, Meepo, Legion Commander, Broodmother, Naga Siren) и **авто-режим для остальных 109**: контрпики по статистике матчапов OpenDota, а если API недоступен — по тегам героя.
- Ссылки вида `#/hero/phantom_lancer` можно шарить, кнопка «назад» в браузере работает.

## Локальный запуск

Нужен только Node.js 18+ (или любой статический сервер — сайт полностью статический).

```bash
cd "dota 2 proect"
node server.js          # http://localhost:3000
# или
npx serve .             # любой статик-сервер
```

`server.js` — мини-сервер без зависимостей: отдаёт статику, умеет `ETag`, кэш-заголовки, `/health`.

## Структура проекта

```
index.html            разметка страницы (главная + карточка героя)
assets/styles.css     тёмная тема, сетки, адаптив
assets/app.js         загрузка данных, поиск, роутинг, рендер
data/heroes.json      127 героев: id, ключ, имена RU/EN, алиасы, теги, роли, картинки
data/counters.json    курируемые контрпики: угроза, предметы, связки с пояснениями
data/items.json       предметы: название и картинка (CDN Dota 2)
data/tag-items.json   тег героя → предметы против него (для авто-режима)
tools/meta.mjs        русские имена, алиасы и теги героев
tools/build-data.mjs  сборка heroes.json/items.json + проверка ключей
server.js             локальный статик-сервер
deploy/               nginx-конфиг и скрипт установки на VPS
```

## Структура JSON с данными

`data/counters.json` — по ключу героя:

```json
{
  "phantom_lancer": {
    "threat": "Иллюзионист-керри: армия клонов забивает одиночную цель…",
    "items": ["bfury", "gungir", "mjollnir", "shivas_guard", "crimson_guard", "sheepstick"],
    "counters": [
      {
        "hero": "sven",
        "why": "Cleave с ультой стирает всю пачку иллюзий одним ударом, а BKB не даёт Лансеру законтрить тебя.",
        "items": ["bfury", "black_king_bar", "blink"]
      }
    ]
  }
}
```

- `items` — что купить **против** этого героя (ключи из `data/items.json`).
- `counters[].items` — предметы для конкретного героя-контрпика.
- Ключи героев — как в OpenDota без префикса `npc_dota_hero_` (`antimage`, `skeleton_king`, `zuus`, `windrunner`…), ключи предметов — внутренние имена Dota (`bfury`, `gungir`, `sheepstick`).

Чтобы добавить героя в ручную подборку: допиши блок в `data/counters.json` и при необходимости новые предметы в `data/items.json` (или запусти `npm run build:data`, он заново соберёт `heroes.json`/`items.json` из `heroes.raw.json` и `items.raw.json` и проверит все ключи).

## Деплой на VPS (Debian/Ubuntu)

Сайт статический, на сервере достаточно nginx. Установка с нуля:

```bash
# локально: собрать архив
tar -czf counterpick.tar.gz index.html assets data server.js package.json deploy README.md

# на сервер
scp counterpick.tar.gz root@<IP-сервера>:/root/
ssh root@<IP-сервера>
mkdir -p /opt/counterpick && tar -xzf /root/counterpick.tar.gz -C /opt/counterpick
cd /opt/counterpick && bash deploy/install.sh
```

`deploy/install.sh` поставит nginx, положит сайт в `/var/www/counterpick` и включит конфиг `deploy/nginx-8080.conf` — CounterPick слушает **порт 8080**, поэтому чужие сайты на :80 не ломаются.

Без nginx, просто Node:

```bash
cd /opt/counterpick && PORT=8080 node server.js
# http://<IP-сервера>:8080
```

## Как это развёрнуто на учебном VPS

- ВМ `car-backend-2063-92dbe531` (`debian13-client`, 10.31.0.36). Сайт лежит в `/var/www/counterpick` и доступен двумя способами:
  - **публично по домену ВМ**: `https://closed-star.vps.ktk-45.ru/counterpick/` — в server-блок основного сайта добавлен `location ^~ /counterpick/` (файл-заготовка: `deploy/nginx-counterpick-location.conf`, бэкап конфига на сервере: `/root/car-backend-2063.nginx.bak`). Основной сайт на `/` продолжает работать;
  - **напрямую по порту 8080**: nginx-конфиг `/etc/nginx/sites-available/counterpick` (`http://10.31.0.36:8080/`), доступен через VPN панели (раздел «VPN» → конфиг WireGuard).
- Дополнительно поднят временный SSH-туннель `counterpick-tunnel` (localhost.run), потому что бесплатный localhost.run меняет домен каждые ~30 минут. Постоянная ссылка — домен ВМ, туннель нужен только как запасной канал.
- Обновить файлы после правок:

```bash
scp -r index.html assets data root@10.31.0.36:/var/www/counterpick/
ssh root@10.31.0.36 systemctl reload nginx
```

Через консоль панели то же самое: распаковать архив в `/var/www/counterpick` и выполнить `systemctl reload nginx`.

Полезные команды на сервере: `nginx -t`, `systemctl reload nginx`, `journalctl -u counterpick-tunnel -f`, `tail -f /var/log/nginx/access.log`, `bash deploy/tunnel-repair.sh` (перезапуск туннеля и вывод текущего адреса).

## Данные и API

- Картинки героев и предметов — официальный CDN Dota 2 (`cdn.cloudflare.steamstatic.com`), без ключей.
- Список героев и предметов собран из открытых данных OpenDota (`heroStats`, `dotaconstants`).
- Живые винрейты — `GET https://api.opendota.com/api/heroes/{hero_id}/matchups` (CORS открыт, ключ не нужен). Винрейт цели против героя пересчитывается в силу контрпика: `100% − винрейт цели`. Ответы кэшируются в `localStorage` на 12 часов.
- Выборка матчапов у OpenDota небольшая, поэтому авто-режим сортирует контрпики со сглаживанием и показывает количество матчей в подсказке к винрейту.

Проект учебный и не связан с Valve. Dota 2 и все изображения принадлежат Valve Corporation.
