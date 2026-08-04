# PROJECT STATE — резюме для продолжения работы (ЧИТАЙТЕ ПЕРВЫМ в новой сессии)

Этот файл — точка восстановления. Если чат/таск закончился, в новой сессии прочитай
этот файл + `bot/`, и продолжай работу с того места, где остановился.

## Суть проекта
Telegram-бот-магазин подписок (оплата звёздами XTR) + ИИ-ассистент + админ-панель.
Бот уже РАБОТАЕТ и протестирован.

## Ключевые данные (не потерять)
- **Бот токен**: 8703346061:AAHK0-QBCy4UlAaGOtli7qpmHGVjC5pWKv4 (в `bot/config.py` загружается из `.env`)
- **Главный админ**: 6382264272 (ему выдана PRO на 1 год до 27.07.2027)
- **GitHub репо**: https://github.com/Romsn-codes/Boot.py (ветка `master`, запушен весь код)
- **Цены**: Обычный 75/125/250/500 | Про 150/300/600/1250 ⭐ (1м/3м/6м/12м)
- **ИИ**: Groq, ключ в `/workspace/.env`, модель llama-3.3-70b-versatile

## Текущий статус (2026-08-04)
- [x] Всё ТЗ реализовано: язык RU/EN, меню «Старт/Поддержка/Предложка» → «Купить/ИИ-старт»
- [x] Оплата звёздами работает (тестовый счёт на 1⭐ был отправлен админу)
- [x] Админ-панель `/console`: промокоды, скидки, аукцион, рассылка, спонсоры, статистика,
      + НОВОЕ: «Выдать подписку» (по ID/@username, план+период, уведомление пользователю)
- [x] PRO включает всё из Обычного (текст в меню покупки)
- [x] Предложка: идеи пользователей уходят админу, ответ реплаем
- [x] Поддержка: сначала ИИ, при провале — тикет админу
- [x] Бонус за спонсоров: неделя Обычной + 7 запросов ИИ (один раз), спонсоры в BONUS_SPONSORS
- [x] ИИ-память: `chat_history` в БД, последние 20 сообщений
- [x] ИИ улучшен: сам создаёт скрипт ФАЙЛОМ (data/scripts/script_<uid>_*.py) и отправляет документом;
      в след. сообщениях НЕ повторяет весь код; умеет объяснять деплой на Termux/VPS/Railway/
      Oracle/серву/render; escalation по-прежнему через кнопку
- [x] GitHub-интеграция (OAuth):
  - Профиль (меню → Старт → Профиль): GitHub, число скриптов, запросов ИИ
  - Подключить GitHub: OAuth через github.com (client_id Ov23li1T87rOCqKnp2kV, secret в .env)
  - Мои файлы: список скриптов, Скачать/Удалить/Залить на GitHub
  - Залить на GitHub: создаёт репо `my-bot-scripts`, пушит файл base64 через API
  - OAuth-сервер: `bot/oauth_server.py`, порт 8080, публичный URL
    https://8080-17abfedf7a4fb066.monkeycode-ai.live (callback: /github/callback)
  - ВАЖНО: URL preview может поменяться в новой сессии → обновить GITHUB_REDIRECT_URI в .env
    и в настройках GitHub OAuth App (github.com/settings/developers)
- [ ] Хостинг 24/7 НЕ развёрнут: фри Railway закончился; serv00.com (бесплатно, без карты,
      SSH+Python+crontab) — регистрация временно закрыта («server user limit reached»),
      скрипт готов: `deploy/serv00-deploy.sh`; нужно пробовать регистрироваться в след. дни

## Запуск бота
```bash
cd /workspace
PYTHONPATH=/workspace python3 -m bot.main
```
Бот запускается в фоне через background terminal (инструмент `background_terminal_create`).
`.env` лежит в /workspace/.env (gitignored) и содержит BOT_TOKEN + ADMIN_ID + LLM + GITHUB.

## Окружение GitHub OAuth
В `bot/config.py` читаются переменные (из `.env`):
```
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_REDIRECT_URI=http://localhost:8080/github/callback
GITHUB_SCOPE=repo,user
OAUTH_BASE_URL=http://localhost:8080
OAUTH_HOST=0.0.0.0
OAUTH_PORT=8080
```
OAuth-сервер стартует только если заданы CLIENT_ID и CLIENT_SECRET.
Таблица `github_accounts(user_id, gh_username, gh_token, connected_at)` в SQLite.

## Хостинг 24/7 — выбранный путь (следующий шаг)
Пакеты готовы: `Dockerfile`, `docker-compose.yml`, `deploy/tg-shop-bot.service` (systemd),
`deploy/serv00-deploy.sh` (для serv00.com). Пользователь без карты и денег → serv00 (когда
откроется регистрация) или Termux/свой комп.

## Важно
- Токен GitHub (PAT) НЕ хранить в файлах проекта. Пользователю рекомендовано отозвать его.
- БД: `data/bot.db` (SQLite), gitignored. Скрипты: `data/scripts/` (gitignored).
- Пользователь просил «чтобы чат не пропадал» — поэтому этот файл и существует.
