# Деплой DotaPicker

## Как устроено на сервере

- ВМ `debian13-client`, внутренний IP `10.31.0.31`, доступ по SSH только через WireGuard-туннель (`10.31.0.0/16`).
- Статика: `/var/www/counterpick` (владелец `www-data:www-data`, файлы `644`).
- nginx отдаёт сайт на `:80`; снаружи он опубликован как `https://vast-owl.vps.ktk-45.ru/` через edge-прокси.
- Бэкенд: `/opt/counterpick/api.py`, systemd `counterpick-api.service`, слушает `127.0.0.1:8787`; nginx проксирует `/api/`.
- База: `/var/lib/counterpick/app.db` (пользователи, сессии, избранное).
- Токен Stratz: `/etc/counterpick/stratz.token` (владелец `www-data`, `600`).
- Cron:
  - `17 * * * *` — `/opt/counterpick/stratz-sync.py` (матчапы);
  - `30 3 * * *` — `/opt/counterpick/translate-items.py` (переводы предметов).

## Обновление файлов

```bash
# с локальной машины (нужен поднятый WireGuard)
pscp -pw <пароль> index.html            root@10.31.0.31:/var/www/counterpick/index.html
pscp -pw <пароль> assets/app.js         root@10.31.0.31:/var/www/counterpick/assets/app.js
pscp -pw <пароль> assets/styles.css     root@10.31.0.31:/var/www/counterpick/assets/styles.css
pscp -pw <пароль> data/items-full.json  root@10.31.0.31:/var/www/counterpick/data/items-full.json

ssh root@10.31.0.31 'chown -R www-data:www-data /var/www/counterpick && find /var/www/counterpick -type f -exec chmod 644 {} \;'
```

После правок CSS/JS поднимайте версию в `index.html` (`?v=N`), иначе браузеры отдадут кэш.

## Бэкенд

```bash
scp api.py root@10.31.0.31:/opt/counterpick/api.py
ssh root@10.31.0.31 'python3 -m py_compile /opt/counterpick/api.py && systemctl restart counterpick-api && systemctl is-active counterpick-api'
```

Логи: `journalctl -u counterpick-api -f`.

## nginx

- `/img/`, `/steamimg/`, `/steamid/` — прокси и кэш картинок Steam CDN;
- `/data/` — без кэша (`no-cache`), чтобы обновления данных подхватывались сразу;
- `/api/` — прокси на `127.0.0.1:8787`;
- `/health` — проверка живости.

Проверка конфига: `nginx -t && systemctl reload nginx`.

## Типовые проблемы

| Симптом | Причина / решение |
|---|---|
| `plink: Connection timed out` | не поднят WireGuard `vpn-student16`; Cloudflare WARP не маршрутизирует в `10.31.0.0/16` |
| `/api/*` отдаёт 502 | упал `counterpick-api`: `systemctl status counterpick-api` |
| Stratz 403 | протух/сбит токен в `/etc/counterpick/stratz.token` (должен быть ровно 311 символов) |
| Картинки Steam не грузятся | проверьте `resolver` и rewrite в location `/steamimg/` |
| Старая версия сайта | не поднят `?v=N` в `index.html` или кэш nginx |
