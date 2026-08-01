from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .i18n import _
from . import config


def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F1F7\U0001F1FA Русский", callback_data="lang:ru"),
         InlineKeyboardButton(text="\U0001F1EC\U0001F1E7 English", callback_data="lang:en")],
    ])


def main_menu_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("btn_start", lang), callback_data="menu:start"),
         InlineKeyboardButton(text=_("btn_support", lang), callback_data="menu:support")],
        [InlineKeyboardButton(text=_("btn_idea", lang), callback_data="menu:idea")],
    ])


def start_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("btn_buy", lang), callback_data="menu:buy"),
         InlineKeyboardButton(text=_("btn_ai_start", lang), callback_data="menu:assistant")],
        [InlineKeyboardButton(text=_("btn_my_sub", lang), callback_data="menu:mysub"),
         InlineKeyboardButton(text=_("btn_auction", lang), callback_data="menu:auction")],
        [InlineKeyboardButton(text=_("btn_sponsors", lang), callback_data="menu:sponsors")],
        [InlineKeyboardButton(text=_("btn_back", lang), callback_data="menu:main")],
    ])


def plans_kb(lang):
    btns = []
    for plan in ("standard", "pro"):
        btns.append([InlineKeyboardButton(text=_("plan_" + plan, lang), callback_data=f"plan:{plan}")])
    btns.append([InlineKeyboardButton(text=_("btn_activate_code", lang), callback_data="promo:start")])
    btns.append([InlineKeyboardButton(text=_("btn_back", lang), callback_data="menu:start")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def periods_kb(lang, plan):
    btns = []
    for p, price in config.PRICING[plan].items():
        price = apply_discount(price)
        btns.append([InlineKeyboardButton(text=f"{_('period_' + p, lang)} — {price} ⭐", callback_data=f"period:{plan}:{p}")])
    btns.append([InlineKeyboardButton(text=_("btn_back", lang), callback_data="menu:buy")])
    return InlineKeyboardMarkup(inline_keyboard=btns)


def pay_kb(lang, price):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {price} ⭐", pay=True)],
        [InlineKeyboardButton(text=_("btn_back", lang), callback_data="menu:buy")],
    ])


def escalate_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("btn_yes_admin", lang), callback_data="escalate:yes"),
         InlineKeyboardButton(text=_("btn_no_admin", lang), callback_data="escalate:no")],
    ])


def assistant_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("btn_back", lang), callback_data="menu:main")],
    ])


def admin_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_("btn_add_code", lang), callback_data="admin:addcode"),
         InlineKeyboardButton(text=_("btn_add_discount", lang), callback_data="admin:adddiscount")],
        [InlineKeyboardButton(text=_("btn_auction_manage", lang), callback_data="admin:auction"),
         InlineKeyboardButton(text=_("btn_broadcast", lang), callback_data="admin:broadcast")],
        [InlineKeyboardButton(text=_("btn_add_sponsor", lang), callback_data="admin:addsponsor"),
         InlineKeyboardButton(text=_("btn_stats", lang), callback_data="admin:stats")],
    ])


def apply_discount(price):
    d = config_discount()
    if d:
        price = int(price * (100 - d) / 100)
    return price


def config_discount():
    from .db import global_discount

    return global_discount()
