#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/Dinktvi/Bot.py"
BOT_DIR="$HOME/Bot.py"

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

PY="$BOT_DIR/venv/bin/python3"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

echo "==> Ставлю pip (если нужно)..."
if ! "$PY" -m pip --version >/dev/null 2>&1; then
  "$PY" -m ensurepip --upgrade 2>/dev/null || "$PY" -m pip install --upgrade pip 2>/dev/null || true
fi

echo "==> Ставлю зависимости..."
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt

echo "==> Создаю папки..."
mkdir -p data assets

if [ ! -f .env ]; then
  echo "==> !!! .env не найден."
  echo ""
  echo "    Создай его так:"
  echo "    cd $BOT_DIR"
  echo "    cp .env.example .env"
  echo "    nano .env"
  echo ""
  echo "    Обязательно заполни:"
  echo "      BOT_TOKEN=<токен из @BotFather>"
  echo "      ADMIN_ID=<твой Telegram id>"
  echo "      USER_LLM_API_KEY=<ключ ИИ>"
  echo ""
  echo "    Затем запусти скрипт заново: bash $0"
  exit 1
fi

echo "==> Останавливаю старый процесс (если есть)..."
if [ -f bot.pid ]; then
  kill "$(cat bot.pid)" 2>/dev/null || true
  sleep 2
fi

echo "==> Запускаю бота..."
nohup "$PY" -m bot.main > bot.log 2>&1 &
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
CRON_LINE="* * * * * cd $BOT_DIR && if ! pgrep -f 'bot.main' > /dev/null; then nohup $PY -m bot.main >> bot.log 2>&1 & echo \$! > bot.pid; fi"
( crontab -l 2>/dev/null | grep -v 'bot.main'; echo "$CRON_LINE" ) | crontab -

echo "==> Готово. Бот будет жить 24/7."
echo "    Лог: $BOT_DIR/bot.log"
