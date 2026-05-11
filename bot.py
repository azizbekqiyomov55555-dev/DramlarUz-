# -*- coding: utf-8 -*-
"""
Kino Bot - v18 (RAM CACHE + TEZKOR QIDIRISH)
Asosiy tuzatishlar:
1. ✅ RAM_CACHE — barcha kinolar RAMda saqlanadi, bazaga fon rejimida yoziladi
2. ✅ Tezkor qidirish — RAMdan millisaniyada topadi
3. ✅ Ishga tushganda bazadan RAM ga yuklab oladi
4. ✅ Qo'shilgan kino darhol RAMga yoziladi
5. ✅ JSONBlob ga async fon rejimida saqlanadi (bot sekinlamaydi)
"""

import logging, asyncio, json, time, re, os, threading, copy
from datetime import datetime
from io import BytesIO
import requests

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# ─── KONFIGURATSIYA ────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN")  or "8723400610:AAH9haL0WChkCsGBx1AGW3uOGVt4XHOZ3LU"
ADMIN_ID   = int(os.environ.get("ADMIN_ID") or "8537782289")

JSONBLOB_URL      = os.environ.get("JSONBLOB_URL") or "https://jsonblob.com/api/jsonBlob/019df4aa-10b1-725c-83f5-9901ab2db9b6"
GSHEET_ID         = os.environ.get("GSHEET_ID")    or "1Lodn9MTb7nysq5l80cQVCu9IKfgQRlnNe654PT0hKQs"
GSHEET_API        = os.environ.get("GSHEET_API")   or ""
NPOINT_URL        = os.environ.get("NPOINT_URL")   or ""
LOCAL_BACKUP_FILE = "db_backup.json"
LOCAL_MOVIES_FILE = "movies_backup.json"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# ❗ RAM CACHE — barcha kinolar shu yerda saqlanadi
# ══════════════════════════════════════════════════════════
class RamCache:
    """
    Bot ishlayotganda barcha ma'lumotlar shu obyektda turadi.
    JSONBlob faqat fon rejimida yoziladi — bot sekinlamaydi.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.movies: dict   = {}   # {code: movie_dict}
        self.users: dict    = {}   # {uid_str: user_dict}
        self.channels: list = []
        self.card_number: str = ""
        self.pending_payments: dict = {}
        self.settings: dict = {
            "install_file_id": None,
            "install_video_id": None,
            "kino_kanal_url": "",
        }
        self.stats: dict    = {"total_views": 0}
        self.btn_texts: dict = {}
        self.emoji_ids: dict = {}
        self.sub_admins: dict = {}   # {uid_str: {"perms": {key: bool}}}
        self.loaded: bool   = False  # bazadan yuklandi?

    # ── Barcha ma'lumotlarni dict ga ──────────────────────
    def to_dict(self) -> dict:
        with self._lock:
            return {
                "movies":           copy.deepcopy(self.movies),
                "users":            copy.deepcopy(self.users),
                "channels":         copy.deepcopy(self.channels),
                "card_number":      self.card_number,
                "pending_payments": copy.deepcopy(self.pending_payments),
                "settings":         copy.deepcopy(self.settings),
                "stats":            copy.deepcopy(self.stats),
                "btn_texts":        copy.deepcopy(self.btn_texts),
                "emoji_ids":        copy.deepcopy(self.emoji_ids),
                "sub_admins":       copy.deepcopy(self.sub_admins),
            }

    # ── Dict dan yuklash ──────────────────────────────────
    def from_dict(self, data: dict):
        if not isinstance(data, dict):
            return
        with self._lock:
            self.movies           = data.get("movies", {}) or {}
            self.users            = data.get("users", {}) or {}
            self.channels         = data.get("channels", []) or []
            self.card_number      = data.get("card_number", "") or ""
            self.pending_payments = data.get("pending_payments", {}) or {}
            self.settings         = data.get("settings", {
                "install_file_id": None,
                "install_video_id": None,
                "kino_kanal_url": "",
            })
            self.stats            = data.get("stats", {"total_views": 0})
            self.btn_texts        = data.get("btn_texts", {}) or {}
            self.emoji_ids        = data.get("emoji_ids", {}) or {}
            self.sub_admins       = data.get("sub_admins", {}) or {}
            self.loaded           = True

    # ── Kino operatsiyalari ───────────────────────────────
    def get_movie(self, code: str) -> dict | None:
        return self.movies.get(code.upper())

    def set_movie(self, code: str, data: dict):
        with self._lock:
            self.movies[code.upper()] = data

    def del_movie(self, code: str):
        with self._lock:
            self.movies.pop(code.upper(), None)

    def get_all_movies(self) -> dict:
        return self.movies  # direct ref — tezkor

    # ── Foydalanuvchi operatsiyalari ──────────────────────
    def get_user(self, uid) -> dict:
        return self.users.get(str(uid), {})

    def set_user(self, uid, data: dict):
        with self._lock:
            self.users[str(uid)] = data

    def ensure_user(self, uid):
        uid_str = str(uid)
        with self._lock:
            if uid_str not in self.users:
                self.users[uid_str] = {
                    "paid_episodes": {},
                    "watched": {},
                }
            u = self.users[uid_str]
            # Eski foydalanuvchilar uchun kalitlar yo'q bo'lsa — qo'shamiz
            if "paid_episodes" not in u or not isinstance(u.get("paid_episodes"), dict):
                u["paid_episodes"] = {}
            if "watched" not in u or not isinstance(u.get("watched"), dict):
                u["watched"] = {}
        return self.users[uid_str]


# Global RAM cache
RAM = RamCache()


def price_to_int(value) -> int:
    """Narxni xavfsiz int ga aylantiradi. 0/bo'sh qiymat bepul hisoblanadi."""
    try:
        if value in (None, "", 0, "0"):
            return 0
        return int(str(value).strip())
    except Exception:
        return 0


def episode_paid_key(code, ep) -> str:
    """Har bir kino-qism uchun yagona alohida to'lov kaliti."""
    return f"{str(code).upper()}_{str(ep)}"


def has_approved_payment(user_id, code, ep) -> bool:
    """Faqat shu foydalanuvchi + shu kino + shu qism uchun tasdiqlangan chekni tekshiradi."""
    uid = str(user_id)
    code = str(code).upper()
    ep = str(ep)
    for pay in (RAM.pending_payments or {}).values():
        if (str(pay.get("user_id")) == uid
                and str(pay.get("code", "")).upper() == code
                and str(pay.get("ep")) == ep
                and pay.get("status") == "approved"):
            return True
    return False


def is_episode_paid(user_id, code, ep) -> bool:
    """
    Bir qism sotib olingani faqat o'sha qism uchun tekshiriladi.
    Eski xato bool yozuvlar faqat approved payment mavjud bo'lsa tan olinadi;
    shunda bitta qism sotib olish boshqa qismlarni ochib yubormaydi.
    """
    uid = str(user_id)
    code = str(code).upper()
    ep = str(ep)
    key = episode_paid_key(code, ep)
    user = RAM.ensure_user(uid)
    paid = user.setdefault("paid_episodes", {})
    value = paid.get(key)

    if isinstance(value, dict):
        return value.get("status") == "approved" or bool(value.get("approved"))

    if value:
        # Legacy True qiymatlarni faqat aynan shu qismga approved chek bo'lsa qabul qilamiz.
        return has_approved_payment(uid, code, ep)

    return False


# ── Admin huquqlari ─────────────────────────────────────────
ADMIN_PERM_KEYS = [
    "kino_joy", "qism_qosh", "pullik", "stat", "kanal_post",
    "maj_kanal", "karta", "ilova", "emoji_soz", "kino_kanal_set",
    "qism_tahrir", "kino_uch", "broadcast",
]

def is_super_admin(uid) -> bool:
    try: return int(uid) == ADMIN_ID
    except: return False

def is_any_admin(uid) -> bool:
    if is_super_admin(uid): return True
    return str(uid) in (RAM.sub_admins or {})

def has_perm(uid, key: str) -> bool:
    if is_super_admin(uid): return True
    sub = (RAM.sub_admins or {}).get(str(uid))
    if not sub: return False
    perms = sub.get("perms", {}) or {}
    # Default: allowed (True). Faqat aniq False bo'lsa — taqiqlangan.
    return perms.get(key, True) is not False


# ❗ Global update_id dedup — bir xil update ikki marta ishlanmasin
_SEEN_UPDATE_IDS: set = set()
_SEEN_MAX = 1000

def _is_duplicate_update(update) -> bool:
    """True bo'lsa — bu update allaqachon ishlangan, o'tkazib yuborish kerak."""
    uid = getattr(update, "update_id", None)
    if uid is None:
        return False
    if uid in _SEEN_UPDATE_IDS:
        logger.warning(f"⚠️ Duplicate update_id={uid} — o'tkazib yuborildi")
        return True
    _SEEN_UPDATE_IDS.add(uid)
    if len(_SEEN_UPDATE_IDS) > _SEEN_MAX:
        oldest = sorted(_SEEN_UPDATE_IDS)[:200]
        for x in oldest:
            _SEEN_UPDATE_IDS.discard(x)
    return False

# ══════════════════════════════════════════════════════════
# STORAGE STATUS
# ══════════════════════════════════════════════════════════
DB_STATUS = {
    "storage_ok": True,
    "fail_count": 0,
    "last_save_ok": None,
    "last_err": None,
    "ram_only": False,
    "pending_save": False,   # saqlanish navbatda?
    "load_failed": False,    # ❗ True bo'lsa — JSONBlob ga YOZISH BLOKLANGAN
}

EMOJI_IDS: dict = {}  # RAM.emoji_ids bilan sinxron

# ─── UNICODE QALIN ─────────────────────────────────────────
def to_bold(text: str) -> str:
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':   result.append(chr(0x1D5D4 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z': result.append(chr(0x1D5EE + ord(ch) - ord('a')))
        elif '0' <= ch <= '9': result.append(chr(0x1D7EC + ord(ch) - ord('0')))
        else:                  result.append(ch)
    return ''.join(result)

_B = to_bold

# ─── BUTTON TEXTS ──────────────────────────────────────────
DEFAULT_BTN = {
    "yordam":         _B('Yordam'),
    "install":        _B('Ilovani ornatish'),
    "barcha_kino":    _B('Barcha kinolar'),
    "kino_kanal":     _B('Kino kodlari kanali'),
    "kino_joy":       _B('Kino joylash'),
    "qism_qosh":      _B('Qism qoshish'),
    "pullik":         _B('Qismni pullik qilish'),
    "stat":           _B('Statistika'),
    "kanal_post":     _B('Kanalga post'),
    "maj_kanal":      _B('Majburiy kanal'),
    "karta":          _B('Karta raqami'),
    "ilova":          _B('Ilova fayl/video'),
    "emoji_soz":      _B('Emoji sozlamalari'),
    "asosiy":         _B('Asosiy menyu'),
    "boshqarish":     _B('Boshqarish'),
    "tekshir":        _B('Tekshirish'),
    "tasdiq":         _B('Tasdiqlash'),
    "bekor":          _B('Bekor qilish'),
    "ulash":          _B('Dostlarga ulashish'),
    "tomosha":        _B('Tomosha qilish'),
    "javob":          _B('Javob berish'),
    "yangi":          _B('Yangilash'),
    "qism_add":       _B('Qism qoshish'),
    "narx_bel":       _B('Narx belgilash'),
    "kut":            _B('Tasdiqlanishini kuting'),
    "bosh":           _B('Bosh menyu'),
    "tiklash":        _B('Hammasini tiklash'),
    "yopish":         _B('Yopish'),
    "default_q":      _B('Defaultga qaytarish'),
    "orqaga":         _B('Orqaga'),
    "broadcast":      _B('Barchaga xabar'),
    "kino_uch":       _B('Kino ochirish'),
    "prev_qism":      _B('Oldingi qismlar'),
    "next_qism":      _B('Boshqa qismlar'),
    "kino_kanal_set": _B('Kino kanali linkini ornatish'),
    "chek_yub":       _B('Chek yuborish'),
    "karta_nusxa":    _B('Karta nusxalash'),
    "miqdor_nusxa":   _B('Miqdor nusxalash'),
    "kanal_qosh":     _B('Kanal qoshish'),
    "kanal_uch":      _B('Kanal ochirish'),
    "kanal_royxat":   _B('Kanallar royxati'),
    "admin_panel":    _B('Admin panel'),
    "qism_tahrir":    _B('Qismlarni tahrirlash'),
    "admin_qosh":     _B('Admin qoshish'),
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
BTN_LABELS["chek_yub"]     = "Chek yuborish"
BTN_LABELS["karta_nusxa"]  = "Karta nusxalash"
BTN_LABELS["miqdor_nusxa"] = "Miqdor nusxalash"
BTN_LABELS["kanal_qosh"]   = "Kanal qo'shish"
BTN_LABELS["kanal_uch"]    = "Kanal o'chirish"
BTN_LABELS["kanal_royxat"] = "Kanallar ro'yxati"
BTN_LABELS["admin_panel"]  = "Admin panel (orqaga)"
BTN_LABELS["qism_tahrir"]  = "Qismlarni tahrirlash"
BTN_LABELS["admin_qosh"]   = "Admin qo'shish"
LABEL_TO_KEY = {v: k for k, v in BTN_LABELS.items()}

# ══════════════════════════════════════════════════════════
# LOKAL FAYL OPERATSIYALARI
# ══════════════════════════════════════════════════════════

def _save_local(data: dict) -> bool:
    try:
        movies = data.get("movies", {})
        tmp = LOCAL_MOVIES_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False)
        os.replace(tmp, LOCAL_MOVIES_FILE)

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
        db = {}
        if os.path.exists(LOCAL_BACKUP_FILE):
            with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        movies = {}
        if os.path.exists(LOCAL_MOVIES_FILE):
            with open(LOCAL_MOVIES_FILE, "r", encoding="utf-8") as f:
                movies = json.load(f)
        db["movies"] = movies
        return db if isinstance(db, dict) else {}
    except Exception as e:
        logger.error(f"Lokal yuklash xato: {e}")
        return None


# ══════════════════════════════════════════════════════════
# JSONBLOB OPERATSIYALARI
# ══════════════════════════════════════════════════════════

def _save_jsonblob(data: dict, retries: int = 3) -> bool:
    if not JSONBLOB_URL:
        return False
    # ❗ Yuklash bajarilmagan bo'lsa — saqlashni BLOKLAYMIZ
    if DB_STATUS.get("load_failed"):
        logger.warning("🛑 JSONBlob ga yozish bloklangan (load_failed) — bazani saqlab qolish uchun.")
        return False
    # ❗ Bo'sh movies bilan yozishni rad etamiz (himoya)
    movies = data.get("movies") if isinstance(data, dict) else None
    if isinstance(movies, dict) and len(movies) == 0:
        logger.warning("🛑 Bo'sh movies bilan JSONBlob ga yozish RAD ETILDI — himoya.")
        return False
    payload = json.dumps(data, ensure_ascii=False)
    size_kb = len(payload.encode("utf-8")) / 1024
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
            logger.error(f"JSONBlob #{attempt+1} status {r.status_code}")
        except Exception as e:
            logger.error(f"JSONBlob #{attempt+1} xato: {e}")
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))
    return False


def _load_jsonblob() -> dict | None:
    """JSONBlob dan yuklash — 6 marta urinadi, har xato uchun kechikish oshadi."""
    if not JSONBLOB_URL:
        return None
    last_err = None
    for attempt in range(6):
        try:
            r = requests.get(
                JSONBLOB_URL,
                headers={"Accept": "application/json"},
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    logger.info(f"✅ JSONBlob dan yuklandi: "
                                f"{len(data.get('movies', {}))} kino, "
                                f"{len(data.get('users', {}))} user")
                    return data
                else:
                    logger.error(f"JSONBlob noto'g'ri format: {type(data)}")
            else:
                logger.error(f"JSONBlob load #{attempt+1} status {r.status_code}")
        except Exception as e:
            last_err = e
            logger.error(f"JSONBlob load #{attempt+1} xato: {e}")
        if attempt < 5:
            time.sleep(2 * (attempt + 1))
    logger.error(f"❌ JSONBlob dan yuklab bo'lmadi (6 urinish). Oxirgi xato: {last_err}")
    return None


# ══════════════════════════════════════════════════════════
# DB YUKLASH — ishga tushganda bir marta chaqiriladi
# ══════════════════════════════════════════════════════════

def _merge_db(blob: dict | None, local: dict | None) -> dict:
    """
    JSONBlob va lokal fayldagi ma'lumotlarni BIRLASHTIRADI.
    Hech qanday kino yo'qolmasligi uchun:
      • Har bir kino bo'yicha — qaysi manbada ko'proq qism bo'lsa, o'sha tanlanadi
      • Faqat bir manbada bor kinolar — o'shanday qo'shiladi
      • Foydalanuvchilar — birlashadi (lokal ustun, chunki yangiroq)
      • Sozlamalar — lokal ustun
    """
    blob  = blob  if isinstance(blob,  dict) else {}
    local = local if isinstance(local, dict) else {}

    blob_movies  = (blob.get("movies")  or {}) if isinstance(blob.get("movies"),  dict) else {}
    local_movies = (local.get("movies") or {}) if isinstance(local.get("movies"), dict) else {}

    merged_movies: dict = {}
    all_codes = set(blob_movies.keys()) | set(local_movies.keys())
    for code in all_codes:
        b = blob_movies.get(code)
        l = local_movies.get(code)
        if b and not l:
            merged_movies[code] = b
        elif l and not b:
            merged_movies[code] = l
        elif b and l:
            # Ikkalasida ham bor — ko'proq qism bor versiyani olamiz
            b_eps = len((b or {}).get("episodes", []) or [])
            l_eps = len((l or {}).get("episodes", []) or [])
            if l_eps >= b_eps:
                base = dict(l)
                # narxlarni ham birlashtir
                prices = dict((b or {}).get("prices", {}) or {})
                prices.update((l or {}).get("prices", {}) or {})
                base["prices"] = prices
                merged_movies[code] = base
            else:
                base = dict(b)
                prices = dict((l or {}).get("prices", {}) or {})
                prices.update((b or {}).get("prices", {}) or {})
                base["prices"] = prices
                merged_movies[code] = base

    # Foydalanuvchilar — birlashadi (lokal ustun)
    merged_users = {}
    merged_users.update((blob.get("users")  or {}) if isinstance(blob.get("users"),  dict) else {})
    merged_users.update((local.get("users") or {}) if isinstance(local.get("users"), dict) else {})

    # Boshqa maydonlar — lokal ustun, bo'lmasa blob
    def pick(key, default):
        if key in local and local.get(key):
            return local.get(key)
        if key in blob and blob.get(key):
            return blob.get(key)
        return default

    return {
        "movies":           merged_movies,
        "users":            merged_users,
        "channels":         pick("channels", []),
        "card_number":      pick("card_number", ""),
        "pending_payments": pick("pending_payments", {}),
        "settings":         pick("settings", {
            "install_file_id": None, "install_video_id": None, "kino_kanal_url": "",
        }),
        "stats":            pick("stats", {"total_views": 0}),
        "btn_texts":        pick("btn_texts", {}),
        "emoji_ids":        pick("emoji_ids", {}),
        "sub_admins":       pick("sub_admins", {}),
    }


def db_initial_load():
    """
    Ishga tushganda:
    1. JSONBlob VA lokal fayldan ikkalasini ham yuklaymiz
    2. Ularni BIRLASHTIRAMIZ (hech qanday kino yo'qolmaydi)
    3. RAMga yozamiz
    4. Ikkala manbaga ham birlashtirilgan natijani sync qilamiz

    ❗ MUHIM: Agar JSONBlob yuklab bo'lmasa VA lokal ham bo'sh bo'lsa —
       BOTNI TO'XTATAMIZ. Aks holda bo'sh RAM JSONBlob ga yozilib, barcha
       kinolar o'chib ketishi mumkin (Fly.io kabi efemer hostingda).
    """
    logger.info("🔄 Ma'lumotlar yuklanmoqda (blob + lokal birlashtirish)...")

    blob  = _load_jsonblob()
    local = _load_local()

    has_blob  = bool(blob  and (blob.get("movies")  or blob.get("users")))
    has_local = bool(local and (local.get("movies") or local.get("users")))

    # ❗ XAVFSIZLIK: agar JSONBlob URL berilgan bo'lsa-yu, undan
    # yuklab bo'lmagan bo'lsa — saqlashni BLOKLAYMIZ. Aks holda
    # bo'sh RAM bazaga yozilib, kinolar o'chib ketadi.
    if JSONBLOB_URL and blob is None:
        logger.error("🛑 JSONBlob dan yuklab bo'lmadi! "
                     "Saqlash bloklanmoqda — bazani buzilishdan saqlash uchun.")
        DB_STATUS["storage_ok"] = False
        DB_STATUS["ram_only"]   = True
        DB_STATUS["last_err"]   = "JSONBlob yuklanmadi — saqlash bloklangan"
        DB_STATUS["load_failed"] = True   # ❗ saqlash funksiyalari shuni tekshiradi
        if has_local:
            RAM.from_dict(local)
            EMOJI_IDS.clear()
            EMOJI_IDS.update(RAM.emoji_ids)
            logger.warning(f"⚠️ Faqat lokal yuklandi: {len(RAM.movies)} kino. "
                           "JSONBlob ga YOZILMAYDI!")
        else:
            RAM.loaded = True
            logger.error("⚠️ Hech narsa yuklanmadi va saqlash bloklangan.")
        return

    if not has_blob and not has_local:
        logger.warning("⚠️ Ma'lumot topilmadi — bo'sh RAM boshlanadi")
        RAM.loaded = True
        return

    merged = _merge_db(blob, local)
    RAM.from_dict(merged)
    EMOJI_IDS.clear()
    EMOJI_IDS.update(RAM.emoji_ids)

    blob_eps  = sum(len(m.get("episodes", []) or []) for m in (blob.get("movies")  or {}).values()) if has_blob  else 0
    local_eps = sum(len(m.get("episodes", []) or []) for m in (local.get("movies") or {}).values()) if has_local else 0
    merged_eps = sum(len(m.get("episodes", []) or []) for m in RAM.movies.values())
    logger.info(f"✅ Birlashtirildi → RAM: {len(RAM.movies)} kino, {merged_eps} qism, {len(RAM.users)} user "
                f"(blob: {len(blob.get('movies',{}) if has_blob else {})}/{blob_eps}, "
                f"lokal: {len(local.get('movies',{}) if has_local else {})}/{local_eps})")

    # Ikkala manbaga ham birlashtirilgan natijani yozib qo'yamiz —
    # endi keyingi safar ham hech narsa yo'qolmaydi.
    _save_local(merged)
    if JSONBLOB_URL:
        threading.Thread(target=_save_jsonblob, args=(copy.deepcopy(merged),), daemon=True).start()
        logger.info("⏳ Birlashtirilgan ma'lumot JSONBlob ga sync qilinmoqda (fon)...")


# ══════════════════════════════════════════════════════════
# SAQLASH — RAM → lokal + JSONBlob (debounced background)
# ══════════════════════════════════════════════════════════
#
# Strategiya:
#   • RAM      — darhol yoziladi (millisaniyada)
#   • Lokal    — har o'zgarishda darhol yoziladi (tez, ishonchli)
#   • JSONBlob — DEBOUNCE bilan fon rejimida (oxirgi o'zgarishdan
#                JSONBLOB_DEBOUNCE soniya keyin bir marta yoziladi).
#   Misol: admin ketma-ket 10 ta qism yuborsa — JSONBlob ga
#          BIR MARTA, hammasi tugagandan keyin yoziladi.
# ──────────────────────────────────────────────────────────

JSONBLOB_DEBOUNCE = 12.0   # soniya — qism yuborish tugagandan keyin

_jsonblob_timer_task = None     # asyncio.Task — kutilayotgan saqlash
_jsonblob_save_lock = None      # asyncio.Lock — _setup da yaratiladi


def _ensure_lock():
    global _jsonblob_save_lock
    if _jsonblob_save_lock is None:
        _jsonblob_save_lock = asyncio.Lock()
    return _jsonblob_save_lock


async def _do_jsonblob_save() -> bool:
    """Haqiqiy JSONBlob ga yozish (status ham yangilanadi)."""
    async with _ensure_lock():
        data = RAM.to_dict()
        ok = await asyncio.to_thread(_save_jsonblob, data)
        now_str = datetime.now().strftime("%H:%M:%S")
        if ok:
            DB_STATUS.update({
                "storage_ok": True,
                "fail_count": 0,
                "last_save_ok": now_str,
                "ram_only": False,
                "pending_save": False,
            })
        else:
            DB_STATUS["fail_count"] = DB_STATUS.get("fail_count", 0) + 1
            DB_STATUS["last_err"] = now_str
            if DB_STATUS["fail_count"] >= 2:
                DB_STATUS.update({"storage_ok": False, "ram_only": True})
        return ok


async def _delayed_jsonblob_save(delay: float):
    """Belgilangan vaqtdan keyin JSONBlob ga yozish."""
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return  # yangi o'zgarish keldi — bu task bekor qilindi
    try:
        await _do_jsonblob_save()
    except Exception as e:
        logger.error(f"JSONBlob debounced save xato: {e}")


async def schedule_save(delay: float = JSONBLOB_DEBOUNCE):
    """
    RAMni saqlash navbatiga qo'yadi.
      • Lokal faylga DARHOL yoziladi (tez, ishonchli)
      • JSONBlob ga `delay` soniyadan keyin yoziladi
      • Agar `delay` ichida yana o'zgarish bo'lsa — taymer qaytadan
        boshlanadi (oxirgi o'zgarishdan keyin bir marta saqlash)
    """
    global _jsonblob_timer_task
    DB_STATUS["pending_save"] = True
    # Lokal faylga darhol yoz
    try:
        _save_local(RAM.to_dict())
    except Exception as e:
        logger.error(f"Lokal saqlash xato: {e}")

    # Eski kutilayotgan taymer bo'lsa — bekor qil va qaytadan boshla
    if _jsonblob_timer_task and not _jsonblob_timer_task.done():
        _jsonblob_timer_task.cancel()
    _jsonblob_timer_task = asyncio.create_task(_delayed_jsonblob_save(delay))


def save_sync():
    """Sinxron (thread) — lokal + JSONBlob fon rejimida."""
    data = RAM.to_dict()
    _save_local(data)
    threading.Thread(target=_save_jsonblob, args=(copy.deepcopy(data),), daemon=True).start()


async def save_now() -> bool:
    """
    DARHOL saqlash — kutilayotgan debounce taymerni bekor qiladi va
    JSONBlob ga shu lahzada yozadi. Muhim operatsiyalar uchun.
    """
    global _jsonblob_timer_task
    if _jsonblob_timer_task and not _jsonblob_timer_task.done():
        _jsonblob_timer_task.cancel()
    try:
        _save_local(RAM.to_dict())
    except Exception as e:
        logger.error(f"Lokal saqlash xato: {e}")
    return await _do_jsonblob_save()


async def save_ram_only():
    """
    Faqat lokal faylga yozadi — JSONBlob ga TEGMAYDI.
    Qism (video) qo'shganda ishlatiladi: ko'p video ketma-ket
    yuborilsa, har biri uchun JSONBlob ga yozish shart emas.
    """
    try:
        _save_local(RAM.to_dict())
    except Exception as e:
        logger.error(f"save_ram_only lokal xato: {e}")
    DB_STATUS["pending_save"] = True


# ══════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════════════

def bt(key: str) -> str:
    raw = RAM.btn_texts.get(key) or DEFAULT_BTN.get(key, "")
    return _B(raw)


def get_eid(key: str):
    return EMOJI_IDS.get(key)


def _norm_search_text(value: str) -> str:
    value = (value or "").upper().strip()
    value = re.sub(r"[^A-Z0-9А-ЯЁЎҚҒҲІЇЄÑÇŞĞÖÜ' ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def find_movie_code(query: str):
    """
    RAMdan kino qidiradi — millisaniyada ishlaydi.
    Qaytaradi: (code, []) yoki (None, [matches])

    Qo'shilgan tuzatishlar:
      • Case-insensitive kod qidirish (RAM kalitlari .upper() bilan saqlanadi)
      • Raqamli kodlar uchun leading-zero (masalan, "1" → "01" / "001" ham topiladi)
      • Yana bo'shliq/belgilarni tozalab solishtirish
    """
    raw = (query or "").strip()
    if not raw:
        return None, []

    movies = RAM.movies  # to'g'ridan-to'g'ri RAM dan
    if not movies:
        return None, []

    # 1. To'liq kod bo'yicha (case-insensitive)
    code_upper = raw.upper().strip()
    if code_upper in movies:
        return code_upper, []

    # 1b. Bo'shliq/belgi tozalangan kod bo'yicha
    code_clean = re.sub(r"\s+", "", code_upper)
    if code_clean and code_clean in movies:
        return code_clean, []

    # 1c. Raqamli kod — leading zero variantlari
    if code_clean.isdigit():
        digit_matches = []
        try:
            num_val = int(code_clean)
        except Exception:
            num_val = None
        for c in movies.keys():
            if isinstance(c, str) and c.isdigit():
                try:
                    if int(c) == num_val:
                        digit_matches.append(c)
                except Exception:
                    pass
        if len(digit_matches) == 1:
            return digit_matches[0], []
        if len(digit_matches) > 1:
            return None, digit_matches[:10]

    # 2. Matn qidirish
    q = _norm_search_text(raw)
    if not q:
        return None, []

    exact, partial = [], []
    for c, movie in movies.items():
        title = movie.get("title", c) if isinstance(movie, dict) else c
        title_norm = _norm_search_text(title)
        code_norm  = _norm_search_text(c)
        if q == title_norm or q == code_norm:
            exact.append(c)
        elif q in title_norm or title_norm in q or q in code_norm or code_norm in q:
            partial.append(c)

    matches = exact or partial
    if len(matches) == 1:
        return matches[0], []
    return None, matches[:10]


def movie_suggestions_text(codes: list) -> str:
    lines = []
    for c in codes:
        movie = RAM.movies.get(c, {})
        lines.append(f"• <b>{movie.get('title', c)}</b> — kod: <code>{c}</code>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# FOYDALANUVCHI RO'YXATGA OLISH
# ══════════════════════════════════════════════════════════

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
        return r.status_code in (200, 201)
    except Exception as e:
        logger.warning(f"GSheet xato: {e}")
    return False


def _gsheet_log_user(user_id: int, name: str, username: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [str(user_id), name, f"@{username}" if username else "", now]
    threading.Thread(target=_gsheet_append_row, args=(row,), daemon=True).start()


def register_user(user):
    uid_str = str(user.id)
    if uid_str not in RAM.users:
        RAM.users[uid_str] = {
            "name": user.full_name,
            "username": user.username or "",
            "joined": datetime.now().isoformat(),
            "paid_episodes": {},
            "watched": {},
        }
        _gsheet_log_user(user.id, user.full_name, user.username or "")
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(schedule_save())
        except RuntimeError:
            save_sync()


# ══════════════════════════════════════════════════════════
# SUB CACHE
# ══════════════════════════════════════════════════════════

_sub_cache: dict[int, tuple[float, list]] = {}
SUB_CACHE_TTL = 10

def _sub_cache_get(user_id):
    e = _sub_cache.get(user_id)
    if e and (time.time() - e[0]) < SUB_CACHE_TTL:
        return e[1]
    return None

def _sub_cache_set(user_id, result):
    _sub_cache[user_id] = (time.time(), result)

def _sub_cache_invalidate(user_id):
    _sub_cache.pop(user_id, None)


# ══════════════════════════════════════════════════════════
# EMOJI YORDAMCHI
# ══════════════════════════════════════════════════════════

EMOJI_RE = re.compile(
    r'[\U0001F000-\U0001FFFF\U00002600-\U000027BF'
    r'\U0000FE00-\U0000FE0F\U00020000-\U0002FA1F'
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
        txt_stripped = strip_emoji_prefix(text)
        if cur_stripped and txt_stripped and cur_stripped == txt_stripped:
            return key
    return None


# ══════════════════════════════════════════════════════════
# NAVIGATSIYA TEKSHIRISH
# ══════════════════════════════════════════════════════════

def _is_admin_nav_button(text: str) -> bool:
    for k in ["asosiy", "boshqarish", "orqaga", "admin_panel"]:
        v = bt(k)
        if v and (text == v or strip_emoji_prefix(text) == strip_emoji_prefix(v)):
            return True
    return False

def _get_admin_nav_key(text: str) -> str | None:
    for k in ["asosiy", "boshqarish", "orqaga", "admin_panel"]:
        v = bt(k)
        if v and (text == v or strip_emoji_prefix(text) == strip_emoji_prefix(v)):
            # orqaga / admin_panel ham admin panelga qaytaradi
            return "boshqarish" if k in ("orqaga", "admin_panel") else k
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


def admin_menu_kb(uid=None):
    pairs = [
        ("kino_joy",       "success"),
        ("qism_qosh",      "primary"),
        ("pullik",         "danger"),
        ("stat",           "primary"),
        ("kanal_post",     "primary"),
        ("maj_kanal",      "danger"),
        ("karta",          "success"),
        ("ilova",          "primary"),
        ("kino_kanal_set", "success"),
        ("emoji_soz",      "primary"),
        ("qism_tahrir",    "primary"),
        ("kino_uch",       "danger"),
        ("broadcast",      "danger"),
    ]
    if uid is not None and not is_super_admin(uid):
        pairs = [(k, st) for (k, st) in pairs if has_perm(uid, k)]
    rows, buf = [], []
    for k, st in pairs:
        buf.append(rbtn(bt(k), style=st, emoji_id=get_eid(k)))
        if len(buf) == 2:
            rows.append(buf); buf = []
    if buf: rows.append(buf)
    if uid is None or is_super_admin(uid):
        rows.append([rbtn(bt("admin_qosh"), style="success", emoji_id=get_eid("admin_qosh"))])
    rows.append([rbtn(bt("asosiy"), style="success", emoji_id=get_eid("asosiy"))])
    return rkb(rows)


def channel_manage_kb():
    return rkb([
        [rbtn(bt("kanal_qosh"),   style="success", emoji_id=get_eid("kanal_qosh")),
         rbtn(bt("kanal_uch"),    style="danger",  emoji_id=get_eid("kanal_uch"))],
        [rbtn(bt("kanal_royxat"), style="primary", emoji_id=get_eid("kanal_royxat"))],
        [rbtn(bt("admin_panel"),  style="success", emoji_id=get_eid("admin_panel"))],
    ])


def channel_delete_inline_kb(channels: list):
    rows = []
    for i, ch in enumerate(channels):
        rows.append([ibtn(
            f"{ch.get('title','?')} ({ch.get('username','?')})",
            data=f"ch_del|{i}", style="danger"
        )])
    rows.append([ibtn(bt("bekor"), data="ch_del_cancel", style="primary", emoji_id=get_eid("bekor"))])
    return ikb(rows)


def subscription_kb(channels: list):
    rows = [[ibtn(c["title"], url=c["url"], style="primary")] for c in channels]
    rows.append([ibtn(bt("tekshir"), data="check_sub", style="success", emoji_id=get_eid("tekshir"))])
    return ikb(rows)


PAGE_SIZE = 5

def movie_episodes_kb(movie: dict, code: str, user_id, page: int = 0):
    eps    = movie.get("episodes", [])
    prices = movie.get("prices", {}) or {}
    RAM.ensure_user(user_id)
    code   = str(code).upper()
    total  = len(eps)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end   = min(start + PAGE_SIZE, total)
    rows  = []
    ep_labels = movie.get("ep_labels", {}) or {}
    for i in range(start, end):
        ek = str(i + 1)
        price_int = price_to_int(prices.get(ek))
        already_paid = is_episode_paid(user_id, code, ek)
        locked = (price_int > 0) and (not already_paid)
        custom_label = ep_labels.get(ek)
        base_label = _B(custom_label) if custom_label else _B(str(ek)+'-qism')
        if locked:
            # 🔒 Pullik: faqat aynan shu qism tasdiqlangandan keyin ochiladi
            rows.append([ibtn(f"🔒 {base_label}  💰 {_B(str(price_int)+' som')}",
                              data=f"ep|{code}|{ek}", style="danger")])
        elif price_int > 0 and already_paid:
            # ✅ Faqat shu qism sotib olingan
            rows.append([ibtn(f"✅ {base_label}",
                              data=f"ep|{code}|{ek}", style="success")])
        else:
            # 🎬 Narx qo'yilmagan qism bepul
            rows.append([ibtn(f"🎬 {base_label}",
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
    kanal_url = RAM.settings.get("kino_kanal_url", "")
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
    return ikb([
        [
            ibtn(bt("qism_add"), data=f"quick_add_ep|{code}", style="success", emoji_id=get_eid("qism_add")),
            ibtn(bt("narx_bel"), data=f"quick_price|{code}",  style="primary", emoji_id=get_eid("narx_bel")),
        ],
        [
            ibtn(_B("Tugatish va bazaga saqlash"), data=f"finish_movie|{code}", style="success"),
        ],
    ])

def payment_sent_kb(card: str = "", price: int = 0):
    rows = [[ibtn(bt("chek_yub"), data="send_check", style="primary", emoji_id=get_eid("chek_yub"))]]
    copy_row = []
    if card:
        copy_row.append({
            "text": bt("karta_nusxa"),
            "copy_text": {"text": str(card)},
        })
    if price:
        copy_row.append({
            "text": bt("miqdor_nusxa"),
            "copy_text": {"text": str(price)},
        })
    if copy_row:
        rows.append(copy_row)
    return ikb(rows)

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
    rows.append([rbtn(bt("tiklash"), style="danger")])
    rows.append([rbtn(bt("orqaga"),  style="success")])
    return rkb(rows)

def emoji_single_action_kb(key: str):
    return ikb([
        [ibtn(bt("default_q"), data=f"emoji_reset|{key}", style="danger")],
        [ibtn(bt("orqaga"),    data="emoji_back",         style="success")],
    ])

def broadcast_color_kb():
    return ikb([
        [
            ibtn(_B('Kok'),    data="bc_color|primary", style="primary"),
            ibtn(_B('Qizil'),  data="bc_color|danger",  style="danger"),
            ibtn(_B('Yashil'), data="bc_color|success", style="success"),
        ],
        [ibtn(bt("bekor"), data="bc_cancel", style="danger", emoji_id=get_eid("bekor"))],
    ])

def broadcast_preview_kb(has_btn: bool):
    rows = [[ibtn(_B('Tugma qoshish'), data="bc_add_btn", style="primary")]]
    if has_btn:
        rows.append([ibtn(_B('Tugmani ochirish'), data="bc_remove_btn", style="danger")])
    rows.append([
        ibtn(_B('Yuborish'), data="bc_send",   style="success"),
        ibtn(bt("bekor"),    data="bc_cancel", style="danger", emoji_id=get_eid("bekor")),
    ])
    return ikb(rows)

def bc_yesno_kb():
    """Tugmali xabar yuborasizmi? Ha / Yo'q"""
    return ikb([
        [
            ibtn("✅ Ha",   data="bc_btn_yes", style="success"),
            ibtn("❌ Yo'q", data="bc_btn_no",  style="danger"),
        ],
        [ibtn(bt("bekor"), data="bc_cancel", style="danger", emoji_id=get_eid("bekor"))],
    ])

def bc_more_yesno_kb():
    """Yana bita tugma qo'shasizmi? Ha / Yo'q"""
    return ikb([
        [
            ibtn("➕ Ha, yana qo'shaman", data="bc_more_yes", style="primary"),
            ibtn("📤 Yo'q, yuboraman",   data="bc_more_no",  style="success"),
        ],
        [ibtn(bt("bekor"), data="bc_cancel", style="danger", emoji_id=get_eid("bekor"))],
    ])


# ══════════════════════════════════════════════════════════
# XABAR YUBORISH
# ══════════════════════════════════════════════════════════

async def sm(bot, chat_id, text, markup=None, pm="HTML", reply_to_message_id=None):
    kw = {"chat_id": chat_id, "text": text, "parse_mode": pm}
    if markup: kw["reply_markup"] = markup
    if reply_to_message_id: kw["reply_to_message_id"] = reply_to_message_id
    return await bot.send_message(**kw)

async def sp(bot, chat_id, photo, caption, markup=None, pm="HTML"):
    kw = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": pm}
    if markup: kw["reply_markup"] = markup
    return await bot.send_photo(**kw)

async def sv(bot, chat_id, video, caption, markup=None, pm="HTML", protect=False):
    kw = {"chat_id": chat_id, "video": video, "caption": caption, "parse_mode": pm}
    if markup: kw["reply_markup"] = markup
    if protect: kw["protect_content"] = True
    return await bot.send_video(**kw)


# ══════════════════════════════════════════════════════════
# KANAL YORDAMCHI
# ══════════════════════════════════════════════════════════

def normalize_channel_username(value: str) -> str:
    value = (value or "").strip()
    if not value: return ""
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
    if chat_id: return chat_id
    return normalize_channel_username(ch.get("username") or ch.get("url") or "")

async def resolve_required_channel(bot, raw_username: str) -> dict:
    username = normalize_channel_username(raw_username)
    if not username: raise ValueError("Kanal username noto'g'ri")
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
    if cached is not None: return cached
    channels = RAM.channels
    if not channels:
        _sub_cache_set(user_id, [])
        return []

    async def check_one(ch):
        try:
            chat_ref = _channel_ref(ch)
            if not chat_ref: return ch
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


# ══════════════════════════════════════════════════════════
# ADMIN STATE TOZALASH
# ══════════════════════════════════════════════════════════

def sub_admin_perm_kb(target_uid: str):
    """Sub-admin uchun perm toggle inline kb."""
    perms = (RAM.sub_admins.get(str(target_uid), {}) or {}).get("perms", {}) or {}
    rows, buf = [], []
    for k in ADMIN_PERM_KEYS:
        on = perms.get(k, True) is not False
        mark = "✅" if on else "❌"
        label = BTN_LABELS.get(k, k)
        buf.append(ibtn(f"{mark} {label}", data=f"adm_perm|{target_uid}|{k}",
                        style="success" if on else "danger"))
        if len(buf) == 2:
            rows.append(buf); buf = []
    if buf: rows.append(buf)
    rows.append([ibtn("🗑 Adminni o'chirish", data=f"adm_del|{target_uid}", style="danger")])
    rows.append([ibtn("✅ Tayyor", data=f"adm_done|{target_uid}", style="primary")])
    return ikb(rows)


def clear_admin_state(context):
    for key in [
        "admin_state", "new_movie_code", "ep_movie_code",
        "price_movie_code", "price_ep", "post_code",
        "reply_to", "awaiting_help", "awaiting_check",
        "editing_btn_key", "emoji_menu",
        "bc_msg", "bc_buttons", "bc_adding_btn",
        "del_movie_code", "poster_code",
        "edit_ep_code", "edit_ep_num", "new_admin_id",
        "channel_manage_menu", "ch_info", "bc_btn_name",
    ]:
        context.user_data.pop(key, None)


def _build_ep_price_list(code: str, eps: list, prices: dict) -> str:
    if not eps: return "⚠️ Bu kinoda hali qism yo'q."
    lines = []
    for i in range(len(eps)):
        ek = str(i + 1)
        price = price_to_int((prices or {}).get(ek))
        if price > 0: lines.append(f"  {ek}-qism — 💰 <b>{price} so'm</b>")
        else:         lines.append(f"  {ek}-qism — bepul")
    return f"📺 Qismlar ({len(eps)} ta):\n" + "\n".join(lines)


def _channels_list_text() -> str:
    channels = RAM.channels
    if not channels: return "📭 Hozircha majburiy kanal yo'q."
    lines = []
    for i, ch in enumerate(channels, 1):
        lines.append(f"  {i}. <b>{ch.get('title','?')}</b> — {ch.get('username','?')}")
    return f"📋 <b>Majburiy kanallar</b> ({len(channels)} ta):\n\n" + "\n".join(lines)


async def send_movie_menu(src, context, code: str):
    movie   = RAM.movies.get(code)
    user_id = src.effective_user.id if hasattr(src, "effective_user") else src.from_user.id
    if not movie:
        await sm(context.bot, user_id, "❌ Bunday kodli kino topilmadi.")
        return
    eps = movie.get("episodes", [])
    if not eps:
        await sm(context.bot, user_id, "⏳ Bu kinoga hali qism yuklanmagan.")
        return
    markup      = movie_episodes_kb(movie, code, user_id, page=0)
    total_pages = max(1, (len(eps) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_info   = f"  (1/{total_pages} sahifa)" if total_pages > 1 else ""
    caption     = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
                   f"📺 Qismlar soni: <b>{len(eps)} ta</b>{page_info}\n\n"
                   f"👇 Qaysi qismni ko'rmoqchisiz?")
    poster = movie.get("poster_file_id")
    try:
        if poster: await sp(context.bot, user_id, poster, caption, markup)
        else:      await sm(context.bot, user_id, caption, markup)
    except Exception as e:
        logger.error(f"send_movie_menu xato: {e}")
        try: await sm(context.bot, user_id, caption, markup)
        except Exception as e2: logger.error(f"fallback xato: {e2}")


# ══════════════════════════════════════════════════════════
# BROADCAST
# ══════════════════════════════════════════════════════════

def build_broadcast_markup(buttons: list):
    if not buttons: return None
    rows = []
    for b in buttons:
        rows.append([ibtn(
            b["text"], url=b["url"],
            style=b.get("style", "primary"),
            emoji_id=b.get("emoji_id"),
        )])
    return ikb(rows)


async def send_broadcast_preview(bot, uid, bc: dict):
    buttons    = bc.get("buttons", [])
    markup     = build_broadcast_markup(buttons)
    preview_kb = broadcast_preview_kb(bool(buttons))
    try:
        kw = {}
        if markup: kw["reply_markup"] = markup
        await bot.copy_message(
            chat_id=uid, from_chat_id=bc["from_chat_id"],
            message_id=bc["message_id"], **kw)
    except Exception as e:
        await sm(bot, uid, f"❌ Preview xato: {e}")
        return
    btn_info = ""
    if buttons:
        btn_info = "\n\n<b>Tugmalar:</b>\n" + "\n".join(
            f"• {b['text']} → {b['url']}" for b in buttons)
    await sm(bot, uid, f"<b>Preview yuqorida ↑</b>{btn_info}\n\nNima qilasiz?",
             parse_mode="HTML", markup=preview_kb)


async def do_broadcast(bot, bc: dict):
    users   = list(RAM.users.keys())
    buttons = bc.get("buttons", [])
    markup  = build_broadcast_markup(buttons)
    ok = fail = 0
    sem = asyncio.Semaphore(10)

    async def send_one(uid):
        nonlocal ok, fail
        async with sem:
            try:
                kw = {}
                if markup: kw["reply_markup"] = markup
                await bot.copy_message(
                    chat_id=int(uid), from_chat_id=bc["from_chat_id"],
                    message_id=bc["message_id"], **kw)
                ok += 1
            except Exception as e:
                fail += 1

    await asyncio.gather(*[send_one(uid) for uid in users])
    return ok, fail


# ══════════════════════════════════════════════════════════
# KINOLAR RO'YXATI — RASM GENERATSIYA
# ══════════════════════════════════════════════════════════

def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text or '').strip()

PHOTO_PAGE_SIZE  = 20
KINO_LIST_PAGE_SIZE = 10


def generate_movies_image(movie_slice: list, page: int = 1, total_pages: int = 1,
                          total_count: int = 0, start_offset: int = 0) -> BytesIO | None:
    if not PIL_AVAILABLE or not movie_slice:
        return None

    BG_COLOR    = (250, 250, 252)
    GRID_COLOR  = (208, 213, 228)
    HEADER_BG   = (20, 60, 160)
    WHITE       = (255, 255, 255)
    TEXT_DARK   = (28, 33, 52)
    CODE_COLOR  = (60, 90, 190)
    VIEWS_COLOR = (40, 140, 70)
    EP_COLOR    = (100, 100, 130)
    ACCENT_COLORS = [
        (25, 95, 215), (40, 160, 70), (200, 50, 60),
        (200, 120, 0), (110, 60, 190), (0, 140, 180),
    ]
    # 4K sifat — kenglik 2160px (4K vertikal). Yozuvlar yirik va tiniq.
    SCALE    = 2
    IMG_W    = 1080 * SCALE   # 2160px
    PAD_X    = 40   * SCALE
    TOP_PAD  = 24   * SCALE
    CARD_H   = 170  * SCALE
    GAP      = 20   * SCALE
    HEADER_H = 160  * SCALE
    FOOTER_H = 100  * SCALE
    BADGE_SZ = 120  * SCALE
    GRID_STP = 50   * SCALE

    img_h = HEADER_H + TOP_PAD + len(movie_slice) * (CARD_H + GAP) + FOOTER_H + 10
    img  = Image.new("RGB", (IMG_W, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

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
                try: return ImageFont.truetype(p, size)
                except: continue
        # Fontlar topilmasa: yangi PIL'da load_default(size=...) ishlaydi
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    fnt_header = try_font(72 * SCALE)
    fnt_num    = try_font(54 * SCALE)
    fnt_title  = try_font(46 * SCALE)
    fnt_sub    = try_font(34 * SCALE)
    fnt_footer = try_font(38 * SCALE)

    for x in range(0, IMG_W, GRID_STP):
        draw.line([(x, 0), (x, img_h)], fill=GRID_COLOR, width=1)
    for y in range(0, img_h, GRID_STP):
        draw.line([(0, y), (IMG_W, y)], fill=GRID_COLOR, width=1)

    draw.rectangle([(0, 0), (IMG_W, HEADER_H)], fill=HEADER_BG)
    h_text = "BARCHA KINOLAR"
    try:
        hbb = draw.textbbox((0, 0), h_text, font=fnt_header)
        hx  = (IMG_W - (hbb[2] - hbb[0])) // 2
        hy  = (HEADER_H - (hbb[3] - hbb[1])) // 2
    except: hx, hy = 40, 28
    draw.text((hx, hy), h_text, fill=WHITE, font=fnt_header)

    for idx, (code, movie) in enumerate(movie_slice):
        y0 = HEADER_H + TOP_PAD + idx * (CARD_H + GAP)
        y1 = y0 + CARD_H
        x0 = PAD_X
        x1 = IMG_W - PAD_X
        col = ACCENT_COLORS[idx % len(ACCENT_COLORS)]
        draw.rounded_rectangle([x0, y0, x1, y1], radius=20*SCALE, fill=WHITE, outline=col, width=5*SCALE)
        draw.rounded_rectangle([x0, y0, x0 + 14*SCALE, y1], radius=7*SCALE, fill=col)
        bx0 = x0 + 32*SCALE
        bx1 = bx0 + BADGE_SZ
        by0 = y0 + (CARD_H - BADGE_SZ) // 2
        by1 = by0 + BADGE_SZ
        draw.ellipse([bx0, by0, bx1, by1], fill=col)
        num_txt = str(start_offset + idx + 1)
        try:
            nb  = draw.textbbox((0, 0), num_txt, font=fnt_num)
            nxc = bx0 + (BADGE_SZ - (nb[2] - nb[0])) // 2
            nyc = by0 + (BADGE_SZ - (nb[3] - nb[1])) // 2 - 4*SCALE
        except: nxc, nyc = bx0 + 30, by0 + 25
        draw.text((nxc, nyc), num_txt, fill=WHITE, font=fnt_num)
        tx = bx1 + 32*SCALE
        raw_title = _strip_html(movie.get("title", code))
        if len(raw_title) > 40: raw_title = raw_title[:38] + "…"
        title_y = y0 + 28*SCALE
        draw.text((tx, title_y), raw_title, fill=TEXT_DARK, font=fnt_title)
        ep_count    = len(movie.get("episodes", []))
        views_total = sum(movie.get("views", {}).values())
        sub_y = y0 + 100*SCALE
        code_part  = f"Kod: {code}"
        ep_part    = f"  |  {ep_count} ta qism mavjud"
        views_part = f"  |  {views_total} korilgan"
        draw.text((tx, sub_y), code_part, fill=CODE_COLOR, font=fnt_sub)
        try:
            cb = draw.textbbox((0, 0), code_part, font=fnt_sub)
            ex = tx + (cb[2] - cb[0])
        except: ex = tx + 200
        draw.text((ex, sub_y), ep_part, fill=EP_COLOR, font=fnt_sub)
        try:
            eb = draw.textbbox((0, 0), ep_part, font=fnt_sub)
            vx = ex + (eb[2] - eb[0])
        except: vx = ex + 160
        draw.text((vx, sub_y), views_part, fill=VIEWS_COLOR, font=fnt_sub)

    fy = img_h - FOOTER_H
    draw.rectangle([(0, fy), (IMG_W, img_h)], fill=HEADER_BG)
    if total_pages > 1:
        start_n = (page - 1) * KINO_LIST_PAGE_SIZE + 1
        end_n   = start_n + len(movie_slice) - 1
        f_text  = f"{start_n}-{end_n} ko'rsatildi  |  Jami: {total_count} ta  |  Kino kodini yuboring!"
    else:
        f_text = f"Jami: {total_count} ta kino  |  Kino kodini yuboring!"
    try:
        fbb = draw.textbbox((0, 0), f_text, font=fnt_footer)
        fx  = (IMG_W - (fbb[2] - fbb[0])) // 2
        fy2 = fy + (FOOTER_H - (fbb[3] - fbb[1])) // 2
    except: fx, fy2 = 40, fy + 16
    draw.text((fx, fy2), f_text, fill=WHITE, font=fnt_footer)

    buf = BytesIO()
    buf.name = "barcha_kinolar_4k.png"
    img.save(buf, format="PNG", optimize=False, compress_level=1)
    buf.seek(0)
    return buf


async def _send_kino_list_page(bot, chat_id: int, page: int = 0, query=None):
    movies      = RAM.movies
    if not movies:
        if query is not None:
            try:
                await query.answer("🎬 Hozircha hech qanday kino qo'shilmagan.", show_alert=True)
                return
            except Exception:
                pass
        await bot.send_message(chat_id,
            "🎬 <b>Hozircha hech qanday kino qo'shilmagan.</b>", parse_mode="HTML")
        return

    # Yangi qo'shilgan kinolar tepada — added_at bo'yicha tartiblash
    all_items = sorted(
        movies.items(),
        key=lambda x: x[1].get("added_at", 0) if isinstance(x[1], dict) else 0,
        reverse=True,
    )
    total_count = len(all_items)
    total_pages = max(1, (total_count + KINO_LIST_PAGE_SIZE - 1) // KINO_LIST_PAGE_SIZE)
    page        = max(0, min(page, total_pages - 1))
    start       = page * KINO_LIST_PAGE_SIZE
    end         = min(start + KINO_LIST_PAGE_SIZE, total_count)
    slice_items = all_items[start:end]

    img_buf = None
    if PIL_AVAILABLE:
        try:
            img_buf = await asyncio.to_thread(
                generate_movies_image, slice_items,
                page + 1, total_pages, total_count, start)
        except Exception as e:
            logger.error(f"kino_list surat xato: {e}")

    nav_row = []
    if page > 0:
        nav_row.append(ibtn(_B('Oldingi kinolar'), data=f"kino_list|{page-1}", style="primary"))
    if page < total_pages - 1:
        nav_row.append(ibtn(_B('Qolgan kinolar'), data=f"kino_list|{page+1}", style="primary"))

    kanal_url = RAM.settings.get("kino_kanal_url", "")
    rows = []
    if nav_row: rows.append(nav_row)
    if kanal_url:
        rows.append([ibtn(bt("kino_kanal"), url=kanal_url, style="primary",
                           emoji_id=get_eid("kino_kanal"))])
    kb = ikb(rows) if rows else None

    # Faqat surat + tugma (ortiqcha matn olib tashlandi)
    caption = "Kino <b>kodini</b> yuboring — video <b>darhol</b> keladi! ⚡"

    # Faqat surat + tugma (ortiqcha matn olib tashlandi)
    caption = "Kino <b>kodini</b> yuboring — video <b>darhol</b> keladi! ⚡"

    # Agar callback orqali kelgan bo'lsa — eski xabarni tahrirlaymiz (yangi surat tashlamaymiz)
    if query is not None and img_buf is not None:
        try:
            from telegram import InputMediaPhoto
            media = InputMediaPhoto(media=img_buf, caption=caption, parse_mode="HTML")
            await query.edit_message_media(media=media, reply_markup=kb)
            return
        except Exception as e:
            logger.error(f"kino_list edit_media xato: {e}")
            # fallback: yangi xabar
            try: img_buf.seek(0)
            except Exception: pass

    if img_buf:
        # Surat sifatida yuboriladi (fayl emas) — chatda darhol ko'rinadi
        await bot.send_photo(chat_id=chat_id, photo=img_buf,
                             caption=caption, parse_mode="HTML", reply_markup=kb)
    else:
        await bot.send_message(chat_id=chat_id,
            text="⚠️ PIL kutubxonasi yo'q. <code>pip install Pillow</code>",
            parse_mode="HTML", reply_markup=kb)


# ══════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_duplicate_update(update): return
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
    await sm(context.bot, user.id, hello, main_menu_kb(is_admin=(is_any_admin(user.id))))


# ══════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ══════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_duplicate_update(update): return
    q    = update.callback_query
    data = q.data or ""
    uid  = q.from_user.id
    await q.answer()

    if data.startswith("kino_list|"):
        try: pg = int(data.split("|")[1])
        except: pg = 0
        await _send_kino_list_page(context.bot, uid, page=pg, query=q)
        return

    if data.startswith("adm_perm|"):
        if not is_super_admin(uid): return
        try:
            _, target, key = data.split("|", 2)
            if key not in ADMIN_PERM_KEYS: return
            if target not in RAM.sub_admins: return
            perms = RAM.sub_admins[target].setdefault("perms", {})
            cur = perms.get(key, True) is not False
            perms[key] = (not cur)
            await schedule_save()
            try:
                await q.edit_message_reply_markup(reply_markup=sub_admin_perm_kb(target))
            except Exception as e:
                logger.warning(f"adm_perm edit kb: {e}")
        except Exception as e:
            logger.error(f"adm_perm xato: {e}")
        return

    if data.startswith("adm_del|"):
        if not is_super_admin(uid): return
        try:
            _, target = data.split("|", 1)
            if target in RAM.sub_admins:
                RAM.sub_admins.pop(target, None)
                await schedule_save()
                try: await q.edit_message_text(f"✅ Admin <code>{target}</code> o'chirildi.", parse_mode="HTML")
                except: pass
                await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb(uid))
        except Exception as e:
            logger.error(f"adm_del xato: {e}")
        return

    if data.startswith("adm_done|"):
        if not is_super_admin(uid): return
        try:
            _, target = data.split("|", 1)
            try: await q.edit_message_text(f"✅ Admin <code>{target}</code> sozlamalari saqlandi.", parse_mode="HTML")
            except: pass
            await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb(uid))
        except Exception as e:
            logger.error(f"adm_done xato: {e}")
        return

    if data.startswith("ch_del|"):
        if not is_any_admin(uid): return
        try:
            idx      = int(data.split("|")[1])
            channels = RAM.channels
            if 0 <= idx < len(channels):
                removed = channels.pop(idx)
                await schedule_save()
                try:
                    await q.edit_message_text(
                        f"✅ <b>{removed.get('title','?')}</b> o'chirildi!\n\n{_channels_list_text()}",
                        parse_mode="HTML")
                except: pass
                await sm(context.bot, uid, "Majburiy kanal boshqaruvi:", channel_manage_kb())
            else:
                await sm(context.bot, uid, "❌ Kanal topilmadi.", channel_manage_kb())
        except Exception as e:
            logger.error(f"ch_del xato: {e}")
        return

    if data == "ch_del_cancel":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
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
        if not is_any_admin(uid): return
        u = len(RAM.users)
        m = len(RAM.movies)
        v = RAM.stats.get("total_views", 0)
        if DB_STATUS["ram_only"]:
            storage_line = (f"\n\n🔴 <b>Storage: RAM ONLY</b>\n"
                           f"JSONBlob ishlamayapti! Xato: <b>{DB_STATUS['fail_count']}</b>x")
        elif DB_STATUS["last_save_ok"]:
            storage_line = f"\n\n🟢 Storage OK | {DB_STATUS['last_save_ok']}"
        else:
            storage_line = "\n\n🟡 Storage tekshirilmagan"
        try:
            await q.edit_message_text(
                f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
                f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>{storage_line}",
                parse_mode="HTML", reply_markup=stats_kb())
        except: pass
        return

    if data == "go_home":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        await sm(context.bot, uid, "Bosh menyu",
                 main_menu_kb(is_admin=(is_any_admin(uid))))
        return

    if data == "waiting_confirm":
        await q.answer("Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)
        return

    # copy_card / copy_amount endi CopyTextButton orqali ishlaydi — handler kerak emas

    if data == "send_check":
        pending = context.user_data.get("pending_check")
        if not pending:
            await q.answer("To'lov ma'lumoti topilmadi", show_alert=True)
            return
        context.user_data["awaiting_check"] = pending
        context.user_data.pop("pending_check", None)
        await q.answer()
        await sm(context.bot, uid, "📤 <b>Chek rasmini yuboring</b> 👇")
        return

    if data == "emoji_back":
        if not is_any_admin(uid): return
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        try: await q.edit_message_text("Tugmani pastdan tanlang 👇")
        except: pass
        await sm(context.bot, uid,
            "<b>Tugma sozlamalari</b>\nO'zgartirmoqchi bo'lgan tugmani pastdan tanlang 👇",
            emoji_menu_kb())
        return

    if data == "emoji_reset_all":
        if not is_any_admin(uid): return
        RAM.btn_texts = {}
        RAM.emoji_ids = {}
        EMOJI_IDS.clear()
        await save_now()
        try: await q.edit_message_text("✅ Barcha tugmalar tiklandi!")
        except: pass
        context.user_data["emoji_menu"] = True
        context.user_data.pop("editing_btn_key", None)
        await sm(context.bot, uid, "✅ Tiklandi! Tugmani tanlang:", emoji_menu_kb())
        return

    if data.startswith("emoji_reset|"):
        if not is_any_admin(uid): return
        key = data.split("|", 1)[1]
        RAM.btn_texts.pop(key, None)
        RAM.emoji_ids.pop(key, None)
        EMOJI_IDS.pop(key, None)
        await save_now()
        default = DEFAULT_BTN.get(key, "")
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        try:
            await q.edit_message_text(
                f"✅ <b>{BTN_LABELS.get(key, key)}</b> tiklandi!\nDefault: <code>{default}</code>",
                parse_mode="HTML")
        except: pass
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    if data.startswith("quick_add_ep|"):
        if not is_any_admin(uid): return
        code = data.split("|", 1)[1]
        context.user_data["admin_state"]   = "add_ep_video"
        context.user_data["ep_movie_code"] = code
        movie  = RAM.movies.get(code, {})
        ep_num = len(movie.get("episodes", [])) + 1
        await sm(context.bot, uid,
            f"🎬 <b>{movie.get('title', code)}</b>\n"
            f"📹 <b>{ep_num}-qism</b> uchun video yuboring:")
        return

    if data.startswith("finish_movie|"):
        if not is_any_admin(uid): return
        code = data.split("|", 1)[1]
        movie = RAM.movies.get(code, {})
        ep_count = len(movie.get("episodes", []))

        # ❗ Agar kino bo'sh (0 qism) bo'lsa — saqlamaymiz, admin'ga ogohlantirish
        if ep_count == 0:
            # state'ni saqlab qolamiz — admin video yuborsa, qism sifatida qabul qilinadi
            context.user_data["admin_state"]   = "add_ep_video"
            context.user_data["ep_movie_code"] = code
            await sm(context.bot, uid,
                f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali <b>birorta ham qism yo'q</b>!\n\n"
                f"Avval kamida 1 ta video yuboring, keyin <b>Tugatish</b> tugmasini bosing.\n\n"
                f"📹 <b>1-qism</b> uchun video yuboring:",
                movie_added_kb(code))
            return

        context.user_data.pop("admin_state", None)
        context.user_data.pop("ep_movie_code", None)

        await sm(context.bot, uid, "💾 Bazaga (JSONBlob) saqlanmoqda, kuting...")
        ok = await save_now()
        if not ok:
            await asyncio.sleep(2)
            ok = await save_now()

        total_movies = len(RAM.movies)
        total_eps = sum(len(m.get("episodes", [])) for m in RAM.movies.values())

        if ok:
            await sm(context.bot, uid,
                f"✅ <b>{movie.get('title', code)}</b> bazaga saqlandi!\n"
                f"Kod: <code>{code}</code>\n"
                f"Bu kinoda qismlar: <b>{ep_count} ta</b>\n\n"
                f"📊 Bazada jami: <b>{total_movies} kino</b>, <b>{total_eps} qism</b>",
                admin_menu_kb(uid))
        else:
            await sm(context.bot, uid,
                f"⚠️ Lokal saqlandi, lekin JSONBlob xato berdi.\n"
                f"Bot ishlayveradi, keyinroq avtomatik qayta urinadi.",
                admin_menu_kb(uid))
        return

    if data.startswith("quick_price|"):
        if not is_any_admin(uid): return
        code  = data.split("|", 1)[1]
        movie = RAM.movies.get(code)
        if not movie:
            await sm(context.bot, uid, "❌ Kino topilmadi!")
            return
        eps = movie.get("episodes", [])
        if not eps:
            await sm(context.bot, uid,
                f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.")
            return
        prices  = movie.get("prices", {})
        ep_list = _build_ep_price_list(code, eps, prices)
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"]      = "set_price_ep"
        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b> — narx belgilash\n\n{ep_list}\n\n"
            f"Qism <b>raqamini</b> kiriting (1 dan {len(eps)} gacha):")
        return


# ══════════════════════════════════════════════════════════
# CALLBACK: BROADCAST
# ══════════════════════════════════════════════════════════

async def cb_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.from_user.id
    data = q.data or ""
    if not is_any_admin(uid): return

    bc = context.user_data.get("bc_msg", {})

    if data == "bc_cancel":
        for k in ["bc_msg", "bc_buttons", "bc_adding_btn", "bc_btn_name", "bc_btn_emoji"]:
            context.user_data.pop(k, None)
        try: await q.edit_message_text("❌ Broadcast bekor qilindi.")
        except: pass
        await sm(context.bot, uid, "Admin panel", admin_menu_kb(uid))
        return

    # Tugmali xabar yuborasizmi? Ha/Yo'q
    if data == "bc_btn_yes":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        await sm(context.bot, uid, "Tugma rangini tanlang:", broadcast_color_kb())
        return

    if data == "bc_btn_no":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        # Tugmasiz darhol barchaga yuborish
        total = len(RAM.users)
        prog_msg = await sm(context.bot, uid, f"⏳ Yuborilmoqda... 0/{total}")
        ok, fail = await do_broadcast(context.bot, bc)
        for k in ["bc_msg", "bc_buttons"]:
            context.user_data.pop(k, None)
        try:
            await context.bot.edit_message_text(
                f"✅ Broadcast tugadi!\n\nYuborildi: <b>{ok}</b>\nXato: <b>{fail}</b>",
                chat_id=uid, message_id=prog_msg.message_id, parse_mode="HTML")
        except:
            await sm(context.bot, uid, f"✅ Broadcast tugadi! Ok:{ok}, Xato:{fail}")
        await sm(context.bot, uid, "Admin panel", admin_menu_kb(uid))
        return

    # Yana bita tugma qo'shasizmi?
    if data == "bc_more_yes":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        await sm(context.bot, uid, "Yangi tugma rangini tanlang:", broadcast_color_kb())
        return

    if data == "bc_more_no":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        # ✅ TUZATILDI: "Yo'q, yuboraman" — darhol BARCHA foydalanuvchilarga yuboradi
        total = len(RAM.users)
        prog_msg = await sm(context.bot, uid, f"⏳ Barchaga yuborilmoqda... 0/{total}")
        ok, fail = await do_broadcast(context.bot, bc)
        for k in ["bc_msg", "bc_buttons", "bc_adding_btn", "bc_btn_name", "bc_btn_url", "bc_btn_emoji"]:
            context.user_data.pop(k, None)
        try:
            await context.bot.edit_message_text(
                f"✅ Broadcast tugadi!\n\nYuborildi: <b>{ok}</b>\nXato: <b>{fail}</b>\nJami: <b>{total}</b>",
                chat_id=uid, message_id=prog_msg.message_id, parse_mode="HTML")
        except:
            await sm(context.bot, uid, f"✅ Broadcast tugadi! Ok:{ok}, Xato:{fail}")
        await sm(context.bot, uid, "Admin panel", admin_menu_kb(uid))
        return

    if data.startswith("bc_color|"):
        color = data.split("|", 1)[1]
        bc["btn_color"] = color
        context.user_data["bc_msg"]        = bc
        context.user_data["bc_adding_btn"] = "text"
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        color_names = {"primary": "🔵 Ko'k", "danger": "🔴 Qizil", "success": "🟢 Yashil"}
        await sm(context.bot, uid,
            f"Rang: <b>{color_names.get(color, color)}</b>\n\nTugma nomini kiriting:")
        return

    if data == "bc_add_btn":
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        await sm(context.bot, uid, "Tugma rangini tanlang:", broadcast_color_kb())
        return

    if data == "bc_remove_btn":
        bc["buttons"] = []
        context.user_data["bc_msg"] = bc
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        await sm(context.bot, uid, "✅ Tugmalar o'chirildi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return

    if data == "bc_send":
        total = len(RAM.users)
        try: await q.edit_message_reply_markup(reply_markup=None)
        except: pass
        prog_msg = await sm(context.bot, uid, f"⏳ Yuborilmoqda... 0/{total}")
        ok, fail = await do_broadcast(context.bot, bc)
        for k in ["bc_msg", "bc_buttons"]:
            context.user_data.pop(k, None)
        try:
            await context.bot.edit_message_text(
                f"✅ Broadcast tugadi!\n\nYuborildi: <b>{ok}</b>\nXato: <b>{fail}</b>",
                chat_id=uid, message_id=prog_msg.message_id, parse_mode="HTML")
        except:
            await sm(context.bot, uid, f"✅ Broadcast tugadi! Ok:{ok}, Xato:{fail}")
        await sm(context.bot, uid, "Admin panel", admin_menu_kb(uid))
        return


# ══════════════════════════════════════════════════════════
# CALLBACK: SAHIFALASH
# ══════════════════════════════════════════════════════════

async def cb_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|")
    if len(parts) != 3: return
    _, code, page_str = parts
    try: page = int(page_str)
    except: return
    movie = RAM.movies.get(code)
    if not movie: return
    user_id     = q.from_user.id
    eps         = movie.get("episodes", [])
    markup      = movie_episodes_kb(movie, code, user_id, page=page)
    total_pages = max(1, (len(eps) + PAGE_SIZE - 1) // PAGE_SIZE)
    caption     = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
                   f"📺 Qismlar soni: <b>{len(eps)} ta</b>  "
                   f"({page + 1}/{total_pages} sahifa)\n\n"
                   f"👇 Qaysi qismni ko'rmoqchisiz?")
    try: await q.edit_message_caption(caption=caption, parse_mode="HTML", reply_markup=markup)
    except:
        try: await q.edit_message_text(caption, parse_mode="HTML", reply_markup=markup)
        except Exception as e: logger.error(f"cb_page xato: {e}")


# ══════════════════════════════════════════════════════════
# CALLBACK: SUBSCRIPTION
# ══════════════════════════════════════════════════════════

async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.from_user.id
    _sub_cache_invalidate(uid)
    ns = await check_subscription(uid, context.bot)
    if ns:
        await q.answer("Hali obuna bo'lmagansiz! ❌", show_alert=True)
        return
    try: await q.edit_message_text("✅ Zo'r! Barcha kanallarga obuna bo'ldingiz!")
    except: pass
    pending = context.user_data.pop("pending_code", None)
    if pending:
        await send_movie_menu(q, context, pending)
    else:
        await sm(context.bot, uid,
            f"🎉 Xush kelibsiz, <b>{q.from_user.full_name}</b>!\n\nKino kodini yuboring 👇",
            main_menu_kb(is_admin=(is_any_admin(uid))))


# ══════════════════════════════════════════════════════════
# CALLBACK: QISM KO'RISH
# ══════════════════════════════════════════════════════════

async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|")
    if len(parts) != 3: return
    _, code, ep = parts
    movie = RAM.movies.get(code)
    if not movie:
        await q.answer("Kino topilmadi", show_alert=True)
        return

    code = str(code).upper()
    user_id = str(q.from_user.id)
    price = price_to_int(movie.get("prices", {}).get(ep))
    RAM.ensure_user(user_id)

    # ❗ Har bir qism alohida tekshiriladi — boshqa qismni sotib olish
    # bu qismni ochmaydi. Faqat shu kino+qism uchun approved to'lov bo'lsa ochiq.
    if price > 0 and not is_episode_paid(user_id, code, ep):
        card = RAM.card_number or "Admin karta raqamini o'rnatmagan"
        txt  = (f"🔒 <b>Bu qism pullik</b>\n\n"
                f"🎬 Kino: <b>{movie.get('title')}</b>\n"
                f"📺 Qism: <b>{ep}</b>\n💰 Narxi: <b>{price} so'm</b>\n\n"
                f"💳 Karta raqami:\n<code>{card}</code>\n\n"
                f"To'lov qiling va chek rasmini yuboring 👇\n"
                f"<i>Admin tasdiqlamaguncha bu qism yopiq turadi.</i>")
        context.user_data["pending_check"] = {"code": code, "ep": ep, "price": price}
        await sm(context.bot, q.from_user.id, txt, payment_sent_kb(card, price))
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
            RAM.ensure_user(user_id)["watched"][f"{code}_{ep}"] = True
            RAM.stats["total_views"] = RAM.stats.get("total_views", 0) + 1
            await schedule_save()
        except Exception as e:
            logger.error(f"update_stats xato: {e}")
    asyncio.create_task(update_stats())


# ══════════════════════════════════════════════════════════
# CALLBACK: TO'LOV
# ══════════════════════════════════════════════════════════

async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|", 1)
    if len(parts) != 2: return
    action, pid = parts
    pay = RAM.pending_payments.get(pid)
    if not pay:
        try: await q.edit_message_caption("To'lov topilmadi.")
        except: pass
        return

    # ❗ Takror tasdiqlash/rad etishni bloklaymiz
    if pay.get("status") in ("approved", "rejected"):
        try:
            await q.answer(f"Bu to'lov allaqachon {pay.get('status')}!", show_alert=True)
        except: pass
        return

    if action == "pay_no":
        pay["status"] = "rejected"
        await save_now()
        try:
            await q.edit_message_caption(
                (q.message.caption or "") + "\n\n<b>❌ Bekor qilindi</b>", parse_mode="HTML")
        except: pass
        await sm(context.bot, pay["user_id"],
                 f"❌ <b>To'lovingiz rad etildi.</b>\n"
                 f"Kino: <code>{pay['code']}</code>, Qism: <b>{pay['ep']}</b>\n"
                 f"Boshqa qismlar uchun ham alohida to'lov qilishingiz kerak.")
        return

    # ✅ TASDIQLASH — faqat shu bitta qism ochiladi
    pay["status"] = "approved"
    pay["code"] = str(pay.get("code", "")).upper()
    pay["ep"] = str(pay.get("ep"))
    pay["approved_at"] = datetime.now().isoformat()
    uid = str(pay["user_id"])
    user_dict = RAM.ensure_user(uid)
    paid_key = episode_paid_key(pay["code"], pay["ep"])
    user_dict["paid_episodes"][paid_key] = {
        "status": "approved",
        "price": pay.get("price"),
        "payment_id": pid,
        "approved_at": pay["approved_at"],
    }
    await save_now()  # darhol saqlash — yo'qolib qolmasin
    try:
        await q.edit_message_caption(
            (q.message.caption or "") + f"\n\n<b>✅ Tasdiqlandi</b> — {pay['ep']}-qism ochildi",
            parse_mode="HTML")
    except: pass

    movie = RAM.movies.get(pay["code"])
    if movie:
        idx = int(pay["ep"]) - 1
        eps = movie.get("episodes", [])
        if 0 <= idx < len(eps):
            await asyncio.gather(
                sm(context.bot, pay["user_id"],
                   "✅ <b>Admin chekingizni tasdiqladi!</b>\n\n"
                   f"🎬 Mana <b>{pay['ep']}-qism</b> videosini tomosha qiling 👇"),
                sv(context.bot, pay["user_id"], eps[idx],
                   f"<b>{movie.get('title')}</b>\nQism: {pay['ep']}", protect=True),
                return_exceptions=True,
            )
            async def update_pay_stats():
                movie.setdefault("views", {})
                movie["views"][pay["ep"]] = movie["views"].get(pay["ep"], 0) + 1
                RAM.stats["total_views"] = RAM.stats.get("total_views", 0) + 1
                await schedule_save()
            asyncio.create_task(update_pay_stats())
    else:
        await sm(context.bot, pay["user_id"], "✅ <b>Admin chekingizni tasdiqladi!</b>")


# ══════════════════════════════════════════════════════════
# CALLBACK: ADMIN JAVOB
# ══════════════════════════════════════════════════════════

async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("|", 1)
    if len(parts) != 2: return
    _, uid_str = parts
    try:
        context.user_data["reply_to"] = int(uid_str)
        await q.message.reply_text(f"<code>{uid_str}</code> ga xabar yozing.", parse_mode="HTML")
    except Exception as e:
        logger.error(f"cb_reply xato: {e}")


# ══════════════════════════════════════════════════════════
# ADMIN RESERVED TEXTS
# ══════════════════════════════════════════════════════════

def _get_admin_reserved_texts() -> set:
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


# ══════════════════════════════════════════════════════════
# TEXT HANDLER
# ══════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_duplicate_update(update): return
    user = update.effective_user
    uid  = user.id
    msg  = update.message
    text = (msg.text or "").strip()

    # ── 1. editing_btn_key ─────────────────────────────
    if is_any_admin(uid) and context.user_data.get("editing_btn_key"):
        key = context.user_data.pop("editing_btn_key")
        if not text:
            context.user_data["editing_btn_key"] = key
            await sm(context.bot, uid, "Bo'sh bo'lmasin. Qayta yuboring:")
            return
        custom_emoji_id  = extract_custom_emoji_id(msg)
        existing         = RAM.btn_texts.get(key) or DEFAULT_BTN.get(key, "")
        existing_label   = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
        existing_emoji_p = extract_emoji_prefix(existing)
        if custom_emoji_id:
            new_text = existing_label
            EMOJI_IDS[key] = custom_emoji_id
            RAM.emoji_ids[key] = custom_emoji_id
            eid_info = f"\nCustom emoji ID: <code>{custom_emoji_id}</code>"
        elif is_only_emoji(text):
            new_emoji_p = (existing_emoji_p + text) if existing_emoji_p else text
            new_text    = f"{new_emoji_p} {existing_label}"
            EMOJI_IDS.pop(key, None)
            RAM.emoji_ids.pop(key, None)
            eid_info = ""
        else:
            new_text = text
            EMOJI_IDS.pop(key, None)
            RAM.emoji_ids.pop(key, None)
            eid_info = ""
        RAM.btn_texts[key] = new_text
        await save_now()
        eid = get_eid(key)
        if eid: eid_info = f"\nCustom emoji ID: <code>{eid}</code>"
        await sm(context.bot, uid,
            f"✅ <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n"
            f"Ko'rinish: <code>{new_text}</code>{eid_info}")
        context.user_data["emoji_menu"] = True
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    # ── 2. Broadcast tugma qo'shish ────────────────────
    if is_any_admin(uid) and context.user_data.get("bc_adding_btn"):
        stage = context.user_data["bc_adding_btn"]
        bc    = context.user_data.get("bc_msg", {})
        if stage == "text":
            context.user_data["bc_btn_name"]   = text
            context.user_data["bc_adding_btn"] = "url"
            await sm(context.bot, uid,
                f"Tugma nomi: <b>{text}</b>\n\nEndi tugma linkini kiriting (https:// bilan):")
        elif stage == "url":
            context.user_data["bc_btn_url"]    = text
            context.user_data["bc_adding_btn"] = "emoji"
            await sm(context.bot, uid,
                "Tugmaga premium emoji qo'shasizmi?\n\n"
                "• Yo'q bo'lsa — <b>0</b> deb yuboring\n"
                "• Bor bo'lsa — premium emoji yuboring (telegram premium emoji)")
        elif stage == "emoji":
            btn_text_val = context.user_data.pop("bc_btn_name", "Tugma")
            btn_url_val  = context.user_data.pop("bc_btn_url", text)
            color        = bc.pop("btn_color", "primary")
            emoji_id     = None
            if text.strip() != "0":
                emoji_id = extract_custom_emoji_id(update.message)
            context.user_data.pop("bc_adding_btn", None)
            new_btn = {"text": btn_text_val, "url": btn_url_val, "style": color}
            if emoji_id:
                new_btn["emoji_id"] = emoji_id
            bc.setdefault("buttons", []).append(new_btn)
            context.user_data["bc_msg"] = bc
            emoji_info = " (premium emoji bilan)" if emoji_id else ""
            await sm(context.bot, uid,
                f"✅ Tugma qo'shildi{emoji_info}!\n\n<b>Yana bita tugma qo'shasizmi?</b>",
                markup=bc_more_yesno_kb())
        return

    # ── 3. Emoji menyu ──────────────────────────────────
    if is_any_admin(uid) and context.user_data.get("emoji_menu"):
        if text == bt("orqaga") or strip_emoji_prefix(text) == strip_emoji_prefix(bt("orqaga")):
            context.user_data.pop("emoji_menu", None)
            context.user_data.pop("editing_btn_key", None)
            await sm(context.bot, uid, "Admin panel", admin_menu_kb(uid))
            return
        if text == bt("tiklash") or strip_emoji_prefix(text) == strip_emoji_prefix(bt("tiklash")):
            RAM.btn_texts = {}
            RAM.emoji_ids = {}
            EMOJI_IDS.clear()
            await save_now()
            await sm(context.bot, uid, "✅ Barcha tugmalar tiklandi!", emoji_menu_kb())
            return
        key = find_key_by_text(text)
        if key:
            cur        = RAM.btn_texts.get(key) or DEFAULT_BTN.get(key, "")
            eid        = get_eid(key)
            cur_emoji  = extract_emoji_prefix(cur)
            eid_info   = f"\nCustom emoji ID: <code>{eid}</code>" if eid else ""
            emoji_info = f"\nHozirgi emoji: <code>{cur_emoji}</code>" if cur_emoji else ""
            context.user_data["editing_btn_key"] = key
            await sm(context.bot, uid,
                f"<b>{BTN_LABELS.get(key, key)}</b>\n\n"
                f"Hozirgi matn: <code>{cur}</code>{eid_info}{emoji_info}\n\n"
                f"Yuboring:\n• Faqat emoji → qo'shiladi\n• Emoji+matn → yangilanadi\n"
                f"• Custom emoji → icon\n• Faqat matn → emoji o'chadi",
                emoji_single_action_kb(key))
        return

    # ── 4. Kanal boshqarish ─────────────────────────────
    if is_any_admin(uid) and context.user_data.get("channel_manage_menu"):
        ch_states = ("add_channel_username", "add_channel_title", "add_channel_url", "add_channel")
        if context.user_data.get("admin_state") in ch_states:
            handled = await admin_state_handler(update, context, text)
            if handled: return
        if text in (bt("admin_panel"), bt("orqaga")) or strip_emoji_prefix(text) in (
            strip_emoji_prefix(bt("admin_panel")), strip_emoji_prefix(bt("orqaga"))
        ):
            context.user_data.pop("channel_manage_menu", None)
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "Admin panel", admin_menu_kb(uid))
            return
        if text == bt("kanal_qosh") or strip_emoji_prefix(text) == strip_emoji_prefix(bt("kanal_qosh")):
            context.user_data["admin_state"] = "add_channel_username"
            await sm(context.bot, uid,
                "➕ <b>Kanal qo'shish</b>\n\nKanal <b>username</b>ini kiriting:\n"
                "<i>Misol: @mykinochannel yoki https://t.me/mykinochannel</i>")
            return
        if text == bt("kanal_uch") or strip_emoji_prefix(text) == strip_emoji_prefix(bt("kanal_uch")):
            channels = RAM.channels
            if not channels:
                await sm(context.bot, uid, "❌ Hozircha kanal yo'q.", channel_manage_kb())
                return
            await sm(context.bot, uid,
                f"{_channels_list_text()}\n\nO'chirmoqchi bo'lgan kanalni tanlang 👇",
                channel_delete_inline_kb(channels))
            return
        if text == bt("kanal_royxat") or strip_emoji_prefix(text) == strip_emoji_prefix(bt("kanal_royxat")):
            await sm(context.bot, uid, _channels_list_text(), channel_manage_kb())
            return
        return

    # ── 5. Admin reply_to ───────────────────────────────
    if is_any_admin(uid) and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        return

    # ── 6. Admin holati + navigatsiya tekshirish ────────
    if is_any_admin(uid) and context.user_data.get("admin_state"):
        nav_key = _get_admin_nav_key(text)
        if nav_key:
            state = context.user_data.get("admin_state")
            clear_admin_state(context)
            if nav_key == "asosiy":
                await sm(context.bot, uid, "Asosiy menyu", main_menu_kb(is_admin=True))
            else:
                await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb(uid))
            logger.info(f"Admin holat '{state}' bekor → {nav_key}")
            return

    # ── 7. Admin state handler ──────────────────────────
    if is_any_admin(uid):
        state = context.user_data.get("admin_state")
        if state:
            handled = await admin_state_handler(update, context, text)
            if handled: return

    # ── 8. Admin tugmalarini aniqlash ───────────────────
    if is_any_admin(uid):
        all_admin_btn_keys = [
            "kino_joy", "qism_qosh", "pullik", "stat",
            "kanal_post", "maj_kanal", "karta", "ilova",
            "emoji_soz", "asosiy", "boshqarish", "broadcast", "kino_uch",
            "kino_kanal_set", "qism_tahrir", "admin_qosh",
        ]
        all_admin_btns = {bt(k): k for k in all_admin_btn_keys if bt(k)}
        if text in all_admin_btns:
            key = all_admin_btns[text]
            # Sub-admin perm check (super-admin har doim ruxsatli)
            if key in ADMIN_PERM_KEYS and not has_perm(uid, key):
                await sm(context.bot, uid, "⛔ Sizda bu amalga ruxsat yo'q.", admin_menu_kb(uid))
                return
            if key == "admin_qosh" and not is_super_admin(uid):
                await sm(context.bot, uid, "⛔ Faqat asosiy admin yangi admin qo'sha oladi.", admin_menu_kb(uid))
                return
            if key == "emoji_soz":
                clear_admin_state(context)
                context.user_data["emoji_menu"] = True
                await sm(context.bot, uid,
                    "<b>Tugma sozlamalari</b>\nO'zgartirmoqchi bo'lgan tugmani pastdan tanlang 👇",
                    emoji_menu_kb())
                return
            if key == "broadcast":
                context.user_data.pop("admin_state", None)
                context.user_data.pop("emoji_menu", None)
                context.user_data.pop("editing_btn_key", None)
                await sm(context.bot, uid,
                    "📢 <b>Barchaga xabar yuborish</b>\n\n"
                    "Xabar yuboring — matn, rasm yoki video.")
                context.user_data["admin_state"] = "broadcast_msg"
                return
            if key == "kino_uch":
                context.user_data.pop("emoji_menu", None)
                context.user_data["admin_state"] = "delete_movie_code"
                await sm(context.bot, uid, "🗑 <b>Kino o'chirish</b>\n\nKino kodini kiriting:")
                return
            context.user_data.pop("emoji_menu", None)
            context.user_data.pop("editing_btn_key", None)
            await admin_buttons(update, context, text)
            return

    # ── 9. Asosiy tugmalar ──────────────────────────────
    if text == bt("yordam"):
        await sm(context.bot, uid,
            "💬 <b>Yordam kerakmi?</b>\n\n"
            "Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\n"
            "Admin tez orada javob beradi! 🙂",
            help_kb(), reply_to_message_id=msg.message_id)
        context.user_data["awaiting_help"] = True
        return

    if text == bt("install"):
        f_id = RAM.settings.get("install_file_id")
        v_id = RAM.settings.get("install_video_id")
        if not f_id and not v_id:
            await sm(context.bot, uid, "Admin hali ilova fayl/video joylamagan.")
            return
        tasks = []
        if v_id: tasks.append(sv(context.bot, uid, v_id, "<b>Ilovani o'rnatish videosi</b>"))
        if f_id: tasks.append(context.bot.send_document(uid, f_id, caption="<b>Ilova fayli</b>", parse_mode="HTML"))
        await asyncio.gather(*tasks, return_exceptions=True)
        return

    if text == bt("barcha_kino"):
        movies = RAM.movies
        if not movies:
            await sm(context.bot, uid,
                "🎬 <b>Hozircha hech qanday kino qo'shilmagan.</b>\n\nKino qo'shilganda bu yerda ko'rinadi! 📽")
            return
        await _send_kino_list_page(context.bot, uid, page=0)
        return

    # ── 10. Yordam so'rovi ──────────────────────────────
    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n{text}")
        await sm(context.bot, ADMIN_ID, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos, chek <b>rasmini</b> yuboring.")
        return

    # ── 11. Kino kodi qidirish (RAMdan — tez!) ──────────
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
        if not is_any_admin(uid):
            await sm(context.bot, uid,
                "❌ Bunday kino topilmadi.\n\nKino nomi yoki kodini to'g'ri yuboring 👇")


# ══════════════════════════════════════════════════════════
# ADMIN BUTTONS
# ══════════════════════════════════════════════════════════

async def admin_buttons(update, context, text: str):
    uid = update.effective_user.id

    if text == bt("boshqarish"):
        context.user_data.pop("admin_state", None)
        context.user_data.pop("channel_manage_menu", None)
        await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb(uid))
        return

    if text == bt("asosiy"):
        context.user_data.pop("admin_state", None)
        context.user_data.pop("channel_manage_menu", None)
        await sm(context.bot, uid, "Asosiy menyu", main_menu_kb(is_admin=True))
        return

    if text == bt("stat"):
        u = len(RAM.users)
        m = len(RAM.movies)
        v = RAM.stats.get("total_views", 0)
        if DB_STATUS["ram_only"]:
            storage_line = (f"\n\n🔴 <b>Storage holati: RAM ONLY</b>\n"
                           f"JSONBlob ishlamayapti! Xatolar: <b>{DB_STATUS['fail_count']}</b>")
        elif DB_STATUS["last_save_ok"]:
            storage_line = f"\n\n🟢 <b>Storage holati: OK</b>\nOxirgi saqlash: <code>{DB_STATUS['last_save_ok']}</code>"
        else:
            storage_line = "\n\n🟡 <b>Storage holati: Tekshirilmagan</b>"
        await sm(context.bot, uid,
            f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
            f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>{storage_line}", stats_kb())
        return

    if text == bt("karta"):
        context.user_data["admin_state"] = "set_card"
        cur = RAM.card_number or "Kiritilmagan"
        await sm(context.bot, uid, f"Joriy karta: <code>{cur}</code>\n\nYangi karta raqamini yuboring:")
        return

    if text == bt("kino_joy"):
        context.user_data["admin_state"] = "add_movie_code"
        await sm(context.bot, uid,
            "🎬 <b>Yangi kino qo'shish</b>\n\n"
            "Kino kodini kiriting (masalan: AVATAR yoki 001):")
        return

    if text == bt("qism_qosh"):
        context.user_data["admin_state"] = "add_ep_code"
        movies = RAM.movies
        if movies:
            codes_list = "\n".join([f"• <code>{c}</code> — {m.get('title', c)}"
                                    for c, m in list(movies.items())[-10:]])
            await sm(context.bot, uid,
                f"📺 <b>Qism qo'shish</b>\n\nSo'nggi kinolar:\n{codes_list}\n\n"
                f"Qism qo'shmoqchi bo'lgan kino <b>kodini</b> kiriting:")
        else:
            await sm(context.bot, uid, "📺 <b>Qism qo'shish</b>\n\nKino kodini kiriting:")
        return

    if text == bt("pullik"):
        context.user_data["admin_state"] = "set_price_code"
        context.user_data.pop("price_movie_code", None)
        context.user_data.pop("price_ep", None)
        await sm(context.bot, uid, "💰 <b>Qismni pullik qilish</b>\n\nKino <b>kodini</b> kiriting:")
        return

    if text == bt("ilova"):
        context.user_data["admin_state"] = "set_install"
        await sm(context.bot, uid, "Ilova fayl yoki video yuboring:")
        return

    if text == bt("kino_kanal_set"):
        context.user_data["admin_state"] = "set_kino_kanal"
        cur_url  = RAM.settings.get("kino_kanal_url", "")
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
            f"📡 <b>Majburiy kanal boshqaruvi</b>\n\n{_channels_list_text()}\n\nNima qilmoqchisiz?",
            channel_manage_kb())
        return

    if text == bt("kanal_post"):
        context.user_data["admin_state"] = "post_channel_code"
        movies = RAM.movies
        if movies:
            codes_list = "\n".join([f"• <code>{c}</code> — {m.get('title', c)}"
                                    for c, m in list(movies.items())[-10:]])
            await sm(context.bot, uid,
                f"📤 <b>Kanalga post</b>\n\nSo'nggi kinolar:\n{codes_list}\n\n"
                f"Post qilmoqchi bo'lgan kino <b>kodini</b> kiriting:")
        else:
            await sm(context.bot, uid, "Post qilmoqchi bo'lgan kino kodini kiriting:")
        return

    if text == bt("admin_qosh"):
        if not is_super_admin(uid):
            await sm(context.bot, uid, "⛔ Faqat asosiy admin yangi admin qo'sha oladi.", admin_menu_kb(uid))
            return
        context.user_data["admin_state"] = "add_admin_id"
        cur = RAM.sub_admins or {}
        cur_list = "\n".join([f"• <code>{u}</code>" for u in cur.keys()]) or "<i>Hozircha yo'q</i>"
        await sm(context.bot, uid,
            "👮 <b>Admin qo'shish</b>\n\n"
            f"Hozirgi adminlar:\n{cur_list}\n\n"
            "Yangi admin uchun foydalanuvchi <b>ID</b> raqamini yuboring:\n"
            "<i>(ID o'chirish uchun: <code>-12345</code> — minus bilan ID)</i>")
        return

    if text == bt("qism_tahrir"):
        context.user_data["admin_state"] = "edit_ep_code"
        context.user_data.pop("edit_ep_num", None)
        movies = RAM.movies
        if movies:
            codes_list = "\n".join([f"• <code>{c}</code> — {m.get('title', c)}"
                                    for c, m in list(movies.items())[-10:]])
            await sm(context.bot, uid,
                f"✏️ <b>Qismlarni tahrirlash</b>\n\nSo'nggi kinolar:\n{codes_list}\n\n"
                f"Tahrirlamoqchi bo'lgan kino <b>kodini</b> kiriting:")
        else:
            await sm(context.bot, uid, "✏️ <b>Qismlarni tahrirlash</b>\n\nKino kodini kiriting:")
        return


# ══════════════════════════════════════════════════════════
# ADMIN STATE HANDLER
# ══════════════════════════════════════════════════════════

async def admin_state_handler(update, context, text: str) -> bool:
    state = context.user_data.get("admin_state")
    uid   = update.effective_user.id
    if not state: return False

    if state == "broadcast_msg":
        bc = {
            "type": "copy",
            "from_chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "buttons": [],
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "✅ Xabar qabul qilindi.\n\n<b>Tugmali xabar yuborasizmi?</b>",
                 markup=bc_yesno_kb())
        return True

    if state == "delete_movie_code":
        code = text.upper().strip()
        if code not in RAM.movies:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {RAM.movies.get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> topilmadi.\n\nShunga o'xshash:\n{hint}\n\nTo'g'ri kodini kiriting:")
            else:
                await sm(context.bot, uid, f"❌ <code>{code}</code> kodli kino topilmadi. Qayta kiriting:")
            return True
        movie = RAM.movies[code]
        title = movie.get("title", code)
        eps   = movie.get("episodes", [])
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
        movie = RAM.movies.get(code) if code else None
        if not movie:
            await sm(context.bot, uid, "❌ Kino topilmadi. /start bosing.")
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            return True
        title = movie.get("title", code)
        eps   = movie.get("episodes", [])
        val   = text.strip().lower()

        if val == "kino":
            RAM.del_movie(code)
            save_ok = await save_now()
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            storage_warn = "\n⚠️ <i>Faqat RAMda saqlandi!</i>" if not save_ok else ""
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> (<code>{code}</code>) butunlay o'chirildi!\n"
                f"Qolgan kinolar: <b>{len(RAM.movies)} ta</b>{storage_warn}",
                admin_menu_kb(uid))
            return True

        if val == "hammasi":
            RAM.movies[code]["episodes"] = []
            RAM.movies[code]["prices"]   = {}
            save_ok = await save_now()
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            storage_warn = "\n⚠️ <i>Faqat RAMda saqlandi!</i>" if not save_ok else ""
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> kinoning barcha qismlari o'chirildi!{storage_warn}",
                admin_menu_kb(uid))
            return True

        if val.isdigit():
            ep_num = int(val)
            if ep_num < 1 or ep_num > len(eps):
                await sm(context.bot, uid,
                    f"❌ <b>{ep_num}</b>-qism mavjud emas. 1–{len(eps)} oralig'ida kiriting:")
                return True
            idx = ep_num - 1
            RAM.movies[code]["episodes"].pop(idx)
            old_prices = movie.get("prices", {})
            new_prices = {}
            for k, v in old_prices.items():
                try:
                    k_int = int(k)
                    if k_int < ep_num:   new_prices[k] = v
                    elif k_int > ep_num: new_prices[str(k_int - 1)] = v
                except: pass
            RAM.movies[code]["prices"] = new_prices
            save_ok = await save_now()
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            storage_warn = "\n⚠️ Faqat RAMda saqlandi!" if not save_ok else ""
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> — <b>{ep_num}-qism</b> o'chirildi!\n"
                f"Qolgan qismlar: <b>{len(RAM.movies[code]['episodes'])} ta</b>{storage_warn}",
                admin_menu_kb(uid))
            return True

        await sm(context.bot, uid,
            "❌ Noto'g'ri. Qism raqami, <code>hammasi</code> yoki <code>kino</code> kiriting:")
        return True

    if state == "set_card":
        RAM.card_number = text
        await save_now()
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, f"✅ Karta saqlandi: <code>{text}</code>", admin_menu_kb(uid))
        return True

    if state == "set_kino_kanal":
        context.user_data.pop("admin_state", None)
        if text.strip() == "0":
            RAM.settings["kino_kanal_url"] = ""
            await save_now()
            await sm(context.bot, uid, "✅ Kino kodlari kanali linki <b>o'chirildi</b>!", admin_menu_kb(uid))
        elif text.startswith("http"):
            RAM.settings["kino_kanal_url"] = text.strip()
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>Kino kodlari kanali</b> linki saqlandi!\nLink: <code>{text.strip()}</code>",
                admin_menu_kb(uid))
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
            await sm(context.bot, uid, "❌ Kod 30 ta belgidan oshmasin.")
            return True
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. To'g'ri kod kiriting:")
            return True
        if code in RAM.movies:
            movie = RAM.movies[code]
            await sm(context.bot, uid,
                f"⚠️ <code>{code}</code> kodi allaqachon mavjud!\n\n"
                f"🎬 Nomi: <b>{movie.get('title', code)}</b>\n"
                f"📺 Qismlar: <b>{len(movie.get('episodes', []))} ta</b>\n\n"
                f"Boshqa kod kiriting.")
            return True
        context.user_data["new_movie_code"] = code
        context.user_data["admin_state"]    = "add_movie_title"
        await sm(context.bot, uid, f"✅ Kod: <code>{code}</code>\n\nEndi kino <b>nomini</b> kiriting:")
        return True

    if state == "add_movie_title":
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid,
                "❌ Bu kino nomi emas — admin tugmasi bosildi.\n\n"
                f"Kino nomini kiriting (masalan: <b>Avatar 2</b>):")
            return True
        code = context.user_data.get("new_movie_code")
        if not code:
            await sm(context.bot, uid, "❌ Xatolik. Qaytadan boshlang.")
            context.user_data.pop("admin_state", None)
            return True
        if not text.strip():
            await sm(context.bot, uid, "❌ Nom bo'sh bo'lmasin.")
            return True
        now        = datetime.now().strftime("%d.%m.%Y %H:%M")
        title_html = text_with_premium_emojis(update.message) or text
        # ❗ Darhol RAMga yoz
        RAM.movies[code] = {
            "title": title_html,
            "episodes": [],
            "prices": {},
            "added_date": now,
            "added_at": time.time(),
            "poster_file_id": None,
        }
        # ❗ DARHOL bazaga ham saqla — kino yo'qolib qolmasin
        await save_now()

        context.user_data["admin_state"] = "add_movie_poster"
        context.user_data["poster_code"] = code
        await sm(context.bot, uid,
            f"✅ <b>{title_html}</b> kinosi RAMga qo'shildi!\n"
            f"Kod: <code>{code}</code>\n"
            f"Jami kinolar: <b>{len(RAM.movies)} ta</b>\n\n"
            f"📷 Kino posterini yuboring\n"
            f"<i>(poster yo'q bo'lsa <b>0</b> kiriting)</i>")
        return True

    if state == "add_movie_poster":
        code = context.user_data.pop("poster_code", None)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("new_movie_code", None)
        if code and code in RAM.movies:
            await sm(context.bot, uid,
                f"✅ Poster o'tkazib yuborildi.\nKod: <code>{code}</code>\n\nQism qo'shishingiz mumkin 👇",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "✅ Kino qo'shildi!", admin_menu_kb(uid))
        return True

    if state == "add_ep_code":
        code = text.upper().strip()
        if not code:
            await sm(context.bot, uid, "❌ Kod kiriting:")
            return True
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. Kino kodini kiriting:")
            return True
        if code not in RAM.movies:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {RAM.movies.get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ <code>{code}</code> topilmadi.\n\nShunga o'xshash:\n{hint}\n\nTo'g'ri kodini kiriting:")
            else:
                movies_list = RAM.movies
                if movies_list:
                    last5 = "\n".join([f"• <code>{c}</code> — {m.get('title',c)}"
                                       for c, m in list(movies_list.items())[-5:]])
                    await sm(context.bot, uid,
                        f"❌ <code>{code}</code> kodli kino topilmadi.\n\n"
                        f"So'nggi kinolar:\n{last5}\n\nQayta kino kodini kiriting:")
                else:
                    await sm(context.bot, uid,
                        f"❌ <code>{code}</code> topilmadi.\n⚠️ Hali kino qo'shilmagan!")
                    context.user_data.pop("admin_state", None)
            return True
        movie  = RAM.movies[code]
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
        # Video kutilayapti — matn kelsa jim o'tkazib yuboramiz
        return True

    if state == "set_price_code":
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. Kino kodini kiriting:")
            return True
        code = text.upper().strip()
        if code not in RAM.movies:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {RAM.movies.get(c,{}).get('title',c)}"
                                   for c in matches[:5]])
                await sm(context.bot, uid,
                    f"❌ Topilmadi.\n\nShunga o'xshash:\n{hint}\n\nTo'g'ri kodini kiriting:")
            else:
                await sm(context.bot, uid, f"❌ <code>{code}</code> topilmadi. Qayta kiriting:")
            return True
        movie  = RAM.movies[code]
        eps    = movie.get("episodes", [])
        prices = movie.get("prices", {})
        if not eps:
            await sm(context.bot, uid,
                f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.")
            context.user_data.pop("admin_state", None)
            return True
        ep_list = _build_ep_price_list(code, eps, prices)
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"]      = "set_price_ep"
        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b>\n\n{ep_list}\n\n"
            f"Qism <b>raqamini</b> kiriting (1 dan {len(eps)} gacha):")
        return True

    if state == "set_price_ep":
        code = context.user_data.get("price_movie_code")
        if not code or code not in RAM.movies:
            await sm(context.bot, uid, "❌ Xatolik. Kino kodini qayta kiriting:")
            context.user_data["admin_state"] = "set_price_code"
            context.user_data.pop("price_movie_code", None)
            return True
        movie = RAM.movies[code]
        eps   = movie.get("episodes", [])
        if not text.strip().isdigit():
            await sm(context.bot, uid, "❌ Faqat <b>raqam</b> kiriting:")
            return True
        ep_num = int(text.strip())
        if ep_num < 1 or ep_num > len(eps):
            await sm(context.bot, uid,
                f"❌ <b>{ep_num}</b>-qism mavjud emas. 1–{len(eps)} kiriting:")
            return True
        context.user_data["price_ep"]    = str(ep_num)
        context.user_data["admin_state"] = "set_price_amount"
        cur_price = movie.get("prices", {}).get(str(ep_num))
        cur_info  = f"\nHozirgi narx: <b>{cur_price} so'm</b>" if cur_price else "\nHozir: <b>bepul</b>"
        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b>\n<b>{ep_num}-qism</b>{cur_info}\n\n"
            f"Yangi narxni kiriting (so'mda):\n<i>Bepul qilish uchun <code>0</code></i>")
        return True

    if state == "add_admin_id":
        if not is_super_admin(uid):
            clear_admin_state(context)
            await sm(context.bot, uid, "⛔ Ruxsat yo'q.", admin_menu_kb(uid))
            return True
        raw = text.strip()
        # Manfiy ID — admin o'chirish
        if raw.startswith("-") and raw[1:].isdigit():
            target = raw[1:]
            if target in (RAM.sub_admins or {}):
                RAM.sub_admins.pop(target, None)
                await save_now()
                clear_admin_state(context)
                await sm(context.bot, uid, f"✅ Admin <code>{target}</code> o'chirildi.", admin_menu_kb(uid))
            else:
                await sm(context.bot, uid, f"❌ <code>{target}</code> admin emas.")
            return True
        if not raw.isdigit():
            await sm(context.bot, uid, "❌ Faqat raqamli <b>ID</b> kiriting (yoki <code>-ID</code> o'chirish uchun):")
            return True
        target = raw
        if int(target) == ADMIN_ID:
            await sm(context.bot, uid, "⚠️ Bu allaqachon asosiy admin.")
            clear_admin_state(context)
            return True
        # Yangi yoki mavjud admin
        if target not in RAM.sub_admins:
            RAM.sub_admins[target] = {"perms": {k: True for k in ADMIN_PERM_KEYS}}
        await save_now()
        clear_admin_state(context)
        await sm(context.bot, uid,
            f"👮 <b>Admin: <code>{target}</code></b>\n\n"
            f"Quyidagi tugmalardan istalganini bosing — <b>yoqib/o'chirib</b> turing.\n"
            f"✅ — admin ko'radi, ❌ — admin ko'rmaydi.",
            sub_admin_perm_kb(target))
        return True

    if state == "edit_ep_code":
        code = text.strip().upper()
        if code not in RAM.movies:
            await sm(context.bot, uid, f"❌ <code>{code}</code> kodli kino topilmadi. Qayta kiriting:")
            return True
        movie = RAM.movies[code]
        eps = movie.get("episodes", [])
        if not eps:
            await sm(context.bot, uid, f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.",
                     admin_menu_kb(uid))
            clear_admin_state(context)
            return True
        ep_labels = movie.get("ep_labels", {}) or {}
        lines = []
        for i in range(len(eps)):
            ek = str(i + 1)
            cur = ep_labels.get(ek)
            if cur: lines.append(f"  {ek} → <b>{cur}</b>")
            else:   lines.append(f"  {ek} → {ek}-qism")
        context.user_data["edit_ep_code"] = code
        context.user_data["admin_state"]  = "edit_ep_num"
        await sm(context.bot, uid,
            f"✏️ <b>{movie.get('title', code)}</b>\n\n"
            f"📺 Qismlar ({len(eps)} ta):\n" + "\n".join(lines) +
            f"\n\nNechanchi qismni tahrirlamoqchisiz? <b>Raqam</b> kiriting (1 dan {len(eps)} gacha):")
        return True

    if state == "edit_ep_num":
        code = context.user_data.get("edit_ep_code")
        if not code or code not in RAM.movies:
            await sm(context.bot, uid, "❌ Xatolik. Kino kodini qayta kiriting:")
            context.user_data["admin_state"] = "edit_ep_code"
            context.user_data.pop("edit_ep_code", None)
            return True
        movie = RAM.movies[code]
        eps = movie.get("episodes", [])
        if not text.strip().isdigit():
            await sm(context.bot, uid, "❌ Faqat <b>raqam</b> kiriting:")
            return True
        ep_num = int(text.strip())
        if ep_num < 1 or ep_num > len(eps):
            await sm(context.bot, uid, f"❌ <b>{ep_num}</b>-qism mavjud emas. 1–{len(eps)} kiriting:")
            return True
        context.user_data["edit_ep_num"]  = str(ep_num)
        context.user_data["admin_state"]  = "edit_ep_label"
        cur_label = (movie.get("ep_labels", {}) or {}).get(str(ep_num)) or f"{ep_num}-qism"
        await sm(context.bot, uid,
            f"✏️ <b>{movie.get('title', code)}</b> — <b>{ep_num}-qism</b>\n\n"
            f"Hozirgi nom: <code>{cur_label}</code>\n\n"
            f"Yangi nomni kiriting (masalan: <code>1-qismdan 10-qismgacha</code>)\n"
            f"<i>Asl nomga qaytarish uchun <code>0</code> yuboring</i>")
        return True

    if state == "edit_ep_label":
        code = context.user_data.get("edit_ep_code")
        ep   = context.user_data.get("edit_ep_num")
        if not code or not ep or code not in RAM.movies:
            await sm(context.bot, uid, "❌ Xatolik. /start bosing.")
            clear_admin_state(context)
            return True
        movie = RAM.movies[code]
        new_label = text.strip()
        movie_title = movie.get("title", code)
        clear_admin_state(context)
        if new_label == "0":
            movie.setdefault("ep_labels", {}).pop(ep, None)
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> nomi asl holatga qaytarildi.",
                admin_menu_kb(uid))
        else:
            movie.setdefault("ep_labels", {})[ep] = new_label
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> nomi yangilandi:\n<b>{new_label}</b>",
                admin_menu_kb(uid))
        return True

    if state == "set_price_amount":
        code = context.user_data.get("price_movie_code")
        ep   = context.user_data.get("price_ep")
        if not code or not ep or code not in RAM.movies:
            await sm(context.bot, uid, "❌ Xatolik. /start bosing.")
            clear_admin_state(context)
            return True
        if not text.strip().isdigit():
            await sm(context.bot, uid, "❌ Faqat <b>raqam</b> kiriting.")
            return True
        amount      = text.strip()
        movie_title = RAM.movies[code].get("title", code)
        clear_admin_state(context)
        if amount == "0":
            RAM.movies[code].setdefault("prices", {}).pop(ep, None)
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> endi <b>bepul</b>!", admin_menu_kb(uid))
        else:
            RAM.movies[code].setdefault("prices", {})[ep] = amount
            await save_now()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> narxi: <b>{amount} so'm</b>",
                admin_menu_kb(uid))
        return True

    if state == "add_channel_username":
        raw_uname = text.strip()
        uname     = normalize_channel_username(raw_uname)
        if not uname or (not uname.startswith("@") and not uname.startswith("-100")):
            await sm(context.bot, uid,
                "❌ Kanal username noto'g'ri.\nMisol: <code>@mykinochannel</code>")
            return True
        for ch in RAM.channels:
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
            await sm(context.bot, uid,
                f"❌ Kanal tekshirilmadi. Bot kanalga admin sifatida qo'shilganligini tekshiring.\n\n"
                f"Xato: <code>{e}</code>")
            return True
        context.user_data["ch_info"]     = channel_info
        context.user_data["admin_state"] = "add_channel_title"
        await sm(context.bot, uid,
            f"✅ Kanal topildi!\n\n📛 Nom: <b>{channel_info['title']}</b>\n"
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
            await sm(context.bot, uid, "❌ Nom bo'sh bo'lmasin.")
            return True
        channel_info["title"] = title
        channel_info["url"]   = channel_join_url(channel_info.get("username", ""), channel_info.get("url", ""))
        RAM.channels.append(channel_info)
        await save_now()
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True
        await sm(context.bot, uid,
            f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n"
            f"📛 Nom: <b>{channel_info['title']}</b>\n"
            f"👤 Username: <b>{channel_info['username']}</b>\n\n"
            f"{_channels_list_text()}",
            channel_manage_kb())
        return True

    if state in ("add_channel_url", "add_channel"):
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True
        await sm(context.bot, uid, "ℹ️ Qaytadan <b>➕ Kanal qo'shish</b> tugmasini bosing.", channel_manage_kb())
        return True

    if state == "post_channel_code":
        reserved = _get_admin_reserved_texts()
        if text in reserved or text.startswith("/"):
            await sm(context.bot, uid, "❌ Bu kino kodi emas. Kino kodini kiriting:")
            return True
        code = text.upper().strip()
        if code not in RAM.movies:
            _, matches = find_movie_code(text)
            if matches:
                hint = "\n".join([f"• <code>{c}</code> — {RAM.movies.get(c,{}).get('title',c)}"
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
        movie    = RAM.movies.get(code, {})
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
            if poster: await sp(context.bot, channel, poster, caption, markup)
            else:      await sm(context.bot, channel, caption, markup)
            await sm(context.bot, uid, "✅ Post yuborildi!", admin_menu_kb(uid))
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
    if _is_duplicate_update(update): return
    uid = update.effective_user.id
    if not is_any_admin(uid): return
    key = context.user_data.get("editing_btn_key")
    if not key: return
    sticker = update.message.sticker
    if not sticker: return
    emoji = sticker.emoji or ""
    if not emoji:
        await sm(context.bot, uid, "Bu stickerda emoji yo'q.")
        return
    context.user_data.pop("editing_btn_key", None)
    existing         = RAM.btn_texts.get(key) or DEFAULT_BTN.get(key, "")
    existing_label   = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
    existing_emoji_p = extract_emoji_prefix(existing)
    new_emoji_p      = (existing_emoji_p + emoji) if existing_emoji_p else emoji
    new_text         = f"{new_emoji_p} {existing_label}"
    RAM.btn_texts[key] = new_text
    EMOJI_IDS.pop(key, None)
    RAM.emoji_ids.pop(key, None)
    await save_now()
    await sm(context.bot, uid,
        f"✅ <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\nKo'rinish: <code>{new_text}</code>")
    context.user_data["emoji_menu"] = True
    await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())


# ══════════════════════════════════════════════════════════
# MEDIA HANDLER
# ══════════════════════════════════════════════════════════

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_duplicate_update(update): return
    user  = update.effective_user
    uid   = user.id
    msg   = update.message
    state = context.user_data.get("admin_state")

    if is_any_admin(uid) and state == "broadcast_msg":
        bc = {
            "type": "copy",
            "from_chat_id": msg.chat_id,
            "message_id": msg.message_id,
            "buttons": [],
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "✅ Xabar qabul qilindi.\n\n<b>Tugmali xabar yuborasizmi?</b>",
                 markup=bc_yesno_kb())
        return

    if is_any_admin(uid) and state == "add_movie_poster":
        code = context.user_data.pop("poster_code", None)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("new_movie_code", None)
        if msg.photo and code and code in RAM.movies:
            RAM.movies[code]["poster_file_id"] = msg.photo[-1].file_id
            await schedule_save()
            await sm(context.bot, uid,
                f"✅ Poster saqlandi!\nKod: <code>{code}</code>",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "⚠️ Rasm yuboring!", movie_added_kb(code) if code else None)
        return

    if is_any_admin(uid) and state == "add_ep_video":
        code = context.user_data.get("ep_movie_code")
        if not code:
            await sm(context.bot, uid, "❌ Kino kodi topilmadi. Qaytadan bosing.")
            context.user_data.pop("admin_state", None)
            return

        # Forward qilingan video document sifatida ham kelishi mumkin
        video_file_id = None
        if msg.video:
            video_file_id = msg.video.file_id
        elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("video"):
            video_file_id = msg.document.file_id

        if not video_file_id:
            movie  = RAM.movies.get(code, {})
            ep_num = len(movie.get("episodes", [])) + 1
            await sm(context.bot, uid,
                f"⚠️ Faqat <b>video</b> yuboring!\n"
                f"Kino: <b>{movie.get('title', code)}</b>\n"
                f"<b>{ep_num}-qism</b> kutilmoqda...")
            return

        # ❗ Duplicate himoya — bir xil file_id ikki marta qo'shilmasin
        movie = RAM.movies.get(code, {})
        if video_file_id in movie.get("episodes", []):
            ep_num = len(movie.get("episodes", []))
            await sm(context.bot, uid,
                f"⚠️ Bu video allaqachon saqlangan!\n"
                f"Jami qismlar: <b>{ep_num} ta</b>\n\n"
                f"📹 Yana video yuboring yoki <b>Tugatish</b> tugmasini bosing.",
                movie_added_kb(code))
            return

        # ❗ Darhol RAMga yoz
        RAM.movies[code]["episodes"].append(video_file_id)
        ep_num = len(RAM.movies[code]["episodes"])

        # ❗ Lokal faylga darhol yoz (har bir qism uchun) — bot to'xtab qolsa ham yo'qolmaydi
        await save_ram_only()
        # ❗ JSONBlob ga ham — har 3-qismda bir marta + debounce
        # (har video uchun yozish sekin, lekin to'liq tashlab qo'yish xavfli)
        if ep_num == 1 or ep_num % 3 == 0:
            # birinchi qism va har 3-qismda — DARHOL JSONBlob ga
            asyncio.create_task(_do_jsonblob_save())
        else:
            # qolganlari uchun debounce taymeri (12 sek dan keyin)
            await schedule_save()

        # Admin yana video yuborishi mumkin — state saqlab qolamiz
        context.user_data["admin_state"]   = "add_ep_video"
        context.user_data["ep_movie_code"] = code

        movie = RAM.movies[code]
        await sm(context.bot, uid,
            f"✅ <b>{ep_num}-qism</b> saqlandi!\n"
            f"Kino: <b>{movie.get('title', code)}</b>\n"
            f"Kod: <code>{code}</code>\n"
            f"Jami qismlar: <b>{ep_num} ta</b>\n\n"
            f"📹 Yana video yuboring yoki <b>Tugatish</b> tugmasini bosing.\n"
            f"<i>Avtomatik bazaga ham saqlandi — yo'qolmaydi.</i>",
            movie_added_kb(code))
        return

    if is_any_admin(uid) and state == "set_install":
        if msg.video:
            RAM.settings["install_video_id"] = msg.video.file_id
            await save_now()
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "✅ O'rnatish videosi saqlandi!", admin_menu_kb(uid))
        elif msg.document:
            RAM.settings["install_file_id"] = msg.document.file_id
            await save_now()
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "✅ O'rnatish fayli saqlandi!", admin_menu_kb(uid))
        else:
            await sm(context.bot, uid, "⚠️ Video yoki fayl yuboring!")
        return

    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info = context.user_data.pop("awaiting_check")
        code = str(pay_info.get("code", "")).upper()
        ep   = str(pay_info.get("ep", ""))
        movie = RAM.movies.get(code)
        idx = int(ep) - 1 if ep.isdigit() else -1
        if not movie or idx < 0 or idx >= len(movie.get("episodes", []) or []):
            await sm(context.bot, uid, "❌ Bu qism topilmadi. Kino kodini qayta yuboring.")
            return
        price = price_to_int(movie.get("prices", {}).get(ep))
        if price <= 0:
            await sm(context.bot, uid, "ℹ️ Bu qism hozir pullik emas. Kino kodini qayta yuboring.")
            return
        if is_episode_paid(uid, code, ep):
            await sm(context.bot, uid, f"✅ Siz <b>{ep}-qism</b>ni allaqachon sotib olgansiz.")
            return

        pid = f"{uid}_{code}_{ep}_{int(time.time())}"
        RAM.pending_payments[pid] = {
            "user_id": uid,
            "code": code,
            "ep": ep,
            "price": price,
            "status": "pending",
        }
        await save_now()
        cap = (f"<b>To'lov cheki</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\nKino: <b>{code}</b>\n"
               f"Qism: <b>{ep}</b>\nNarx: <b>{price} so'm</b>")
        await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, payment_admin_kb(pid))
        await sm(context.bot, uid,
            "✅ <b>Chekingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
            "👨‍💼 Admin tekshirib tasdiqlaydi va faqat shu qism videosini sizga yuboradi.\n"
            "⏱ Tekshirish vaqti: <b>5 daqiqadan 2 soatgacha</b>.\n\n"
            "🙏 Kutganingiz uchun rahmat!")
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

    if is_any_admin(uid) and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            cap = "<b>Admin javobi</b>"
            if msg.photo:
                if msg.caption: cap += f"\n{msg.caption}"
                await sp(context.bot, target, msg.photo[-1].file_id, cap)
            elif msg.video:
                if msg.caption: cap += f"\n{msg.caption}"
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

    # ── Ishga tushganda bazadan RAM ga yukla ──────────────
    db_initial_load()
    logger.info(f"🚀 RAM cache: {len(RAM.movies)} kino, {len(RAM.users)} user yuklandi")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(15)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))

    # ── Har 5 daqiqada JSONBlob ga sinxron saqlash ────────
    async def _periodic_sync(context_job):
        try:
            data    = RAM.to_dict()
            was_down = DB_STATUS.get("ram_only", False)
            ok      = await asyncio.to_thread(_save_jsonblob, data)
            _save_local(data)
            now_str = datetime.now().strftime("%H:%M:%S")
            if ok:
                DB_STATUS.update({
                    "storage_ok": True, "fail_count": 0,
                    "last_save_ok": now_str, "ram_only": False,
                })
                if was_down:
                    try:
                        await context_job.bot.send_message(
                            ADMIN_ID,
                            f"✅ <b>Storage tiklandi!</b>\n{now_str}\n"
                            f"RAMdagi {len(RAM.movies)} kino saqlandi.",
                            parse_mode="HTML")
                    except: pass
            else:
                DB_STATUS["fail_count"] = DB_STATUS.get("fail_count", 0) + 1
                DB_STATUS["last_err"]   = now_str
                if DB_STATUS["fail_count"] >= 2:
                    DB_STATUS.update({"storage_ok": False, "ram_only": True})
                if DB_STATUS["fail_count"] == 2:
                    try:
                        await context_job.bot.send_message(
                            ADMIN_ID,
                            f"⚠️ <b>JSONBlob ishlamayapti!</b>\n{now_str}\n"
                            f"Bot RAMdan ishlayapti (ma'lumotlar yo'qolmaydi).",
                            parse_mode="HTML")
                    except: pass
            status = "✅" if ok else "⚠️"
            logger.info(f"{status} Periodik sync: {len(RAM.movies)} kino, {len(RAM.users)} user")
        except Exception as e:
            logger.error(f"Periodik sync xato: {e}")

    async def _startup_notify(context_job):
        try:
            ok = await asyncio.to_thread(_save_jsonblob, RAM.to_dict())
            now_str = datetime.now().strftime("%H:%M:%S")
            if ok:
                DB_STATUS.update({"storage_ok": True, "last_save_ok": now_str, "ram_only": False})
                storage_msg = f"🟢 JSONBlob ishlayapti — {now_str}"
            else:
                DB_STATUS.update({"storage_ok": False, "ram_only": True, "last_err": now_str})
                storage_msg = f"🔴 JSONBlob ishlamayapti! Bot RAMdan ishlaydi."
            await context_job.bot.send_message(
                ADMIN_ID,
                f"🚀 <b>Bot v18 ishga tushdi!</b>\n\n"
                f"💾 RAM: <b>{len(RAM.movies)}</b> kino, <b>{len(RAM.users)}</b> user\n"
                f"📦 Storage: {storage_msg}\n\n"
                f"✅ Barcha so'rovlar RAMdan javob beradi — tez!",
                parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Startup notify xato: {e}")

    if app.job_queue:
        app.job_queue.run_once(_startup_notify, when=5)
        app.job_queue.run_repeating(_periodic_sync, interval=120, first=60)
        logger.info("🔄 Periodik sync yoqildi (har 2 daqiqada)")

    logger.info(f"🚀 Bot v18 ishga tushdi! RAM: {len(RAM.movies)} kino, {len(RAM.users)} user")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
