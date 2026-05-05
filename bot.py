# -*- coding: utf-8 -*-
"""
Kino Bot - v17 (TUZATILGAN)
Asosiy tuzatishlar:
1. Admin holatda "Asosiy menyu" / "Boshqarish" bosish → holat bekor bo'ladi
2. Qism saqlash ishonchli (retry bilan)
3. Kino nomi sifatida admin tugmalari qabul qilinmaydi
4. Kino o'chirish holatida ham navigatsiya ishlaydi
"""

import logging, asyncio, json, time, re, os, threading, copy
from datetime import datetime
from functools import lru_cache
from io import BytesIO
import requests

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# ─── KONFIGURATSIYA ────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN")  or "8723400610:AAHLeZMgQfCt_tFCe4nG0EbKRNeXcIQxz6Q"
ADMIN_ID   = int(os.environ.get("ADMIN_ID") or "8537782289")

JSONBLOB_URL = os.environ.get("JSONBLOB_URL") or "https://jsonblob.com/api/jsonBlob/019df4aa-10b1-725c-83f5-9901ab2db9b6"
GSHEET_ID    = os.environ.get("GSHEET_ID")  or "1Lodn9MTb7nysq5l80cQVCu9IKfgQRlnNe654PT0hKQs"
GSHEET_API   = os.environ.get("GSHEET_API") or ""
NPOINT_URL   = os.environ.get("NPOINT_URL") or ""

LOCAL_BACKUP_FILE = "db_backup.json"
LOCAL_MOVIES_FILE = "movies_backup.json"

_save_lock = threading.Lock()

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── UNICODE QALIN (BOLD) YORDAMCHI ────────────────────────
def to_bold(text: str) -> str:
    """Matnni Unicode Mathematical Bold harflarga o'tkazadi (tugmalar uchun)"""
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr(0x1D400 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            result.append(chr(0x1D41A + ord(ch) - ord('a')))
        elif '0' <= ch <= '9':
            result.append(chr(0x1D7CE + ord(ch) - ord('0')))
        else:
            result.append(ch)
    return ''.join(result)

_B = to_bold  # qisqartma


# ─── BUTTON TEXTS ──────────────────────────────────────────
DEFAULT_BTN = {
    "yordam":         f"🎧 {_B('Yordam')}",
    "install":        f"📲 {_B('Ilovani ornatish')}",
    "barcha_kino":    f"🎬 {_B('Barcha kinolar')}",
    "kino_kanal":     f"📺 {_B('Kino kodlari kanali')}",
    "kino_joy":       f"🎥 {_B('Kino joylash')}",
    "qism_qosh":      f"➕ {_B('Qism qoshish')}",
    "pullik":         f"💰 {_B('Qismni pullik qilish')}",
    "stat":           f"📊 {_B('Statistika')}",
    "kanal_post":     f"📤 {_B('Kanalga post')}",
    "maj_kanal":      f"📡 {_B('Majburiy kanal')}",
    "karta":          f"💳 {_B('Karta raqami')}",
    "ilova":          f"📦 {_B('Ilova fayl/video')}",
    "emoji_soz":      f"🎨 {_B('Emoji sozlamalari')}",
    "asosiy":         f"🏠 {_B('Asosiy menyu')}",
    "boshqarish":     f"⚙️ {_B('Boshqarish')}",
    "tekshir":        f"✅ {_B('Tekshirish')}",
    "tasdiq":         f"✅ {_B('Tasdiqlash')}",
    "bekor":          f"❌ {_B('Bekor qilish')}",
    "ulash":          f"🔗 {_B('Dostlarga ulashish')}",
    "tomosha":        f"▶️ {_B('Tomosha qilish')}",
    "javob":          f"💬 {_B('Javob berish')}",
    "yangi":          f"🔄 {_B('Yangilash')}",
    "qism_add":       f"➕ {_B('Qism qoshish')}",
    "narx_bel":       f"💰 {_B('Narx belgilash')}",
    "kut":            f"⏳ {_B('Tasdiqlanishini kuting')}",
    "bosh":           f"🏠 {_B('Bosh menyu')}",
    "tiklash":        f"🔄 {_B('Hammasini tiklash')}",
    "yopish":         f"❌ {_B('Yopish')}",
    "default_q":      f"🔄 {_B('Defaultga qaytarish')}",
    "orqaga":         f"⬅️ {_B('Orqaga')}",
    "broadcast":      f"📢 {_B('Barchaga xabar')}",
    "kino_uch":       f"🗑 {_B('Kino ochirish')}",
    "prev_qism":      f"⬅️ {_B('Oldingi qismlar')}",
    "next_qism":      f"➡️ {_B('Boshqa qismlar')}",
    "kino_kanal_set": f"🔗 {_B('Kino kanali linkini ornatish')}",
}

BTN_LABELS = {
    "yordam":        "Yordam tugmasi",
    "install":       "O'rnatish tugmasi",
    "barcha_kino":   "Barcha kinolar tugmasi",
    "kino_kanal":    "Kino kodlari kanali tugmasi",
    "kino_kanal_set":"Kino kanali linki",
    "kino_joy":      "Kino joylash",
    "qism_qosh":     "Qism qo'shish",
    "pullik":        "Pullik qilish",
    "stat":          "Statistika",
    "kanal_post":    "Kanalga post",
    "maj_kanal":     "Majburiy kanal",
    "karta":         "Karta raqami",
    "ilova":         "Ilova fayl/video",
    "emoji_soz":     "Emoji sozlamalari",
    "asosiy":        "Asosiy menyu",
    "boshqarish":    "⚙️ Boshqarish",
    "tekshir":       "Tekshirish",
    "tasdiq":        "Tasdiqlash",
    "bekor":         "Bekor qilish",
    "ulash":         "Ulashish",
    "tomosha":       "Tomosha qilish",
    "javob":         "Javob berish",
    "yangi":         "Yangilash",
    "qism_add":      "Qism qo'shish (inline)",
    "narx_bel":      "Narx belgilash",
    "kut":           "Kuting tugmasi",
    "bosh":          "Bosh menyu (inline)",
    "tiklash":       "Hammasini tiklash",
    "yopish":        "Yopish",
    "default_q":     "Defaultga qaytarish",
    "orqaga":        "Orqaga",
    "broadcast":     "Barchaga xabar",
    "kino_uch":      "Kino o'chirish",
    "prev_qism":     "Oldingi qismlar tugmasi",
    "next_qism":     "Boshqa qismlar tugmasi",
}

LABEL_TO_KEY = {v: k for k, v in BTN_LABELS.items()}

DEFAULT_DB = {
    "users": {}, "movies": {}, "channels": [], "card_number": "",
    "pending_payments": {},
    "settings": {"install_file_id": None, "install_video_id": None, "kino_kanal_url": ""},
    "stats": {"total_views": 0},
    "btn_texts": {},
    "emoji_ids": {},
}

EMOJI_IDS: dict = {}

# ─── RAM / STORAGE HOLATI ──────────────────────────────────
DB_STATUS: dict = {
    "storage_ok": True,       # JSONBlob ishlayaptimi?
    "fail_count": 0,          # Ketma-ket xatolar soni
    "last_save_ok": None,     # Oxirgi muvaffaqiyatli saqlash vaqti
    "last_err": None,         # Oxirgi xato xabari
    "ram_only": False,        # True bo'lsa — faqat RAMdan ishlayapti
}

_sub_cache: dict[int, tuple[float, list]] = {}
SUB_CACHE_TTL = 10


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


def _save_local(data: dict) -> bool:
    try:
        movies = data.get("movies", {})
        try:
            tmp = LOCAL_MOVIES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(movies, f, ensure_ascii=False)
            os.replace(tmp, LOCAL_MOVIES_FILE)
        except Exception as e:
            logger.error(f"Movies backup xato: {e}")

        db_small = {k: v for k, v in data.items() if k != "movies"}
        db_small["movies"] = {}
        tmp = LOCAL_BACKUP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db_small, f, ensure_ascii=False)
        os.replace(tmp, LOCAL_BACKUP_FILE)
        return True
    except Exception as e:
        logger.error(f"Lokal backup xato: {e}")
        return False


def _load_local() -> dict | None:
    try:
        db = None
        if os.path.exists(LOCAL_BACKUP_FILE):
            with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        movies = {}
        if os.path.exists(LOCAL_MOVIES_FILE):
            with open(LOCAL_MOVIES_FILE, "r", encoding="utf-8") as f:
                movies = json.load(f)
        if db is None:
            db = {}
        db["movies"] = movies
        return _normalize_db(db)
    except Exception as e:
        logger.error(f"Lokal yuklash xato: {e}")
        return None


def _save_jsonblob(data: dict, retries: int = 3) -> bool:
    """JSONBlob ga to'liq DB saqlash (retry bilan)"""
    if not JSONBLOB_URL:
        return False
    payload = json.dumps(data, ensure_ascii=False)
    size_kb = len(payload.encode("utf-8")) / 1024
    logger.info(f"JSONBlob saqlash: {size_kb:.1f} KB")

    for attempt in range(retries):
        try:
            r = requests.put(
                JSONBLOB_URL,
                headers={"Content-Type": "application/json"},
                data=payload.encode("utf-8"),
                timeout=45,
            )
            if r.status_code in (200, 201):
                logger.info(f"✅ JSONBlob saqlandi ({size_kb:.1f} KB)")
                return True
            logger.error(f"JSONBlob save #{attempt+1} status {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.error(f"JSONBlob save #{attempt+1} xato: {e}")
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
    return False


def _load_jsonblob() -> dict | None:
    if not JSONBLOB_URL:
        return None
    for attempt in range(3):
        try:
            r = requests.get(
                JSONBLOB_URL,
                headers={"Accept": "application/json"},
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    logger.info(f"✅ JSONBlob dan yuklandi: "
                                f"{len(data.get('movies', {}))} kino, "
                                f"{len(data.get('users', {}))} user")
                    return data
        except Exception as e:
            logger.error(f"JSONBlob load #{attempt+1}: {e}")
        if attempt < 2:
            time.sleep(2)
    return None


def _gsheet_append_row(row_data: list) -> bool:
    if not GSHEET_ID:
        return False
    try:
        url = (f"https://sheets.googleapis.com/v4/spreadsheets/"
               f"{GSHEET_ID}/values/Users!A:Z:append"
               f"?valueInputOption=RAW&insertDataOption=INSERT_ROWS")
        if GSHEET_API:
            url += f"&key={GSHEET_API}"
        body = {"values": [row_data]}
        r = requests.post(url, headers={"Content-Type": "application/json"},
                          data=json.dumps(body), timeout=10)
        if r.status_code in (200, 201):
            return True
        logger.warning(f"GSheet append status {r.status_code}")
    except Exception as e:
        logger.warning(f"GSheet append xato: {e}")
    return False


def _gsheet_log_user(user_id: int, name: str, username: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [str(user_id), name, f"@{username}" if username else "", now]
    threading.Thread(target=_gsheet_append_row, args=(row,), daemon=True).start()


def _save_npoint_meta(data: dict) -> bool:
    if not NPOINT_URL:
        return False
    try:
        meta = {
            "channels": data.get("channels", []),
            "card_number": data.get("card_number", ""),
            "settings": data.get("settings", {}),
            "btn_texts": data.get("btn_texts", {}),
            "emoji_ids": data.get("emoji_ids", {}),
            "stats": data.get("stats", {}),
        }
        payload = json.dumps(meta, ensure_ascii=False)
        r = requests.put(NPOINT_URL, headers={"Content-Type": "application/json"},
                         data=payload.encode("utf-8"), timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        logger.error(f"npoint save xato: {e}")
    return False


def db_load():
    logger.info("DB yuklanmoqda...")
    blob = _load_jsonblob()
    if blob and isinstance(blob, dict) and _has_real_content(blob):
        db = _normalize_db(blob)
        EMOJI_IDS.clear()
        EMOJI_IDS.update(db.get("emoji_ids", {}))
        _save_local(db)
        logger.info(f"✅ JSONBlob dan yuklandi: "
                    f"{len(db.get('movies', {}))} kino, "
                    f"{len(db.get('users', {}))} user")
        return db

    local = _load_local()
    if local and _has_real_content(local):
        EMOJI_IDS.clear()
        EMOJI_IDS.update(local.get("emoji_ids", {}))
        logger.info(f"✅ Lokal backupdan yuklandi: {len(local.get('movies', {}))} kino")
        threading.Thread(target=_save_jsonblob, args=(local,), daemon=True).start()
        return local

    logger.warning("⚠️ Hech narsa topilmadi — bo'sh DB")
    return json.loads(json.dumps(DEFAULT_DB))


async def db_save_async(data: dict) -> bool:
    data["emoji_ids"] = dict(EMOJI_IDS)
    _save_local(data)
    ok = await asyncio.to_thread(_save_jsonblob, data)
    if NPOINT_URL:
        asyncio.create_task(asyncio.to_thread(_save_npoint_meta, data))
    n = len(data.get("movies", {}))
    now_str = datetime.now().strftime("%H:%M:%S")
    if ok:
        DB_STATUS["storage_ok"]   = True
        DB_STATUS["fail_count"]   = 0
        DB_STATUS["last_save_ok"] = now_str
        DB_STATUS["ram_only"]     = False
        logger.info(f"✅ DB saqlandi — {n} kino")
    else:
        DB_STATUS["fail_count"] = DB_STATUS.get("fail_count", 0) + 1
        DB_STATUS["last_err"]   = now_str
        if DB_STATUS["fail_count"] >= 2:
            DB_STATUS["storage_ok"] = False
            DB_STATUS["ram_only"]   = True
        logger.warning(f"⚠️ JSONBlob saqlanmadi ({DB_STATUS['fail_count']}x), faqat RAM — {n} kino")
    return ok


DB = db_load()


def save():
    DB["emoji_ids"] = dict(EMOJI_IDS)
    _save_local(DB)
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(db_save_async(DB))
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    except RuntimeError:
        threading.Thread(target=_save_jsonblob, args=(copy.deepcopy(DB),), daemon=True).start()


async def save_now() -> bool:
    return await db_save_async(DB)


def bt(key: str) -> str:
    raw = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
    # Har qanday holatda matnni Unicode qalin (bold) ko'rinishga o'tkazamiz,
    # shunda DB'da saqlangan oddiy matnlar ham qalin chiqadi.
    return _B(raw)


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
# ADMIN NAVIGATSIYA TUGMALARI — HOLAT BEKOR QILISH
# ══════════════════════════════════════════════════════════

def _is_admin_nav_button(text: str) -> bool:
    """
    Matn admin navigatsiya tugmasi ekanligini tekshiradi.
    Bu tugmalar bossilsa, joriy holat bekor qilinib menyu ochiladi.
    """
    nav_keys = ["asosiy", "boshqarish"]
    for k in nav_keys:
        v = bt(k)
        if v and (text == v or strip_emoji_prefix(text) == strip_emoji_prefix(v)):
            return True
    return False


def _get_admin_nav_key(text: str) -> str | None:
    """Qaysi navigatsiya tugmasi ekanligini qaytaradi."""
    for k in ["asosiy", "boshqarish"]:
        v = bt(k)
        if v and (text == v or strip_emoji_prefix(text) == strip_emoji_prefix(v)):
            return k
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
    ], [
        rbtn(bt("barcha_kino"), style="primary", emoji_id=get_eid("barcha_kino")),
    ]]
    if is_admin:
        rows.append([rbtn(bt("boshqarish"), style="primary", emoji_id=get_eid("boshqarish"))])
    return rkb(rows)


def admin_menu_kb():
    return rkb([
        [rbtn(bt("kino_joy"),        style="success", emoji_id=get_eid("kino_joy")),
         rbtn(bt("qism_qosh"),       style="primary", emoji_id=get_eid("qism_qosh"))],
        [rbtn(bt("pullik"),          style="danger",  emoji_id=get_eid("pullik")),
         rbtn(bt("stat"),            style="primary", emoji_id=get_eid("stat"))],
        [rbtn(bt("kanal_post"),      style="primary", emoji_id=get_eid("kanal_post")),
         rbtn(bt("maj_kanal"),       style="danger",  emoji_id=get_eid("maj_kanal"))],
        [rbtn(bt("karta"),           style="success", emoji_id=get_eid("karta")),
         rbtn(bt("ilova"),           style="primary", emoji_id=get_eid("ilova"))],
        [rbtn(bt("kino_kanal_set"),  style="success", emoji_id=get_eid("kino_kanal_set"))],
        [rbtn(bt("emoji_soz"),       style="primary", emoji_id=get_eid("emoji_soz"))],
        [rbtn(bt("kino_uch"),        style="danger",  emoji_id=get_eid("kino_uch")),
         rbtn(bt("broadcast"),       style="danger",  emoji_id=get_eid("broadcast"))],
        [rbtn(bt("asosiy"),          style="success", emoji_id=get_eid("asosiy"))],
    ])


def channel_manage_kb():
    return rkb([
        [rbtn(f"➕ {_B('Kanal qoshish')}",   style="success"),
         rbtn(f"🗑 {_B('Kanal ochirish')}",   style="danger")],
        [rbtn(f"📋 {_B('Kanallar royxati')}", style="primary")],
        [rbtn(f"⬅️ {_B('Admin panel')}",       style="success")],
    ])


def channel_delete_inline_kb(channels: list):
    rows = []
    for i, ch in enumerate(channels):
        rows.append([ibtn(
            f"🗑 {ch.get('title','?')} ({ch.get('username','?')})",
            data=f"ch_del|{i}",
            style="danger"
        )])
    rows.append([ibtn(f"❌ {_B('Bekor')}", data="ch_del_cancel", style="primary")])
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
            rows.append([ibtn(f"{_B(str(ek)+'-qism')}  💰 {_B(str(price)+' som')}",
                              data=f"ep|{code}|{ek}", style="danger")])
        else:
            rows.append([ibtn(f"{_B(str(ek)+'-qism')}",
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
    # Kino kodlari kanali tugmasi
    kanal_url = DB.get("settings", {}).get("kino_kanal_url", "")
    if kanal_url:
        rows.append([ibtn(bt("kino_kanal"), url=kanal_url, style="primary",
                          emoji_id=get_eid("kino_kanal"))])
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
    rows.append([rbtn(f"🗑 {_B('Hammasini tiklash')}", style="danger")])
    rows.append([rbtn(f"⬅️ {_B('Orqaga')}",            style="success")])
    return rkb(rows)


def emoji_single_action_kb(key: str):
    return ikb([
        [ibtn(f"🗑 {_B('Defaultga qaytarish')}", data=f"emoji_reset|{key}", style="danger")],
        [ibtn(f"⬅️ {_B('Orqaga')}",              data="emoji_back",          style="success")],
    ])


def broadcast_color_kb():
    return ikb([
        [
            ibtn(f"🔵 {_B('Kok')}",   data="bc_color|primary", style="primary"),
            ibtn(f"🔴 {_B('Qizil')}",  data="bc_color|danger",  style="danger"),
            ibtn(f"🟢 {_B('Yashil')}", data="bc_color|success", style="success"),
        ],
        [ibtn(f"❌ {_B('Bekor')}", data="bc_cancel", style="danger")],
    ])


def broadcast_preview_kb(has_btn: bool):
    rows = [[ibtn(f"➕ {_B('Tugma qoshish')}", data="bc_add_btn", style="primary")]]
    if has_btn:
        rows.append([ibtn(f"🗑 {_B('Tugmani ochirish')}", data="bc_remove_btn", style="danger")])
    rows.append([
        ibtn(f"✅ {_B('Yuborish')}", data="bc_send",   style="success"),
        ibtn(f"❌ {_B('Bekor')}",    data="bc_cancel", style="danger"),
    ])
    return ikb(rows)


# ══════════════════════════════════════════════════════════
# XABAR YUBORISH
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
    cached = _sub_cache_get(user_id)
    if cached is not None:
        return cached

    channels = DB.get("channels", [])
    if not channels:
        _sub_cache_set(user_id, [])
        return []

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
    is_new = uid not in DB["users"]
    if is_new:
        DB["users"][uid] = {
            "name": user.full_name,
            "username": user.username or "",
            "joined": datetime.now().isoformat(),
            "paid_episodes": {},
            "watched": {},
        }
        _gsheet_log_user(user.id, user.full_name, user.username or "")
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
# BARCHA KINOLAR RASMI GENERATSIYA
# ══════════════════════════════════════════════════════════

def _strip_html(text: str) -> str:
    """HTML teglarini olib tashlaydi"""
    return re.sub(r'<[^>]+>', '', text or '').strip()


PHOTO_PAGE_SIZE = 20   # Har bir suratda nechta kino ko'rsatilsin


def generate_movies_image(movie_slice: list, page: int = 1, total_pages: int = 1,
                          total_count: int = 0, start_offset: int = 0) -> BytesIO | None:
    """
    Berilgan movie_slice ro'yxatini chiroyli oq katak fonda, qalin yozuv bilan rasmga chiqaradi.
    movie_slice: [(code, movie_dict), ...]
    """
    if not PIL_AVAILABLE:
        return None
    if not movie_slice:
        return None

    movie_list = movie_slice

    # ── Ranglar ──────────────────────────────────────────────
    BG_COLOR     = (250, 250, 252)
    GRID_COLOR   = (208, 213, 228)
    HEADER_BG    = (20, 60, 160)
    WHITE        = (255, 255, 255)
    TEXT_DARK    = (28, 33, 52)
    CODE_COLOR   = (60, 90, 190)
    VIEWS_COLOR  = (40, 140, 70)
    EP_COLOR     = (100, 100, 130)
    ACCENT_COLORS = [
        (25,  95,  215),
        (40,  160,  70),
        (200,  50,  60),
        (200, 120,   0),
        (110,  60, 190),
        (  0, 140, 180),
    ]

    # ── O'lchamlar ───────────────────────────────────────────
    IMG_W    = 820
    PAD_X    = 22
    TOP_PAD  = 14
    CARD_H   = 92
    GAP      = 8
    HEADER_H = 92
    FOOTER_H = 52
    BADGE_SZ = 52
    GRID_STP = 28

    img_h = HEADER_H + TOP_PAD + len(movie_list) * (CARD_H + GAP) + FOOTER_H + 10

    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # ── Shrift topish ─────────────────────────────────────────
    font_paths_bold = [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    ]

    def try_font(size):
        for p in font_paths_bold:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    fnt_header = try_font(34)
    fnt_num    = try_font(22)
    fnt_title  = try_font(20)
    fnt_sub    = try_font(14)
    fnt_footer = try_font(17)

    # ── Katak fon (grid) ─────────────────────────────────────
    for x in range(0, IMG_W, GRID_STP):
        draw.line([(x, 0), (x, img_h)], fill=GRID_COLOR, width=1)
    for y in range(0, img_h, GRID_STP):
        draw.line([(0, y), (IMG_W, y)], fill=GRID_COLOR, width=1)

    # ── Header ───────────────────────────────────────────────
    draw.rectangle([(0, 0), (IMG_W, HEADER_H)], fill=HEADER_BG)
    h_text = "BARCHA KINOLAR"
    try:
        hbb = draw.textbbox((0, 0), h_text, font=fnt_header)
        hx  = (IMG_W - (hbb[2] - hbb[0])) // 2
        hy  = (HEADER_H - (hbb[3] - hbb[1])) // 2
    except Exception:
        hx, hy = 40, 28
    draw.text((hx, hy), h_text, fill=WHITE, font=fnt_header)

    # ── Kino kartochkalari ────────────────────────────────────
    for idx, (code, movie) in enumerate(movie_list):
        y0 = HEADER_H + TOP_PAD + idx * (CARD_H + GAP)
        y1 = y0 + CARD_H
        x0 = PAD_X
        x1 = IMG_W - PAD_X
        col = ACCENT_COLORS[idx % len(ACCENT_COLORS)]

        # Oq karta
        draw.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=WHITE, outline=col, width=3)

        # Chap rang chizig'i
        draw.rounded_rectangle([x0, y0, x0 + 7, y1], radius=4, fill=col)

        # Raqam nishoni (badge)
        bx0 = x0 + 16
        bx1 = bx0 + BADGE_SZ
        by0 = y0 + (CARD_H - BADGE_SZ) // 2
        by1 = by0 + BADGE_SZ
        draw.ellipse([bx0, by0, bx1, by1], fill=col)
        num_txt = str(start_offset + idx + 1)
        try:
            nb  = draw.textbbox((0, 0), num_txt, font=fnt_num)
            nxc = bx0 + (BADGE_SZ - (nb[2] - nb[0])) // 2
            nyc = by0 + (BADGE_SZ - (nb[3] - nb[1])) // 2
        except Exception:
            nxc, nyc = bx0 + 14, by0 + 12
        draw.text((nxc, nyc), num_txt, fill=WHITE, font=fnt_num)

        # Matn maydoni
        tx = bx1 + 16

        # Kino nomi (qalin)
        raw_title = _strip_html(movie.get("title", code))
        if len(raw_title) > 40:
            raw_title = raw_title[:38] + "…"
        title_y = y0 + 14
        draw.text((tx, title_y), raw_title, fill=TEXT_DARK, font=fnt_title)

        # Kod | qismlar | ko'rilganlar (qalin)
        ep_count    = len(movie.get("episodes", []))
        views_total = sum(movie.get("views", {}).values())
        sub_y = y0 + 50

        code_part  = f"Kod: {code}"
        ep_part    = f"  |  {ep_count} qism"
        views_part = f"  |  {views_total} korilgan"

        draw.text((tx, sub_y), code_part, fill=CODE_COLOR, font=fnt_sub)
        try:
            cb = draw.textbbox((0, 0), code_part, font=fnt_sub)
            ex = tx + (cb[2] - cb[0])
        except Exception:
            ex = tx + 85
        draw.text((ex, sub_y), ep_part, fill=EP_COLOR, font=fnt_sub)
        try:
            eb = draw.textbbox((0, 0), ep_part, font=fnt_sub)
            vx = ex + (eb[2] - eb[0])
        except Exception:
            vx = ex + 68
        draw.text((vx, sub_y), views_part, fill=VIEWS_COLOR, font=fnt_sub)

    # ── Footer ───────────────────────────────────────────────
    fy = img_h - FOOTER_H
    draw.rectangle([(0, fy), (IMG_W, img_h)], fill=HEADER_BG)
    if total_pages > 1:
        start_n = (page - 1) * PHOTO_PAGE_SIZE + 1
        end_n   = start_n + len(movie_list) - 1
        f_text = f"{start_n}-{end_n} ko'rsatildi  |  Jami: {total_count} ta  |  Kino kodini yuboring!"
    else:
        f_text = f"Jami: {total_count} ta kino  |  Kino kodini yuboring!"
    try:
        fbb = draw.textbbox((0, 0), f_text, font=fnt_footer)
        fx  = (IMG_W - (fbb[2] - fbb[0])) // 2
        fy2 = fy + (FOOTER_H - (fbb[3] - fbb[1])) // 2
    except Exception:
        fx, fy2 = 40, fy + 16
    draw.text((fx, fy2), f_text, fill=WHITE, font=fnt_footer)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf



def _make_placeholder_image(title: str, code: str, idx: int) -> BytesIO | None:
    """
    Poster bo'lmagan kinolar uchun chiroyli placeholder surat yasaydi.
    """
    if not PIL_AVAILABLE:
        return None

    ACCENT_COLORS = [
        (25,  95,  215),
        (40,  160,  70),
        (200,  50,  60),
        (200, 120,   0),
        (110,  60, 190),
        (  0, 140, 180),
    ]
    W, H  = 640, 360
    col   = ACCENT_COLORS[idx % len(ACCENT_COLORS)]
    dark  = tuple(max(0, c - 60) for c in col)
    WHITE = (255, 255, 255)

    img  = Image.new("RGB", (W, H), col)
    draw = ImageDraw.Draw(img)

    # Gradient effect — pastki qism to'qroq
    for y in range(H):
        ratio = y / H
        r = int(col[0] * (1 - ratio * 0.4))
        g = int(col[1] * (1 - ratio * 0.4))
        b = int(col[2] * (1 - ratio * 0.4))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    font_paths_bold = [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]

    def try_font(size):
        for p in font_paths_bold:
            if os.path.exists(p):
                try: return ImageFont.truetype(p, size)
                except: continue
        return ImageFont.load_default()

    fnt_title = try_font(32)
    fnt_code  = try_font(20)
    fnt_icon  = try_font(48)

    # Markazda 🎬 belgisi
    icon_y = H // 2 - 80
    try:
        ib = draw.textbbox((0, 0), "🎬", font=fnt_icon)
        draw.text(((W - (ib[2]-ib[0])) // 2, icon_y), "🎬", font=fnt_icon)
    except Exception:
        pass

    # Kino nomi
    short = title if len(title) <= 28 else title[:26] + "…"
    try:
        tb = draw.textbbox((0, 0), short, font=fnt_title)
        tx = (W - (tb[2] - tb[0])) // 2
        ty = H // 2 - 10
    except Exception:
        tx, ty = 40, H // 2 - 10
    draw.text((tx + 2, ty + 2), short, fill=(0, 0, 0, 80), font=fnt_title)
    draw.text((tx, ty), short, fill=WHITE, font=fnt_title)

    # Kod
    code_txt = f"Kod: {code}"
    try:
        cb = draw.textbbox((0, 0), code_txt, font=fnt_code)
        cx = (W - (cb[2] - cb[0])) // 2
        cy = ty + (tb[3] - tb[1]) + 16 if 'tb' in dir() else ty + 50
    except Exception:
        cx, cy = W // 2 - 40, ty + 50
    draw.text((cx, cy), code_txt, fill=(220, 230, 255), font=fnt_code)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf


KINO_LIST_PAGE_SIZE = 10   # Har bir suratda nechta kino


async def _send_kino_list_page(bot, chat_id: int, page: int = 0):
    """
    Kinolar ro'yxatini sahifalab PIL surat sifatida yuboradi.
    Oxirgi sahifada 'Qolgan kinolar' tugmasi bo'lmaydi.
    Har sahifada 'Keyingi sahifa ➡️' tugmasi bo'ladi (agar bor bo'lsa).
    """
    movies = DB.get("movies", {})
    if not movies:
        return

    # Eng yangi — oxiridan boshlaymiz (additions oxirda bo'ladi)
    all_items   = list(movies.items())[::-1]   # teskari — yangi birinchi
    total_count = len(all_items)
    total_pages = max(1, (total_count + KINO_LIST_PAGE_SIZE - 1) // KINO_LIST_PAGE_SIZE)
    page        = max(0, min(page, total_pages - 1))

    start = page * KINO_LIST_PAGE_SIZE
    end   = min(start + KINO_LIST_PAGE_SIZE, total_count)
    slice_items = all_items[start:end]

    # ── PIL surat yasash ─────────────────────────────────
    img_buf = None
    if PIL_AVAILABLE:
        try:
            img_buf = await asyncio.to_thread(
                generate_movies_image,
                slice_items,
                page + 1,
                total_pages,
                total_count,
                start,
            )
        except Exception as e:
            logger.error(f"kino_list surat xato: {e}")

    # ── Inline tugmalar ───────────────────────────────────
    nav_row  = []
    if page > 0:
        nav_row.append(ibtn(f"⬅️ {_B('Oldingi kinolar')}", data=f"kino_list|{page - 1}", style="primary"))
    if page < total_pages - 1:
        nav_row.append(ibtn(f"🎬 {_B('Qolgan kinolar')}", data=f"kino_list|{page + 1}", style="primary"))

    kanal_url = DB.get("settings", {}).get("kino_kanal_url", "")
    kanal_row = []
    if kanal_url:
        kanal_row = [ibtn(bt("kino_kanal"), url=kanal_url, style="primary",
                           emoji_id=get_eid("kino_kanal"))]

    rows = []
    if nav_row:
        rows.append(nav_row)
    if kanal_row:
        rows.append(kanal_row)
    kb = ikb(rows) if rows else None

    caption = (
        f"🎬 <b>Kinolar ro'yxati</b>  —  sahifa {page+1}/{total_pages}\n"
        f"📋 Ko'rsatilmoqda: <b>{start+1}–{end}</b>  |  Jami: <b>{total_count} ta</b>\n\n"
        f"Kino <b>kodini</b> yuboring — video <b>darhol</b> keladi! ⚡"
    )

    if img_buf:
        await bot.send_photo(
            chat_id=chat_id, photo=img_buf,
            caption=caption, parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=("⚠️ <b>Surat yasash uchun Pillow kutubxonasi kerak.</b>\n\n"
                  "Serverda quyidagini ishga tushiring:\n"
                  "<code>pip install Pillow</code>\n\n"
                  "Shundan keyin <b>Barcha kinolar</b> tugmasi chiroyli surat ko'rinishida chiqadi."),
            parse_mode="HTML",
            reply_markup=kb
        )


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
# CALLBACK HANDLER
# ══════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data or ""
    uid  = q.from_user.id

    await q.answer()

    if data.startswith("kino_list|"):
        try:
            pg = int(data.split("|")[1])
        except Exception:
            pg = 0
        await _send_kino_list_page(context.bot, uid, page=pg)
        return

    if data.startswith("ch_del|"):
        if uid != ADMIN_ID:
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

    if data.startswith("bc_"):
        await cb_broadcast(update, context)
        return

    if data == "check_sub":
        await cb_check_sub(update, context)
        return

    if data.startswith("page|"):
        await cb_page(update, context)
        return

    if data.startswith("ep|"):
        await cb_episode(update, context)
        return

    if data.startswith("pay_ok|") or data.startswith("pay_no|"):
        await cb_payment(update, context)
        return

    if data.startswith("reply|"):
        await cb_reply(update, context)
        return

    if data == "refresh_stats":
        if uid != ADMIN_ID:
            return
        u = len(DB.get("users", {}))
        m = len(DB.get("movies", {}))
        v = DB.get("stats", {}).get("total_views", 0)
        if DB_STATUS["ram_only"]:
            storage_line = (
                f"\n\n🔴 <b>Storage: RAM ONLY</b>\n"
                f"JSONBlob ishlamayapti! Xato: <b>{DB_STATUS['fail_count']}</b>x\n"
                f"<code>{DB_STATUS.get('last_err', '—')}</code>"
            )
        elif DB_STATUS["last_save_ok"]:
            storage_line = f"\n\n🟢 Storage OK | {DB_STATUS['last_save_ok']}"
        else:
            storage_line = "\n\n🟡 Storage tekshirilmagan"
        try:
            await q.edit_message_text(
                f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
                f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>{storage_line}",
                parse_mode="HTML", reply_markup=stats_kb())
        except Exception:
            pass
        return

    if data == "go_home":
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Bosh menyu",
            main_menu_kb(is_admin=(uid == ADMIN_ID)))
        return

    if data == "waiting_confirm":
        await q.answer("Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)
        return

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

    if data == "emoji_reset_all":
        if uid != ADMIN_ID:
            return
        DB["btn_texts"] = {}
        DB["emoji_ids"] = {}
        EMOJI_IDS.clear()
        await save_now()
        try:
            await q.edit_message_text("✅ Barcha tugmalar tiklandi!")
        except Exception:
            pass
        context.user_data["emoji_menu"] = True
        context.user_data.pop("editing_btn_key", None)
        await sm(context.bot, uid, "✅ Tiklandi! Tugmani tanlang:", emoji_menu_kb())
        return

    if data.startswith("emoji_reset|"):
        if uid != ADMIN_ID:
            return
        key = data.split("|", 1)[1]
        DB.get("btn_texts", {}).pop(key, None)
        DB.get("emoji_ids", {}).pop(key, None)
        EMOJI_IDS.pop(key, None)
        await save_now()
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

    if data.startswith("quick_add_ep|"):
        if uid != ADMIN_ID:
            return
        code = data.split("|", 1)[1]
        context.user_data["admin_state"]   = "add_ep_video"
        context.user_data["ep_movie_code"] = code
        movie = DB["movies"].get(code, {})
        ep_num = len(movie.get("episodes", [])) + 1
        await sm(context.bot, uid,
            f"🎬 <b>{movie.get('title', code)}</b>\n"
            f"📹 <b>{ep_num}-qism</b> uchun video yuboring:")
        return

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
# CALLBACK: SUBSCRIPTION
# ══════════════════════════════════════════════════════════

async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id

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
# CALLBACK: QISM KO'RISH
# ══════════════════════════════════════════════════════════

async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
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

    bot_me    = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption   = f"🎬 <b>{movie.get('title')}</b>\n📺 Qism: <b>{ep}</b>"

    try:
        await sv(context.bot, q.from_user.id, eps[idx], caption, share_kb(share_url), protect=True)
    except Exception as e:
        logger.error(f"Video yuborishda xato: {e}")
        await sm(context.bot, q.from_user.id, "❌ Video yuborishda xato. Qayta urinib ko'ring.")
        return

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
# TEXT HANDLER (TUZATILGAN)
# ══════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    msg  = update.message
    text = (msg.text or "").strip()

    # ── 1. editing_btn_key ─────────────────────────────
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
        await save_now()

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

    # ── 2. Broadcast tugma qo'shish ────────────────────
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

    # ── 3. Emoji menyu ──────────────────────────────────
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
            await save_now()
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

    # ── 4. Kanal boshqarish submenu ─────────────────────
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

    # ── 5. Admin reply_to ───────────────────────────────
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        return

    # ══════════════════════════════════════════════════
    # ❗ MUHIM: Admin holatda navigatsiya tugmalarini
    # birinchi tekshirish — holat bekor qilinadi
    # ══════════════════════════════════════════════════
    if uid == ADMIN_ID and context.user_data.get("admin_state"):
        nav_key = _get_admin_nav_key(text)
        if nav_key:
            state = context.user_data.get("admin_state")
            # broadcast_msg holatida navigatsiya ishlaydi
            # Boshqa holatlarda ham ishlaydi
            clear_admin_state(context)
            if nav_key == "asosiy":
                await sm(context.bot, uid, "Asosiy menyu", main_menu_kb(is_admin=True))
            else:  # boshqarish
                await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb())
            logger.info(f"Admin holat '{state}' bekor qilindi, navigatsiya: {nav_key}")
            return

    # ── 6. Admin state handler ──────────────────────────
    if uid == ADMIN_ID:
        state = context.user_data.get("admin_state")
        if state:
            handled = await admin_state_handler(update, context, text)
            if handled:
                return

    # ── 7. Admin tugmalarini aniqlash ───────────────────
    if uid == ADMIN_ID:
        all_admin_btn_keys = [
            "kino_joy", "qism_qosh", "pullik", "stat",
            "kanal_post", "maj_kanal", "karta", "ilova",
            "emoji_soz", "asosiy", "boshqarish", "broadcast", "kino_uch",
            "kino_kanal_set",
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

    # ── 8. Yordam ───────────────────────────────────────
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
        s    = DB.get("settings", {})
        f_id = s.get("install_file_id")
        v_id = s.get("install_video_id")
        if not f_id and not v_id:
            await sm(context.bot, uid, "Admin hali ilova fayl/video joylamagan.")
            return
        tasks = []
        if v_id:
            tasks.append(sv(context.bot, uid, v_id, "<b>Ilovani o'rnatish videosi</b>"))
        if f_id:
            tasks.append(context.bot.send_document(uid, f_id, caption="<b>Ilova fayli</b>", parse_mode="HTML"))
        await asyncio.gather(*tasks, return_exceptions=True)
        return

    # ── Barcha kinolar ──────────────────────────────────────
    if text == bt("barcha_kino"):
        movies = DB.get("movies", {})
        if not movies:
            await sm(context.bot, uid,
                "🎬 <b>Hozircha hech qanday kino qo'shilmagan.</b>\n\n"
                "Kino qo'shilganda bu yerda ko'rinadi! 📽")
            return
        await _send_kino_list_page(context.bot, uid, page=0)
        return

    # ── 9. Yordam so'rovi ───────────────────────────────
    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n{text}")
        await sm(context.bot, ADMIN_ID, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    # ── 10. To'lov cheki (matn) ─────────────────────────
    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos, chek <b>rasmini</b> yuboring.")
        return

    # ── 11. Kino kodi ───────────────────────────────────
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
        # Storage holati
        if DB_STATUS["ram_only"]:
            storage_line = (
                f"\n\n🔴 <b>Storage holati: RAM ONLY</b>\n"
                f"⚠️ JSONBlob ishlamayapti! Bot faqat RAMdan ishlayapti.\n"
                f"Xatolar soni: <b>{DB_STATUS['fail_count']}</b>\n"
                f"Oxirgi xato: <code>{DB_STATUS.get('last_err', '—')}</code>"
            )
        elif DB_STATUS["last_save_ok"]:
            storage_line = (
                f"\n\n🟢 <b>Storage holati: OK</b>\n"
                f"Oxirgi saqlash: <code>{DB_STATUS['last_save_ok']}</code>"
            )
        else:
            storage_line = "\n\n🟡 <b>Storage holati: Tekshirilmagan</b>"
        await sm(context.bot, uid,
            f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
            f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>{storage_line}", stats_kb())
        return

    if text == bt("karta"):
        context.user_data["admin_state"] = "set_card"
        cur = DB.get("card_number") or "Kiritilmagan"
        await sm(context.bot, uid,
            f"Joriy karta: <code>{cur}</code>\n\nYangi karta raqamini yuboring:")
        return

    if text == bt("kino_joy"):
        context.user_data["admin_state"] = "add_movie_code"
        await sm(context.bot, uid,
            "🎬 <b>Yangi kino qo'shish</b>\n\n"
            "Kino kodini kiriting (masalan: AVATAR yoki 001):\n"
            "<i>Lotin harflari va raqamlardan iborat bo'lsin</i>")
        return

    if text == bt("qism_qosh"):
        context.user_data["admin_state"] = "add_ep_code"
        movies = DB.get("movies", {})
        if movies:
            codes_list = "\n".join([f"• <code>{c}</code> — {m.get('title', c)}"
                                    for c, m in list(movies.items())[-10:]])
            await sm(context.bot, uid,
                f"📺 <b>Qism qo'shish</b>\n\n"
                f"So'nggi kinolar:\n{codes_list}\n\n"
                f"Qism qo'shmoqchi bo'lgan kino <b>kodini</b> kiriting:")
        else:
            await sm(context.bot, uid,
                "📺 <b>Qism qo'shish</b>\n\nKino kodini kiriting:")
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

    if text == bt("kino_kanal_set"):
        context.user_data["admin_state"] = "set_kino_kanal"
        cur_url = DB.get("settings", {}).get("kino_kanal_url", "")
        cur_info = f"\n\nJoriy link: <code>{cur_url}</code>" if cur_url else "\n\n<i>Hali o'rnatilmagan</i>"
        await sm(context.bot, uid,
            f"📺 <b>Kino kodlari kanali linki</b>{cur_info}\n\n"
            f"Kanal linkini kiriting (masalan: https://t.me/mykinochannel)\n"
            f"<i>O'chirish uchun <code>0</code> kiriting</i>")
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
        movies = DB.get("movies", {})
        if movies:
            codes_list = "\n".join([f"• <code>{c}</code> — {m.get('title', c)}"
                                    for c, m in list(movies.items())[-10:]])
            await sm(context.bot, uid,
                f"📤 <b>Kanalga post</b>\n\nSo'nggi kinolar:\n{codes_list}\n\n"
                f"Post qilmoqchi bo'lgan kino <b>kodini</b> kiriting:")
        else:
            await sm(context.bot, uid, "Post qilmoqchi bo'lgan kino kodini kiriting:")
        return


# ══════════════════════════════════════════════════════════
# ADMIN STATE HANDLER (TUZATILGAN)
# ══════════════════════════════════════════════════════════

# Admin tugmalari ro'yxati — bularni kino nomi/kodi sifatida qabul qilmaymiz
ADMIN_RESERVED_TEXTS = set()


def _get_admin_reserved_texts() -> set:
    """Admin tugmalari matni — bularni holat inputi sifatida qabul qilmaymiz"""
    keys = [
        "kino_joy", "qism_qosh", "pullik", "stat", "kanal_post",
        "maj_kanal", "karta", "ilova", "emoji_soz", "asosiy",
        "boshqarish", "broadcast", "kino_uch", "yordam", "install",
        "barcha_kino", "kino_kanal_set",
    ]
    result = set()
    for k in keys:
        v = bt(k)
        if v:
            result.add(v)
            result.add(strip_emoji_prefix(v))
    return result


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
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {DB['movies'].get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> topilmadi.\n\nShunga o'xshash kinolar:\n{hint}\n\n"
                    f"To'g'ri kodini kiriting:")
            else:
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
            save_ok = await db_save_async(DB)
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            storage_warn = "\n⚠️ <i>Faqat RAMda saqlandi, storage ishlamayapti!</i>" if not save_ok else ""
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> (<code>{code}</code>) butunlay o'chirildi!\n"
                f"Qolgan kinolar: <b>{len(DB['movies'])} ta</b>{storage_warn}",
                admin_menu_kb())
            return True

        if val == "hammasi":
            DB["movies"][code]["episodes"] = []
            DB["movies"][code]["prices"]   = {}
            save_ok = await db_save_async(DB)
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            storage_warn = "\n⚠️ <i>Faqat RAMda saqlandi, storage ishlamayapti!</i>" if not save_ok else ""
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> kinoning barcha qismlari o'chirildi!{storage_warn}",
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
            save_ok = await db_save_async(DB)
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            storage_warn = "\n⚠️ <i>Faqat RAMda saqlandi!</i>" if not save_ok else ""
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> — <b>{ep_num}-qism</b> o'chirildi!\n"
                f"Qolgan qismlar: <b>{len(DB['movies'][code]['episodes'])} ta</b>{storage_warn}",
                admin_menu_kb())
            return True

        await sm(context.bot, uid,
            "❌ Noto'g'ri. Qism raqami, <code>hammasi</code> yoki <code>kino</code> kiriting:")
        return True

    if state == "set_card":
        DB["card_number"] = text
        await save_now()
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, f"✅ Karta saqlandi: <code>{text}</code>", admin_menu_kb())
        return True

    if state == "set_kino_kanal":
        context.user_data.pop("admin_state", None)
        if text.strip() == "0":
            DB.setdefault("settings", {})["kino_kanal_url"] = ""
            await save_now()
            await sm(context.bot, uid,
                "✅ Kino kodlari kanali linki <b>o'chirildi</b>!\n"
                "Endi tugma ko'rinmaydi.", admin_menu_kb())
        elif text.startswith("http"):
            DB.setdefault("settings", {})["kino_kanal_url"] = text.strip()
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>Kino kodlari kanali</b> linki saqlandi!\n"
                f"Link: <code>{text.strip()}</code>\n\n"
                f"Endi kino qismlar ostida tugma ko'rinadi.", admin_menu_kb())
        else:
            await sm(context.bot, uid,
                "❌ Link noto'g'ri. <code>https://</code> bilan boshlanishi kerak.\n"
                "Qayta kiriting yoki o'chirish uchun <code>0</code> yuboring:")
            context.user_data["admin_state"] = "set_kino_kanal"
        return True

    if state == "add_movie_code":
        code = text.upper().strip()
        if not code:
            await sm(context.bot, uid, "❌ Kod bo'sh bo'lmasin. Qayta kiriting:")
            return True
        if len(code) > 30:
            await sm(context.bot, uid, "❌ Kod 30 ta belgidan oshmasin. Qayta kiriting:")
            return True
        # Admin tugmalari kodi bo'la olmaydi
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. To'g'ri kod kiriting:")
            return True
        if code in DB["movies"]:
            movie = DB["movies"][code]
            await sm(context.bot, uid,
                f"⚠️ <code>{code}</code> kodi allaqachon mavjud!\n\n"
                f"🎬 Nomi: <b>{movie.get('title', code)}</b>\n"
                f"📺 Qismlar: <b>{len(movie.get('episodes', []))} ta</b>\n\n"
                f"Boshqa kod kiriting yoki bu kinoga qism qo'shish uchun "
                f"<b>{bt('qism_qosh')}</b> tugmasini bosing.")
            return True

        context.user_data["new_movie_code"] = code
        context.user_data["admin_state"]    = "add_movie_title"
        await sm(context.bot, uid,
            f"✅ Kod: <code>{code}</code>\n\nEndi kino <b>nomini</b> kiriting:")
        return True

    if state == "add_movie_title":
        # ❗ Asosiy tuzatish: kino nomi sifatida admin tugmalari qabul qilinmaydi
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid,
                "❌ Bu kino nomi emas — admin tugmasi bosildi.\n\n"
                f"Kino nomini kiriting (masalan: <b>Avatar 2</b>):")
            return True

        code = context.user_data.get("new_movie_code")
        if not code:
            await sm(context.bot, uid, "❌ Xatolik yuz berdi. Qaytadan boshlang.")
            context.user_data.pop("admin_state", None)
            return True
        if not text.strip():
            await sm(context.bot, uid, "❌ Nom bo'sh bo'lmasin. Qayta kiriting:")
            return True

        now        = datetime.now().strftime("%d.%m.%Y %H:%M")
        title_html = text_with_premium_emojis(update.message) or text

        DB["movies"][code] = {
            "title": title_html,
            "episodes": [],
            "prices": {},
            "added_date": now,
            "poster_file_id": None,
        }
        await save_now()

        context.user_data["admin_state"] = "add_movie_poster"
        context.user_data["poster_code"] = code

        await sm(context.bot, uid,
            f"✅ <b>{title_html}</b> kinosi qo'shildi!\n"
            f"Kod: <code>{code}</code>\n"
            f"Jami kinolar: <b>{len(DB['movies'])} ta</b>\n\n"
            f"📷 Kino posterini yuboring\n"
            f"<i>(poster yo'q bo'lsa <b>0</b> kiriting)</i>")
        return True

    if state == "add_movie_poster":
        code = context.user_data.pop("poster_code", None)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("new_movie_code", None)
        if code and code in DB["movies"]:
            await sm(context.bot, uid,
                f"✅ Poster o'tkazib yuborildi.\n"
                f"Kod: <code>{code}</code>\n\n"
                f"Endi qism qo'shishingiz mumkin 👇",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "✅ Kino qo'shildi!", admin_menu_kb())
        return True

    if state == "add_ep_code":
        code = text.upper().strip()
        if not code:
            await sm(context.bot, uid, "❌ Kod kiriting:")
            return True
        # Admin tugmasi kino kodi emas
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. Kino kodini kiriting:")
            return True

        if code not in DB["movies"]:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {DB['movies'].get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> topilmadi.\n\nShunga o'xshash:\n{hint}\n\nTo'g'ri kodini kiriting:")
            else:
                movies_list = DB.get("movies", {})
                if movies_list:
                    last5 = "\n".join([f"• <code>{c}</code> — {m.get('title',c)}"
                                       for c, m in list(movies_list.items())[-5:]])
                    await sm(context.bot, uid,
                        f"❌ <code>{code}</code> kodli kino topilmadi.\n\n"
                        f"So'nggi kinolar:\n{last5}\n\nQayta kino kodini kiriting:")
                else:
                    await sm(context.bot, uid,
                        f"❌ <code>{code}</code> kodli kino topilmadi.\n\n"
                        f"⚠️ Hali hech qanday kino qo'shilmagan. Avval kino qo'shing!")
                    context.user_data.pop("admin_state", None)
            return True

        movie  = DB["movies"][code]
        ep_num = len(movie.get("episodes", [])) + 1
        context.user_data["ep_movie_code"] = code
        context.user_data["admin_state"]   = "add_ep_video"
        await sm(context.bot, uid,
            f"🎬 <b>{movie.get('title', code)}</b>\n"
            f"Kod: <code>{code}</code>\n"
            f"Hozirgi qismlar: <b>{len(movie.get('episodes', []))} ta</b>\n\n"
            f"📹 <b>{ep_num}-qism</b> uchun video yuboring:")
        return True

    if state == "add_ep_video":
        code = context.user_data.get("ep_movie_code", "")
        movie = DB["movies"].get(code, {})
        ep_num = len(movie.get("episodes", [])) + 1
        await sm(context.bot, uid,
            f"⚠️ Iltimos, matn emas — <b>video fayl</b> yuboring!\n\n"
            f"🎬 Kino: <b>{movie.get('title', code)}</b>\n"
            f"📹 <b>{ep_num}-qism</b> kutilmoqda...")
        return True

    if state == "set_price_code":
        # Admin tugmasi kino kodi emas
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. Kino kodini kiriting:")
            return True
        code = text.upper().strip()
        if code not in DB["movies"]:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {DB['movies'].get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> topilmadi.\n\nShunga o'xshash:\n{hint}\n\nTo'g'ri kodini kiriting:")
            else:
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> kodli kino topilmadi.\nQayta kino kodini kiriting:")
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
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> endi <b>bepul</b>!",
                admin_menu_kb())
        else:
            DB["movies"][code].setdefault("prices", {})[ep] = amount
            await save_now()
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
        context.user_data["ch_info"]     = channel_info
        context.user_data["admin_state"] = "add_channel_title"
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
        await save_now()
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
        # Admin tugmasi kino kodi emas
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. Kino kodini kiriting:")
            return True
        code = text.upper().strip()
        if code not in DB["movies"]:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {DB['movies'].get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> topilmadi.\n\nShunga o'xshash:\n{hint}\n\nTo'g'ri kodini kiriting:")
            else:
                await sm(context.bot, uid, "❌ Bunday kod yo'q. Qayta kiriting:")
            return True
        context.user_data["post_code"]   = code
        context.user_data["admin_state"] = "post_channel_target"
        await sm(context.bot, uid, "Kanal username'ini kiriting (masalan @mychannel):")
        return True

    if state == "post_channel_target":
        channel = text.strip()
        code    = context.user_data.pop("post_code", None)
        context.user_data.pop("admin_state", None)
        if not code:
            await sm(context.bot, uid, "❌ Kino kodi topilmadi. Qayta boshlang.")
            return True
        movie    = DB["movies"].get(code, {})
        bot_me   = await context.bot.get_me()
        markup   = channel_post_kb(bot_me.username, code)
        title    = movie.get("title", code)
        ep_count = len(movie.get("episodes", []))
        caption  = (
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
    existing         = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
    existing_label   = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
    existing_emoji_p = extract_emoji_prefix(existing)
    new_emoji_p      = (existing_emoji_p + emoji) if existing_emoji_p else emoji
    new_text         = f"{new_emoji_p} {existing_label}"
    DB.setdefault("btn_texts", {})[key] = new_text
    EMOJI_IDS.pop(key, None)
    DB.get("emoji_ids", {}).pop(key, None)
    await save_now()
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
        if msg.photo and code and code in DB["movies"]:
            DB["movies"][code]["poster_file_id"] = msg.photo[-1].file_id
            await save_now()
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
        if not msg.video:
            movie = DB["movies"].get(code, {})
            ep_num = len(movie.get("episodes", [])) + 1
            await sm(context.bot, uid,
                f"⚠️ Faqat <b>video</b> yuboring!\n"
                f"Kino: <b>{movie.get('title', code)}</b>\n"
                f"<b>{ep_num}-qism</b> kutilmoqda...")
            return

        DB["movies"][code]["episodes"].append(msg.video.file_id)
        ep_num = len(DB["movies"][code]["episodes"])

        # DARHOL saqlash — muhim! (retry bilan)
        save_ok = await db_save_async(DB)
        if not save_ok:
            # Qayta urinish
            await asyncio.sleep(2)
            await db_save_async(DB)

        context.user_data.pop("admin_state", None)
        context.user_data.pop("ep_movie_code", None)

        movie = DB["movies"][code]
        await sm(context.bot, uid,
            f"✅ <b>{ep_num}-qism</b> saqlandi!\n"
            f"Kino: <b>{movie.get('title', code)}</b>\n"
            f"Kod: <code>{code}</code>\n"
            f"Jami qismlar: <b>{ep_num} ta</b>\n\n"
            f"Yana qism qo'shish yoki narx belgilash:",
            movie_added_kb(code))
        return

    if uid == ADMIN_ID and state == "set_install":
        if msg.video:
            DB["settings"]["install_video_id"] = msg.video.file_id
            await save_now()
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "✅ O'rnatish videosi saqlandi!", admin_menu_kb())
        elif msg.document:
            DB["settings"]["install_file_id"] = msg.document.file_id
            await save_now()
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

    logger.info(f"📦 Storage: JSONBlob={bool(JSONBLOB_URL)}, "
                f"GSheet={bool(GSHEET_ID)}, npoint={bool(NPOINT_URL)}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))

    async def _periodic_sync(context_job):
        """Har 5 daqiqada JSONBlob ga to'liq DB sync"""
        try:
            DB["emoji_ids"] = dict(EMOJI_IDS)
            _save_local(DB)
            was_down = DB_STATUS.get("ram_only", False)
            ok = await asyncio.to_thread(_save_jsonblob, DB)
            now_str = datetime.now().strftime("%H:%M:%S")
            if ok:
                DB_STATUS["storage_ok"]   = True
                DB_STATUS["fail_count"]   = 0
                DB_STATUS["last_save_ok"] = now_str
                if was_down:
                    DB_STATUS["ram_only"] = False
                    # Admin ga xabar ber
                    try:
                        await context_job.bot.send_message(
                            ADMIN_ID,
                            f"✅ <b>Storage tiklandi!</b>\n"
                            f"JSONBlob yana ishlayapti — {now_str}\n"
                            f"RAMdagi {len(DB.get('movies', {}))} kino saqlandi.",
                            parse_mode="HTML")
                    except Exception:
                        pass
                status = "✅"
            else:
                DB_STATUS["fail_count"] = DB_STATUS.get("fail_count", 0) + 1
                DB_STATUS["last_err"]   = now_str
                if DB_STATUS["fail_count"] >= 2:
                    DB_STATUS["storage_ok"] = False
                    DB_STATUS["ram_only"]   = True
                # Faqat birinchi marta xato bo'lganda admin ga xabar
                if DB_STATUS["fail_count"] == 2:
                    try:
                        await context_job.bot.send_message(
                            ADMIN_ID,
                            f"⚠️ <b>Storage ishlamayapti!</b>\n"
                            f"JSONBlob ulanmadi — {now_str}\n"
                            f"Bot hozir faqat RAMdan ishlayapti.\n"
                            f"Ma'lumotlar yo'qolmaydi (lokal backup bor).",
                            parse_mode="HTML")
                    except Exception:
                        pass
                status = "⚠️"
            logger.info(f"{status} Periodik sync: {len(DB.get('movies', {}))} kino, "
                       f"{len(DB.get('users', {}))} user | RAM_ONLY={DB_STATUS['ram_only']}")
        except Exception as e:
            logger.error(f"Periodik sync xato: {e}")

    if app.job_queue:
        app.job_queue.run_repeating(_periodic_sync, interval=300, first=60)
        logger.info("🔄 Periodik sync yoqildi (har 5 daqiqada → JSONBlob)")

    logger.info(f"🚀 Bot v17 ishga tushdi! — {len(DB.get('movies', {}))} kino, "
                f"{len(DB.get('users', {}))} foydalanuvchi")

    async def _startup_notify(context_job):
        """Bot ishga tushganda adminga storage holati haqida xabar"""
        try:
            movies_n = len(DB.get("movies", {}))
            users_n  = len(DB.get("users", {}))
            # Storage test
            ok = await asyncio.to_thread(_save_jsonblob, DB)
            now_str = datetime.now().strftime("%H:%M:%S")
            if ok:
                DB_STATUS["storage_ok"]   = True
                DB_STATUS["last_save_ok"] = now_str
                DB_STATUS["ram_only"]     = False
                storage_msg = f"🟢 JSONBlob ishlayapti — {now_str}"
            else:
                DB_STATUS["storage_ok"] = False
                DB_STATUS["ram_only"]   = True
                DB_STATUS["last_err"]   = now_str
                storage_msg = f"🔴 JSONBlob ishlamayapti! Bot RAMdan ishlaydi."
            await context_job.bot.send_message(
                ADMIN_ID,
                f"🚀 <b>Bot ishga tushdi!</b>\n\n"
                f"📦 RAM da: <b>{movies_n}</b> kino, <b>{users_n}</b> user\n"
                f"💾 Storage: {storage_msg}",
                parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Startup notify xato: {e}")

    if app.job_queue:
        app.job_queue.run_once(_startup_notify, when=5)
        app.job_queue.run_repeating(_periodic_sync, interval=300, first=60)
        logger.info("🔄 Periodik sync yoqildi (har 5 daqiqada → JSONBlob)")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
