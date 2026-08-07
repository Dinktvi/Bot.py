"""Cloud hosting via SSH: deploy a bot from a GitHub repo and keep it alive 24/7.

Deploys by cloning a public GitHub repo onto a remote server (e.g. serv00.com),
installs deps, writes a minimal .env, starts the bot with nohup and installs a
cron entry that auto-restarts it if it dies. The bot on the server is the user's
own project, deployed from GitHub only.
"""

import re
import time

import paramiko

DEPLOY_TIMEOUT = 180
RUN_TIMEOUT = 60


class HostError(Exception):
    pass


def _connect(host, user, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=user,
            password=password,
            port=22,
            timeout=25,
            banner_timeout=25,
            auth_timeout=25,
        )
    except Exception as e:
        raise HostError(f"SSH connect failed: {e}")
    return client


def _exec(client, cmd, timeout=RUN_TIMEOUT, stream=False):
    """Run a command; return (stdout, stderr). If stream, print output lines."""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    if stream:
        out = ""
        for line in stdout:
            print(line.rstrip())
            out += line
        err = stderr.read().decode("utf-8", "replace")
        return out, err
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return out, err


def _safe_quote(s):
    return s.replace("'", "'\\''")


def deploy(host, user, password, repo_url, bot_token, dir_name, name, admin_id):
    """Clone repo_url onto the server, install deps, start the bot, set cron."""
    repo_url = repo_url.strip().rstrip("/")
    if not re.match(r"^https://github\.com/.+/.+", repo_url):
        raise HostError("Only GitHub repo URLs are supported (https://github.com/owner/repo)")

    client = _connect(host, user, password)
    try:
        _exec(client, f"mkdir -p ~/bots/{_safe_quote(dir_name)}", 60)

        out, err = _exec(client, f"ls ~/bots/{_safe_quote(dir_name)}/.git >/dev/null 2>&1 && echo yes || echo no", 30)
        if out.strip() == "yes":
            _exec(client, f"cd ~/bots/{_safe_quote(dir_name)} && git pull --ff-only", 120)
        else:
            _exec(client, f"cd ~/bots && git clone --depth 1 {_safe_quote(repo_url)} {_safe_quote(dir_name)}", DEPLOY_TIMEOUT)

        py = f"~/bots/{dir_name}/venv/bin/python3"
        _exec(client, f"cd ~/bots/{dir_name} && python3 -m venv venv", 120)
        _exec(client, f"cd ~/bots/{dir_name} && {py} -m ensurepip --upgrade 2>/dev/null; true", 60)
        _exec(client, f"cd ~/bots/{dir_name} && {py} -m pip install -q --upgrade pip", 120)
        _exec(client, f"cd ~/bots/{dir_name} && {py} -m pip install -q -r requirements.txt", DEPLOY_TIMEOUT)

        env_file = (
            f"BOT_TOKEN={bot_token}\n"
            f"ADMIN_ID={admin_id}\n"
        )
        _exec(client, f"cd ~/bots/{dir_name} && cat > .env <<'BOTEOF'\n{env_file}BOTEOF", 30)

        _exec(client, f"cd ~/bots/{dir_name} && mkdir -p data", 30)

        start_cmd = (
            f"cd ~/bots/{dir_name} && "
            f"if [ -f bot.pid ]; then kill $(cat bot.pid) 2>/dev/null; sleep 2; fi; "
            f"nohup {py} -m bot.main > bot.log 2>&1 & echo $! > bot.pid"
        )
        _exec(client, start_cmd, 60)

        cron = (
            f"( crontab -l 2>/dev/null | grep -v '{dir_name}'; "
            f"echo '* * * * * cd ~/bots/{dir_name} && if ! pgrep -f bot.main >/dev/null; "
            f"then nohup {py} -m bot.main >> bot.log 2>&1 & echo $! > bot.pid; fi' ) | crontab -"
        )
        _exec(client, cron, 60)
        return True
    finally:
        client.close()


def status(host, user, password, dir_name):
    client = _connect(host, user, password)
    try:
        out, _ = _exec(client, f"cd ~/bots/{dir_name} && if [ -f bot.pid ] && kill -0 $(cat bot.pid) 2>/dev/null; then echo running; else echo stopped; fi", 30)
        return out.strip()
    finally:
        client.close()


def restart(host, user, password, dir_name):
    client = _connect(host, user, password)
    try:
        py = f"~/bots/{dir_name}/venv/bin/python3"
        _exec(client, f"cd ~/bots/{dir_name} && if [ -f bot.pid ]; then kill $(cat bot.pid) 2>/dev/null; sleep 2; fi; nohup {py} -m bot.main > bot.log 2>&1 & echo $! > bot.pid", 60)
        return True
    finally:
        client.close()


def logs(host, user, password, dir_name, lines=40):
    client = _connect(host, user, password)
    try:
        out, _ = _exec(client, f"cd ~/bots/{dir_name} && tail -n {lines} bot.log 2>/dev/null || echo 'no log yet'", 30)
        return out
    finally:
        client.close()


def remove(host, user, password, dir_name):
    """Stop the bot and remove its cron entry. Leaves files on disk."""
    client = _connect(host, user, password)
    try:
        _exec(client, f"cd ~/bots/{dir_name} && if [ -f bot.pid ]; then kill $(cat bot.pid) 2>/dev/null; fi; true", 30)
        _exec(client, f"( crontab -l 2>/dev/null | grep -v '{dir_name}' ) | crontab -", 30)
        return True
    finally:
        client.close()
