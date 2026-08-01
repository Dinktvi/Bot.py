from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from .. import db
from ..i18n import _

router = Router()


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


@router.message()
async def fallback(message: Message):
    lang = get_lang(message.from_user.id)
    await message.answer(_("unknown", lang))


@router.callback_query()
async def fallback_cb(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    await cq.answer(_("unknown", lang))
