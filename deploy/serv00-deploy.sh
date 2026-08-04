#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/Romsn-codes/Boot.py"
BOT_DIR="$HOME/Boot.py"

cd "$HOME"

if [ -d "$BOT_DIR" ]; then
  echo "==> Обновляю репозиторий..."
  cd "$BOT_DIR"
  git pull
else
  echo "==> Клонирую репозиторий..."
  git clone "$REPO_URL"
  cd "$BOT_DIR"
fi

echo "==> Создаю виртуальное окружение..."
if [ ! -d venv ]; then
  python3 -m venv venv
fi
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

echo "==> Создаю папки..."
mkdir -p data assets

if [ ! -f .env ]; then
  echo "==> !!! .env не найден. Создай его командой:"
  echo "    nano $BOT_DIR/.env"
  echo "    Затем скопируй содержимое из инструкции и запусти скрипт заново."
  exit 1
fi

echo "==> Останавливаю старый процесс (если есть)..."
if [ -f bot.pid ]; then
  kill "$(cat bot.pid)" 2>/dev/null || true
  sleep 2
fi

echo "==> Запускаю бота..."
nohup ./venv/bin/python3 -m bot.main > bot.log 2>&1 &
echo $! > bot.pid

sleep 3
if kill -0 "$(cat bot.pid)" 2>/dev/null; then
  echo "==> Бот запущен (PID $(cat bot.pid))."
  echo "    Лог: $BOT_DIR/bot.log"
else
  echo "==> Бот упал. Смотри лог: $BOT_DIR/bot.log"
  exit 1
fi

echo "==> Настраиваю автозапуск через cron (проверка каждую минуту)..."
CRON_LINE="* * * * * cd $BOT_DIR && if ! pgrep -f 'python3 -m bot.main' > /dev/null; then nohup ./venv/bin/python3 -m bot.main >> bot.log 2>&1 & echo \$! > bot.pid; fi"
( crontab -l 2>/dev/null | grep -v 'bot.main'; echo "$CRON_LINE" ) | crontab -

echo "==> Готово. Бот будет жить 24/7."
echo "    Лог: $BOT_DIR/bot.log"
