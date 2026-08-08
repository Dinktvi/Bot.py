"""Render cloud hosting via API.

Deploys a bot from a public GitHub repo using the Render REST API.
The user provides a Render API key (created in Render dashboard -> API Keys).
"""

import re
import time

import requests

API_BASE = "https://api.render.com/v1"

DEPLOY_POLL_SEC = 5
DEPLOY_TIMEOUT_SEC = 300


class HostError(Exception):
    pass


def _headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _check(resp):
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("message") or str(resp.json())
        except Exception:
            detail = resp.text[:300]
        raise HostError(f"Render API {resp.status_code}: {detail}")
    return resp


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (s or "bot")[:30]


def deploy(api_key, repo_url, bot_token, admin_id, name):
    """Create a Render web service from a public GitHub repo and deploy it."""
    repo_url = repo_url.strip().rstrip("/")
    if not re.match(r"^https://github\.com/.+/.+", repo_url):
        raise HostError("Only GitHub repo URLs are supported (https://github.com/owner/repo)")

    slug = _slug(name)
    payload = {
        "type": "web_service",
        "name": slug,
        "repo": repo_url,
        "branch": "main",
        "autoDeploy": "no",
        "plan": "free",
        "runtime": "python",
        "buildCommand": "pip install -r requirements.txt",
        "startCommand": "python3 -m bot.main",
        "envVars": [
            {"key": "BOT_TOKEN", "value": bot_token},
            {"key": "ADMIN_ID", "value": str(admin_id)},
        ],
    }

    resp = _check(requests.post(f"{API_BASE}/services", headers=_headers(api_key), json=payload, timeout=60))
    service = resp.json()
    service_id = service.get("id")
    service_url = f"https://{slug}.onrender.com"

    # trigger first deploy
    _check(requests.post(f"{API_BASE}/services/{service_id}/deploys", headers=_headers(api_key), json={}, timeout=60))

    return service_id, service_url


def wait_live(api_key, service_id, timeout=DEPLOY_TIMEOUT_SEC):
    """Poll deploys until one reaches 'live' status."""
    t0 = time.time()
    last_status = "created"
    while time.time() - t0 < timeout:
        resp = _check(requests.get(f"{API_BASE}/services/{service_id}/deploys?limit=1", headers=_headers(api_key), timeout=60))
        deploys = resp.json()
        if not deploys:
            time.sleep(DEPLOY_POLL_SEC)
            continue
        status = deploys[0].get("status", "created")
        if status != last_status:
            last_status = status
        if status == "live":
            return True
        if status in ("deploy_failed", "build_failed", "canceled"):
            raise HostError(f"Render deploy {status}")
        time.sleep(DEPLOY_POLL_SEC)
    raise HostError(f"Timeout waiting for deploy, last status: {last_status}")


def status(api_key, service_id):
    resp = _check(requests.get(f"{API_BASE}/services/{service_id}", headers=_headers(api_key), timeout=60))
    s = resp.json()
    susp = s.get("suspended") or "notSuspended"
    return "running" if susp == "notSuspended" else "stopped"


def restart(api_key, service_id):
    _check(requests.post(f"{API_BASE}/services/{service_id}/deploys", headers=_headers(api_key), json={}, timeout=60))
    return True


def logs(api_key, service_id, lines=40):
    resp = _check(requests.get(f"{API_BASE}/services/{service_id}/logs?limit={lines}", headers=_headers(api_key), timeout=60))
    data = resp.json()
    out = ""
    for item in data:
        out += f"{item.get('time', '')} {item.get('level', '')} {item.get('message', '')}\n"
    return out.strip() or "no logs yet"


def remove(api_key, service_id):
    _check(requests.delete(f"{API_BASE}/services/{service_id}", headers=_headers(api_key), timeout=60))
    return True
