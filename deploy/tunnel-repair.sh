#!/usr/bin/env bash
# Перезапуск публичного туннеля CounterPick и вывод актуального адреса.
set -euo pipefail

systemctl restart counterpick-tunnel
sleep 8

if ! systemctl is-active --quiet counterpick-tunnel; then
  echo "Туннель не запустился. Логи:" >&2
  journalctl -u counterpick-tunnel --no-pager -n 30 >&2
  exit 1
fi

URL="$(journalctl -u counterpick-tunnel --no-pager -n 80 | grep -oE 'https://[a-z0-9.-]+\.(lhr\.life|localhost\.run)' | tail -n 1 || true)"
echo "Туннель активен: ${URL:-не удалось распознать адрес, смотри journalctl -u counterpick-tunnel}"
