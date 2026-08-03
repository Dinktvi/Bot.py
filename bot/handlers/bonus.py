from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .. import config, db
from ..i18n import _
from ..keyboards import main_menu_kb

router = Router()


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


def bonus_kb(lang):
    rows = []
    for s in config.BONUS_SPONSORS:
        rows.append([InlineKeyboardButton(text=f"📢 {s['name']}", url=s["url"])])
    rows.append([InlineKeyboardButton(text=_("btn_claim", lang), callback_data="bonus:claim")])
    rows.append([InlineKeyboardButton(text=_("btn_back", lang), callback_data="menu:start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "menu:bonus")
async def cb_bonus(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    await state.clear()
    await cq.message.delete()
    await cq.message.answer(
        _("bonus_menu", lang, req=config.BONUS_AI_REQUESTS),
        reply_markup=bonus_kb(lang),
    )
    await cq.answer()


@router.callback_query(F.data == "bonus:claim")
async def cb_claim(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    if not db.claim_bonus(cq.from_user.id):
        await cq.answer(_("bonus_claimed", lang), show_alert=True)
        return
    until = db.grant_free_week(cq.from_user.id)
    await cq.message.delete()
    await cq.message.answer(
        _("bonus_ok", lang, until=until.strftime("%d.%m.%Y"), req=config.BONUS_AI_REQUESTS),
        reply_markup=main_menu_kb(lang),
    )
    await cq.answer()
