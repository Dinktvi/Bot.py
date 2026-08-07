from datetime import datetime
from pathlib import Path

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, LabeledPrice, FSInputFile

from .. import config, db
from ..i18n import _
from ..states import UserPromoStates
from ..keyboards import plans_kb, periods_kb, pay_kb, apply_discount, main_menu_kb

router = Router()


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


async def get_photo(name):
    path = Path(config.ASSETS_DIR) / name
    return FSInputFile(str(path)) if path.exists() else None


@router.callback_query(F.data == "menu:buy")
async def cb_buy(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    await cq.message.delete()
    photo = await get_photo("plans.png")
    if photo:
        await cq.message.answer_photo(photo, caption=_("buy_choose", lang), reply_markup=plans_kb(lang))
    else:
        await cq.message.answer(_("buy_choose", lang), reply_markup=plans_kb(lang))
    await cq.answer()


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    plan = cq.data.split(":")[1]
    kb = periods_kb(lang, plan)
    try:
        await cq.message.edit_caption(caption=_("buy_choose", lang), reply_markup=kb)
    except TelegramBadRequest:
        try:
            await cq.message.edit_text(text=_("buy_choose", lang), reply_markup=kb)
        except TelegramBadRequest:
            await cq.message.delete()
            await cq.message.answer(_("buy_choose", lang), reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("period:"))
async def cb_period(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    _sep, plan, period = cq.data.split(":")
    price = apply_discount(config.PRICING[plan][period])
    promo = (await state.get_data()).get("promo")
    discount = 0
    if promo:
        p = db.get_promo(promo)
        if p:
            discount = p["discount"]
            price = int(price * (100 - discount) / 100)
    price = max(1, price)

    title = _("pay_title", lang, plan=_(f"plan_{plan}", lang), period=_(f"period_{period}", lang))
    desc = _("pay_desc", lang, period=_(f"period_{period}", lang))
    payload = f"{plan}:{period}"
    if promo:
        payload += f":{promo}"
    prices = [LabeledPrice(label=f"⭐ {price}", amount=price)]

    text = _("pay_confirm", lang, plan=_(f"plan_{plan}", lang),
             period=_(f"period_{period}", lang), price=price)
    if plan == "pro":
        text += "\n\n" + _("pro_includes", lang)
    if discount:
        text += "\n\n" + _("pay_promo_applied", lang, discount=discount)

    kb = pay_kb(lang, price)

    try:
        await cq.message.delete()
        await cq.message.answer_invoice(
            title=title,
            description=desc,
            payload=payload,
            currency="XTR",
            prices=prices,
            provider_token="",
            reply_markup=kb,
        )
    except TelegramBadRequest as e:
        print("[shop] invoice error:", e)
        await cq.message.answer(_("unknown", lang))
    await cq.answer()


@router.pre_checkout_query()
async def on_pre_checkout(pq):
    await pq.answer(ok=True)


@router.message(F.successful_payment)
async def on_payment(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if len(parts) < 2 or parts[0] not in config.PRICING or parts[1] not in config.PERIOD_MONTHS:
        await message.answer(
            "⚠️ Не удалось распознать товар оплаты. Напиши в поддержку — тебе вернут подписку."
        )
        return
    plan, period = parts[0], parts[1]
    promo = parts[2] if len(parts) > 2 else None
    months = config.PERIOD_MONTHS[period]
    price = message.successful_payment.total_amount

    used_promo = None
    if promo:
        res = db.use_promo(promo)
        if res and res != "used":
            used_promo = promo

    until = db.add_subscription(message.from_user.id, plan, period, months, price, used_promo)
    until_str = until.strftime("%d.%m.%Y")

    text = _("pay_success", lang, plan=_(f"plan_{plan}", lang),
             period=_(f"period_{period}", lang), until=until_str)
    await message.answer(text, reply_markup=main_menu_kb(lang))
    await state.clear()


@router.callback_query(F.data == "menu:mysub")
async def cb_my_sub(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    sub = db.get_active_subscription(cq.from_user.id)
    if sub:
        until = datetime.fromisoformat(sub["expires_at"]).strftime("%d.%m.%Y")
        text = _("pay_active", lang, plan=_(f"plan_{sub['plan']}", lang), until=until)
    else:
        text = _("pay_no_sub", lang)
    await cq.message.delete()
    await cq.message.answer(text, reply_markup=main_menu_kb(lang))
    await cq.answer()


# ---------- promo code ----------

@router.callback_query(F.data == "promo:start")
async def cb_promo_start(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    await state.set_state(UserPromoStates.enter_code)
    await cq.message.answer(_("promo_ask", lang))
    await cq.answer()


@router.message(UserPromoStates.enter_code)
async def on_promo_enter(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    code = (message.text or "").strip().upper()
    promo = db.get_promo(code)
    if promo:
        if promo["max_uses"] > 0 and promo["uses"] >= promo["max_uses"]:
            await message.answer(_("promo_used", lang))
        else:
            await state.update_data(promo=code)
            await message.answer(_("promo_ok", lang, discount=promo["discount"]))
            await message.answer(_("buy_choose", lang), reply_markup=plans_kb(lang))
    else:
        await message.answer(_("promo_invalid", lang))
    await state.clear()


# ---------- menu redirects ----------

@router.callback_query(F.data == "menu:assistant")
async def cb_assistant(cq: CallbackQuery, state: FSMContext):
    from .support import start_assistant

    await start_assistant(cq, state)


@router.callback_query(F.data == "menu:auction")
async def cb_auction(cq: CallbackQuery, state: FSMContext):
    from .support import show_auction

    await show_auction(cq, state)


@router.callback_query(F.data == "menu:support")
async def cb_support(cq: CallbackQuery, state: FSMContext):
    from .support import start_support

    await start_support(cq, state)


@router.callback_query(F.data == "menu:sponsors")
async def cb_sponsors(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    sponsors = db.active_sponsors()
    if not sponsors:
        text = _("sponsors_empty", lang)
    else:
        text = "\n\n".join(_("sponsor_item", lang, name=s["name"], link=s["link"]) for s in sponsors)
    await cq.message.delete()
    await cq.message.answer(text, reply_markup=main_menu_kb(lang))
    await cq.answer()
