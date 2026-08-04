from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import config, db
from ..i18n import _
from ..keyboards import lang_kb, admin_kb

router = Router()


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


async def _show_main(message: Message, state: FSMContext):
    await state.clear()
    from ..main import show_main_menu

    await show_main_menu(message, get_lang(message.from_user.id))


@router.message(F.text.startswith("/"))
async def on_command(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    text = (message.text or "").strip()
    cmd = text.split()[0].lower().split("@")[0]

    if cmd == "/start":
        await state.clear()
        user = message.from_user
        db.upsert_user(user.id, user.username, user.first_name)
        u = db.get_user(user.id)
        if not u["lang"] or u["lang"] not in ("ru", "en"):
            await message.answer(_("lang_choose", "ru"), reply_markup=lang_kb())
        else:
            from ..main import show_main_menu

            await show_main_menu(message, u["lang"])
        return

    if cmd in ("/menu", "/help"):
        await _show_main(message, state)
        return

    if cmd == "/plans":
        await state.clear()
        from ..keyboards import plans_kb

        await message.answer(_("buy_choose", lang), reply_markup=plans_kb(lang))
        return

    if cmd in ("/create", "/my_bots"):
        await state.clear()
        from .support import _enter_assistant

        await _enter_assistant(message, state)
        return

    if cmd == "/suggest":
        await state.clear()
        from ..states import IdeaStates

        await state.set_state(IdeaStates.idea)
        await message.answer(_("idea_ask", lang))
        return

    if cmd == "/language":
        await state.clear()
        await message.answer(_("lang_choose", lang), reply_markup=lang_kb())
        return

    if cmd == "/profile":
        await state.clear()
        from .profile import profile_from_message

        await profile_from_message(message, message.from_user.id, lang)
        return

    if cmd == "/console":
        await state.clear()
        if message.from_user.id not in config.ADMIN_IDS:
            await message.answer(_("admin_not_allowed", lang))
            return
        await message.answer(_("admin_panel", lang), reply_markup=admin_kb(lang))
        return

    if cmd == "/del_lot":
        await state.clear()
        if message.from_user.id not in config.ADMIN_IDS:
            await message.answer(_("admin_not_allowed", lang))
            return
        parts = text.split()
        if len(parts) < 2:
            await message.answer(_("admin_auction_none", lang))
            return
        try:
            lot_id = int(parts[1])
        except ValueError:
            return
        db.del_auction(lot_id)
        await message.answer("✅ Лот удалён.")
        return

    await message.answer(_("unknown", lang))
