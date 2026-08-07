import asyncio
import base64
import os
import sqlite3
import threading

import requests

from . import config

_REPO = os.getenv("DB_BACKUP_REPO", "Dinktvi/bot-data")
_PATH = "bot.db"
_lock = threading.Lock()
_sha = None
_last_push = 0.0


def _enabled():
    token = os.getenv("DB_BACKUP_TOKEN", "")
    return bool(token and _REPO)


def _headers():
    return {
        "Authorization": f"Bearer {os.getenv('DB_BACKUP_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
    }


def pull():
    if not _enabled():
        return
    global _sha
    try:
        r = requests.get(
            f"https://api.github.com/repos/{_REPO}/contents/{_PATH}",
            headers=_headers(),
            timeout=30,
        )
        if r.status_code != 200:
            return
        data = r.json()
        raw = base64.b64decode(data["content"])
        with _lock:
            os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
            tmp = config.DB_PATH + ".tmp"
            with open(tmp, "wb") as f:
                f.write(raw)
            os.replace(tmp, config.DB_PATH)
            _sha = data.get("sha")
        print("[db-backup] pulled bot.db from GitHub")
    except Exception as e:
        print(f"[db-backup] pull failed: {e}")


def push():
    if not _enabled():
        return
    global _sha
    with _lock:
        try:
            tmp = config.DB_PATH + ".tmp"
            src = sqlite3.connect(config.DB_PATH)
            dst = sqlite3.connect(tmp)
            with dst:
                src.backup(dst)
            dst.close()
            src.close()
            with open(tmp, "rb") as f:
                content = f.read()
            os.remove(tmp)
            if not _sha:
                try:
                    r = requests.get(
                        f"https://api.github.com/repos/{_REPO}/contents/{_PATH}",
                        headers=_headers(),
                        timeout=30,
                    )
                    if r.status_code == 200:
                        _sha = r.json().get("sha")
                except Exception:
                    pass
            body = {
                "message": "chore: sync bot.db",
                "content": base64.b64encode(content).decode(),
            }
            if _sha:
                body["sha"] = _sha
            r = requests.put(
                f"https://api.github.com/repos/{_REPO}/contents/{_PATH}",
                headers=_headers(),
                json=body,
                timeout=30,
            )
            if r.status_code in (200, 201):
                _sha = r.json().get("content", {}).get("sha")
                print(f"[db-backup] pushed bot.db ({len(content)} bytes)")
            else:
                print(f"[db-backup] push failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"[db-backup] push failed: {e}")


async def sync_loop():
    await asyncio.sleep(10)
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(push)
        except Exception as e:
            print(f"[db-backup] loop error: {e}")
