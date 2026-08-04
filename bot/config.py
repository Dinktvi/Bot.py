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
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scripts")

LLM_API_KEY = os.getenv("USER_LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("USER_LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("USER_LLM_MODEL", "deepseek-chat")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8080/github/callback")
GITHUB_SCOPE = "repo,user"
OAUTH_BASE_URL = os.getenv("OAUTH_BASE_URL", "http://localhost:8080")
OAUTH_HOST = os.getenv("OAUTH_HOST", "0.0.0.0")
OAUTH_PORT = int(os.getenv("OAUTH_PORT", "8080"))

BOT_NAME = "AI Helper Bot"
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID", "")

BONUS_SPONSORS = [
    {"name": "Zhirick_script", "url": "https://t.me/Zhirick_script"},
    {"name": "volgavpnbot", "url": "https://t.me/volgavpnbot?start=_tgr_k71Coeo2YTgy"},
    {"name": "VoxelVPNbot", "url": "https://t.me/VoxelVPNbot?start=_tgr_MP84l4c3YzIy"},
    {"name": "pochemutak1bot", "url": "https://t.me/pochemutak1bot?start=_tgr_PyCuTBQzNmEy"},
]

BONUS_AI_REQUESTS = 7
BONUS_FREE_DAYS = 7

os.makedirs(os.path.join(os.path.dirname(__file__), "..", "data"), exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)
