import asyncio
from datetime import datetime
from html import escape
from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, FSInputFile

from .. import config, db
from ..i18n import _
from ..states import ChatStates, IdeaStates
from ..keyboards import (
    assistant_kb,
    escalate_kb,
    main_menu_kb,
)
from ..services import llm
from ..runtime import bot

router = Router()

BUY_HINT = "menu:buy"


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


def has_sub(user_id):
    return db.get_active_subscription(user_id) is not None


async def _photo(name):
    p = Path(config.ASSETS_DIR) / name
    return FSInputFile(str(p)) if p.exists() else None


# ---------- AI assistant ----------

async def start_assistant(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not has_sub(cq.from_user.id):
        await cq.message.delete()
        await cq.message.answer(_("assistant_need_sub", lang), reply_markup=main_menu_kb(lang))
        await cq.answer()
        return
    if not llm.is_configured():
        await cq.message.delete()
        await cq.message.answer(_("assistant_no_key", lang), reply_markup=main_menu_kb(lang))
        await cq.answer()
        return
    await state.set_state(ChatStates.assistant)
    await cq.message.delete()
    photo = await _photo("assistant.png")
    if photo:
        await cq.message.answer_photo(photo, caption=_("assistant_start", lang), reply_markup=assistant_kb(lang))
    else:
        await cq.message.answer(_("assistant_start", lang), reply_markup=assistant_kb(lang))
    await cq.answer()


@router.message(ChatStates.assistant)
async def assistant_message(message: Message):
    lang = get_lang(message.from_user.id)
    if not has_sub(message.from_user.id):
        await message.answer(_("assistant_need_sub", lang), reply_markup=main_menu_kb(lang))
        return
    thinking = await message.answer(_("assistant_thinking", lang))
    answer = await asyncio.to_thread(llm.ask, message.text or "", lang)
    if answer is None:
        await thinking.delete()
        await message.answer(_("assistant_no_key", lang), reply_markup=assistant_kb(lang))
        return
    await thinking.delete()
    if llm.should_escalate(answer):
        await message.answer(answer[:3500], reply_markup=escalate_kb(lang))
    else:
        await message.answer(answer[:3500], reply_markup=assistant_kb(lang))


@router.callback_query(F.data.startswith("escalate:"))
async def cb_escalate(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    choice = cq.data.split(":")[1]
    await state.clear()
    if choice == "yes":
        await cq.message.delete()
        await cq.message.answer(_("ticket_created", lang), reply_markup=main_menu_kb(lang))
        await notify_admins(cq.from_user, text=_("ticket_admin_new", lang, user=cq.from_user.id, text=_("btn_yes_admin", lang)))
    else:
        await cq.message.answer(_("main_menu", lang), reply_markup=main_menu_kb(lang))
    await cq.answer()


# ---------- Support chat (AI first, escalate) ----------

async def start_support(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    await state.set_state(ChatStates.support)
    await cq.message.delete()
    await cq.message.answer(_("support_start", lang), reply_markup=assistant_kb(lang))
    await cq.answer()


@router.message(ChatStates.support)
async def support_message(message: Message):
    lang = get_lang(message.from_user.id)
    user_text = escape(message.text or "")
    if not llm.is_configured():
        await notify_admins(
            message.from_user,
            text=_("ticket_admin_new", lang, user=link_user(message), text=user_text),
        )
        await message.answer(_("ticket_created", lang), reply_markup=main_menu_kb(lang))
        return

    thinking = await message.answer(_("assistant_thinking", lang))
    answer = await asyncio.to_thread(llm.ask, message.text or "", lang)
    if answer is None:
        await thinking.delete()
        await message.answer(_("assistant_no_key", lang), reply_markup=main_menu_kb(lang))
        return
    await thinking.delete()
    if llm.should_escalate(answer):
        await notify_admins(
            message.from_user,
            text=_("ticket_admin_new", lang, user=link_user(message), text=user_text),
        )
        await message.answer(_("ticket_created", lang), reply_markup=main_menu_kb(lang))
    else:
        await message.answer(answer[:3500], reply_markup=assistant_kb(lang))


def link_user(msg):
    uid = msg.from_user.id
    name = msg.from_user.username or msg.from_user.first_name or str(uid)
    return f"<a href=\"tg://user?id={uid}\">{escape(name)}</a>"


async def notify_admins(from_user, text):
    for aid in config.ADMIN_IDS:
        try:
            sent = await bot.send_message(aid, text)
            db.track_admin_message(sent.message_id, from_user.id)
        except Exception as e:
            print("[support] notify admin failed:", e)


@router.message(F.reply_to_message & F.from_user.id.in_(config.ADMIN_IDS))
async def admin_reply(message: Message):
    if not message.reply_to_message:
        return
    target = db.get_admin_reply_target(message.reply_to_message.message_id)
    if not target:
        return
    user_text = escape(message.text or message.caption or "")
    try:
        await bot.send_message(target, f"👨‍💻 <b>Администратор:</b>\n\n{user_text}")
        db.close_ticket_for(target)
    except Exception as e:
        print("[support] reply to user failed:", e)


# ---------- Auction ----------

async def show_auction(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    await cq.message.delete()
    photo = await _photo("auction.png")
    lots = db.active_auctions()
    if not lots:
        if photo:
            await cq.message.answer_photo(photo, caption=_("auction_empty", lang), reply_markup=main_menu_kb(lang))
        else:
            await cq.message.answer(_("auction_empty", lang), reply_markup=main_menu_kb(lang))
        await cq.answer()
        return
    for lot in lots:
        ends = datetime.fromisoformat(lot["ends_at"])
        left = ends - datetime.now()
        mins = int(left.total_seconds() // 60)
        h, m = divmod(mins, 60)
        time_str = f"{h}ч {m}м" if h else f"{m}м"
        text = _("auction_lot", lang,
                 title=lot["title"],
                 desc=lot["description"],
                 start=lot["start_price"],
                 current=lot["current_price"],
                 time=time_str)
        if photo:
            await cq.message.answer_photo(photo, caption=text)
        else:
            await cq.message.answer(text)
    await cq.message.answer(_("main_menu", lang), reply_markup=main_menu_kb(lang))
    await cq.answer()


# ---------- Idea proposal (Предложка) ----------

@router.callback_query(F.data == "menu:idea")
async def cb_idea(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    await state.set_state(IdeaStates.idea)
    await cq.message.delete()
    await cq.message.answer(_("idea_ask", lang), reply_markup=assistant_kb(lang))
    await cq.answer()


@router.message(IdeaStates.idea)
async def on_idea(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    user_text = escape(message.text or message.caption or "")
    await notify_admins(
        message.from_user,
        text=_("idea_admin_new", lang, user=link_user(message), text=user_text),
    )
    await state.clear()
    await message.answer(_("idea_ok", lang), reply_markup=main_menu_kb(lang))


@router.message(F.text.regexp(r"^\d+$"))
async def auction_bid(message: Message):
    lang = get_lang(message.from_user.id)
    lots = db.active_auctions()
    if not lots:
        return
    amount = int(message.text)
    placed = False
    for lot in lots:
        res = db.place_bid(lot["id"], message.from_user.id, amount)
        if res == "ok":
            placed = True
            await message.answer(_("auction_bid_ok", lang, amount=amount))
            break
        if res == "low":
            await message.answer(_("auction_bid_low", lang, current=lot["current_price"]))
            break
    if placed:
        for aid in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    aid,
                    f"🔨 Новая ставка на «{lot['title']}»: {amount} ⭐ (от {message.from_user.id})",
                )
            except Exception:
                pass
