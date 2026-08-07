from pathlib import Path

from aiogram.types import FSInputFile, Message

from . import config, db
from .i18n import _
from .images import generate_all
from .keyboards import main_menu_kb


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


async def show_main_menu(message: Message, lang: str):
    image_path = Path(config.ASSETS_DIR) / "main.png"
    if not image_path.exists():
        generate_all()
    caption = _("welcome", lang, name=config.BOT_NAME)
    try:
        await message.answer_photo(
            FSInputFile(str(image_path)),
            caption=caption,
            reply_markup=main_menu_kb(lang),
        )
    except Exception:
        await message.answer(caption, reply_markup=main_menu_kb(lang))
