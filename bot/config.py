import os

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Create a .env file from .env.example")

GLOBAL_ADMIN_ID = int(os.getenv("ADMIN_ID", "6382264272"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", str(GLOBAL_ADMIN_ID)).split(",") if x]

PAYMENT_CURRENCY = "XTR"

PRICING = {
    "standard": {
        "1m": 75,
        "3m": 125,
        "6m": 250,
        "12m": 500,
    },
    "pro": {
        "1m": 150,
        "3m": 300,
        "6m": 600,
        "12m": 1250,
    },
}

PLAN_NAMES = {"standard": "Обычный", "pro": "Про"}
PERIOD_NAMES = {"1m": "1 месяц", "3m": "3 месяца", "6m": "6 месяцев", "12m": "12 месяцев"}
PERIOD_MONTHS = {"1m": 1, "3m": 3, "6m": 6, "12m": 12}

DB_PATH = os.getenv("DB_PATH", "data/bot.db")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

LLM_API_KEY = os.getenv("USER_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("USER_LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("USER_LLM_MODEL", "deepseek-chat")

BOT_NAME = "AI Helper Bot"
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID", "")

os.makedirs(os.path.join(os.path.dirname(__file__), "..", "data"), exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
