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
CACHE_TTL    = 10            # days

# Dashboard URL (sizning server IP manziliz)
DASHBOARD_URL = "http://45.138.159.2:5000"

API_ID       = 34770679             # ← your integer api_id
API_HASH     = "6a3258244408960dd948f565bbb1416f"            # ← your api_hash string
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
                message_id      INTEGER,
                chat_id         INTEGER,
                user_id         INTEGER,
                sender_name     TEXT,
                username        TEXT,
                text            TEXT,
                media_type      TEXT,
                media_path      TEXT,
                is_deleted      INTEGER DEFAULT 0,
                is_edited       INTEGER DEFAULT 0,
                original_text   TEXT,
                timestamp       TEXT,
                expires_at      TEXT,
                business_owner_id INTEGER,
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
            "ALTER TABLE business_cache ADD COLUMN business_owner_id INTEGER",
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
    business_owner_id: int | None = None,
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
                timestamp, expires_at, business_owner_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id, chat_id, user_id, sender_name, username or "",
                text or "", media_type, media_path,
                int(existing is not None), original,
                datetime.utcnow().isoformat(), _expires_at(), business_owner_id,
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
    # Disabled - expired messages are kept and shown as "Expired"
    return 0


async def purge_loop() -> None:
    # Disabled - messages are not auto-deleted, just marked as expired
    while True:
        await asyncio.sleep(86400)  # Sleep 24 hours


# ─────────────────────────────────────────────────────────────
#  WEB DASHBOARD
# ─────────────────────────────────────────────────────────────

flask_app = Flask(__name__)

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TG Business Logger</title>
<style>
:root{
  --bg:#0d0f1a;--surf:#141726;--card:#1c2035;--border:#252a45;
  --accent:#5b8dee;--accent2:#7c5cfc;--green:#3ecf8e;--red:#f66;
  --yellow:#f5a623;--text:#e2e8f0;--muted:#6b7280;--dim:#9ca3af;
  --del-bg:#2a1414;--edit-bg:#1a2330;
}
html,body{height:100%;margin:0;padding:0;overflow:hidden}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:auto}

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

/* ── 3-panel layout ── */
.panels{display:flex;flex:1;overflow:hidden;min-height:0;height:100%}
.panel{display:flex;flex-direction:column;border-right:1px solid var(--border);min-width:0;min-height:0;height:100%;overflow:hidden}
.panel:last-child{border-right:none}
#p-chats{width:320px;flex-shrink:0}
#p-msgs{flex:1}

/* ── panel header ── */
.ph{padding:10px 14px;background:var(--surf);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;min-height:44px}
.ph-title{font-size:.82rem;font-weight:600;color:var(--dim)}
.ph-actions{display:flex;gap:6px;align-items:center}
.del-btn{background:#4a1a1a;border:1px solid #7a2020;color:var(--red);border-radius:6px;padding:3px 10px;font-size:.72rem;cursor:pointer;display:none}
.del-btn:hover{background:#6a2020}
.del-btn.show{display:block}
.search{background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:4px 10px;font-size:.78rem;width:100%;outline:none}
.search:focus{border-color:var(--accent)}
.ps{padding:8px 10px;flex-shrink:0;min-height:50px}

/* ── panel body ── */
.pb{flex:1;overflow-y:auto;overflow-x:hidden;padding:6px;min-height:0;height:100%}
.pb::-webkit-scrollbar{width:6px}
.pb::-webkit-scrollbar-track{background:var(--surf)}
.pb::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.pb::-webkit-scrollbar-thumb:hover{background:var(--accent)}

/* ── chat items ── */
.chat-item{border-radius:8px;padding:10px 12px;cursor:pointer;display:flex;align-items:center;gap:10px;margin-bottom:3px;transition:.15s;user-select:none;position:relative}
.chat-item:hover{background:var(--card)}
.chat-item.active{background:var(--card);border-left:3px solid var(--accent)}
.avatar{width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;flex-shrink:0}
.chat-body{flex:1;min-width:0}
.chat-name{font-size:.88rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}
.chat-preview{font-size:.75rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chat-meta{display:flex;flex-direction:column;align-items:flex-end;gap:4px}
.chat-time{font-size:.7rem;color:var(--muted)}
.chat-badge{font-size:.68rem;background:var(--accent);border-radius:10px;padding:2px 6px;color:#fff;font-weight:600}
.chat-badge.red{background:var(--red)}
.chat-badge.yellow{background:var(--yellow)}

/* ── empty states ── */
.empty{text-align:center;padding:40px 16px;color:var(--muted);font-size:.83rem}
.empty-icon{font-size:2rem;margin-bottom:8px}

/* ── messages panel ── */
.msg-list{padding:8px}
.msg-wrap{display:flex;gap:6px;align-items:flex-start;margin-bottom:6px}
.msg-wrap input[type=checkbox]{margin-top:5px;flex-shrink:0;accent-color:var(--accent);width:14px;height:14px;cursor:pointer}
.msg{flex:1;border-radius:10px;padding:9px 12px;border-left:3px solid var(--border);min-width:0}
.msg.normal{background:var(--card);border-left-color:var(--accent)}
.msg.deleted{background:var(--del-bg);border-left-color:var(--red)}
.msg.edited{background:var(--edit-bg);border-left-color:var(--yellow)}
.msg.media-only{border-left-color:var(--green)}
.msg.expired{background:#1a1a2a;border-left-color:#666;opacity:0.7}
.msg-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:5px}
.msender{font-weight:600;color:var(--accent);font-size:.8rem}
.muname{color:var(--muted);font-size:.75rem}
.muid{color:var(--muted);font-size:.72rem;background:var(--border);border-radius:3px;padding:1px 5px}
.mts{color:var(--muted);font-size:.72rem;margin-left:auto}
.badge{font-size:.62rem;font-weight:700;padding:1px 6px;border-radius:10px;text-transform:uppercase}
.badge.del{background:#5c1414;color:#ff8080}
.badge.edit{background:#1a3020;color:#6ddb9a}
.badge.med{background:#1a2a3a;color:var(--accent)}
.msg-text{font-size:.85rem;line-height:1.5;word-break:break-word;color:var(--text)}
.msg-text.dim{color:var(--muted);font-style:italic}
.original{font-size:.76rem;color:var(--muted);margin-top:3px}
.original b{color:#9ca3af}
.expires{font-size:.68rem;color:var(--muted);margin-top:3px}
.expires.soon{color:var(--yellow)}

/* ── media ── */
.media-wrap{margin-top:7px}
.media-wrap img{max-width:260px;max-height:260px;border-radius:8px;cursor:pointer;display:block}
.media-wrap video{max-width:260px;max-height:260px;border-radius:8px;display:block}
.media-wrap audio{width:100%;max-width:300px;height:36px;margin-top:2px}
.sticker-img{max-width:120px;max-height:120px}
.expired-media{background:#2a2a3a;border:1px dashed #666;border-radius:8px;padding:20px;text-align:center;color:#999;font-size:.85rem;font-style:italic}

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
    <span>TTL: 10 days</span>
  </div>
</header>

<div class="gstats">
  <div class="gstat">Chats <span class="sv" id="gs-chats">—</span></div>
  <div class="gstat">Messages <span class="sv" id="gs-msgs">—</span></div>
  <div class="gstat red">Deleted <span class="sv" id="gs-del">—</span></div>
  <div class="gstat yellow">Edited <span class="sv" id="gs-edit">—</span></div>
  <div class="gstat green">Media files <span class="sv" id="gs-media">—</span></div>
</div>

<div class="panels">
  <!-- Panel 1: Chats List -->
  <div class="panel" id="p-chats">
    <div class="ph">
      <span class="ph-title">� CHATS</span>
      <div class="ph-actions">
        <button class="del-btn" id="del-chats-btn" onclick="deleteSelected('chats')">🗑 Delete</button>
      </div>
    </div>
    <div class="ps"><input class="search" id="s-chats" placeholder="Search chats…" oninput="renderChats()"></div>
    <div class="pb" id="list-chats" "><div class="empty"><div class="empty-icon">💬</div>Loading…</div></div>
  </div>

  <!-- Panel 2: Messages -->
  <div class="panel" id="p-msgs">
    <div class="ph">
      <span class="ph-title">� MESSAGES</span>
      <div class="ph-actions">
        <button class="del-btn" id="del-msgs-btn" onclick="deleteSelected('messages')">🗑 Delete</button>
        <button class="del-btn show" id="filter-btn" style="background:#1a2a1a;border-color:#2a5a2a;color:var(--green)" onclick="cycleFilter()">Filter: All</button>
      </div>
    </div>
    <div class="ps"><input class="search" id="s-msgs" placeholder="Search messages…" oninput="renderMessages()"></div>
    <div class="pb" id="list-msgs"><div class="empty"><div class="empty-icon">←</div>Select a chat</div></div>
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
let refreshInterval = null;

function checkPassword() {
  const input = document.getElementById('pwd-input');
  const error = document.getElementById('pwd-error');
  if (input.value === CORRECT_PASSWORD) {
    isUnlocked = true;
    document.getElementById('password-overlay').classList.add('hidden');
    document.getElementById('main-content').classList.remove('blur-content');
    fetchData();
    startAutoRefresh();
  } else {
    error.textContent = '❌ Incorrect password';
    input.value = '';
    input.focus();
  }
}

// Auto-refresh control
function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    if (!isMediaPlaying()) {
      fetchData();
    }
  }, 5000);
}

function isMediaPlaying() {
  // Check if any video or audio is playing
  const videos = document.querySelectorAll('video');
  const audios = document.querySelectorAll('audio');
  
  for (let v of videos) {
    if (!v.paused && !v.ended) return true;
  }
  for (let a of audios) {
    if (!a.paused && !a.ended) return true;
  }
  return false;
}

// Focus password input on load
window.addEventListener('load', () => {
  document.getElementById('pwd-input').focus();
});

// ── State ─────────────────────────────────────────────────
let allData         = { chats:[], stats:{} };
let selectedChatId  = null;
let msgFilter       = 'all';   // all | deleted | edited | media

// Persistent selection sets (survive auto-refresh)
const selChats = new Set();
const selMsgs  = new Set();   // keys: "msgId_chatId"

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

// ── Media rendering ───────────────────────────────────────
function mediaHtml(m) {
  if (!m.media_type || !m.media_path) return '';
  
  // Check if media is expired
  const isExpired = daysLeft(m.expires_at) < 0;
  
  if (isExpired) {
    return `<div class="media-wrap"><div class="expired-media">🕐 Expired ${m.media_type}</div></div>`;
  }
  
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

// ── Render Chats ──────────────────────────────────────────
function renderChats() {
  const wrap = document.getElementById('list-chats');
  const q = document.getElementById('s-chats').value.toLowerCase();
  
  let chats = allData.chats || [];
  if (q) chats = chats.filter(c =>
    (c.contact_name + c.contact_username + String(c.chat_id)).toLowerCase().includes(q)
  );
  
  if (!chats.length) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">💬</div>No chats found</div>';
    return;
  }

  wrap.innerHTML = chats.map(chat => {
    const av = initials(chat.contact_name || `Chat ${chat.chat_id}`);
    const active = selectedChatId === chat.chat_id ? 'active' : '';
    const sel = selChats.has(chat.chat_id) ? 'checked' : '';
    const delBadge = chat.deleted_count > 0 ? `<span class="chat-badge red">${chat.deleted_count}</span>` : '';
    const editBadge = chat.edited_count > 0 ? `<span class="chat-badge yellow">${chat.edited_count}</span>` : '';
    const lastText = chat.last_text && chat.last_text !== '[non-text content]'
      ? (chat.last_text.length > 35 ? chat.last_text.slice(0,35)+'…' : chat.last_text)
      : (chat.last_media_type ? `[${chat.last_media_type}]` : '[no content]');
    const username = chat.contact_username ? `@${esc(chat.contact_username)}` : '';
    
    return `
      <div class="chat-item ${active}" onclick="selectChat(${chat.chat_id})">
        <div class="avatar">${av}</div>
        <div class="chat-body">
          <div class="chat-name">${esc(chat.contact_name || `Chat ${chat.chat_id}`)}</div>
          <div class="chat-preview">${esc(lastText)}</div>
        </div>
        <div class="chat-meta">
          <div class="chat-time">${timeAgo(chat.last_ts)}</div>
          ${delBadge}${editBadge}
        </div>
      </div>`;
  }).join('');
}

function selectChat(chatId) {
  selectedChatId = chatId;
  renderChats();  // Re-render to show active state
  renderMessages();
}

// ── Render Messages ───────────────────────────────────────
function renderMessages() {
  const wrap = document.getElementById('list-msgs');
  if (!selectedChatId) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">←</div>Select a chat</div>';
    return;
  }
  
  const chat = (allData.chats||[]).find(c => c.chat_id === selectedChatId);
  if (!chat) return;

  let msgs = chat.messages || [];
  const q  = document.getElementById('s-msgs').value.toLowerCase();

  if (msgFilter === 'deleted') msgs = msgs.filter(m => m.is_deleted);
  if (msgFilter === 'edited')  msgs = msgs.filter(m => m.is_edited);
  if (msgFilter === 'media')   msgs = msgs.filter(m => m.media_type);
  if (q) msgs = msgs.filter(m =>
    (m.text+m.original_text+m.sender_name+m.username).toLowerCase().includes(q)
  );

  if (!msgs.length) {
    wrap.innerHTML = '<div class="empty"><div class="empty-icon">🔍</div>No messages</div>';
    return;
  }

  wrap.innerHTML = '<div class="msg-list">' + msgs.map(m => {
    const key     = `${m.message_id}_${m.chat_id}`;
    const sel     = selMsgs.has(key) ? 'checked' : '';
    const dl      = daysLeft(m.expires_at);
    const isExpired = dl < 0;
    
    // If message is expired, show "Expired message"
    if (isExpired) {
      return `
        <div class="msg-wrap" data-key="${key}">
          <input type="checkbox" ${sel}
            onclick="toggleSel(selMsgs,'${key}','del-msgs-btn');restoreChecks()">
          <div class="msg expired">
            <div class="msg-meta">
              <span class="msender">${esc(m.sender_name)}</span>
              <span class="badge" style="background:#5c1414;color:#ff8080">EXPIRED</span>
              <span class="mts">${timeAgo(m.timestamp)}</span>
            </div>
            <div class="msg-text dim">🕐 Expired message (${Math.abs(Math.floor(dl))} days ago)</div>
          </div>
        </div>`;
    }
    
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
    const ecls = dl <= 1 ? 'expires soon' : 'expires';
    const exp  = dl > 0 ? `⏳ ${dl>=1?Math.ceil(dl)+'d':' <1d'} left` : '⚠️ Expired';
    const uname= m.username ? `<span class="muname">@${esc(m.username)}</span>` : '';
    const uid  = m.user_id  ? `<span class="muid">${m.user_id}</span>` : '';

    return `
      <div class="msg-wrap" data-key="${key}">
        <input type="checkbox" ${sel}
          onclick="toggleSel(selMsgs,'${key}','del-msgs-btn');restoreChecks()">
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
  }).join('') + '</div>';
  
  // Add event listeners to media elements to pause refresh when playing
  setTimeout(() => {
    document.querySelectorAll('#list-msgs video, #list-msgs audio').forEach(media => {
      media.addEventListener('play', () => {
        console.log('Media started playing - pausing auto-refresh');
      });
      media.addEventListener('pause', () => {
        console.log('Media paused');
      });
      media.addEventListener('ended', () => {
        console.log('Media ended');
      });
    });
  }, 100);
}

// ── Restore checkboxes after re-render ────────────────────
function restoreChecks() {
  document.querySelectorAll('#list-chats .chat-item input').forEach(cb => {
    const cid = parseInt(cb.closest('.chat-item').dataset.cid);
    cb.checked = selChats.has(cid);
  });
  document.querySelectorAll('#list-msgs .msg-wrap input').forEach(cb => {
    const key = cb.closest('.msg-wrap').dataset.key;
    cb.checked = selMsgs.has(key);
  });
}

// ── Delete selected ───────────────────────────────────────
async function deleteSelected(type) {
  let ids = [];
  if (type === 'chats')    ids = [...selChats].map(id=>({chat_id:id}));
  if (type === 'messages') ids = [...selMsgs].map(k=>{ const[m,c]=k.split('_'); return{message_id:parseInt(m),chat_id:parseInt(c)}; });
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} item(s)? This cannot be undone.`)) return;
  try {
    const r = await fetch('/api/delete', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type, ids})
    });
    const j = await r.json();
    if (j.ok) {
      if (type==='chats')    { selChats.clear(); updateDelBtn('del-chats-btn',selChats); }
      if (type==='messages') { selMsgs.clear();  updateDelBtn('del-msgs-btn', selMsgs); }
      await fetchData();
    }
  } catch(e) { alert('Delete failed: '+e); }
}

// ── Fetch & refresh ───────────────────────────────────────
async function fetchData() {
  if (!isUnlocked) return;  // Don't fetch until password is entered
  
  // Save scroll positions before refresh
  const chatsScroll = document.getElementById('list-chats')?.scrollTop || 0;
  const msgsScroll = document.getElementById('list-msgs')?.scrollTop || 0;
  
  try {
    const r = await fetch('/api/data');
    const j = await r.json();
    allData = j;

    document.getElementById('gs-chats').textContent = j.stats.chats;
    document.getElementById('gs-msgs').textContent  = j.stats.messages;
    document.getElementById('gs-del').textContent   = j.stats.deleted;
    document.getElementById('gs-edit').textContent  = j.stats.edited;
    document.getElementById('gs-media').textContent = j.stats.media_files;
    document.getElementById('ts').textContent       = new Date().toLocaleTimeString();

    renderChats();
    renderMessages();
    restoreChecks();
    
    // Restore scroll positions after refresh
    setTimeout(() => {
      const chatsEl = document.getElementById('list-chats');
      const msgsEl = document.getElementById('list-msgs');
      if (chatsEl) chatsEl.scrollTop = chatsScroll;
      if (msgsEl) msgsEl.scrollTop = msgsScroll;
    }, 50);
  } catch(e) { console.error(e); }
}

// Don't auto-start - wait for password
// fetchData() and setInterval are called from checkPassword()
</script>

</div><!-- end main-content -->

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
    Returns chats with contact names (2-panel Telegram-style).
    Structure: chats[] with messages[]
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

    # Group by chat_id
    chats_map = {}
    for m in msgs:
        cid = m["chat_id"]
        if cid not in chats_map:
            chats_map[cid] = []
        chats_map[cid].append(m)

    # Build chat list with contact names
    chats = []
    for chat_id, chat_msgs in chats_map.items():
        # Get all unique senders in this chat (both sides)
        senders = {}
        for m in chat_msgs:
            if m["user_id"] and m["sender_name"]:
                senders[m["user_id"]] = {
                    "name": m["sender_name"],
                    "username": m["username"]
                }
        
        # Build contact name showing both sides (e.g., "saminov | Dr.Iskandar Dodirov")
        sender_names = [info["name"] for uid, info in senders.items() if info["name"]]
        
        if len(sender_names) >= 2:
            contact_name = f"{sender_names[0]} | {sender_names[1]}"
        elif len(sender_names) == 1:
            contact_name = sender_names[0]
        else:
            contact_name = f"Chat {chat_id}"
        
        # Use first sender's username for reference
        contact_username = None
        for uid, info in senders.items():
            if info["username"]:
                contact_username = info["username"]
                break
        
        last_msg = chat_msgs[-1]
        
        chats.append({
            "chat_id": chat_id,
            "contact_name": contact_name,
            "contact_username": contact_username,
            "msg_count": len(chat_msgs),
            "deleted_count": sum(1 for m in chat_msgs if m["is_deleted"]),
            "edited_count": sum(1 for m in chat_msgs if m["is_edited"]),
            "last_text": last_msg["text"],
            "last_media_type": last_msg["media_type"],
            "last_ts": last_msg["timestamp"],
            "messages": chat_msgs,
        })

    # Sort by most recent message
    chats.sort(key=lambda c: c["last_ts"], reverse=True)

    total_msgs = len(msgs)
    total_chats = len(chats)
    deleted = sum(1 for m in msgs if m["is_deleted"])
    edited = sum(1 for m in msgs if m["is_edited"])
    media_files = len(os.listdir(MEDIA_CACHE)) if os.path.exists(MEDIA_CACHE) else 0

    return jsonify({
        "chats": chats,
        "stats": {
            "chats": total_chats,
            "messages": total_msgs,
            "deleted": deleted,
            "edited": edited,
            "media_files": media_files,
        }
    })


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
    # Koyeb beradigan portni olamiz, bo'lmasa 8080
    port = int(os.environ.get("PORT", WEB_PORT))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


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
        f"👋 Salom, {user.first_name}!\nBot faol va ishlamoqda.\n\nFoydalanish qo'llanmasi: @mysherlock_options"
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
        f"• /clear — Clear all messages\n"
        f"• /story [@user or id] — Download stories\n"
        f"• /get — Reply to any message to save its media\n"
        f"• /admin — This menu\n\n"
        f"🌐 <b>Dashboard:</b> {DASHBOARD_URL}\n"
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
        f"⏳ Message TTL: <code>{CACHE_TTL} days</code>\n\n"
        f"🌐 Dashboard: {DASHBOARD_URL}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


@admin_only
async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /clear command - clear all messages from database
    Usage: /clear - deletes all cached messages
           /clear confirm - actually deletes (safety check)
    """
    parts = update.message.text.split()
    
    # Safety check - require confirmation
    if len(parts) < 2 or parts[1].lower() != "confirm":
        msg_count = count_cache()
        media_count = len(os.listdir(MEDIA_CACHE)) if os.path.exists(MEDIA_CACHE) else 0
        await update.message.reply_text(
            f"⚠️ <b>WARNING: Database Clear</b>\n\n"
            f"This will delete:\n"
            f"• {msg_count} cached messages\n"
            f"• {media_count} media files\n\n"
            f"To confirm, send:\n"
            f"<code>/clear confirm</code>",
            parse_mode="HTML"
        )
        return
    
    # Get counts before deletion
    msg_count = count_cache()
    media_count = len(os.listdir(MEDIA_CACHE)) if os.path.exists(MEDIA_CACHE) else 0
    
    status = await update.message.reply_text("🗑 Clearing database...")
    
    try:
        # Delete all messages from database
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM business_cache")
            conn.commit()
        
        # Delete all media files
        deleted_files = 0
        if os.path.exists(MEDIA_CACHE):
            for filename in os.listdir(MEDIA_CACHE):
                file_path = os.path.join(MEDIA_CACHE, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        deleted_files += 1
                except Exception as e:
                    log.warning(f"Failed to delete {filename}: {e}")
        
        await status.edit_text(
            f"✅ <b>Database Cleared!</b>\n\n"
            f"• Deleted {msg_count} messages\n"
            f"• Deleted {deleted_files} media files\n\n"
            f"Database is now empty.",
            parse_mode="HTML"
        )
        log.info(f"Database cleared by admin: {msg_count} messages, {deleted_files} files")
        
    except Exception as e:
        await status.edit_text(f"❌ Error clearing database: {e}")
        log.error(f"Database clear failed: {e}")


@admin_only
async def cmd_ad(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /ad command - broadcast message to all users
    Usage: Reply to a message (with or without media) with /ad
    The replied message will be forwarded/sent to all users
    """
    # Must reply to a message
    reply = update.message.reply_to_message
    if not reply:
        await update.message.reply_text(
            "❌ Usage:\n"
            "1. Send a message with media and caption (your ad)\n"
            "2. Reply to that message with /ad\n"
            "3. Bot will send it to all users"
        )
        return
    
    # Get media and caption from replied message
    has_media = False
    media_file = None
    media_type = None
    caption = reply.caption or reply.text or ""
    
    # Check for media types
    if reply.photo:
        has_media = True
        media_file = reply.photo[-1].file_id
        media_type = "photo"
    elif reply.video:
        has_media = True
        media_file = reply.video.file_id
        media_type = "video"
    elif reply.document:
        has_media = True
        media_file = reply.document.file_id
        media_type = "document"
    elif reply.animation:
        has_media = True
        media_file = reply.animation.file_id
        media_type = "animation"
    elif reply.audio:
        has_media = True
        media_file = reply.audio.file_id
        media_type = "audio"
    elif reply.voice:
        has_media = True
        media_file = reply.voice.file_id
        media_type = "voice"
    elif reply.video_note:
        has_media = True
        media_file = reply.video_note.file_id
        media_type = "video_note"
    elif reply.sticker:
        has_media = True
        media_file = reply.sticker.file_id
        media_type = "sticker"
    
    # If no media and no text, error
    if not has_media and not caption:
        await update.message.reply_text("❌ The replied message has no content to broadcast.")
        return
    
    users = get_all_users()
    if not users:
        await update.message.reply_text("❌ No users yet.")
        return
    
    media_info = f" ({media_type})" if has_media else " (text only)"
    await update.message.reply_text(f"📢 Broadcasting{media_info} to {len(users)} users…")
    
    ok = fail = 0
    for (uid,) in users:
        try:
            if has_media:
                # Send media with caption
                if media_type == "photo":
                    await ctx.bot.send_photo(chat_id=uid, photo=media_file, caption=caption)
                elif media_type == "video":
                    await ctx.bot.send_video(chat_id=uid, video=media_file, caption=caption)
                elif media_type == "document":
                    await ctx.bot.send_document(chat_id=uid, document=media_file, caption=caption)
                elif media_type == "animation":
                    await ctx.bot.send_animation(chat_id=uid, animation=media_file, caption=caption)
                elif media_type == "audio":
                    await ctx.bot.send_audio(chat_id=uid, audio=media_file, caption=caption)
                elif media_type == "voice":
                    await ctx.bot.send_voice(chat_id=uid, voice=media_file, caption=caption)
                elif media_type == "video_note":
                    await ctx.bot.send_video_note(chat_id=uid, video_note=media_file)
                elif media_type == "sticker":
                    await ctx.bot.send_sticker(chat_id=uid, sticker=media_file)
            else:
                # Send text only
                await ctx.bot.send_message(chat_id=uid, text=caption)
            ok += 1
        except Exception as e:
            log.warning("Broadcast fail uid=%s: %s", uid, e)
            fail += 1
        await asyncio.sleep(0.05)
    
    await update.message.reply_text(
        f"✅ <b>Broadcast Complete!</b>\n"
        f"• Delivered: {ok}\n"
        f"• Failed: {fail}\n"
        f"• Total users: {len(users)}", 
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────────────────────
#  /get
# ─────────────────────────────────────────────────────────────

async def cmd_get(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /get command - works in all chats (not just admin)
    Reply to a message with /get to save its media (including view-once photos/videos)
    The /get command message will be deleted after processing
    """
    # Check if user is authorized (you can modify this check)
    user_id = update.effective_user.id if update.effective_user else None
    if user_id != ADMIN_ID:
        # Optional: allow only admin, or allow all users
        # For now, allowing all users - remove this check if you want admin-only
        pass
    
    reply = update.message.reply_to_message
    if not reply:
        msg = await update.message.reply_text("❌ Reply to a message with /get to save its media.")
        # Delete both the /get command and error message after 5 seconds
        await asyncio.sleep(5)
        try:
            await update.message.delete()
            await msg.delete()
        except Exception:
            pass
        return
    
    status = await update.message.reply_text("⏳ Fetching media…")

    # Try Bot API first (for regular photos/videos)
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
                await ctx.bot.send_video(chat_id=user_id, video=buf, caption=caption, parse_mode="HTML")
            else:
                buf.name = "media.jpg"
                await ctx.bot.send_photo(chat_id=user_id, photo=buf, caption=caption, parse_mode="HTML")
            await status.edit_text("✅ Media saved and sent!")
            
            # Delete the /get command and status message after 3 seconds
            await asyncio.sleep(3)
            try:
                await update.message.delete()
                await status.delete()
            except Exception:
                pass
            return
        except Exception as e:
            log.warning("/get Bot API failed: %s", e)

    # Try Telethon for view-once media
    if not telethon_client:
        await status.edit_text("❌ Could not fetch. Set API_ID and API_HASH for one-time photos.")
        await asyncio.sleep(5)
        try:
            await update.message.delete()
            await status.delete()
        except Exception:
            pass
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
            await asyncio.sleep(5)
            try:
                await update.message.delete()
                await status.delete()
            except Exception:
                pass
            return
        
        media_bytes = await telethon_client.download_media(msg.media, file=bytes)
        if not media_bytes:
            await status.edit_text("❌ Download returned empty data.")
            await asyncio.sleep(5)
            try:
                await update.message.delete()
                await status.delete()
            except Exception:
                pass
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
            await ctx.bot.send_video(chat_id=user_id, video=buf, caption=caption, parse_mode="HTML")
        else:
            buf.name = "secret.jpg"
            await ctx.bot.send_photo(chat_id=user_id, photo=buf, caption=caption, parse_mode="HTML")
        
        await status.edit_text("✅ One-time media saved and sent!")
        
        # Delete the /get command and status message after 3 seconds
        await asyncio.sleep(3)
        try:
            await update.message.delete()
            await status.delete()
        except Exception:
            pass
            
    except Exception as e:
        log.error("/get Telethon failed: %s", e)
        await status.edit_text(
            f"❌ Failed: <code>{e}</code>\n• Photo may have expired\n• Message deleted\n• No Telethon access",
            parse_mode="HTML"
        )
        await asyncio.sleep(5)
        try:
            await update.message.delete()
            await status.delete()
        except Exception:
            pass


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

    # Get business owner ID from business connection
    business_owner_id = None
    if hasattr(update, 'business_connection') and update.business_connection:
        business_owner_id = update.business_connection.user_id
    elif msg.business_connection_id:
        # Fallback: try to get from bot's business connections
        business_owner_id = getattr(ctx.bot_data.get('business_connections', {}).get(msg.business_connection_id), 'user_id', None)

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
                  media_type=media_type, media_path=media_path, business_owner_id=business_owner_id)
    log.info("Cached msg id=%s from %s", msg.message_id, sender_name)


async def on_edited_business_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.edited_business_message
    if not msg:
        return
    
    # Get business owner ID
    business_owner_id = None
    if hasattr(update, 'business_connection') and update.business_connection:
        business_owner_id = update.business_connection.user_id
    elif msg.business_connection_id:
        business_owner_id = getattr(ctx.bot_data.get('business_connections', {}).get(msg.business_connection_id), 'user_id', None)
    
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
    
    # Send notification to business owner (not global admin)
    target_id = business_owner_id if business_owner_id else ADMIN_ID
    try:
        await ctx.bot.send_message(chat_id=target_id, text=notification, parse_mode="HTML")
    except Exception as e:
        log.error("Edit notify failed: %s", e)

    cache_message(msg.message_id, msg.chat.id, user_id, new_text, sender_name,
                  sender.username if sender else None, business_owner_id=business_owner_id)


async def on_deleted_business_messages(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = update.deleted_business_messages
    if not deleted:
        return

    chat_id     = deleted.chat.id
    message_ids = deleted.message_ids
    log.info("Deletion: %d msg(s) in chat %s", len(message_ids), chat_id)

    for mid in message_ids:
        cached = fetch_cached(mid, chat_id)

        # Get business owner ID from cached data
        business_owner_id = cached["business_owner_id"] if cached and cached["business_owner_id"] else ADMIN_ID

        if cached and cached["user_id"] == business_owner_id:
            log.info("Skipping business owner's own deleted msg id=%s", mid)
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
                        await ctx.bot.send_photo(chat_id=business_owner_id, photo=f, caption=caption, parse_mode="HTML")
                    elif ext in ("mp4","gif"):
                        await ctx.bot.send_video(chat_id=business_owner_id, video=f, caption=caption, parse_mode="HTML")
                    elif ext in ("webp","webm"):
                        await ctx.bot.send_sticker(chat_id=business_owner_id, sticker=f)
                        await ctx.bot.send_message(chat_id=business_owner_id, text=caption, parse_mode="HTML")
                    elif ext == "ogg":
                        await ctx.bot.send_voice(chat_id=business_owner_id, voice=f, caption=caption, parse_mode="HTML")
                    elif ext == "mp3":
                        await ctx.bot.send_audio(chat_id=business_owner_id, audio=f, caption=caption, parse_mode="HTML")
                    else:
                        await ctx.bot.send_document(chat_id=business_owner_id, document=f, caption=caption, parse_mode="HTML")
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
                await ctx.bot.send_message(chat_id=business_owner_id, text=notification, parse_mode="HTML")
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
    port = int(os.environ.get("PORT", WEB_PORT))
    log.info("Web dashboard running at http://0.0.0.0:%s", port)

    asyncio.create_task(purge_loop())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("ad",    cmd_ad))
    app.add_handler(CommandHandler("story", cmd_story))
    app.add_handler(CommandHandler("get",   cmd_get, filters=filters.ALL))  # Works in all chats
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
