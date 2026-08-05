import asyncio
import re
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
    provider_kb,
)
from ..services import llm
from ..runtime import bot

router = Router()

BUY_HINT = "menu:buy"

CODE_BLOCK_RE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


def has_sub(user_id):
    return db.get_active_subscription(user_id) is not None


async def _photo(name):
    p = Path(config.ASSETS_DIR) / name
    return FSInputFile(str(p)) if p.exists() else None


def _split_code_blocks(text):
    """Split assistant answer into (clean_text, list_of_code_blocks)."""
    blocks = CODE_BLOCK_RE.findall(text)
    if not blocks:
        return text.strip(), []
    clean = CODE_BLOCK_RE.sub("", text).strip()
    return clean, [{"lang": lang or "py", "code": code} for lang, code in blocks]


def _save_script(user_id, lang, code):
    name = f"script_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{lang or 'py'}"
    path = Path(config.SCRIPTS_DIR) / name
    path.write_text(code, encoding="utf-8")
    return path, name


# ---------- AI assistant ----------

async def _enter_assistant(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    if not has_sub(message.from_user.id):
        await message.answer(_("assistant_need_sub", lang), reply_markup=main_menu_kb(lang))
        return
    if not llm.is_configured():
        await message.answer(_("assistant_no_key", lang), reply_markup=main_menu_kb(lang))
        return
    await state.set_state(ChatStates.assistant)
    photo = await _photo("assistant.png")
    if photo:
        await message.answer_photo(photo, caption=_("assistant_start", lang), reply_markup=assistant_kb(lang))
    else:
        await message.answer(_("assistant_start", lang), reply_markup=assistant_kb(lang))


async def start_assistant(cq: CallbackQuery, state: FSMContext):
    try:
        await cq.message.delete()
    except Exception:
        pass
    await _enter_assistant(cq.message, state)
    await cq.answer()


@router.callback_query(F.data.startswith("model:"))
async def cb_model(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    uid = cq.from_user.id
    choice = cq.data.split(":")[1]
    if choice == "choose":
        current = db.get_ai_provider(uid)
        cur_name = config.AI_PROVIDERS[current]["name"] if current in config.AI_PROVIDERS else current
        await cq.message.edit_text(
            _("model_choose", lang, current=cur_name),
            reply_markup=provider_kb(lang, current),
        )
    elif choice in config.AI_PROVIDERS:
        db.set_ai_provider(uid, choice)
        p = config.AI_PROVIDERS[choice]
        await cq.message.edit_text(
            _("model_set", lang, model=p["name"]),
            reply_markup=assistant_kb(lang),
        )
    await cq.answer()


@router.message(ChatStates.assistant)
async def assistant_message(message: Message):
    lang = get_lang(message.from_user.id)
    user_id = message.from_user.id
    has_sub_flag = has_sub(user_id)
    requests = db.get_ai_requests(user_id)
    if not has_sub_flag and requests <= 0:
        await message.answer(_("assistant_need_sub", lang), reply_markup=main_menu_kb(lang))
        return
    user_text = message.text or ""
    thinking = await message.answer(_("assistant_thinking", lang))
    history = db.get_history(user_id)
    provider = db.get_ai_provider(user_id)
    answer = await asyncio.to_thread(llm.ask, user_text, lang, history, provider)
    if answer is None:
        await thinking.delete()
        await message.answer(_("assistant_no_key", lang), reply_markup=assistant_kb(lang))
        return
    await thinking.delete()
    db.add_history(user_id, "user", user_text)
    db.add_history(user_id, "assistant", answer)
    if not has_sub_flag:
        db.use_ai_request(user_id)

    clean, blocks = _split_code_blocks(answer)
    for b in blocks:
        path, name = _save_script(user_id, b["lang"], b["code"])
        try:
            await message.answer_document(FSInputFile(str(path)), caption=_("assistant_file_ready", lang, name=name))
        except Exception as e:
            print("[assistant] send file failed:", e)

    reply_text = clean or _("assistant_file_only", lang)
    kb = escalate_kb(lang) if llm.should_escalate(reply_text) else assistant_kb(lang)
    await message.answer(reply_text[:3500], reply_markup=kb)


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
    history = db.get_history(message.from_user.id)
    provider = db.get_ai_provider(message.from_user.id)
    answer = await asyncio.to_thread(llm.ask, message.text or "", lang, history, provider)
    if answer is None:
        await thinking.delete()
        await message.answer(_("assistant_no_key", lang), reply_markup=main_menu_kb(lang))
        return
    await thinking.delete()
    db.add_history(message.from_user.id, "user", message.text or "")
    db.add_history(message.from_user.id, "assistant", answer)
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
