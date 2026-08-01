import asyncio

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile

from .. import config, db
from ..i18n import _
from ..states import AdminStates
from ..keyboards import admin_kb, main_menu_kb
from ..runtime import bot

router = Router()


def is_admin(user_id):
    return user_id in config.ADMIN_IDS


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


@router.message(Command("console"))
async def cmd_console(message: Message):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await message.answer(_("admin_not_allowed", lang))
        return
    await message.answer(_("admin_panel", lang), reply_markup=admin_kb(lang))


# ---------- promo code ----------

@router.callback_query(F.data == "admin:addcode")
async def cb_addcode(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not is_admin(cq.from_user.id):
        await cq.answer(_("admin_not_allowed", lang))
        return
    await state.set_state(AdminStates.add_code)
    await cq.message.answer(_("admin_code_ask", lang))
    await cq.answer()


@router.message(AdminStates.add_code)
async def on_add_code(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer(_("admin_code_ask", lang))
        return
    try:
        code, discount, max_uses = parts[0], int(parts[1].rstrip("%")), int(parts[2])
    except ValueError:
        await message.answer(_("admin_code_ask", lang))
        return
    db.add_promo(code, discount, max_uses)
    await message.answer(_("admin_code_ok", lang, code=code.upper(), d=discount, u=max_uses))
    await state.clear()


# ---------- global discount ----------

@router.callback_query(F.data == "admin:adddiscount")
async def cb_adddiscount(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not is_admin(cq.from_user.id):
        await cq.answer(_("admin_not_allowed", lang))
        return
    await state.set_state(AdminStates.add_discount)
    await cq.message.answer(_("admin_discount_ask", lang))
    await cq.answer()


@router.message(AdminStates.add_discount)
async def on_add_discount(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        d = int(message.text.strip())
    except ValueError:
        await message.answer(_("admin_discount_ask", lang))
        return
    db.set_setting("global_discount", str(d))
    await message.answer(_("admin_discount_ok", lang, d=d))
    await state.clear()


# ---------- auction ----------

@router.callback_query(F.data == "admin:auction")
async def cb_auction_manage(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not is_admin(cq.from_user.id):
        await cq.answer(_("admin_not_allowed", lang))
        return
    lots = db.active_auctions()
    if lots:
        list_text = "\n".join(f"#{l['id']} «{l['title']}» — {l['current_price']} ⭐" for l in lots)
        text = _("admin_auction_list", lang, list=list_text)
    else:
        text = _("admin_auction_none", lang)
    await cq.message.answer(text)
    await cq.message.answer(_("admin_auction_ask", lang))
    await state.set_state(AdminStates.add_auction)
    await cq.answer()


@router.message(AdminStates.add_auction)
async def on_add_auction(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = message.text.split("|")
    if len(parts) < 3:
        await message.answer(_("admin_auction_ask", lang))
        return
    title = parts[0].strip()
    desc = parts[1].strip()
    try:
        start = int(parts[2].strip().replace("⭐", "").strip())
    except ValueError:
        await message.answer(_("admin_auction_ask", lang))
        return
    db.add_auction(title, desc, start)
    await message.answer(_("admin_auction_ok", lang))
    await state.clear()


@router.message(Command("del_lot"))
async def cmd_del_lot(message: Message):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await message.answer(_("admin_not_allowed", lang))
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(_("admin_auction_none", lang))
        return
    try:
        lot_id = int(parts[1])
    except ValueError:
        return
    db.del_auction(lot_id)
    await message.answer("✅ Лот удалён.")


# ---------- broadcast ----------

@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not is_admin(cq.from_user.id):
        await cq.answer(_("admin_not_allowed", lang))
        return
    await state.set_state(AdminStates.broadcast)
    await cq.message.answer(_("admin_broadcast_ask", lang))
    await cq.answer()


@router.message(AdminStates.broadcast)
async def on_broadcast(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = message.text or message.caption or ""
    photo = None
    if message.photo:
        photo = message.photo[-1].file_id

    users = db.all_user_ids()
    sent = 0
    for uid in users:
        if uid == message.from_user.id:
            continue
        try:
            if photo:
                await bot.send_photo(uid, photo, caption=text)
            else:
                await bot.send_message(uid, text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await message.answer(_("admin_broadcast_done", lang, n=sent))
    await state.clear()


# ---------- sponsors ----------

@router.callback_query(F.data == "admin:addsponsor")
async def cb_addsponsor(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not is_admin(cq.from_user.id):
        await cq.answer(_("admin_not_allowed", lang))
        return
    await state.set_state(AdminStates.add_sponsor)
    await cq.message.answer(_("admin_sponsor_ask", lang))
    await cq.answer()


@router.message(AdminStates.add_sponsor)
async def on_add_sponsor(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = message.text.split("|")
    if len(parts) < 2:
        await message.answer(_("admin_sponsor_ask", lang))
        return
    name = parts[0].strip()
    link = parts[1].strip()
    db.add_sponsor(name, link)
    await message.answer(_("admin_sponsor_ok", lang))
    await state.clear()


# ---------- stats ----------

@router.callback_query(F.data == "admin:stats")
async def cb_stats(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    if not is_admin(cq.from_user.id):
        await cq.answer(_("admin_not_allowed", lang))
        return
    text = _("stats_text", lang,
             users=db.count_users(),
             subs=db.count_subs(),
             revenue=db.revenue(),
             tickets=db.open_tickets_count(),
             lots=db.count_active_lots())
    await cq.message.answer(text)
    await cq.answer()
