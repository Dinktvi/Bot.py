import base64
import requests
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile

from .. import config, db
from ..i18n import _
from ..keyboards import profile_kb, main_menu_kb
from .support import get_lang

router = Router()


def _files_for(user_id):
    d = Path(config.SCRIPTS_DIR)
    if not d.exists():
        return []
    return sorted(d.glob(f"script_{user_id}_*.py"), key=lambda p: p.stat().st_mtime, reverse=True)


# ---------- profile ----------

async def show_profile(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    user_id = cq.from_user.id
    gh = db.get_github(user_id)
    files = _files_for(user_id)
    gh_line = f"@{gh['gh_username']}" if gh else _("profile_gh_none", lang)
    text = _("profile_text", lang,
             gh=gh_line,
             files=len(files),
             requests=db.get_ai_requests(user_id))
    await cq.message.delete()
    await cq.message.answer(text, reply_markup=profile_kb(lang))
    await cq.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(cq: CallbackQuery):
    await show_profile(cq)


# ---------- connect / disconnect github ----------

@router.callback_query(F.data == "gh:connect")
async def cb_gh_connect(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    if not (config.GITHUB_CLIENT_ID and config.GITHUB_CLIENT_SECRET):
        await cq.answer(_("gh_not_configured", lang), show_alert=True)
        return
    from ..oauth_server import make_oauth_url
    url = make_oauth_url(cq.from_user.id)
    await cq.message.answer(_("gh_connect_hint", lang, url=url))
    await cq.answer()


@router.callback_query(F.data == "gh:disconnect")
async def cb_gh_disconnect(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    db.disconnect_github(cq.from_user.id)
    await cq.answer(_("gh_disconnected", lang), show_alert=True)
    await show_profile(cq)


# ---------- my files ----------

@router.callback_query(F.data == "menu:files")
async def cb_files(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    user_id = cq.from_user.id
    files = _files_for(user_id)
    if not files:
        await cq.message.answer(_("files_empty", lang), reply_markup=profile_kb(lang))
        await cq.answer()
        return
    await cq.message.delete()
    for p in files:
        kb = profile_kb(lang)
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_("btn_download", lang), callback_data=f"file:dl:{p.name}"),
             InlineKeyboardButton(text=_("btn_delete", lang), callback_data=f"file:del:{p.name}")],
            [InlineKeyboardButton(text=_("btn_push_gh", lang), callback_data=f"file:push:{p.name}")],
        ])
        try:
            await cq.message.answer_document(FSInputFile(str(p)), reply_markup=kb)
        except Exception:
            pass
    await cq.message.answer(_("main_menu", lang), reply_markup=main_menu_kb(lang))
    await cq.answer()


@router.callback_query(F.data.startswith("file:dl:"))
async def cb_file_dl(cq: CallbackQuery):
    name = cq.data.split(":", 2)[2]
    p = Path(config.SCRIPTS_DIR) / name
    if p.exists():
        await cq.message.answer_document(FSInputFile(str(p)))
    await cq.answer()


@router.callback_query(F.data.startswith("file:del:"))
async def cb_file_del(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    name = cq.data.split(":", 2)[2]
    if name.startswith(f"script_{cq.from_user.id}_"):
        p = Path(config.SCRIPTS_DIR) / name
        if p.exists():
            p.unlink()
        await cq.answer(_("file_deleted", lang), show_alert=True)
        try:
            await cq.message.delete()
        except Exception:
            pass


@router.callback_query(F.data.startswith("file:push:"))
async def cb_file_push(cq: CallbackQuery):
    lang = get_lang(cq.from_user.id)
    user_id = cq.from_user.id
    name = cq.data.split(":", 2)[2]
    gh = db.get_github(user_id)
    if not gh:
        from ..oauth_server import make_oauth_url
        url = make_oauth_url(user_id)
        await cq.message.answer(_("gh_connect_hint", lang, url=url))
        await cq.answer()
        return
    p = Path(config.SCRIPTS_DIR) / name
    if not p.exists():
        await cq.answer(_("file_not_found", lang), show_alert=True)
        return
    await cq.answer(_("gh_pushing", lang))
    msg = await cq.message.answer(_("gh_pushing", lang))
    try:
        code = p.read_text(encoding="utf-8")
        gh_user = gh["gh_username"]
        repo = "my-bot-scripts"
        headers = {"Authorization": f"token {gh['gh_token']}", "Accept": "application/vnd.github+json"}
        # check if repo exists
        r = requests.get(f"https://api.github.com/repos/{gh_user}/{repo}", headers=headers, timeout=20)
        if r.status_code == 404:
            rr = requests.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json={"name": repo, "description": "Bot scripts generated by AI assistant", "private": False},
                timeout=20,
            )
            if rr.status_code not in (200, 201):
                await msg.edit_text(_("gh_repo_fail", lang, detail=str(rr.status_code)))
                return
        # upload file
        url = f"https://api.github.com/repos/{gh_user}/{repo}/contents/{name}"
        existing = requests.get(url, headers=headers, timeout=20).json()
        sha = existing.get("sha")
        data = {"message": f"Add {name}", "content": base64.b64encode(code.encode()).decode()}
        if sha:
            data["sha"] = sha
        up = requests.put(url, headers=headers, json=data, timeout=20)
        if up.status_code in (200, 201):
            await msg.edit_text(
                _("gh_push_ok", lang, repo=f"{gh_user}/{repo}", file=name),
                disable_web_page_preview=True,
            )
        else:
            await msg.edit_text(_("gh_push_fail", lang, detail=up.text[:200]))
    except Exception as e:
        await msg.edit_text(_("gh_push_fail", lang, detail=str(e)[:200]))
