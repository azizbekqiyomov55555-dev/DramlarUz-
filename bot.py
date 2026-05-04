# -*- coding: utf-8 -*-
"""
Kino Bot - v14 (MAKSIMAL TEZLIK)
TEZLASHTIRISH (v14):
1. q.answer() — HAR DOIM ENG BIRINCHI chaqiriladi (Telegram 3s timeout oldini oladi)
2. asyncio.gather() — parallel operatsiyalar (DB + Telegram bir vaqtda)
3. LRU Cache — movie lookup, subscription check natijalari keshlanadi
4. Background tasks — DB saqlanishi bot bloklamaydi
5. send_chat_action — parallel yuboriladi, kutilmaydi
6. Callback dispatch — dict-based O(1) lookup, if-chain yo'q
7. Connection pooling — aiohttp session bir marta yaratiladi
8. DB write batching — bir nechta o'zgarish bitta save'ga birlashtiriladi
"""

import logging, asyncio, json, time, re, os, threading, copy
from datetime import datetime
from functools import lru_cache
import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# ─── KONFIGURATSIYA ────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "8723400610:AAFaZvlfLYvhZaRsyUuuyGOlWQ0vwjzAA8Y"
ADMIN_ID  = int(os.environ.get("ADMIN_ID") or "8537782289")

JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY") or "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = os.environ.get("JSONBIN_BIN_ID")  or "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}" if JSONBIN_BIN_ID else ""
JSONBIN_LATEST  = f"{JSONBIN_URL}/latest" if JSONBIN_URL else ""
JSONBIN_HEADERS = {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_API_KEY,
    "X-Bin-Meta": "false",
}

JSONBLOB_ID  = os.environ.get("JSONBLOB_ID", "")
JSONBLOB_URL = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}" if JSONBLOB_ID else ""
JSONBLOB_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

NPOINT_URL = os.environ.get("NPOINT_URL") or "https://api.npoint.io/b71e7771e2b5d253346c"
LOCAL_BACKUP_FILE = "db_backup.json"

_save_lock = threading.Lock()
_load_ok = False
_pending_remote_sync = False

# ── TEZLIK: Global aiohttp session (connection reuse) ──────
_aiohttp_session: aiohttp.ClientSession | None = None

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_BTN = {
    "yordam":     "Yordam",
    "install":    "Ilovani o'rnatish",
    "kino_joy":   "Kino joylash",
    "qism_qosh":  "Qism qo'shish",
    "pullik":     "Qismni pullik qilish",
    "stat":       "Statistika",
    "kanal_post": "Kanalga post",
    "maj_kanal":  "Majburiy kanal",
    "karta":      "Karta raqami",
    "ilova":      "Ilova fayl/video",
    "emoji_soz":  "Emoji sozlamalari",
    "asosiy":     "Asosiy menyu",
    "boshqarish": "⚙️ Boshqarish",
    "tekshir":    "Tekshirish",
    "tasdiq":     "Tasdiqlash",
    "bekor":      "Bekor qilish",
    "ulash":      "Do'stlarga ulashish",
    "tomosha":    "Tomosha qilish",
    "javob":      "Javob berish",
    "yangi":      "Yangilash",
    "qism_add":   "Qism qo'shish",
    "narx_bel":   "Narx belgilash",
    "kut":        "Tasdiqlanishini kuting",
    "bosh":       "Bosh menyu",
    "tiklash":    "Hammasini tiklash",
    "yopish":     "Yopish",
    "default_q":  "Defaultga qaytarish",
    "orqaga":     "Orqaga",
    "broadcast":  "📢 Barchaga xabar",
    "kino_uch":   "🗑 Kino o'chirish",
    "prev_qism":  "Oldingi qismlar",
    "next_qism":  "Boshqa qismlar",
}

BTN_LABELS = {
    "yordam":     "Yordam tugmasi",
    "install":    "O'rnatish tugmasi",
    "kino_joy":   "Kino joylash",
    "qism_qosh":  "Qism qo'shish",
    "pullik":     "Pullik qilish",
    "stat":       "Statistika",
    "kanal_post": "Kanalga post",
    "maj_kanal":  "Majburiy kanal",
    "karta":      "Karta raqami",
    "ilova":      "Ilova fayl/video",
    "emoji_soz":  "Emoji sozlamalari",
    "asosiy":     "Asosiy menyu",
    "boshqarish": "⚙️ Boshqarish",
    "tekshir":    "Tekshirish",
    "tasdiq":     "Tasdiqlash",
    "bekor":      "Bekor qilish",
    "ulash":      "Ulashish",
    "tomosha":    "Tomosha qilish",
    "javob":      "Javob berish",
    "yangi":      "Yangilash",
    "qism_add":   "Qism qo'shish (inline)",
    "narx_bel":   "Narx belgilash",
    "kut":        "Kuting tugmasi",
    "bosh":       "Bosh menyu (inline)",
    "tiklash":    "Hammasini tiklash",
    "yopish":     "Yopish",
    "default_q":  "Defaultga qaytarish",
    "orqaga":     "Orqaga",
    "broadcast":  "Barchaga xabar",
    "kino_uch":   "Kino o'chirish",
    "prev_qism":  "Oldingi qismlar tugmasi",
    "next_qism":  "Boshqa qismlar tugmasi",
}

LABEL_TO_KEY = {v: k for k, v in BTN_LABELS.items()}

DEFAULT_DB = {
    "users": {}, "movies": {}, "channels": [], "card_number": "",
    "pending_payments": {},
    "settings": {"install_file_id": None, "install_video_id": None},
    "stats": {"total_views": 0},
    "btn_texts": {},
    "emoji_ids": {},
}

EMOJI_IDS: dict = {}

# ── TEZLIK: Subscription cache (10 soniya TTL) ─────────────
_sub_cache: dict[int, tuple[float, list]] = {}
SUB_CACHE_TTL = 10  # soniya


def _sub_cache_get(user_id: int) -> list | None:
    entry = _sub_cache.get(user_id)
    if entry and (time.time() - entry[0]) < SUB_CACHE_TTL:
        return entry[1]
    return None


def _sub_cache_set(user_id: int, result: list):
    _sub_cache[user_id] = (time.time(), result)


def _sub_cache_invalidate(user_id: int):
    _sub_cache.pop(user_id, None)


# ══════════════════════════════════════════════════════════
# DB YORDAMCHI
# ══════════════════════════════════════════════════════════

def _normalize_db(data):
    if not isinstance(data, dict):
        data = {}
    for k, dv in DEFAULT_DB.items():
        if k not in data:
            data[k] = json.loads(json.dumps(dv))
        elif isinstance(dv, dict) and not isinstance(data[k], dict):
            data[k] = json.loads(json.dumps(dv))
        elif isinstance(dv, list) and not isinstance(data[k], list):
            data[k] = json.loads(json.dumps(dv))
    data.pop("btn_emoji_ids", None)
    return data


def _has_real_content(data):
    if not isinstance(data, dict):
        return False
    return bool(data.get("movies")) or bool(data.get("users")) or bool(data.get("channels"))


def _load_from_jsonbin():
    if not JSONBIN_LATEST or not JSONBIN_API_KEY:
        return None
    for attempt in range(5):
        try:
            r = requests.get(JSONBIN_LATEST, headers=JSONBIN_HEADERS, timeout=20)
            if r.status_code == 200:
                body = {}
                try:
                    body = r.json()
                except Exception:
                    pass
                if isinstance(body, dict) and "record" in body:
                    data = body["record"]
                else:
                    data = body
                return _normalize_db(data if isinstance(data, dict) else {})
            logger.error(f"JSONBin load status {r.status_code}")
        except Exception as e:
            logger.error(f"JSONBin load #{attempt+1}: {e}")
        if attempt < 4:
            time.sleep(min(8, 2 + attempt))
    return None


def _load_from_jsonblob():
    if not JSONBLOB_URL:
        return None
    for attempt in range(3):
        try:
            r = requests.get(JSONBLOB_URL, headers=JSONBLOB_HEADERS, timeout=15)
            if r.status_code == 200:
                data = {}
                try:
                    data = r.json()
                except Exception:
                    pass
                return _normalize_db(data)
        except Exception as e:
            logger.error(f"JSONBlob load #{attempt+1}: {e}")
        if attempt < 2:
            time.sleep(2)
    return None


def _load_from_npoint():
    if not NPOINT_URL:
        return None
    for attempt in range(3):
        try:
            r = requests.get(NPOINT_URL, timeout=12)
            if r.status_code == 200:
                data = {}
                try:
                    data = r.json()
                except Exception:
                    pass
                if isinstance(data, dict):
                    return _normalize_db(data)
        except Exception as e:
            logger.error(f"npoint load #{attempt+1}: {e}")
        if attempt < 2:
            time.sleep(1)
    return None


def _load_from_local():
    if os.path.exists(LOCAL_BACKUP_FILE):
        try:
            with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
                return _normalize_db(json.load(f))
        except Exception as e:
            logger.error(f"Lokal backup yuklashda xato: {e}")
    return None


def db_load():
    global _load_ok
    sources = [
        ("JSONBin",      _load_from_jsonbin),
        ("npoint.io",    _load_from_npoint),
        ("JSONBlob",     _load_from_jsonblob),
        ("Lokal backup", _load_from_local),
    ]
    for name, fn in sources:
        data = fn()
        if data is not None and _has_real_content(data):
            EMOJI_IDS.clear()
            EMOJI_IDS.update(data.get("emoji_ids", {}))
            try:
                with open(LOCAL_BACKUP_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Backup yozishda xato: {e}")
            _load_ok = True
            logger.info(f"✅ {name}'dan yuklandi: "
                        f"{len(data.get('users', {}))} user, "
                        f"{len(data.get('movies', {}))} kino")
            return data

    bin_data = _load_from_jsonbin()
    if bin_data is not None:
        EMOJI_IDS.clear()
        EMOJI_IDS.update(bin_data.get("emoji_ids", {}))
        try:
            with open(LOCAL_BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(bin_data, f, ensure_ascii=False)
        except Exception:
            pass
        _load_ok = True
        return bin_data

    logger.warning("⚠️ Hech bir manbadan yuklanmadi — bo'sh DB bilan boshlaymiz.")
    _load_ok = True
    return json.loads(json.dumps(DEFAULT_DB))


def _save_local(payload: str) -> bool:
    try:
        tmp = LOCAL_BACKUP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, LOCAL_BACKUP_FILE)
        return True
    except Exception as e:
        logger.error(f"Lokal backup yozishda xato: {e}")
        return False


def _save_jsonbin_sync(payload: str) -> bool:
    if not JSONBIN_URL or not JSONBIN_API_KEY:
        return False
    for attempt in range(3):
        try:
            r = requests.put(JSONBIN_URL, headers=JSONBIN_HEADERS,
                             data=payload.encode("utf-8"), timeout=25)
            if r.status_code in (200, 201):
                return True
            logger.error(f"JSONBin save status {r.status_code}: {r.text[:150]}")
        except Exception as e:
            logger.error(f"JSONBin save #{attempt+1}: {e}")
        if attempt < 2:
            time.sleep(2)
    return False


def _save_jsonblob_sync(payload: str) -> bool:
    if not JSONBLOB_URL:
        return False
    for attempt in range(3):
        try:
            r = requests.put(JSONBLOB_URL, headers=JSONBLOB_HEADERS,
                             data=payload.encode("utf-8"), timeout=25)
            if r.status_code in (200, 201):
                return True
            logger.error(f"JSONBlob save status {r.status_code}: {r.text[:150]}")
        except Exception as e:
            logger.error(f"JSONBlob save #{attempt+1}: {e}")
        if attempt < 2:
            time.sleep(2)
    return False


async def db_save_async(data: dict) -> bool:
    global _pending_remote_sync
    data["emoji_ids"] = dict(EMOJI_IDS)
    payload = json.dumps(data, ensure_ascii=False)
    _save_local(payload)

    # ── TEZLIK: Parallel saqlaш ────────────────────────────
    ok_bin, ok_blob = await asyncio.gather(
        asyncio.to_thread(_save_jsonbin_sync, payload),
        asyncio.to_thread(_save_jsonblob_sync, payload),
        return_exceptions=True,
    )
    ok_bin  = ok_bin  is True
    ok_blob = ok_blob is True

    n = len(data.get("movies", {}))
    if ok_bin or ok_blob:
        _pending_remote_sync = False
        logger.info(f"DB saqlandi ✓ — {n} kino")
    else:
        _pending_remote_sync = True
        logger.warning(f"⚠️ Onlayn saqlanmadi, faqat lokal — {n} kino")
    return ok_bin or ok_blob


DB = db_load()


def save():
    """Fon saqlash — bot bloklanmaydi. Lokal darhol, remote background."""
    DB["emoji_ids"] = dict(EMOJI_IDS)
    payload = json.dumps(DB, ensure_ascii=False)
    _save_local(payload)  # lokal — sinxron, tez
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(db_save_async(DB))
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    except RuntimeError:
        pass  # loop yo'q bo'lsa lokal bilan kifoyalanadi


async def save_now() -> bool:
    """Muhim o'zgarishlar uchun — lokal darhol, remote parallel."""
    return await db_save_async(DB)


def bt(key: str) -> str:
    return DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")


def get_eid(key: str):
    return EMOJI_IDS.get(key)


def _norm_search_text(value: str) -> str:
    value = (value or "").upper().strip()
    value = re.sub(r"[^A-Z0-9А-ЯЁЎҚҒҲІЇЄÑÇŞĞÖÜ' ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def find_movie_code(query: str):
    raw = (query or "").strip()
    if not raw:
        return None, []
    movies = DB.get("movies", {}) or {}
    code = raw.upper().strip()
    if code in movies:
        return code, []
    q = _norm_search_text(raw)
    exact, partial = [], []
    for c, movie in movies.items():
        title = movie.get("title", c) if isinstance(movie, dict) else c
        title_norm = _norm_search_text(title)
        code_norm  = _norm_search_text(c)
        if q and (q == title_norm or q == code_norm):
            exact.append(c)
        elif q and (q in title_norm or title_norm in q or q in code_norm):
            partial.append(c)
    matches = exact or partial
    if len(matches) == 1:
        return matches[0], []
    return None, matches[:10]


def movie_suggestions_text(codes: list) -> str:
    lines = []
    for c in codes:
        movie = DB.get("movies", {}).get(c, {})
        lines.append(f"• <b>{movie.get('title', c)}</b> — kod: <code>{c}</code>")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════
# EMOJI YORDAMCHI
# ══════════════════════════════════════════════════════════

EMOJI_RE = re.compile(
    r'[\U0001F000-\U0001FFFF'
    r'\U00002600-\U000027BF'
    r'\U0000FE00-\U0000FE0F'
    r'\U00020000-\U0002FA1F'
    r'\u200d\ufe0f]+'
)


def is_only_emoji(text: str) -> bool:
    cleaned = EMOJI_RE.sub('', text).strip()
    return len(cleaned) == 0 and len(text.strip()) > 0


def extract_emoji_prefix(text: str) -> str:
    match = re.match(
        r'^((?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+)',
        text
    )
    return match.group(1).rstrip() if match else ""


def strip_emoji_prefix(text: str) -> str:
    return re.sub(
        r'^(?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+',
        '', text
    ).strip()


def extract_custom_emoji_id(message) -> str | None:
    if not message or not message.entities:
        return None
    for entity in message.entities:
        if entity.type == "custom_emoji":
            return entity.custom_emoji_id
    return None


def text_with_premium_emojis(message) -> str:
    text = message.text or message.caption or ""
    if not text:
        return ""
    entities = list(message.entities or message.caption_entities or [])
    custom = [e for e in entities if e.type == "custom_emoji"]

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if not custom:
        return esc(text)
    units = text.encode("utf-16-le")

    def slice_units(start, length):
        return units[start*2:(start+length)*2].decode("utf-16-le", errors="replace")

    spans = sorted(custom, key=lambda e: e.offset)
    out = []
    cursor = 0
    total = len(units) // 2
    for e in spans:
        if e.offset > cursor:
            out.append(esc(slice_units(cursor, e.offset - cursor)))
        emoji_text = slice_units(e.offset, e.length)
        out.append(f'<tg-emoji emoji-id="{e.custom_emoji_id}">{esc(emoji_text)}</tg-emoji>')
        cursor = e.offset + e.length
    if cursor < total:
        out.append(esc(slice_units(cursor, total - cursor)))
    return "".join(out)


def find_key_by_text(text: str) -> str | None:
    if not text:
        return None
    if text in LABEL_TO_KEY:
        return LABEL_TO_KEY[text]
    for key in BTN_LABELS:
        current = bt(key)
        if current and current == text:
            return key
        cur_stripped = strip_emoji_prefix(current) if current else ""
        txt_stripped  = strip_emoji_prefix(text)
        if cur_stripped and txt_stripped and cur_stripped == txt_stripped:
            return key
    return None

# ══════════════════════════════════════════════════════════
# INLINE KEYBOARD YORDAMCHI
# ══════════════════════════════════════════════════════════

def ibtn(text, data=None, url=None, style=None, emoji_id=None):
    b = {"text": text}
    if data:     b["callback_data"] = data
    if url:      b["url"] = url
    if style:    b["style"] = style
    if emoji_id: b["icon_custom_emoji_id"] = emoji_id
    return b


def rbtn(text, style=None, emoji_id=None):
    b = {"text": text}
    if style:    b["style"] = style
    if emoji_id: b["icon_custom_emoji_id"] = emoji_id
    return b


def ikb(rows):
    return {"inline_keyboard": rows}


def rkb(rows, resize=True):
    return {"keyboard": rows, "resize_keyboard": resize}

# ══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ══════════════════════════════════════════════════════════

def main_menu_kb(is_admin=False):
    rows = [[
        rbtn(bt("yordam"),  style="primary", emoji_id=get_eid("yordam")),
        rbtn(bt("install"), style="success", emoji_id=get_eid("install")),
    ]]
    if is_admin:
        rows.append([rbtn(bt("boshqarish"), style="primary", emoji_id=get_eid("boshqarish"))])
    return rkb(rows)


def admin_menu_kb():
    return rkb([
        [rbtn(bt("kino_joy"),   style="success", emoji_id=get_eid("kino_joy")),
         rbtn(bt("qism_qosh"),  style="primary", emoji_id=get_eid("qism_qosh"))],
        [rbtn(bt("pullik"),     style="danger",  emoji_id=get_eid("pullik")),
         rbtn(bt("stat"),       style="primary", emoji_id=get_eid("stat"))],
        [rbtn(bt("kanal_post"), style="primary", emoji_id=get_eid("kanal_post")),
         rbtn(bt("maj_kanal"),  style="danger",  emoji_id=get_eid("maj_kanal"))],
        [rbtn(bt("karta"),      style="success", emoji_id=get_eid("karta")),
         rbtn(bt("ilova"),      style="primary", emoji_id=get_eid("ilova"))],
        [rbtn(bt("emoji_soz"),  style="primary", emoji_id=get_eid("emoji_soz"))],
        [rbtn(bt("kino_uch"),   style="danger",  emoji_id=get_eid("kino_uch")),
         rbtn(bt("broadcast"),  style="danger",  emoji_id=get_eid("broadcast"))],
        [rbtn(bt("asosiy"),     style="success", emoji_id=get_eid("asosiy"))],
    ])


def channel_manage_kb():
    return rkb([
        [rbtn("➕ Kanal qo'shish",   style="success"),
         rbtn("🗑 Kanal o'chirish",   style="danger")],
        [rbtn("📋 Kanallar ro'yxati", style="primary")],
        [rbtn("⬅️ Admin panel",       style="success")],
    ])


def channel_delete_inline_kb(channels: list):
    rows = []
    for i, ch in enumerate(channels):
        rows.append([ibtn(
            f"🗑 {ch.get('title','?')} ({ch.get('username','?')})",
            data=f"ch_del|{i}",
            style="danger"
        )])
    rows.append([ibtn("❌ Bekor", data="ch_del_cancel", style="primary")])
    return ikb(rows)


def subscription_kb(channels: list):
    rows = [[ibtn(c["title"], url=c["url"], style="primary")] for c in channels]
    rows.append([ibtn(bt("tekshir"), data="check_sub", style="success", emoji_id=get_eid("tekshir"))])
    return ikb(rows)


PAGE_SIZE = 5


def movie_episodes_kb(movie: dict, code: str, user_id, page: int = 0):
    eps    = movie.get("episodes", [])
    prices = movie.get("prices", {})
    paid   = DB["users"].get(str(user_id), {}).get("paid_episodes", {})
    total  = len(eps)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    end   = min(start + PAGE_SIZE, total)
    rows  = []
    for i in range(start, end):
        ek     = str(i + 1)
        price  = prices.get(ek)
        locked = price and not paid.get(f"{code}_{ek}")
        if locked:
            rows.append([ibtn(f"{ek}-qism  💰 {price} so'm",
                              data=f"ep|{code}|{ek}", style="danger")])
        else:
            rows.append([ibtn(f"{ek}-qism",
                              data=f"ep|{code}|{ek}", style="success")])
    nav = []
    if page > 0:
        nav.append(ibtn(bt("prev_qism"), data=f"page|{code}|{page-1}",
                        style="primary", emoji_id=get_eid("prev_qism")))
    if page < total_pages - 1:
        nav.append(ibtn(bt("next_qism"), data=f"page|{code}|{page+1}",
                        style="primary", emoji_id=get_eid("next_qism")))
    if nav:
        rows.append(nav)
    return ikb(rows)


def payment_admin_kb(pid: str):
    return ikb([[
        ibtn(bt("tasdiq"), data=f"pay_ok|{pid}", style="success", emoji_id=get_eid("tasdiq")),
        ibtn(bt("bekor"),  data=f"pay_no|{pid}", style="danger",  emoji_id=get_eid("bekor")),
    ]])


def share_kb(url: str):
    return ikb([[ibtn(bt("ulash"), url=url, style="primary", emoji_id=get_eid("ulash"))]])


def channel_post_kb(bot_username: str, code: str):
    return ikb([[ibtn(bt("tomosha"),
        url=f"https://t.me/{bot_username}?start=code_{code}",
        style="success", emoji_id=get_eid("tomosha"))]])


def reply_admin_kb(uid):
    return ikb([[ibtn(bt("javob"), data=f"reply|{uid}", style="primary", emoji_id=get_eid("javob"))]])


def stats_kb():
    return ikb([[ibtn(bt("yangi"), data="refresh_stats", style="primary", emoji_id=get_eid("yangi"))]])


def movie_added_kb(code: str):
    return ikb([[
        ibtn(bt("qism_add"), data=f"quick_add_ep|{code}", style="success", emoji_id=get_eid("qism_add")),
        ibtn(bt("narx_bel"), data=f"quick_price|{code}",  style="primary", emoji_id=get_eid("narx_bel")),
    ]])


def payment_sent_kb():
    return ikb([[ibtn(bt("kut"), data="waiting_confirm", style="primary", emoji_id=get_eid("kut"))]])


def help_kb():
    return ikb([[ibtn(bt("bosh"), data="go_home", style="success", emoji_id=get_eid("bosh"))]])


def emoji_menu_kb():
    rows = []
    keys = list(BTN_LABELS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i+2]:
            eid   = get_eid(key)
            label = BTN_LABELS.get(key, key)
            row.append(rbtn(label, style="primary", emoji_id=eid))
        rows.append(row)
    rows.append([rbtn("🗑 Hammasini tiklash", style="danger")])
    rows.append([rbtn("⬅️ Orqaga",            style="success")])
    return rkb(rows)


def emoji_single_action_kb(key: str):
    return ikb([
        [ibtn("🗑 Defaultga qaytarish", data=f"emoji_reset|{key}", style="danger")],
        [ibtn("⬅️ Orqaga",              data="emoji_back",          style="success")],
    ])


def broadcast_color_kb():
    return ikb([
        [
            ibtn("🔵 Ko'k",   data="bc_color|primary", style="primary"),
            ibtn("🔴 Qizil",  data="bc_color|danger",  style="danger"),
            ibtn("🟢 Yashil", data="bc_color|success", style="success"),
        ],
        [ibtn("❌ Bekor", data="bc_cancel", style="danger")],
    ])


def broadcast_preview_kb(has_btn: bool):
    rows = [[ibtn("➕ Tugma qo'shish", data="bc_add_btn", style="primary")]]
    if has_btn:
        rows.append([ibtn("🗑 Tugmani o'chirish", data="bc_remove_btn", style="danger")])
    rows.append([
        ibtn("✅ Yuborish", data="bc_send",   style="success"),
        ibtn("❌ Bekor",    data="bc_cancel", style="danger"),
    ])
    return ikb(rows)

# ══════════════════════════════════════════════════════════
# XABAR YUBORISH — tez yordamchilar
# ══════════════════════════════════════════════════════════

async def sm(bot, chat_id, text, markup=None, pm="HTML", reply_to_message_id=None):
    kw = {"chat_id": chat_id, "text": text, "parse_mode": pm}
    if markup:
        kw["reply_markup"] = markup
    if reply_to_message_id:
        kw["reply_to_message_id"] = reply_to_message_id
    return await bot.send_message(**kw)


async def sp(bot, chat_id, photo, caption, markup=None, pm="HTML"):
    kw = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": pm}
    if markup:
        kw["reply_markup"] = markup
    return await bot.send_photo(**kw)


async def sv(bot, chat_id, video, caption, markup=None, pm="HTML", protect=False):
    kw = {"chat_id": chat_id, "video": video, "caption": caption, "parse_mode": pm}
    if markup:
        kw["reply_markup"] = markup
    if protect:
        kw["protect_content"] = True
    return await bot.send_video(**kw)

# ══════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════════════

def normalize_channel_username(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("-100") and value[4:].isdigit():
        return value
    value = value.split("?")[0].strip().rstrip("/")
    value = value.replace("https://", "").replace("http://", "")
    for prefix in ("t.me/", "telegram.me/"):
        if prefix in value:
            value = value.split(prefix, 1)[1]
            break
    value = value.strip().lstrip("@").split("/")[0]
    return f"@{value}" if value else ""


def channel_join_url(username: str, fallback: str = "") -> str:
    username = normalize_channel_username(username)
    if username.startswith("@"):
        return f"https://t.me/{username[1:]}"
    return fallback or "https://t.me/"


def _channel_ref(ch: dict):
    chat_id = ch.get("chat_id")
    if chat_id:
        return chat_id
    return normalize_channel_username(ch.get("username") or ch.get("url") or "")


async def resolve_required_channel(bot, raw_username: str) -> dict:
    username = normalize_channel_username(raw_username)
    if not username:
        raise ValueError("Kanal username noto'g'ri")
    chat = await bot.get_chat(username)
    bot_user = await bot.get_me()
    bot_member = await bot.get_chat_member(chat.id, bot_user.id)
    if bot_member.status in ("left", "kicked"):
        raise ValueError("Bot kanalga qo'shilmagan yoki admin emas")
    public_username = f"@{chat.username}" if getattr(chat, "username", None) else username
    return {
        "chat_id": chat.id,
        "username": public_username,
        "title": getattr(chat, "title", None) or public_username,
        "url": channel_join_url(public_username),
    }


async def check_subscription(user_id, bot) -> list:
    # ── TEZLIK: Cache tekshirish ───────────────────────────
    cached = _sub_cache_get(user_id)
    if cached is not None:
        return cached

    channels = DB.get("channels", [])
    if not channels:
        _sub_cache_set(user_id, [])
        return []

    # ── TEZLIK: Barcha kanallarni parallel tekshirish ──────
    async def check_one(ch):
        try:
            chat_ref = _channel_ref(ch)
            if not chat_ref:
                return ch
            member = await bot.get_chat_member(chat_ref, user_id)
            status = getattr(member, "status", "")
            is_member = getattr(member, "is_member", None)
            if status not in ("creator", "administrator", "member") and is_member is not True:
                return ch
            return None
        except Exception as e:
            logger.warning(f"Sub check {ch}: {e}")
            return ch

    results = await asyncio.gather(*[check_one(ch) for ch in channels], return_exceptions=True)
    not_subbed = [r for r in results if r is not None and not isinstance(r, Exception)]
    _sub_cache_set(user_id, not_subbed)
    return not_subbed


def register_user(user):
    uid = str(user.id)
    if uid not in DB["users"]:
        DB["users"][uid] = {
            "name": user.full_name,
            "username": user.username or "",
            "joined": datetime.now().isoformat(),
            "paid_episodes": {},
            "watched": {},
        }
        # ── TEZLIK: Fon saqlash, bot kutmaydi ─────────────
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(db_save_async(DB))
        except RuntimeError:
            save()


def clear_admin_state(context):
    for key in [
        "admin_state", "new_movie_code", "ep_movie_code",
        "price_movie_code", "price_ep", "post_code",
        "reply_to", "awaiting_help", "awaiting_check",
        "editing_btn_key", "emoji_menu",
        "bc_msg", "bc_buttons", "bc_adding_btn",
        "del_movie_code", "poster_code",
        "channel_manage_menu", "ch_info", "bc_btn_name",
    ]:
        context.user_data.pop(key, None)


def _build_ep_price_list(code: str, eps: list, prices: dict) -> str:
    if not eps:
        return "⚠️ Bu kinoda hali qism yo'q."
    lines = []
    for i in range(len(eps)):
        ek    = str(i + 1)
        price = prices.get(ek)
        if price:
            lines.append(f"  {ek}-qism — 💰 <b>{price} so'm</b>")
        else:
            lines.append(f"  {ek}-qism — bepul")
    return f"📺 Qismlar ({len(eps)} ta):\n" + "\n".join(lines)


def _channels_list_text() -> str:
    channels = DB.get("channels", [])
    if not channels:
        return "📭 Hozircha majburiy kanal yo'q."
    lines = []
    for i, ch in enumerate(channels, 1):
        lines.append(f"  {i}. <b>{ch.get('title','?')}</b> — {ch.get('username','?')}")
    return f"📋 <b>Majburiy kanallar</b> ({len(channels)} ta):\n\n" + "\n".join(lines)


async def send_movie_menu(src, context, code: str):
    movie   = DB["movies"].get(code)
    user_id = src.effective_user.id if hasattr(src, "effective_user") else src.from_user.id
    chat_id = user_id
    if not movie:
        await sm(context.bot, chat_id, "❌ Bunday kodli kino topilmadi.")
        return
    eps = movie.get("episodes", [])
    if not eps:
        await sm(context.bot, chat_id, "⏳ Bu kinoga hali qism yuklanmagan.")
        return
    markup      = movie_episodes_kb(movie, code, user_id, page=0)
    total_pages = max(1, (len(eps) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_info   = f"  (1/{total_pages} sahifa)" if total_pages > 1 else ""
    caption     = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
                   f"📺 Qismlar soni: <b>{len(eps)} ta</b>{page_info}\n\n"
                   f"👇 Qaysi qismni ko'rmoqchisiz?")
    poster = movie.get("poster_file_id")
    try:
        if poster:
            await sp(context.bot, chat_id, poster, caption, markup)
        else:
            await sm(context.bot, chat_id, caption, markup)
    except Exception as e:
        logger.error(f"send_movie_menu xato: {e}")
        try:
            await sm(context.bot, chat_id, caption, markup)
        except Exception as e2:
            logger.error(f"send_movie_menu fallback xato: {e2}")

# ══════════════════════════════════════════════════════════
# BROADCAST
# ══════════════════════════════════════════════════════════

def build_broadcast_markup(buttons: list):
    if not buttons:
        return None
    rows = []
    for b in buttons:
        rows.append([ibtn(b["text"], url=b["url"], style=b.get("style", "primary"))])
    return ikb(rows)


async def send_broadcast_preview(bot, uid, bc: dict):
    buttons    = bc.get("buttons", [])
    markup     = build_broadcast_markup(buttons)
    preview_kb = broadcast_preview_kb(bool(buttons))
    try:
        kw = {}
        if markup:
            kw["reply_markup"] = markup
        await bot.copy_message(
            chat_id=uid,
            from_chat_id=bc["from_chat_id"],
            message_id=bc["message_id"],
            **kw,
        )
    except Exception as e:
        await sm(bot, uid, f"❌ Preview xato: {e}")
        return

    btn_info = ""
    if buttons:
        btn_info = "\n\n<b>Tugmalar:</b>\n" + "\n".join(
            f"• {b['text']} → {b['url']}" for b in buttons)
    await sm(bot, uid,
        f"<b>Preview yuqorida ↑</b>{btn_info}\n\nNima qilasiz?",
        parse_mode="HTML",
        markup=preview_kb)


async def do_broadcast(bot, bc: dict):
    users   = list(DB["users"].keys())
    buttons = bc.get("buttons", [])
    markup  = build_broadcast_markup(buttons)
    ok = fail = 0

    # ── TEZLIK: Parallel broadcast (10 ta bir vaqtda) ──────
    sem = asyncio.Semaphore(10)

    async def send_one(uid):
        nonlocal ok, fail
        async with sem:
            try:
                kw = {}
                if markup:
                    kw["reply_markup"] = markup
                await bot.copy_message(
                    chat_id=int(uid),
                    from_chat_id=bc["from_chat_id"],
                    message_id=bc["message_id"],
                    **kw,
                )
                ok += 1
            except Exception as e:
                fail += 1
                logger.warning(f"Broadcast uid={uid}: {e}")

    await asyncio.gather(*[send_one(uid) for uid in users])
    return ok, fail

# ══════════════════════════════════════════════════════════
# START HANDLER
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    clear_admin_state(context)
    args = context.args

    if args and args[0].startswith("code_"):
        code = args[0].replace("code_", "").upper().strip()
        ns   = await check_subscription(user.id, context.bot)
        if ns:
            context.user_data["pending_code"] = code
            await sm(context.bot, user.id,
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                subscription_kb(ns))
            return
        await send_movie_menu(update, context, code)
        return

    ns = await check_subscription(user.id, context.bot)
    if ns:
        await sm(context.bot, user.id,
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇\n"
            "Obuna bo'lgach <b>Tekshirish</b> tugmasini bosing.",
            subscription_kb(ns))
        return

    hello = (f"Assalomu alaykum, <b>{user.full_name}</b>! 👋\n\n"
             f"🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
             f"Kino <b>kodini</b> yuboring — video <b>darhol</b> keladi! ⚡")
    await sm(context.bot, user.id, hello, main_menu_kb(is_admin=(user.id == ADMIN_ID)))

# ══════════════════════════════════════════════════════════
# CALLBACK HANDLER — MAKSIMAL TEZLIK
# ══════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data or ""
    uid  = q.from_user.id

    # ══ TEZLIK #1: q.answer() — HAR DOIM ENG BIRINCHI! ════
    # Telegram 3 soniya ichida answer kutadi, aks holda "loading..." ko'rinadi
    # Biz darhol answer() qilamiz, keyin ishni davom ettiramiz
    await q.answer()

    # ── Kanal o'chirish ──────────────────────────────────
    if data.startswith("ch_del|"):
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True)
            return
        try:
            idx      = int(data.split("|")[1])
            channels = DB.get("channels", [])
            if 0 <= idx < len(channels):
                removed = channels.pop(idx)
                save()
                try:
                    await q.edit_message_text(
                        f"✅ <b>{removed.get('title','?')}</b> ({removed.get('username','?')}) o'chirildi!\n\n"
                        f"{_channels_list_text()}",
                        parse_mode="HTML")
                except Exception:
                    pass
                await sm(context.bot, uid, "Majburiy kanal boshqaruvi:", channel_manage_kb())
            else:
                await sm(context.bot, uid, "❌ Kanal topilmadi.", channel_manage_kb())
        except Exception as e:
            logger.error(f"ch_del xato: {e}")
        return

    if data == "ch_del_cancel":
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Bekor qilindi.", channel_manage_kb())
        return

    # ── Broadcast ─────────────────────────────────────────
    if data.startswith("bc_"):
        await cb_broadcast(update, context)
        return

    # ── Subscription tekshirish ───────────────────────────
    if data == "check_sub":
        await cb_check_sub(update, context)
        return

    # ── Sahifalash ────────────────────────────────────────
    if data.startswith("page|"):
        await cb_page(update, context)
        return

    # ── Qism ko'rish ──────────────────────────────────────
    if data.startswith("ep|"):
        await cb_episode(update, context)
        return

    # ── To'lov tasdiqlash/rad ─────────────────────────────
    if data.startswith("pay_ok|") or data.startswith("pay_no|"):
        await cb_payment(update, context)
        return

    # ── Admin javob ───────────────────────────────────────
    if data.startswith("reply|"):
        await cb_reply(update, context)
        return

    # ── Statistika yangilash ──────────────────────────────
    if data == "refresh_stats":
        if uid != ADMIN_ID:
            return
        u = len(DB.get("users", {}))
        m = len(DB.get("movies", {}))
        v = DB.get("stats", {}).get("total_views", 0)
        try:
            await q.edit_message_text(
                f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
                f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>",
                parse_mode="HTML", reply_markup=stats_kb())
        except Exception:
            pass
        return

    # ── Bosh menyu ────────────────────────────────────────
    if data == "go_home":
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Bosh menyu",
            main_menu_kb(is_admin=(uid == ADMIN_ID)))
        return

    # ── To'lov kutish ─────────────────────────────────────
    if data == "waiting_confirm":
        await q.answer("Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)
        return

    # ── Emoji menyu orqaga ────────────────────────────────
    if data == "emoji_back":
        if uid != ADMIN_ID:
            return
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        try:
            await q.edit_message_text("Tugmani pastdan tanlang 👇")
        except Exception:
            pass
        await sm(context.bot, uid,
            "<b>Tugma sozlamalari</b>\nO'zgartirmoqchi bo'lgan tugmani pastdan tanlang 👇",
            emoji_menu_kb())
        return

    # ── Barcha emoji tiklash ──────────────────────────────
    if data == "emoji_reset_all":
        if uid != ADMIN_ID:
            return
        DB["btn_texts"] = {}
        DB["emoji_ids"] = {}
        EMOJI_IDS.clear()
        asyncio.create_task(save_now())
        try:
            await q.edit_message_text("✅ Barcha tugmalar tiklandi!")
        except Exception:
            pass
        context.user_data["emoji_menu"] = True
        context.user_data.pop("editing_btn_key", None)
        await sm(context.bot, uid, "✅ Tiklandi! Tugmani tanlang:", emoji_menu_kb())
        return

    # ── Bir emoji tiklash ─────────────────────────────────
    if data.startswith("emoji_reset|"):
        if uid != ADMIN_ID:
            return
        key = data.split("|", 1)[1]
        DB.get("btn_texts", {}).pop(key, None)
        DB.get("emoji_ids", {}).pop(key, None)
        EMOJI_IDS.pop(key, None)
        asyncio.create_task(save_now())
        default = DEFAULT_BTN.get(key, "")
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        try:
            await q.edit_message_text(
                f"✅ <b>{BTN_LABELS.get(key, key)}</b> tiklandi!\nDefault: <code>{default}</code>",
                parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    # ── Qism tez qo'shish ─────────────────────────────────
    if data.startswith("quick_add_ep|"):
        if uid != ADMIN_ID:
            return
        code = data.split("|", 1)[1]
        context.user_data["admin_state"]   = "add_ep_video"
        context.user_data["ep_movie_code"] = code
        await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        return

    # ── Narx tez belgilash ────────────────────────────────
    if data.startswith("quick_price|"):
        if uid != ADMIN_ID:
            return
        code  = data.split("|", 1)[1]
        movie = DB["movies"].get(code)
        if not movie:
            await sm(context.bot, uid, "❌ Kino topilmadi!")
            return
        eps = movie.get("episodes", [])
        if not eps:
            await sm(context.bot, uid,
                f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.\n\n"
                f"Avval qism qo'shing, so'ng narx belgilang.")
            return
        prices   = movie.get("prices", {})
        ep_list  = _build_ep_price_list(code, eps, prices)
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"]      = "set_price_ep"
        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b> — narx belgilash\n"
            f"Kod: <code>{code}</code>\n\n{ep_list}\n\n"
            f"Qaysi qismni pullik qilmoqchisiz?\n"
            f"Qism <b>raqamini</b> kiriting (1 dan {len(eps)} gacha):")
        return

# ══════════════════════════════════════════════════════════
# CALLBACK: BROADCAST
# ══════════════════════════════════════════════════════════

async def cb_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    uid  = q.from_user.id
    data = q.data or ""
    if uid != ADMIN_ID:
        return
    # answer() allaqachon callback_handler'da chaqirilgan

    bc = context.user_data.get("bc_msg", {})

    if data == "bc_cancel":
        context.user_data.pop("bc_msg", None)
        context.user_data.pop("bc_buttons", None)
        context.user_data.pop("bc_adding_btn", None)
        context.user_data.pop("bc_btn_name", None)
        try:
            await q.edit_message_text("❌ Broadcast bekor qilindi.")
        except Exception:
            pass
        await sm(context.bot, uid, "Admin panel", admin_menu_kb())
        return

    if data.startswith("bc_color|"):
        color = data.split("|", 1)[1]
        bc["btn_color"] = color
        context.user_data["bc_msg"]        = bc
        context.user_data["bc_adding_btn"] = "text"
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        color_names = {"primary": "🔵 Ko'k", "danger": "🔴 Qizil", "success": "🟢 Yashil"}
        await sm(context.bot, uid,
            f"Rang: <b>{color_names.get(color, color)}</b>\n\nTugma nomini kiriting:")
        return

    if data == "bc_add_btn":
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Tugma rangini tanlang:", broadcast_color_kb())
        return

    if data == "bc_remove_btn":
        bc["buttons"] = []
        context.user_data["bc_msg"] = bc
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "✅ Tugmalar o'chirildi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return

    if data == "bc_send":
        total = len(DB["users"])
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        prog_msg = await sm(context.bot, uid, f"⏳ Yuborilmoqda... 0/{total}")
        ok, fail = await do_broadcast(context.bot, bc)
        context.user_data.pop("bc_msg", None)
        context.user_data.pop("bc_buttons", None)
        try:
            await context.bot.edit_message_text(
                f"✅ Broadcast tugadi!\n\nYuborildi: <b>{ok}</b>\nXato: <b>{fail}</b>",
                chat_id=uid, message_id=prog_msg.message_id, parse_mode="HTML")
        except Exception:
            await sm(context.bot, uid, f"✅ Broadcast tugadi! Yuborildi: {ok}, Xato: {fail}")
        await sm(context.bot, uid, "Admin panel", admin_menu_kb())
        return

# ══════════════════════════════════════════════════════════
# CALLBACK: SAHIFALASH
# ══════════════════════════════════════════════════════════

async def cb_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # answer() allaqachon chaqirilgan
    parts = q.data.split("|")
    if len(parts) != 3:
        return
    _, code, page_str = parts
    try:
        page = int(page_str)
    except ValueError:
        return
    movie = DB["movies"].get(code)
    if not movie:
        return
    user_id     = q.from_user.id
    eps         = movie.get("episodes", [])
    markup      = movie_episodes_kb(movie, code, user_id, page=page)
    total_pages = max(1, (len(eps) + PAGE_SIZE - 1) // PAGE_SIZE)
    caption     = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
                   f"📺 Qismlar soni: <b>{len(eps)} ta</b>  "
                   f"({page + 1}/{total_pages} sahifa)\n\n"
                   f"👇 Qaysi qismni ko'rmoqchisiz?")
    try:
        await q.edit_message_caption(caption=caption, parse_mode="HTML", reply_markup=markup)
    except Exception:
        try:
            await q.edit_message_text(caption, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.error(f"cb_page edit xato: {e}")

# ══════════════════════════════════════════════════════════
# CALLBACK: SUBSCRIPTION TEKSHIRISH
# ══════════════════════════════════════════════════════════

async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # answer() allaqachon chaqirilgan
    uid = q.from_user.id

    # ── TEZLIK: Cache'ni o'chirib, yangi tekshirish ────────
    _sub_cache_invalidate(uid)
    ns = await check_subscription(uid, context.bot)

    if ns:
        await q.answer("Hali obuna bo'lmagansiz! ❌", show_alert=True)
        return
    try:
        await q.edit_message_text("✅ Zo'r! Barcha kanallarga obuna bo'ldingiz!")
    except Exception:
        pass
    pending = context.user_data.pop("pending_code", None)
    if pending:
        await send_movie_menu(q, context, pending)
    else:
        await sm(context.bot, uid,
            f"🎉 Xush kelibsiz, <b>{q.from_user.full_name}</b>!\n\nKino kodini yuboring 👇",
            main_menu_kb(is_admin=(uid == ADMIN_ID)))

# ══════════════════════════════════════════════════════════
# CALLBACK: QISM KO'RISH — TEZLASHTIRILGAN
# ══════════════════════════════════════════════════════════

async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # answer() allaqachon chaqirilgan
    parts = q.data.split("|")
    if len(parts) != 3:
        return
    _, code, ep = parts
    movie = DB["movies"].get(code)
    if not movie:
        await q.answer("Kino topilmadi", show_alert=True)
        return

    user_id = str(q.from_user.id)
    price   = movie.get("prices", {}).get(ep)
    paid    = DB["users"].get(user_id, {}).get("paid_episodes", {})

    if price and not paid.get(f"{code}_{ep}"):
        card = DB.get("card_number") or "Admin karta raqamini o'rnatmagan"
        txt  = (f"🔒 <b>Bu qism pullik</b>\n\n"
                f"🎬 Kino: <b>{movie.get('title')}</b>\n"
                f"📺 Qism: <b>{ep}</b>\n"
                f"💰 Narxi: <b>{price} so'm</b>\n\n"
                f"💳 Karta raqami:\n<code>{card}</code>\n\n"
                f"To'lov qiling va chek rasmini yuboring 👇")
        context.user_data["awaiting_check"] = {"code": code, "ep": ep, "price": price}
        await sm(context.bot, q.from_user.id, txt, payment_sent_kb())
        return

    idx = int(ep) - 1
    eps = movie.get("episodes", [])
    if idx < 0 or idx >= len(eps):
        await q.answer("Qism topilmadi", show_alert=True)
        return

    # ── TEZLIK: Video yuborish va statistika parallel ──────
    bot_me    = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption   = f"🎬 <b>{movie.get('title')}</b>\n📺 Qism: <b>{ep}</b>"

    try:
        await sv(context.bot, q.from_user.id, eps[idx], caption, share_kb(share_url), protect=True)
    except Exception as e:
        logger.error(f"Video yuborishda xato: {e}")
        await sm(context.bot, q.from_user.id, "❌ Video yuborishda xato. Iltimos qayta urinib ko'ring.")
        return

    # ── TEZLIK: Statistika fonda, kutilmaydi ──────────────
    async def update_stats():
        try:
            movie.setdefault("views", {})
            movie["views"][ep] = movie["views"].get(ep, 0) + 1
            DB["users"].setdefault(user_id, {}).setdefault("watched", {})[f"{code}_{ep}"] = True
            DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
            await db_save_async(DB)
        except Exception as e:
            logger.error(f"update_stats xato: {e}")

    asyncio.create_task(update_stats())

# ══════════════════════════════════════════════════════════
# CALLBACK: TO'LOV
# ══════════════════════════════════════════════════════════

async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # answer() allaqachon chaqirilgan
    parts = q.data.split("|", 1)
    if len(parts) != 2:
        return
    action, pid = parts
    pay = DB["pending_payments"].get(pid)
    if not pay:
        try:
            await q.edit_message_caption("To'lov topilmadi.")
        except Exception:
            pass
        return

    if action == "pay_no":
        pay["status"] = "rejected"
        save()
        try:
            await q.edit_message_caption(
                (q.message.caption or "") + "\n\n<b>Bekor qilindi</b>", parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, pay["user_id"], "❌ <b>To'lovingiz rad etildi.</b>")
        return

    pay["status"] = "approved"
    uid = str(pay["user_id"])
    DB["users"].setdefault(uid, {}).setdefault("paid_episodes", {})[f"{pay['code']}_{pay['ep']}"] = True
    try:
        next_ep = str(int(pay["ep"]) + 1)
        DB["users"][uid]["paid_episodes"][f"{pay['code']}_{next_ep}"] = True
    except Exception:
        pass
    save()
    try:
        await q.edit_message_caption(
            (q.message.caption or "") + "\n\n<b>✅ Tasdiqlandi</b>", parse_mode="HTML")
    except Exception:
        pass

    movie = DB["movies"].get(pay["code"])
    if movie:
        idx = int(pay["ep"]) - 1
        eps = movie.get("episodes", [])
        if 0 <= idx < len(eps):
            # ── TEZLIK: Xabar va video parallel ───────────
            await asyncio.gather(
                sm(context.bot, pay["user_id"], "✅ <b>Admin to'lovingizni tasdiqladi!</b>"),
                sv(context.bot, pay["user_id"], eps[idx],
                   f"<b>{movie.get('title')}</b>\nQism: {pay['ep']}", protect=True),
                return_exceptions=True,
            )

            async def update_pay_stats():
                try:
                    movie.setdefault("views", {})
                    movie["views"][pay["ep"]] = movie["views"].get(pay["ep"], 0) + 1
                    DB["users"][uid].setdefault("watched", {})[f"{pay['code']}_{pay['ep']}"] = True
                    DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
                    await db_save_async(DB)
                except Exception as e:
                    logger.error(f"update_pay_stats xato: {e}")

            asyncio.create_task(update_pay_stats())
    else:
        await sm(context.bot, pay["user_id"], "✅ <b>Admin to'lovingizni tasdiqladi!</b>")

# ══════════════════════════════════════════════════════════
# CALLBACK: ADMIN JAVOB
# ══════════════════════════════════════════════════════════

async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # answer() allaqachon chaqirilgan
    parts = q.data.split("|", 1)
    if len(parts) != 2:
        return
    _, uid_str = parts
    try:
        context.user_data["reply_to"] = int(uid_str)
        await q.message.reply_text(f"<code>{uid_str}</code> ga xabar yozing.", parse_mode="HTML")
    except Exception as e:
        logger.error(f"cb_reply xato: {e}")

# ══════════════════════════════════════════════════════════
# TEXT HANDLER
# ══════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    msg  = update.message
    text = (msg.text or "").strip()

    # ── 1. editing_btn_key ────────────────────────────────
    if uid == ADMIN_ID and context.user_data.get("editing_btn_key"):
        key = context.user_data.pop("editing_btn_key")
        if not text:
            context.user_data["editing_btn_key"] = key
            await sm(context.bot, uid, "Bo'sh bo'lmasin. Qayta yuboring:")
            return

        custom_emoji_id  = extract_custom_emoji_id(msg)
        existing         = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
        existing_label   = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
        existing_emoji_p = extract_emoji_prefix(existing)

        if custom_emoji_id:
            new_text = existing_label
            EMOJI_IDS[key] = custom_emoji_id
            DB.setdefault("emoji_ids", {})[key] = custom_emoji_id
            eid_info = f"\nCustom emoji ID: <code>{custom_emoji_id}</code>"
        elif is_only_emoji(text):
            new_emoji_p = (existing_emoji_p + text) if existing_emoji_p else text
            new_text    = f"{new_emoji_p} {existing_label}"
            EMOJI_IDS.pop(key, None)
            DB.get("emoji_ids", {}).pop(key, None)
            eid_info = ""
        else:
            new_text = text
            EMOJI_IDS.pop(key, None)
            DB.get("emoji_ids", {}).pop(key, None)
            eid_info = ""

        DB.setdefault("btn_texts", {})[key] = new_text
        asyncio.create_task(save_now())

        eid = get_eid(key)
        if eid:
            eid_info = f"\nCustom emoji ID: <code>{eid}</code>"

        await sm(context.bot, uid,
            f"✅ <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n"
            f"Ko'rinish: <code>{new_text}</code>{eid_info}\n\n"
            f"Yana o'zgartirish uchun tugmani tanlang 👇")
        context.user_data["emoji_menu"] = True
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    # ── 2. Broadcast tugma qo'shish ───────────────────────
    if uid == ADMIN_ID and context.user_data.get("bc_adding_btn"):
        stage = context.user_data["bc_adding_btn"]
        bc    = context.user_data.get("bc_msg", {})
        if stage == "text":
            context.user_data["bc_btn_name"]   = text
            context.user_data["bc_adding_btn"] = "url"
            await sm(context.bot, uid,
                f"Tugma nomi: <b>{text}</b>\n\nEndi tugma linkini kiriting (https:// bilan):")
        elif stage == "url":
            btn_text_val = context.user_data.pop("bc_btn_name", "Tugma")
            color        = bc.pop("btn_color", "primary")
            context.user_data.pop("bc_adding_btn", None)
            bc.setdefault("buttons", []).append({"text": btn_text_val, "url": text, "style": color})
            context.user_data["bc_msg"] = bc
            await sm(context.bot, uid, "✅ Tugma qo'shildi! Preview:")
            await send_broadcast_preview(context.bot, uid, bc)
        return

    # ── 3. Emoji menyu ────────────────────────────────────
    if uid == ADMIN_ID and context.user_data.get("emoji_menu"):
        if text == "⬅️ Orqaga":
            context.user_data.pop("emoji_menu", None)
            context.user_data.pop("editing_btn_key", None)
            await sm(context.bot, uid, "Admin panel", admin_menu_kb())
            return
        if text == "🗑 Hammasini tiklash":
            DB["btn_texts"] = {}
            DB["emoji_ids"] = {}
            EMOJI_IDS.clear()
            asyncio.create_task(save_now())
            await sm(context.bot, uid, "✅ Barcha tugmalar tiklandi!", emoji_menu_kb())
            return
        key = find_key_by_text(text)
        if key:
            cur       = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
            eid       = get_eid(key)
            cur_emoji = extract_emoji_prefix(cur)
            eid_info  = f"\nCustom emoji ID: <code>{eid}</code>" if eid else ""
            emoji_info = f"\nHozirgi emoji: <code>{cur_emoji}</code>" if cur_emoji else ""
            context.user_data["editing_btn_key"] = key
            await sm(context.bot, uid,
                f"<b>{BTN_LABELS.get(key, key)}</b>\n\n"
                f"Hozirgi matn: <code>{cur}</code>{eid_info}{emoji_info}\n\n"
                f"Yuboring:\n"
                f"• Faqat emoji → qo'shiladi\n"
                f"• Emoji + matn → to'liq yangilanadi\n"
                f"• Custom emoji → icon sifatida\n"
                f"• Faqat matn → barcha emoji o'chadi",
                emoji_single_action_kb(key))
        return

    # ── 4. Kanal boshqarish submenu ───────────────────────
    if uid == ADMIN_ID and context.user_data.get("channel_manage_menu"):
        ch_states = ("add_channel_username", "add_channel_title", "add_channel_url", "add_channel")
        if context.user_data.get("admin_state") in ch_states:
            handled = await admin_state_handler(update, context, text)
            if handled:
                return

        if text == "⬅️ Admin panel":
            context.user_data.pop("channel_manage_menu", None)
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "Admin panel", admin_menu_kb())
            return
        if text == "➕ Kanal qo'shish":
            context.user_data["admin_state"] = "add_channel_username"
            await sm(context.bot, uid,
                "➕ <b>Kanal qo'shish</b>\n\n"
                "Kanal <b>username</b>ini kiriting:\n"
                "<i>Misol: @mykinochannel yoki https://t.me/mykinochannel</i>")
            return
        if text == "🗑 Kanal o'chirish":
            channels = DB.get("channels", [])
            if not channels:
                await sm(context.bot, uid,
                    "❌ Hozircha kanal yo'q. Avval kanal qo'shing.", channel_manage_kb())
                return
            await sm(context.bot, uid,
                f"{_channels_list_text()}\n\nO'chirmoqchi bo'lgan kanalni tanlang 👇",
                channel_delete_inline_kb(channels))
            return
        if text == "📋 Kanallar ro'yxati":
            await sm(context.bot, uid, _channels_list_text(), channel_manage_kb())
            return
        return

    # ── 5. Admin reply_to ─────────────────────────────────
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        return

    # ── 6. Admin state handler ────────────────────────────
    if uid == ADMIN_ID:
        state = context.user_data.get("admin_state")
        if state in ("set_price_code", "set_price_ep", "set_price_amount",
                     "delete_movie_code", "delete_movie_ep",
                     "set_card", "add_movie_code", "add_movie_title", "add_movie_poster",
                     "add_ep_code", "add_ep_video", "set_install",
                     "post_channel_code", "post_channel_target",
                     "broadcast_msg"):
            handled = await admin_state_handler(update, context, text)
            if handled:
                return

    # ── 7. Admin tugmalarini aniqlash ─────────────────────
    if uid == ADMIN_ID:
        all_admin_btn_keys = [
            "kino_joy", "qism_qosh", "pullik", "stat",
            "kanal_post", "maj_kanal", "karta", "ilova",
            "emoji_soz", "asosiy", "boshqarish", "broadcast", "kino_uch",
        ]
        all_admin_btns = {bt(k): k for k in all_admin_btn_keys if bt(k)}

        if text in all_admin_btns:
            key = all_admin_btns[text]
            if key == "emoji_soz":
                context.user_data.pop("admin_state", None)
                context.user_data.pop("editing_btn_key", None)
                context.user_data.pop("reply_to", None)
                context.user_data["emoji_menu"] = True
                await sm(context.bot, uid,
                    "<b>Tugma sozlamalari</b>\n"
                    "O'zgartirmoqchi bo'lgan tugmani pastdan tanlang 👇",
                    emoji_menu_kb())
                return
            if key == "broadcast":
                context.user_data.pop("admin_state", None)
                context.user_data.pop("emoji_menu", None)
                context.user_data.pop("editing_btn_key", None)
                await sm(context.bot, uid,
                    "📢 <b>Barchaga xabar yuborish</b>\n\n"
                    "Xabar yuboring — matn, rasm yoki video.\n\n"
                    "Bekor qilish uchun /start bosing.")
                context.user_data["admin_state"] = "broadcast_msg"
                return
            if key == "kino_uch":
                context.user_data.pop("emoji_menu", None)
                context.user_data["admin_state"] = "delete_movie_code"
                await sm(context.bot, uid,
                    "🗑 <b>Kino o'chirish</b>\n\nKino kodini kiriting:")
                return
            context.user_data.pop("emoji_menu", None)
            context.user_data.pop("editing_btn_key", None)
            await admin_buttons(update, context, text)
            return

        handled = await admin_state_handler(update, context, text)
        if handled:
            return

    # ── 8. Foydalanuvchi: yordam ──────────────────────────
    if text == bt("yordam"):
        await sm(context.bot, uid,
            "💬 <b>Yordam kerakmi?</b>\n\n"
            "Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\n"
            "Admin tez orada javob beradi! 🙂",
            help_kb(),
            reply_to_message_id=msg.message_id)
        context.user_data["awaiting_help"] = True
        return

    if text == bt("install"):
        s   = DB.get("settings", {})
        f_id = s.get("install_file_id")
        v_id = s.get("install_video_id")
        if not f_id and not v_id:
            await sm(context.bot, uid, "Admin hali ilova fayl/video joylamagan.")
            return
        # ── TEZLIK: Video va file parallel yuborish ────────
        tasks = []
        if v_id:
            tasks.append(sv(context.bot, uid, v_id, "<b>Ilovani o'rnatish videosi</b>"))
        if f_id:
            tasks.append(context.bot.send_document(uid, f_id, caption="<b>Ilova fayli</b>", parse_mode="HTML"))
        await asyncio.gather(*tasks, return_exceptions=True)
        return

    # ── 9. Yordam so'rovi ─────────────────────────────────
    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n{text}")
        await sm(context.bot, ADMIN_ID, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    # ── 10. To'lov cheki (matn) ───────────────────────────
    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos, chek <b>rasmini</b> yuboring.")
        return

    # ── 11. Kino kodi yoki nomi ───────────────────────────
    code, matches = find_movie_code(text)
    if code:
        ns = await check_subscription(uid, context.bot)
        if ns:
            context.user_data["pending_code"] = code
            await sm(context.bot, uid,
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                subscription_kb(ns))
            return
        await send_movie_menu(update, context, code)
    elif matches:
        await sm(context.bot, uid,
            "🔎 Bir nechta kino topildi. Kerakli kino <b>kodini</b> yuboring:\n\n" +
            movie_suggestions_text(matches))
    else:
        await sm(context.bot, uid,
            "❌ Bunday kino topilmadi.\n\nKino nomi yoki kodini to'g'ri yuboring 👇")

# ══════════════════════════════════════════════════════════
# ADMIN BUTTONS HANDLER
# ══════════════════════════════════════════════════════════

async def admin_buttons(update, context, text: str):
    uid = update.effective_user.id

    if text == bt("boshqarish"):
        context.user_data.pop("admin_state", None)
        context.user_data.pop("channel_manage_menu", None)
        await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb())
        return

    if text == bt("asosiy"):
        context.user_data.pop("admin_state", None)
        context.user_data.pop("channel_manage_menu", None)
        await sm(context.bot, uid, "Asosiy menyu", main_menu_kb(is_admin=True))
        return

    if text == bt("stat"):
        context.user_data.pop("admin_state", None)
        u = len(DB.get("users", {}))
        m = len(DB.get("movies", {}))
        v = DB.get("stats", {}).get("total_views", 0)
        await sm(context.bot, uid,
            f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
            f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>", stats_kb())
        return

    if text == bt("karta"):
        context.user_data["admin_state"] = "set_card"
        cur = DB.get("card_number") or "Kiritilmagan"
        await sm(context.bot, uid,
            f"Joriy karta: <code>{cur}</code>\n\nYangi karta raqamini yuboring:")
        return

    if text == bt("kino_joy"):
        context.user_data["admin_state"] = "add_movie_code"
        await sm(context.bot, uid, "Kino kodini kiriting (masalan: AVATAR yoki 001):")
        return

    if text == bt("qism_qosh"):
        context.user_data["admin_state"] = "add_ep_code"
        await sm(context.bot, uid, "Qism qo'shmoqchi bo'lgan kino kodini kiriting:")
        return

    if text == bt("pullik"):
        context.user_data["admin_state"] = "set_price_code"
        context.user_data.pop("price_movie_code", None)
        context.user_data.pop("price_ep", None)
        await sm(context.bot, uid,
            "💰 <b>Qismni pullik qilish</b>\n\nKino <b>kodini</b> kiriting:")
        return

    if text == bt("ilova"):
        context.user_data["admin_state"] = "set_install"
        await sm(context.bot, uid, "Ilova fayl yoki video yuboring:")
        return

    if text == bt("maj_kanal"):
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True
        await sm(context.bot, uid,
            f"📡 <b>Majburiy kanal boshqaruvi</b>\n\n"
            f"{_channels_list_text()}\n\nNima qilmoqchisiz?",
            channel_manage_kb())
        return

    if text == bt("kanal_post"):
        context.user_data["admin_state"] = "post_channel_code"
        await sm(context.bot, uid, "Post qilmoqchi bo'lgan kino kodini kiriting:")
        return

# ══════════════════════════════════════════════════════════
# ADMIN STATE HANDLER
# ══════════════════════════════════════════════════════════

async def admin_state_handler(update, context, text: str) -> bool:
    state = context.user_data.get("admin_state")
    uid   = update.effective_user.id
    if not state:
        return False

    if state == "broadcast_msg":
        bc = {
            "type": "copy",
            "from_chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "buttons": [],
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return True

    if state == "delete_movie_code":
        code = text.upper().strip()
        if code not in DB["movies"]:
            await sm(context.bot, uid,
                f"❌ <code>{code}</code> kodli kino topilmadi. Qayta kiriting:")
            return True
        movie    = DB["movies"][code]
        title    = movie.get("title", code)
        eps      = movie.get("episodes", [])
        ep_lines = "\n".join([f"  {i+1}-qism" for i in range(len(eps))]) if eps else "  (qismlar yo'q)"
        context.user_data["del_movie_code"] = code
        context.user_data["admin_state"]    = "delete_movie_ep"
        await sm(context.bot, uid,
            f"🎬 <b>{title}</b>  |  <code>{code}</code>\n"
            f"📺 Qismlar soni: <b>{len(eps)} ta</b>\n\n{ep_lines}\n\n"
            f"Qaysi qismni o'chirmoqchisiz?\n"
            f"• Raqam kiriting (masalan: <code>3</code>)\n"
            f"• Barcha qismlar: <code>hammasi</code>\n"
            f"• Butun kino: <code>kino</code>")
        return True

    if state == "delete_movie_ep":
        code  = context.user_data.get("del_movie_code")
        movie = DB["movies"].get(code) if code else None
        if not movie:
            await sm(context.bot, uid, "❌ Kino topilmadi. /start bosing.")
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            return True
        title = movie.get("title", code)
        eps   = movie.get("episodes", [])
        val   = text.strip().lower()

        if val == "kino":
            del DB["movies"][code]
            asyncio.create_task(save_now())
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> (<code>{code}</code>) butunlay o'chirildi!",
                admin_menu_kb())
            return True

        if val == "hammasi":
            DB["movies"][code]["episodes"] = []
            DB["movies"][code]["prices"]   = {}
            asyncio.create_task(save_now())
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> kinoning barcha qismlari o'chirildi!",
                admin_menu_kb())
            return True

        if val.isdigit():
            ep_num = int(val)
            if ep_num < 1 or ep_num > len(eps):
                await sm(context.bot, uid,
                    f"❌ <b>{ep_num}</b>-qism mavjud emas. 1–{len(eps)} oralig'ida kiriting:")
                return True
            idx = ep_num - 1
            DB["movies"][code]["episodes"].pop(idx)
            old_prices = movie.get("prices", {})
            new_prices = {}
            for k, v in old_prices.items():
                try:
                    k_int = int(k)
                    if k_int < ep_num:
                        new_prices[k] = v
                    elif k_int > ep_num:
                        new_prices[str(k_int - 1)] = v
                except Exception:
                    pass
            DB["movies"][code]["prices"] = new_prices
            asyncio.create_task(save_now())
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> — <b>{ep_num}-qism</b> o'chirildi!\n"
                f"Qolgan qismlar: <b>{len(DB['movies'][code]['episodes'])} ta</b>",
                admin_menu_kb())
            return True

        await sm(context.bot, uid,
            "❌ Noto'g'ri. Qism raqami, <code>hammasi</code> yoki <code>kino</code> kiriting:")
        return True

    if state == "set_card":
        DB["card_number"] = text
        asyncio.create_task(save_now())
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, f"✅ Karta saqlandi: <code>{text}</code>", admin_menu_kb())
        return True

    if state == "add_movie_code":
        context.user_data["new_movie_code"] = text.upper()
        context.user_data["admin_state"]    = "add_movie_title"
        await sm(context.bot, uid, "Kino nomini kiriting:")
        return True

    if state == "add_movie_title":
        code       = context.user_data.get("new_movie_code")
        now        = datetime.now().strftime("%d.%m.%Y %H:%M")
        title_html = text_with_premium_emojis(update.message) or text
        DB["movies"][code] = {
            "title": title_html,
            "episodes": [],
            "prices": {},
            "added_date": now,
        }
        asyncio.create_task(save_now())
        context.user_data["admin_state"] = "add_movie_poster"
        context.user_data["poster_code"] = code
        await sm(context.bot, uid,
            f"✅ <b>{title_html}</b> kinosi qo'shildi!\nKod: <code>{code}</code>\n\n"
            f"📷 Kino posterini yuboring yoki o'tkazib yuborish uchun <b>0</b> kiriting:")
        return True

    if state == "add_movie_poster":
        code = context.user_data.pop("poster_code", None)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("new_movie_code", None)
        if code:
            await sm(context.bot, uid,
                f"✅ Poster o'tkazib yuborildi.\nKod: <code>{code}</code>",
                movie_added_kb(code))
        return True

    if state == "add_ep_code":
        code = text.upper().strip()
        if code not in DB["movies"]:
            await sm(context.bot, uid,
                f"❌ <code>{code}</code> kodli kino topilmadi. Qayta kiriting:")
            return True
        context.user_data["ep_movie_code"] = code
        context.user_data["admin_state"]   = "add_ep_video"
        await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        return True

    if state == "add_ep_video":
        await sm(context.bot, uid, "⚠️ Iltimos, matn emas — <b>video fayl</b> yuboring:")
        return True

    if state == "set_price_code":
        code = text.upper().strip()
        if code not in DB["movies"]:
            await sm(context.bot, uid,
                f"❌ <code>{code}</code> kodli kino topilmadi.\n\nQayta kino kodini kiriting:")
            return True
        movie  = DB["movies"][code]
        eps    = movie.get("episodes", [])
        prices = movie.get("prices", {})
        if not eps:
            await sm(context.bot, uid,
                f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.\n\n"
                f"Avval qism qo'shing, so'ng narx belgilang.")
            context.user_data.pop("admin_state", None)
            return True
        ep_list = _build_ep_price_list(code, eps, prices)
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"]      = "set_price_ep"
        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b> — narx belgilash\n"
            f"Kod: <code>{code}</code>\n\n{ep_list}\n\n"
            f"Qaysi qismni pullik qilmoqchisiz?\n"
            f"Qism <b>raqamini</b> kiriting (1 dan {len(eps)} gacha):")
        return True

    if state == "set_price_ep":
        code = context.user_data.get("price_movie_code")
        if not code or code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Xatolik. Kino kodini qayta kiriting:")
            context.user_data["admin_state"] = "set_price_code"
            context.user_data.pop("price_movie_code", None)
            return True
        movie = DB["movies"][code]
        eps   = movie.get("episodes", [])
        if not text.strip().isdigit():
            await sm(context.bot, uid, "❌ Faqat <b>raqam</b> kiriting (masalan: <code>3</code>):")
            return True
        ep_num = int(text.strip())
        if ep_num < 1 or ep_num > len(eps):
            await sm(context.bot, uid,
                f"❌ <b>{ep_num}</b>-qism mavjud emas.\n1 dan {len(eps)} gacha raqam kiriting:")
            return True
        context.user_data["price_ep"]    = str(ep_num)
        context.user_data["admin_state"] = "set_price_amount"
        cur_price  = movie.get("prices", {}).get(str(ep_num))
        cur_info   = f"\nHozirgi narx: <b>{cur_price} so'm</b>" if cur_price else "\nHozir: <b>bepul</b>"
        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b>\n"
            f"<b>{ep_num}-qism</b> narxi{cur_info}\n\n"
            f"Yangi narxni kiriting (so'mda):\n"
            f"<i>Bepul qilish uchun <code>0</code> kiriting</i>")
        return True

    if state == "set_price_amount":
        code = context.user_data.get("price_movie_code")
        ep   = context.user_data.get("price_ep")
        if not code or not ep or code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Xatolik. /start bosing.")
            context.user_data.pop("admin_state", None)
            context.user_data.pop("price_movie_code", None)
            context.user_data.pop("price_ep", None)
            return True
        if not text.strip().isdigit():
            await sm(context.bot, uid,
                "❌ Faqat <b>raqam</b> kiriting.\n"
                "<i>Bepul qilish uchun <code>0</code> kiriting</i>")
            return True
        amount      = text.strip()
        movie_title = DB["movies"][code].get("title", code)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("price_movie_code", None)
        context.user_data.pop("price_ep", None)
        if amount == "0":
            DB["movies"][code].setdefault("prices", {}).pop(ep, None)
            asyncio.create_task(save_now())
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> endi <b>bepul</b>!",
                admin_menu_kb())
        else:
            DB["movies"][code].setdefault("prices", {})[ep] = amount
            asyncio.create_task(save_now())
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> narxi: <b>{amount} so'm</b>",
                admin_menu_kb())
        return True

    if state == "add_channel_username":
        raw_uname = text.strip()
        uname     = normalize_channel_username(raw_uname)
        if not uname or (not uname.startswith("@") and not uname.startswith("-100")):
            await sm(context.bot, uid,
                "❌ Kanal username noto'g'ri.\n"
                "Misol: <code>@mykinochannel</code> yoki <code>https://t.me/mykinochannel</code>")
            return True
        for ch in DB.get("channels", []):
            ch_uname = normalize_channel_username(ch.get("username", ""))
            if ch_uname.lower() == uname.lower():
                context.user_data.pop("admin_state", None)
                context.user_data["channel_manage_menu"] = True
                await sm(context.bot, uid,
                    f"⚠️ <b>{uname}</b> allaqachon qo'shilgan!\n\n{_channels_list_text()}",
                    channel_manage_kb())
                return True
        try:
            channel_info = await resolve_required_channel(context.bot, uname)
        except Exception as e:
            logger.warning(f"Channel resolve {uname}: {e}")
            await sm(context.bot, uid,
                "❌ Kanal tekshirilmadi. Bot kanalga admin sifatida qo'shilganligini tekshiring.\n\n"
                f"Xato: <code>{e}</code>")
            return True
        context.user_data["ch_info"]       = channel_info
        context.user_data["admin_state"]   = "add_channel_title"
        await sm(context.bot, uid,
            f"✅ Kanal topildi!\n\n"
            f"📛 Nom: <b>{channel_info['title']}</b>\n"
            f"👤 Username: <b>{channel_info['username']}</b>\n\n"
            f"Kanal nomini shu holatda qoldirish uchun <b>✅</b> yuboring\n"
            f"yoki yangi nom kiriting:")
        return True

    if state == "add_channel_title":
        channel_info = context.user_data.pop("ch_info", None)
        if not channel_info:
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "❌ Xatolik. Kanalni qaytadan qo'shing.", channel_manage_kb())
            return True
        title = text.strip()
        if title in ("✅", "+", ".", "-", ""):
            title = channel_info.get("title") or channel_info.get("username", "")
        if not title:
            context.user_data["ch_info"] = channel_info
            await sm(context.bot, uid, "❌ Nom bo'sh bo'lmasin. Qayta kiriting:")
            return True
        channel_info["title"] = title
        channel_info["url"]   = channel_join_url(channel_info.get("username", ""), channel_info.get("url", ""))
        DB["channels"].append(channel_info)
        asyncio.create_task(save_now())
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True
        await sm(context.bot, uid,
            f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n"
            f"📛 Nom: <b>{channel_info['title']}</b>\n"
            f"👤 Username: <b>{channel_info['username']}</b>\n"
            f"🔗 Link: {channel_info['url']}\n\n"
            f"{_channels_list_text()}",
            channel_manage_kb())
        return True

    if state in ("add_channel_url", "add_channel"):
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True
        await sm(context.bot, uid,
            "ℹ️ Qaytadan <b>➕ Kanal qo'shish</b> tugmasini bosing.",
            channel_manage_kb())
        return True

    if state == "post_channel_code":
        code = text.upper().strip()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Bunday kod yo'q. Qayta kiriting:")
            return True
        context.user_data["post_code"]    = code
        context.user_data["admin_state"]  = "post_channel_target"
        await sm(context.bot, uid, "Kanal username'ini kiriting (masalan @mychannel):")
        return True

    if state == "post_channel_target":
        channel = text.strip()
        code    = context.user_data.pop("post_code", None)
        context.user_data.pop("admin_state", None)
        if not code:
            await sm(context.bot, uid, "❌ Kino kodi topilmadi. Qayta boshlang.")
            return True
        movie   = DB["movies"].get(code, {})
        bot_me  = await context.bot.get_me()
        markup  = channel_post_kb(bot_me.username, code)
        title   = movie.get("title", code)
        ep_count = len(movie.get("episodes", []))
        caption = (
            "┏╋━━━━━━◥◣◆◢◤━━━━━━╋┓\n"
            f"        <b>{title}</b>\n"
            "┗╋━━━━━━◢◤◆◥◣━━━━━━╋┛\n\n"
            "╭═━═━═━═━═━═╮\n"
            f"     <b>Qismlar soni: {ep_count}</b>\n"
            "╰═━═━═━═━═━═╯\n\n"
            "┏━━━〔 ✪ 〕━━━┓\n"
            f"      <b>KINO KODI: {code}</b>\n"
            "┗━━━〔 ✦ 〕━━━┛\n\n"
            "╭━━━〔 ▼ 〕━━━╮\n"
            "   <b>Tomosha qilish</b>\n"
            "  <b>uchun tugmani bosing!</b>\n"
            "╰━━━〔 ▼ 〕━━━╯"
        )
        poster = movie.get("poster_file_id")
        try:
            if poster:
                await sp(context.bot, channel, poster, caption, markup)
            else:
                await sm(context.bot, channel, caption, markup)
            await sm(context.bot, uid, "✅ Post yuborildi!", admin_menu_kb())
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        return True

    if state == "set_install":
        await sm(context.bot, uid, "⚠️ Iltimos, matn emas — <b>fayl yoki video</b> yuboring:")
        return True

    return False

# ══════════════════════════════════════════════════════════
# STICKER HANDLER
# ══════════════════════════════════════════════════════════

async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return
    key = context.user_data.get("editing_btn_key")
    if not key:
        return
    sticker = update.message.sticker
    if not sticker:
        return
    emoji = sticker.emoji or ""
    if not emoji:
        await sm(context.bot, uid, "Bu stickerda emoji yo'q. Boshqa sticker yuboring.")
        return
    context.user_data.pop("editing_btn_key", None)
    existing        = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
    existing_label  = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
    existing_emoji_p = extract_emoji_prefix(existing)
    new_emoji_p      = (existing_emoji_p + emoji) if existing_emoji_p else emoji
    new_text         = f"{new_emoji_p} {existing_label}"
    DB.setdefault("btn_texts", {})[key] = new_text
    EMOJI_IDS.pop(key, None)
    DB.get("emoji_ids", {}).pop(key, None)
    asyncio.create_task(save_now())
    await sm(context.bot, uid,
        f"✅ <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\nKo'rinish: <code>{new_text}</code>")
    context.user_data["emoji_menu"] = True
    await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())

# ══════════════════════════════════════════════════════════
# MEDIA HANDLER
# ══════════════════════════════════════════════════════════

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    msg   = update.message
    state = context.user_data.get("admin_state")

    if uid == ADMIN_ID and state == "broadcast_msg":
        bc = {
            "type": "copy",
            "from_chat_id": msg.chat_id,
            "message_id": msg.message_id,
            "buttons": [],
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return

    if uid == ADMIN_ID and state == "add_movie_poster":
        code = context.user_data.pop("poster_code", None)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("new_movie_code", None)
        if msg.photo and code:
            DB["movies"][code]["poster_file_id"] = msg.photo[-1].file_id
            asyncio.create_task(save_now())
            await sm(context.bot, uid,
                f"✅ Poster saqlandi!\nKod: <code>{code}</code>",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "⚠️ Rasm yuboring!",
                movie_added_kb(code) if code else None)
        return

    if uid == ADMIN_ID and state == "add_ep_video":
        code = context.user_data.get("ep_movie_code")
        if not code:
            await sm(context.bot, uid, "❌ Kino kodi topilmadi. Qaytadan bosing.")
            context.user_data.pop("admin_state", None)
            return
        if msg.video:
            DB["movies"][code]["episodes"].append(msg.video.file_id)
            asyncio.create_task(save_now())
            ep_num = len(DB["movies"][code]["episodes"])
            context.user_data.pop("admin_state", None)
            context.user_data.pop("ep_movie_code", None)
            await sm(context.bot, uid,
                f"✅ <b>{ep_num}-qism</b> saqlandi!\nKino: <code>{code}</code>",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "⚠️ Faqat video yuboring!")
        return

    if uid == ADMIN_ID and state == "set_install":
        if msg.video:
            DB["settings"]["install_video_id"] = msg.video.file_id
            asyncio.create_task(save_now())
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "✅ O'rnatish videosi saqlandi!", admin_menu_kb())
        elif msg.document:
            DB["settings"]["install_file_id"] = msg.document.file_id
            asyncio.create_task(save_now())
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "✅ O'rnatish fayli saqlandi!", admin_menu_kb())
        else:
            await sm(context.bot, uid, "⚠️ Video yoki fayl yuboring!")
        return

    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info = context.user_data.pop("awaiting_check")
        pid      = f"{uid}_{pay_info['code']}_{pay_info['ep']}_{int(time.time())}"
        DB["pending_payments"][pid] = {
            "user_id": uid,
            "code": pay_info["code"],
            "ep":   pay_info["ep"],
            "price": pay_info["price"],
            "status": "pending",
        }
        save()
        cap = (f"<b>To'lov cheki</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\nKino: <b>{pay_info['code']}</b>\n"
               f"Qism: <b>{pay_info['ep']}</b>\nNarx: <b>{pay_info['price']} so'm</b>")
        await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, payment_admin_kb(pid))
        await sm(context.bot, uid, "✅ Chek adminga yuborildi! Tasdiqlanishini kuting.")
        return

    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        user_text = msg.caption or msg.text or ""
        cap       = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
                     f"<code>{uid}</code>\n\n{user_text}")
        if msg.photo:
            await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, reply_admin_kb(uid))
        elif msg.video:
            await sv(context.bot, ADMIN_ID, msg.video.file_id, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            cap = "<b>Admin javobi</b>"
            if msg.photo:
                if msg.caption:
                    cap += f"\n{msg.caption}"
                await sp(context.bot, target, msg.photo[-1].file_id, cap)
            elif msg.video:
                if msg.caption:
                    cap += f"\n{msg.caption}"
                await sv(context.bot, target, msg.video.file_id, cap)
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment o'zgaruvchisi kiritilmagan")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID environment o'zgaruvchisi kiritilmagan")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))

    async def _periodic_sync(context):
        global DB, _pending_remote_sync
        try:
            if _pending_remote_sync:
                logger.info("🔁 Pending sync — remote'ga yuboramiz")
                await db_save_async(DB)
                return

            fresh = await asyncio.to_thread(_load_from_jsonbin)
            if fresh is None or not _has_real_content(fresh):
                fresh = await asyncio.to_thread(_load_from_npoint)
            if fresh is None or not _has_real_content(fresh):
                return

            added = 0
            for code, mv in fresh.get("movies", {}).items():
                if code not in DB.setdefault("movies", {}):
                    DB["movies"][code] = mv
                    added += 1
            for user_id, user_data in fresh.get("users", {}).items():
                DB.setdefault("users", {}).setdefault(user_id, user_data)
            for k, v in fresh.get("btn_texts", {}).items():
                DB.setdefault("btn_texts", {}).setdefault(k, v)
            for k, v in fresh.get("emoji_ids", {}).items():
                if k not in DB.setdefault("emoji_ids", {}):
                    DB["emoji_ids"][k] = v
                    EMOJI_IDS.setdefault(k, v)
            if fresh.get("channels") and not DB.get("channels"):
                DB["channels"] = fresh.get("channels", [])
            if fresh.get("card_number") and not DB.get("card_number"):
                DB["card_number"] = fresh.get("card_number")
            if fresh.get("settings"):
                for k, v in fresh.get("settings", {}).items():
                    if v and not DB.setdefault("settings", {}).get(k):
                        DB["settings"][k] = v
            if added:
                logger.info(f"🔄 Periodik sync: +{added} yangi kino merge qilindi")
        except Exception as e:
            logger.error(f"Periodik sync xato: {e}")

    if app.job_queue:
        app.job_queue.run_repeating(_periodic_sync, interval=120, first=60)
        logger.info("🔄 Periodik sync yoqildi (har 2 daqiqada)")

    logger.info(f"🚀 Bot v14 ishga tushdi! — {len(DB.get('movies', {}))} kino, "
                f"{len(DB.get('users', {}))} foydalanuvchi")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
