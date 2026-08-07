import asyncio
import secrets
import time

import requests
from aiohttp import web

from . import config, db
from .runtime import bot

_states = {}
_TTL = 600


def make_oauth_url(user_id):
    state = secrets.token_urlsafe(16)
    _states[state] = {"user_id": user_id, "ts": time.time()}
    return (
        "https://github.com/login/oauth/authorize"
        f"?client_id={config.GITHUB_CLIENT_ID}"
        f"&redirect_uri={config.GITHUB_REDIRECT_URI}"
        f"&scope={config.GITHUB_SCOPE}"
        f"&state={state}"
    )


def _cleanup():
    now = time.time()
    for s in list(_states):
        if now - _states[s]["ts"] > _TTL:
            _states.pop(s, None)


async def _login(request):
    _cleanup()
    state = request.query.get("state", "")
    info = _states.get(state)
    if not info:
        return web.Response(text="❌ Ошибка: ссылка недействительна или устарела.", content_type="text/html")
    user_id = info["user_id"]
    url = make_oauth_url(user_id)
    return web.Response(
        text=(
            "<html><body style='font-family:sans-serif;text-align:center;padding-top:60px'>"
            "<h2>Подключение GitHub</h2>"
            f"<p>Нажмите кнопку, чтобы авторизоваться:</p>"
            f"<a href='{url}' style='display:inline-block;padding:12px 24px;background:#24292e;color:#fff;"
            "border-radius:6px;text-decoration:none'>Войти через GitHub</a>"
            "</body></html>"
        ),
        content_type="text/html",
    )


async def _callback(request):
    code = request.query.get("code", "")
    state = request.query.get("state", "")
    info = _states.pop(state, None)
    if not info:
        return web.Response(text="❌ Ошибка: state не совпал.", content_type="text/html")
    user_id = info["user_id"]
    try:
        resp = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": config.GITHUB_REDIRECT_URI,
            },
            timeout=20,
        )
        token = resp.json().get("access_token")
        if not token:
            raise ValueError("no access_token")
        me = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {token}"},
            timeout=20,
        ).json()
        gh_username = me.get("login", "unknown")
        db.save_github(user_id, gh_username, token)
        lang = "ru"
        u = db.get_user(user_id)
        if u:
            lang = u["lang"]
        text = ("✅ GitHub подключён как <b>{name}</b>!\n\nТеперь ты можешь заливать свои скрипты в репозиторий."
                if lang == "ru" else
                "✅ GitHub connected as <b>{name}</b>!\n\nNow you can upload your scripts to a repository.")
        await bot.send_message(user_id, text.format(name=gh_username))
    except Exception as e:
        print("[oauth] callback error:", e)
        try:
            await bot.send_message(user_id, "❌ Не удалось подключить GitHub. Попробуй ещё раз.")
        except Exception:
            pass
    return web.Response(
        text=(
            "<html><body style='font-family:sans-serif;text-align:center;padding-top:60px'>"
            "<h2>✅ Готово!</h2><p>Можешь вернуться в Telegram.</p></body></html>"
        ),
        content_type="text/html",
    )


async def _root(request):
    return web.Response(text="Bot OAuth server is running.", content_type="text/html")


async def run_oauth_server():
    app = web.Application()
    app.router.add_get("/", _root)
    app.router.add_get("/github/login", _login)
    app.router.add_get("/github/callback", _callback)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(config.OAUTH_PORT)
    site = web.TCPSite(runner, config.OAUTH_HOST, port)
    await site.start()
    print(f"[oauth] server running on http://{config.OAUTH_HOST}:{port}")
    while True:
        await asyncio.sleep(3600)
