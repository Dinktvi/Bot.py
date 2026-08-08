import asyncio
import re

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import config, db
from ..i18n import _
from ..keyboards import cloud_kb, cloud_host_kb, cloud_list_kb, cloud_platform_kb, main_menu_kb
from ..services import cloud_host, cloud_render

router = Router()


class CloudStates(StatesGroup):
    platform = State()
    render_key = State()
    ssh_host = State()
    ssh_user = State()
    ssh_pass = State()
    repo_url = State()
    bot_token = State()


def get_lang(user_id):
    u = db.get_user(user_id)
    return u["lang"] if u else "ru"


def has_sub(user_id):
    return db.get_active_subscription(user_id) is not None


def _bot_name(host):
    return host["name"] or f"#{host['id']}"


def _do(host, op, *args):
    if host["platform"] == "render":
        return op(host["render_key"], host["service_id"], *args)
    return op(host["ssh_host"], host["ssh_user"], host["ssh_pass"], host["dir_name"], *args)


# ---------- entry ----------

async def show_cloud(cq: CallbackQuery, state: FSMContext, uid: int):
    lang = get_lang(uid)
    if not has_sub(uid):
        await cq.answer(_("cloud_need_sub", lang), show_alert=True)
        return
    await state.clear()
    hosts = db.get_cloud_hosts(uid)
    if not hosts:
        await cq.message.delete()
        await cq.message.answer(_("cloud_empty", lang), reply_markup=cloud_kb(lang))
    else:
        await cq.message.delete()
        await cq.message.answer(_("cloud_list", lang), reply_markup=cloud_list_kb(lang, hosts))
    await cq.answer()


@router.callback_query(F.data == "menu:cloud")
async def cb_cloud(cq: CallbackQuery, state: FSMContext):
    await show_cloud(cq, state, cq.from_user.id)


@router.callback_query(F.data == "cloud:add")
async def cb_cloud_add(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    if not has_sub(cq.from_user.id):
        await cq.answer(_("cloud_need_sub", lang), show_alert=True)
        return
    await state.set_state(CloudStates.platform)
    await cq.message.answer(_("cloud_ask_platform", lang), reply_markup=cloud_platform_kb(lang))
    await cq.answer()


@router.callback_query(F.data.startswith("cloud:plat:"))
async def cb_platform(cq: CallbackQuery, state: FSMContext):
    lang = get_lang(cq.from_user.id)
    plat = cq.data.split(":")[2]
    if plat not in ("ssh", "render"):
        return
    await state.update_data(platform=plat)
    if plat == "render":
        await state.set_state(CloudStates.render_key)
        await cq.message.answer(_("cloud_ask_render_key", lang))
    else:
        await state.set_state(CloudStates.ssh_host)
        await cq.message.answer(_("cloud_ask_host", lang))
    await cq.answer()


@router.message(CloudStates.render_key)
async def on_render_key(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    key = (message.text or "").strip()
    if len(key) < 10:
        await message.answer(_("cloud_ask_render_key", lang))
        return
    await state.update_data(render_key=key)
    await state.set_state(CloudStates.repo_url)
    await message.answer(_("cloud_ask_repo", lang))


# ---------- SSH flow ----------

@router.message(CloudStates.ssh_host)
async def on_host(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    host = (message.text or "").strip()
    if not re.match(r"^[\w.\-]+$", host):
        await message.answer(_("cloud_ask_host", lang))
        return
    await state.update_data(ssh_host=host)
    await state.set_state(CloudStates.ssh_user)
    await message.answer(_("cloud_ask_user", lang))


@router.message(CloudStates.ssh_user)
async def on_user(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    user = (message.text or "").strip()
    if not re.match(r"^[\w.\-]+$", user):
        await message.answer(_("cloud_ask_user", lang))
        return
    await state.update_data(ssh_user=user)
    await state.set_state(CloudStates.ssh_pass)
    await message.answer(_("cloud_ask_pass", lang))


@router.message(CloudStates.ssh_pass)
async def on_pass(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    pwd = message.text or ""
    if len(pwd) < 4:
        await message.answer(_("cloud_ask_pass", lang))
        return
    await state.update_data(ssh_pass=pwd)
    await state.set_state(CloudStates.repo_url)
    await message.answer(_("cloud_ask_repo", lang))


@router.message(CloudStates.repo_url)
async def on_repo(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    repo = (message.text or "").strip().rstrip("/")
    if not re.match(r"^https://github\.com/.+/.+", repo):
        await message.answer(_("cloud_ask_repo", lang))
        return
    await state.update_data(repo_url=repo)
    await state.set_state(CloudStates.bot_token)
    await message.answer(_("cloud_ask_token", lang))


@router.message(CloudStates.bot_token)
async def on_token(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    token = (message.text or "").strip()
    if not token or ":" not in token:
        await message.answer(_("cloud_ask_token", lang))
        return
    data = await state.get_data()
    name = (data.get("repo_url") or "").split("/")[-1].replace(".git", "") or "bot"
    if not data.get("repo_url"):
        name = "bot"

    busy = await message.answer(_("cloud_deploying", lang))
    hid = None
    extra_txt = ""
    try:
        if data["platform"] == "render":
            hid = db.add_cloud_host(
                message.from_user.id, name, platform="render",
                render_key=data["render_key"], repo_url=data["repo_url"], bot_token=token,
            )
            host_row = db.get_cloud_host(hid)
            service_id, service_url = await asyncio.to_thread(
                cloud_render.deploy,
                host_row["render_key"], host_row["repo_url"], host_row["bot_token"],
                message.from_user.id, host_row["name"],
            )
            db.update_cloud_service(hid, service_id=service_id, service_url=service_url)
            await busy.edit_text(_("cloud_render_building", lang, name=name))
            ok = await asyncio.to_thread(cloud_render.wait_live, host_row["render_key"], service_id)
            if not ok:
                raise cloud_render.HostError("deploy not live")
            extra_txt = _("cloud_render_url", lang, url=service_url)
        else:
            hid = db.add_cloud_host(
                message.from_user.id, name, platform="ssh",
                ssh_host=data["ssh_host"], ssh_user=data["ssh_user"], ssh_pass=data["ssh_pass"],
                repo_url=data["repo_url"], bot_token=token,
            )
            host_row = db.get_cloud_host(hid)
            ok = await asyncio.to_thread(
                cloud_host.deploy,
                host_row["ssh_host"], host_row["ssh_user"], host_row["ssh_pass"],
                host_row["repo_url"], host_row["bot_token"], host_row["dir_name"],
                host_row["name"], message.from_user.id,
            )
            if not ok:
                raise cloud_host.HostError("deploy returned false")
        await busy.edit_text(_("cloud_deploy_ok", lang, name=name, extra=extra_txt))
        await message.answer(_("cloud_manage_hint", lang), reply_markup=cloud_host_kb(lang, hid))
    except cloud_host.HostError as e:
        if hid:
            db.delete_cloud_host(hid)
        await busy.edit_text(_("cloud_deploy_fail", lang, detail=str(e)))
    except cloud_render.HostError as e:
        if hid:
            db.delete_cloud_host(hid)
        await busy.edit_text(_("cloud_deploy_fail", lang, detail=str(e)))
    except Exception as e:
        if hid:
            db.delete_cloud_host(hid)
        await busy.edit_text(_("cloud_deploy_fail", lang, detail=str(e)[:300]))
    await state.clear()


# ---------- management ----------

def _get_host(cq: CallbackQuery):
    parts = cq.data.split(":")
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    host = db.get_cloud_host(int(parts[1]))
    if not host or host["user_id"] != cq.from_user.id:
        return None
    return host


def _manage_kb(host):
    return cloud_host_kb(get_lang(host["user_id"]), host["id"])


@router.callback_query(F.data.startswith("cloud:h:"))
async def cb_host(cq: CallbackQuery):
    host = _get_host(cq)
    lang = get_lang(cq.from_user.id)
    if not host:
        await cq.answer(_("cloud_not_found", lang), show_alert=True)
        return
    plat = _("cloud_plat_render", lang) if host["platform"] == "render" else _("cloud_plat_ssh", lang)
    extra = ""
    if host["platform"] == "render" and host["service_url"]:
        extra = f"\n🔗 {host['service_url']}"
    await cq.message.delete()
    await cq.message.answer(
        _("cloud_host_info", lang, name=_bot_name(host), repo=host["repo_url"], plat=plat, extra=extra),
        reply_markup=_manage_kb(host),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("cloud:status:"))
async def cb_status(cq: CallbackQuery):
    host = _get_host(cq)
    lang = get_lang(cq.from_user.id)
    if not host:
        await cq.answer(_("cloud_not_found", lang), show_alert=True)
        return
    busy = await cq.message.answer(_("cloud_checking", lang))
    try:
        st = await asyncio.to_thread(_do, host, cloud_host.status if host["platform"] == "ssh" else cloud_render.status)
        state_txt = _("cloud_running", lang) if st == "running" else _("cloud_stopped", lang)
        await busy.edit_text(_("cloud_status", lang, name=_bot_name(host), state=state_txt))
    except (cloud_host.HostError, cloud_render.HostError) as e:
        await busy.edit_text(_("cloud_op_fail", lang, detail=str(e)))
    await cq.answer()


@router.callback_query(F.data.startswith("cloud:restart:"))
async def cb_restart(cq: CallbackQuery):
    host = _get_host(cq)
    lang = get_lang(cq.from_user.id)
    if not host:
        await cq.answer(_("cloud_not_found", lang), show_alert=True)
        return
    busy = await cq.message.answer(_("cloud_restarting", lang))
    try:
        await asyncio.to_thread(_do, host, cloud_host.restart if host["platform"] == "ssh" else cloud_render.restart)
        await busy.edit_text(_("cloud_restart_ok", lang, name=_bot_name(host)))
    except (cloud_host.HostError, cloud_render.HostError) as e:
        await busy.edit_text(_("cloud_op_fail", lang, detail=str(e)))
    await cq.answer()


@router.callback_query(F.data.startswith("cloud:logs:"))
async def cb_logs(cq: CallbackQuery):
    host = _get_host(cq)
    lang = get_lang(cq.from_user.id)
    if not host:
        await cq.answer(_("cloud_not_found", lang), show_alert=True)
        return
    busy = await cq.message.answer(_("cloud_loading_logs", lang))
    try:
        out = await asyncio.to_thread(_do, host, cloud_host.logs if host["platform"] == "ssh" else cloud_render.logs, 40)
        text = out.strip() or "—"
        await busy.edit_text(_("cloud_logs", lang, name=_bot_name(host), logs=text[:3000]))
    except (cloud_host.HostError, cloud_render.HostError) as e:
        await busy.edit_text(_("cloud_op_fail", lang, detail=str(e)))
    await cq.answer()


@router.callback_query(F.data.startswith("cloud:remove:"))
async def cb_remove(cq: CallbackQuery):
    host = _get_host(cq)
    lang = get_lang(cq.from_user.id)
    if not host:
        await cq.answer(_("cloud_not_found", lang), show_alert=True)
        return
    busy = await cq.message.answer(_("cloud_removing", lang))
    try:
        await asyncio.to_thread(_do, host, cloud_host.remove if host["platform"] == "ssh" else cloud_render.remove)
    except (cloud_host.HostError, cloud_render.HostError):
        pass
    db.delete_cloud_host(host["id"])
    await busy.edit_text(_("cloud_removed", lang, name=_bot_name(host)))
    hosts = db.get_cloud_hosts(cq.from_user.id)
    await cq.message.answer(
        _("cloud_list", lang) if hosts else _("cloud_empty", lang),
        reply_markup=cloud_list_kb(lang, hosts) if hosts else cloud_kb(lang),
    )
    await cq.answer()
