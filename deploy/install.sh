#!/usr/bin/env bash
# Установка CounterPick на Debian/Ubuntu VPS.
# Запуск из папки с распакованным сайтом:  sudo bash deploy/install.sh
set -euo pipefail

APP_DIR="/var/www/counterpick"
SITE_NAME="counterpick"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Нужны права root: sudo bash deploy/install.sh" >&2
  exit 1
fi

echo "==> 1/5 Проверяю пакеты"
if ! command -v nginx >/dev/null 2>&1; then
  echo "Ставлю nginx…"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx ca-certificates >/dev/null
fi

echo "==> 2/5 Копирую файлы в $APP_DIR"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR"/*
cp -r "$SRC_DIR"/index.html "$SRC_DIR"/assets "$SRC_DIR"/data "$APP_DIR"/
chown -R www-data:www-data "$APP_DIR"
find "$APP_DIR" -type d -exec chmod 755 {} \;
find "$APP_DIR" -type f -exec chmod 644 {} \;

echo "==> 3/5 Настраиваю nginx"
install -m 644 "$SRC_DIR/deploy/nginx-8080.conf" "/etc/nginx/sites-available/$SITE_NAME"
ln -sf "/etc/nginx/sites-available/$SITE_NAME" "/etc/nginx/sites-enabled/$SITE_NAME"
# существующие сайты на :80 не трогаем — CounterPick слушает :8080
nginx -t
systemctl enable --now nginx >/dev/null 2>&1 || true
systemctl reload nginx

echo "==> 4/5 Проверяю ответ сайта"
sleep 1
if command -v curl >/dev/null 2>&1; then
  CODE="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ || true)"
  echo "    HTTP $CODE"
else
  echo "    curl не установлен — проверь вручную"
fi

echo "==> 5/5 Открываю порт 8080 в firewall (если включён)"
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 8080/tcp >/dev/null 2>&1 || true
fi

IP="$(curl -s -4 --max-time 5 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo
echo "Готово! Сайт доступен: http://$IP:8080/"
echo "Конфиг nginx: /etc/nginx/sites-available/$SITE_NAME"
echo "Логи: /var/log/nginx/access.log, /var/log/nginx/error.log"
