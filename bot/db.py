import sqlite3
import threading
from datetime import datetime, timedelta

from . import config

_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _lock:
        conn = get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                lang TEXT DEFAULT 'ru',
                created_at TEXT,
                is_banned INTEGER DEFAULT 0,
                ai_requests INTEGER DEFAULT 0,
                ai_provider TEXT DEFAULT '',
                bonus_claimed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                plan TEXT,
                period TEXT,
                months INTEGER,
                price INTEGER,
                promo TEXT,
                purchased_at TEXT,
                expires_at TEXT
            );

            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount INTEGER,
                max_uses INTEGER DEFAULT 0,
                uses INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS auction_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                start_price INTEGER,
                current_price INTEGER,
                highest_bidder INTEGER,
                created_at TEXT,
                ends_at TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS sponsors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                link TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS admin_replies (
                message_id INTEGER PRIMARY KEY,
                user_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS github_accounts (
                user_id INTEGER PRIMARY KEY,
                gh_username TEXT,
                gh_token TEXT,
                connected_at TEXT
            );
            """
        )
        for col, ddl in (
            ("ai_requests", "ai_requests INTEGER DEFAULT 0"),
            ("bonus_claimed", "bonus_claimed INTEGER DEFAULT 0"),
            ("ai_provider", "ai_provider TEXT DEFAULT ''"),
        ):
            cols = [r[1] for r in conn.execute("PRAGMA table_info(users)")]
            if col not in cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {ddl}")
        conn.commit()
        conn.close()


# ---------- users ----------

def get_user(user_id):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        return row


def get_user_by_username(username):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        return row


def upsert_user(user_id, username, first_name, lang=None):
    with _lock:
        conn = get_conn()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO users (user_id, username, first_name, lang, created_at) VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (user_id, username, first_name, lang or "ru", now),
        )
        conn.commit()
        conn.close()


def set_lang(user_id, lang):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        conn.commit()
        conn.close()


def get_ai_provider(user_id):
    u = get_user(user_id)
    if not u or not u["ai_provider"]:
        return config.DEFAULT_AI_PROVIDER
    return u["ai_provider"]


def set_ai_provider(user_id, provider):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE users SET ai_provider=? WHERE user_id=?", (provider, user_id))
        conn.commit()
        conn.close()


def count_users():
    with _lock:
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        return n


def all_user_ids():
    with _lock:
        conn = get_conn()
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        return [r["user_id"] for r in rows]


# ---------- subscriptions ----------

def get_active_subscription(user_id):
    with _lock:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id=? AND expires_at > ? ORDER BY expires_at DESC LIMIT 1",
            (user_id, datetime.now().isoformat()),
        ).fetchone()
        conn.close()
        return row


def add_subscription(user_id, plan, period, months, price, promo=None):
    with _lock:
        conn = get_conn()
        now = datetime.now()
        until = now + timedelta(days=30 * months)
        conn.execute(
            "INSERT INTO subscriptions (user_id, plan, period, months, price, promo, purchased_at, expires_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, plan, period, months, price, promo, now.isoformat(), until.isoformat()),
        )
        conn.commit()
        conn.close()
        return until


def count_subs():
    with _lock:
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
        conn.close()
        return n


def revenue():
    with _lock:
        conn = get_conn()
        n = conn.execute("SELECT COALESCE(SUM(price),0) FROM subscriptions").fetchone()[0]
        conn.close()
        return n


# ---------- bonus (subscription gift) ----------

def get_ai_requests(user_id):
    row = get_user(user_id)
    return row["ai_requests"] if row else 0


def use_ai_request(user_id):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE users SET ai_requests = MAX(ai_requests - 1, 0) WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()


def claim_bonus(user_id):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT bonus_claimed FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row or row["bonus_claimed"]:
            conn.close()
            return False
        conn.execute(
            "UPDATE users SET bonus_claimed=1, ai_requests = ai_requests + 7 WHERE user_id=?",
            (user_id,),
        )
        conn.commit()
        conn.close()
        return True


def grant_free_week(user_id):
    with _lock:
        conn = get_conn()
        now = datetime.now()
        row = conn.execute(
            "SELECT expires_at FROM subscriptions WHERE user_id=? ORDER BY expires_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row and row["expires_at"] > now.isoformat():
            base = datetime.fromisoformat(row["expires_at"])
        else:
            base = now
        until = base + timedelta(days=7)
        conn.execute(
            "INSERT INTO subscriptions (user_id, plan, period, months, price, promo, purchased_at, expires_at) "
            "VALUES (?, 'standard', 'bonus', 0, 0, 'bonus', ?, ?)",
            (user_id, now.isoformat(), until.isoformat()),
        )
        conn.commit()
        conn.close()
        return until


# ---------- promo codes ----------

def add_promo(code, discount, max_uses):
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO promo_codes (code, discount, max_uses, uses, active) VALUES (?,?,?,0,1) "
            "ON CONFLICT(code) DO UPDATE SET discount=excluded.discount, max_uses=excluded.max_uses, active=1",
            (code.upper(), discount, max_uses),
        )
        conn.commit()
        conn.close()


def get_promo(code):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM promo_codes WHERE code=? AND active=1", (code.upper(),)).fetchone()
        conn.close()
        return row


def use_promo(code):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM promo_codes WHERE code=? AND active=1", (code.upper(),)).fetchone()
        if not row:
            conn.close()
            return None
        if row["max_uses"] > 0 and row["uses"] >= row["max_uses"]:
            conn.close()
            return "used"
        conn.execute("UPDATE promo_codes SET uses=uses+1 WHERE code=?", (code.upper(),))
        conn.commit()
        conn.close()
        return row


# ---------- settings / global discount ----------

def set_setting(key, value):
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        conn.commit()
        conn.close()


def get_setting(key, default=None):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
        if row:
            return row["value"]
        return default


def global_discount():
    try:
        return int(get_setting("global_discount", "0"))
    except (TypeError, ValueError):
        return 0


# ---------- auction ----------

def add_auction(title, desc, start_price, hours=24):
    with _lock:
        conn = get_conn()
        now = datetime.now()
        ends = now + timedelta(hours=hours)
        conn.execute(
            "INSERT INTO auction_items (title, description, start_price, current_price, created_at, ends_at, active) "
            "VALUES (?,?,?,?,?,?,1)",
            (title, desc, start_price, start_price, now.isoformat(), ends.isoformat()),
        )
        conn.commit()
        conn.close()


def active_auctions():
    with _lock:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM auction_items WHERE active=1 AND ends_at > ? ORDER BY ends_at ASC",
            (datetime.now().isoformat(),),
        ).fetchall()
        conn.close()
        return rows


def get_auction(lot_id):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM auction_items WHERE id=?", (lot_id,)).fetchone()
        conn.close()
        return row


def place_bid(lot_id, user_id, amount):
    with _lock:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM auction_items WHERE id=? AND active=1 AND ends_at > ?",
            (lot_id, datetime.now().isoformat()),
        ).fetchone()
        if not row:
            conn.close()
            return "notfound"
        if amount <= row["current_price"]:
            conn.close()
            return "low"
        conn.execute(
            "UPDATE auction_items SET current_price=?, highest_bidder=? WHERE id=?",
            (amount, user_id, lot_id),
        )
        conn.commit()
        conn.close()
        return "ok"


def finish_auction(lot_id):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE auction_items SET active=0 WHERE id=?", (lot_id,))
        conn.commit()
        conn.close()


def close_expired_auctions():
    with _lock:
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM auction_items WHERE active=1 AND ends_at <= ?",
            (datetime.now().isoformat(),),
        ).fetchall()
        for row in rows:
            conn.execute("UPDATE auction_items SET active=0 WHERE id=?", (row["id"],))
        conn.commit()
        conn.close()
        return rows


def del_auction(lot_id):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE auction_items SET active=0 WHERE id=?", (lot_id,))
        conn.commit()
        conn.close()


def count_active_lots():
    with _lock:
        conn = get_conn()
        n = conn.execute(
            "SELECT COUNT(*) FROM auction_items WHERE active=1 AND ends_at > ?",
            (datetime.now().isoformat(),),
        ).fetchone()[0]
        conn.close()
        return n


# ---------- sponsors ----------

def add_sponsor(name, link):
    with _lock:
        conn = get_conn()
        conn.execute("INSERT INTO sponsors (name, link, active) VALUES (?,?,1)", (name, link))
        conn.commit()
        conn.close()


def active_sponsors():
    with _lock:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM sponsors WHERE active=1").fetchall()
        conn.close()
        return rows


# ---------- tickets ----------

def create_ticket(user_id):
    with _lock:
        conn = get_conn()
        conn.execute("INSERT INTO tickets (user_id, status, created_at) VALUES (?, 'open', ?)",
                     (user_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()


def open_tickets_count():
    with _lock:
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='open'").fetchone()[0]
        conn.close()
        return n


def close_ticket_for(user_id):
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE tickets SET status='closed' WHERE user_id=? AND status='open'", (user_id,))
        conn.commit()
        conn.close()


def has_open_ticket(user_id):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT id FROM tickets WHERE user_id=? AND status='open' LIMIT 1", (user_id,)).fetchone()
        conn.close()
        return row is not None


# ---------- admin reply tracking ----------

def track_admin_message(message_id, user_id):
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO admin_replies (message_id, user_id) VALUES (?,?) "
            "ON CONFLICT(message_id) DO UPDATE SET user_id=excluded.user_id",
            (message_id, user_id),
        )
        conn.commit()
        conn.close()


def get_admin_reply_target(message_id):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT user_id FROM admin_replies WHERE message_id=?", (message_id,)).fetchone()
        conn.close()
        return row["user_id"] if row else None


# ---------- chat history (AI memory) ----------

def add_history(user_id, role, content):
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO chat_history (user_id, role, content, created_at) VALUES (?,?,?,?)",
            (user_id, role, content, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()


def get_history(user_id, limit=20):
    with _lock:
        conn = get_conn()
        rows = conn.execute(
            "SELECT role, content FROM chat_history WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


# ---------- GitHub OAuth ----------

def save_github(user_id, gh_username, gh_token):
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO github_accounts (user_id, gh_username, gh_token, connected_at) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET gh_username=excluded.gh_username, gh_token=excluded.gh_token",
            (user_id, gh_username, gh_token, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()


def get_github(user_id):
    with _lock:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM github_accounts WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        return row


def disconnect_github(user_id):
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM github_accounts WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
