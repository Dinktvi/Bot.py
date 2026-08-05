# Telegram Bot: Subscription Shop + AI Assistant

Бот-магазин подписок (в Telegram Stars) с ИИ-ассистентом, поддержкой и админ-панелью.

## Возможности
- Выбор языка при старте: Русский / English
- Меню: «Старт / Поддержка / Предложка» → «Старт» открывает «Купить подписку / ИИ-старт»
- «Предложка» — отправить свою идею бота/сценария напрямую админу
- Красивое меню с картинками (генерируются автоматически, Pillow)
- Тарифы «Обычный» и «Про» с оплатой звёздами (XTR), PRO включает всё из Обычного
  - Обычный: 1м 75⭐ / 3м 125⭐ / 6м 250⭐ / год 500⭐
  - Про: 1м 150⭐ / 3м 300⭐ / 6м 600⭐ / год 1250⭐
- Промокоды со скидками, глобальная скидка
- Аукцион (ставки в звёздах)
- ИИ-ассистент (помогает создавать ботов, сценарии, скрипты)
- Поддержка: сначала ИИ, при провале — живой админ (ответ реплаем на сообщение)
- Спонсоры, рассылка, статистика

## Где взять ключ для ИИ
- **Groq — бесплатный тир**: https://console.groq.com → API Keys → `gsk_...`,
  BASE_URL `https://api.groq.com/openai/v1`, модель `llama-3.3-70b-versatile`
- **DeepSeek — дёшево**: https://platform.deepseek.com → API Keys,
  BASE_URL `https://api.deepseek.com/v1`, модель `deepseek-chat`
- **Meta Llama — бесплатно (DeepInfra)**: https://deepinfra.com → API Keys,
  BASE_URL `https://api.deepinfra.com/v1/openai`, модель `meta-llama/Meta-Llama-3.3-70B-Instruct`
- **Gemini — бесплатный тир**: https://aistudio.google.com → API Keys,
  BASE_URL `https://generativelanguage.googleapis.com/v1beta/openai`, модель `gemini-2.0-flash`

Пропиши в `.env` → перезапусти бота.

## Запуск
```bash
chmod +x run.sh
./run.sh
```

## Конфигурация (.env)
```bash
cp .env.example .env
```
- `BOT_TOKEN` — токен бота (уже указан)
- `ADMIN_ID` — глобальный админ: `6382264272`
- `USER_LLM_API_KEY` — **свой** ключ для ИИ-ассистента (без него ИИ не работает,
  запросы уходят админу напрямую)
- `USER_LLM_BASE_URL` / `USER_LLM_MODEL` — совместимый endpoint (по умолчанию DeepSeek)

## Админ-панель
Команда `/console` (только для админов):
- Добавить промокод: `КОД скидка% лимит` (например `HELLO 20 100`)
- Добавить глобальную скидку: число в %
- Аукцион: новый лот `Название | описание | стартовая_ставка`; удаление `/del_lot ID`
- Рассылка: текст (можно с фото) — уйдёт всем пользователям бота
- Добавить спонсора: `Название | ссылка`
- Статистика

## Поддержка и ИИ
- Кнопка «ИИ-ассистент» — чат с ИИ (доступно подписчикам)
- Кнопка «Поддержка» — сначала отвечает ИИ; если ИИ «не смог», заявка
  отправляется админу. Админ отвечает, нажав reply на сообщение о заявке.

## Структура
```
bot/
  main.py          — точка входа, /start, меню
  config.py        — токен, админ, цены, LLM
  i18n.py          — переводы RU/EN
  db.py            — SQLite
  images.py        — генерация картинок (Pillow)
  keyboards.py     — inline-клавиатуры
  states.py        — FSM-состояния
  runtime.py       — инстанс бота
  handlers/
    shop.py        — покупка, оплата звёздами, промокоды
    support.py     — ИИ-ассистент, поддержка, аукцион
    admin.py       — /console админ-панель
    fallback.py    — фолбэк
  services/llm.py  — вызов LLM
```

## 24/7 хостинг (VPS)
Эта среда не даёт гарантии круглосуточной работы (автозасыпание). Для настоящего 24/7 разверни на VPS одним из способов:

### Railway (бесплатно ~$5 на 30 дней, без карты)
1. https://railway.com → Sign up через GitHub
2. New Project → Deploy from GitHub repo → выбрать `Dinktvi/Bot.py`
3. В **Variables** добавить: `BOT_TOKEN`, `ADMIN_ID`, `USER_LLM_API_KEY`, `USER_LLM_BASE_URL`, `USER_LLM_MODEL`
4. В **Volumes** подключить `/app/data` (папка `data`), чтобы БД и скрипты не стирались при редеплое.
   Бот слушает `$PORT` (health-check), поэтому Railway считает его живым.

> Подписки, промокоды и скрипты хранятся в SQLite (`data/bot.db`).
> Путь к БД — абсолютный от корня проекта, поэтому при обновлении кода
> и перезапуске подписки **не обнуляются**, пока папка `data` сохраняется
> (volume на Railway / локальная папка на VPS).

### Docker
```bash
# на VPS с установленным Docker
docker compose up -d --build
```

### systemd
```bash
sudo cp deploy/tg-shop-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tg-shop-bot
# логи: journalctl -u tg-shop-bot -f
```

### serv00.com (бесплатно, регистрация открывается волнами)
```bash
ssh <логин>@<хост>.serv00.net
cd ~ && wget -qO- https://raw.githubusercontent.com/Dinktvi/Bot.py/master/deploy/serv00-deploy.sh | bash
```

## Выбор модели ИИ
В меню ИИ-ассистента есть кнопка «Модель ИИ» — пользователь выбирает
между Groq (Llama 3.3), DeepSeek и Meta Llama (кнопки появляются только
для тех провайдеров, у которых задан ключ в `.env`).

ИИ перед ответом показывает, что именно делает (пишет код / объясняет) и
примерное время; после ответа сообщает фактическое время выполнения.

### Проверка после запуска
- `/start` в боте → меню с картинкой
- `/console` → админ-панель (только для админов)
- Оплата звёздами: бот сам принимает платежи (XTR), никаких настроек провайдера не нужно
