import asyncio
import logging
import os
import sys
from pathlib import Path

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, ErrorEvent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from . import config, db
from . import github_db
from .handlers import shop, support, admin as admin_handlers, bonus, fallback, profile as profile_handlers, commands as commands_handlers
from .i18n import _
from .images import generate_all
from .keyboards import lang_kb, start_kb
from .menu import get_lang, show_main_menu
from .runtime import bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(commands_handlers.router)
dp.include_router(shop.router)
dp.include_router(admin_handlers.router)
dp.include_router(support.router)
dp.include_router(bonus.router)
dp.include_router(profile_handlers.router)
dp.include_router(fallback.router)


@dp.errors()
async def on_error(event: ErrorEvent):
    logging.exception("Update handler error: %s", event.exception)
    return True


@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cq: CallbackQuery, state: FSMContext):
    lang = cq.data.split(":")[1]
    db.set_lang(cq.from_user.id, lang)
    db.upsert_user(cq.from_user.id, cq.from_user.username, cq.from_user.first_name)
    await cq.message.delete()
    await show_main_menu(cq.message, lang)
    await cq.answer()


@dp.callback_query(F.data == "menu:main")
async def cb_main(cq: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = get_lang(cq.from_user.id)
    await cq.message.delete()
    await show_main_menu(cq.message, lang)
    await cq.answer()


@dp.callback_query(F.data == "menu:start")
async def cb_start(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    await cq.message.delete()
    await cq.message.answer(_("start_menu", lang), reply_markup=start_kb(lang))
    await cq.answer()


async def on_startup():
    github_db.pull()
    db.init_db()
    generate_all()
    me = await bot.get_me()
    logging.info("Bot started: @%s", me.username)


async def auction_loop():
    await asyncio.sleep(5)
    while True:
        await asyncio.sleep(30)
        try:
            finished = db.close_expired_auctions()
            for lot in finished:
                bidder = lot["highest_bidder"]
                if bidder:
                    try:
                        await bot.send_message(
                            bidder,
                            _("auction_bid_done", "ru",
                              title=lot["title"], winner=bidder, amount=lot["current_price"]),
                        )
                    except Exception:
                        pass
                for aid in config.ADMIN_IDS:
                    try:
                        await bot.send_message(
                            aid,
                            f"🏆 Лот «{lot['title']}» завершён. Победитель: {bidder} — {lot['current_price']} ⭐",
                        )
                    except Exception:
                        pass
        except Exception as e:
            logging.warning("auction_loop error: %s", e)


async def _health_server():
    port = os.getenv("PORT")
    if not port:
        return
    try:
        from aiohttp import web
    except ImportError:
        return
    app = web.Application()
    async def _ok(_req):
        return web.Response(text="ok")
    app.router.add_get("/", _ok)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(port))
    await site.start()
    print(f"[health] server on :{port}")
    while True:
        await asyncio.sleep(3600)


async def main():
    dp.startup.register(on_startup)
    asyncio.get_running_loop().create_task(auction_loop())
    asyncio.get_running_loop().create_task(_health_server())
    asyncio.get_running_loop().create_task(github_db.sync_loop())
    if config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET:
        from .oauth_server import run_oauth_server
        asyncio.get_running_loop().create_task(run_oauth_server())
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
