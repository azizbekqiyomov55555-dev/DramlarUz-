# -*- coding: utf-8 -*-
"""
Kino Bot - Bot API 9.4 rangli tugmalar + emoji icon
TUZATILGAN VERSIYA
Asosiy o'zgarishlar:
  1. sm() chaqiruvlarida noto'g'ri parametr nomlari tuzatildi (parse_mode -> pm)
  2. JSONBin save() ishonchliroq â€” 5 marta retry, 201 ham qabul qilinadi
  3. Local backup fayl: db_backup.json â€” JSONBin xato bersa ham kinolar yo'qolmaydi
  4. Har muhim o'zgarishda darhol save() â€” kino qo'shish, statistika, to'lov
  5. db_load() avval JSONBin'dan, agar xato bo'lsa local backup'dan yuklaydi
  6. Statistika va kinolar har doim saqlanadi
  7. Emoji menyuda "Bekor" matn rejimi qo'shildi
  8. Bir nechta kichik bug fix
"""
import logging, asyncio, json, time, re, os
from datetime import datetime
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# KONFIG
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

BOT_TOKEN       = "8622992113:AAHif8dJz3eq_Zm8PTafxpSiNsEqE5VmoMc"
ADMIN_ID        = 8537782289
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# Local backup fayl â€” hosting reset bo'lsa ham JSONBin'dan tiklanadi,
# JSONBin ishlamasa ham bu fayldan tiklanadi.
LOCAL_BACKUP    = "db_backup.json"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_BTN = {
    "yordam":       "Yordam",
    "install":      "Ilovani o'rnatish",
    "kino_joy":     "Kino joylash",
    "qism_qosh":    "Qism qo'shish",
    "pullik":       "Qismni pullik qilish",
    "stat":         "Statistika",
    "kanal_post":   "Kanalga post",
    "maj_kanal":    "Majburiy kanal",
    "karta":        "Karta raqami",
    "ilova":        "Ilova fayl/video",
    "emoji_soz":    "Emoji sozlamalari",
    "asosiy":       "Asosiy menyu",
    "boshqarish":   "âš™ï¸ Boshqarish",
    "tekshir":      "Tekshirish",
    "tasdiq":       "Tasdiqlash",
    "bekor":        "Bekor qilish",
    "ulash":        "Do'stlarga ulashish",
    "tomosha":      "Tomosha qilish",
    "javob":        "Javob berish",
    "yangi":        "Yangilash",
    "qism_add":     "Qism qo'shish",
    "narx_bel":     "Narx belgilash",
    "kut":          "Tasdiqlanishini kuting",
    "bosh":         "Bosh menyu",
    "tiklash":      "Hammasini tiklash",
    "yopish":       "Yopish",
    "default_q":    "Defaultga qaytarish",
    "orqaga":       "Orqaga",
}

BTN_LABELS = {
    "yordam":       "Yordam tugmasi",
    "install":      "O'rnatish tugmasi",
    "kino_joy":     "Kino joylash",
    "qism_qosh":    "Qism qo'shish",
    "pullik":       "Pullik qilish",
    "stat":         "Statistika",
    "kanal_post":   "Kanalga post",
    "maj_kanal":    "Majburiy kanal",
    "karta":        "Karta raqami",
    "ilova":        "Ilova fayl/video",
    "emoji_soz":    "Emoji sozlamalari",
    "asosiy":       "Asosiy menyu",
    "boshqarish":   "âš™ï¸ Boshqarish",
    "tekshir":      "Tekshirish",
    "tasdiq":       "Tasdiqlash",
    "bekor":        "Bekor qilish",
    "ulash":        "Ulashish",
    "tomosha":      "Tomosha qilish",
    "javob":        "Javob berish",
    "yangi":        "Yangilash",
    "qism_add":     "Qism qo'shish (inline)",
    "narx_bel":     "Narx belgilash",
    "kut":          "Kuting tugmasi",
    "bosh":         "Bosh menyu (inline)",
    "tiklash":      "Hammasini tiklash",
    "yopish":       "Yopish",
    "default_q":    "Defaultga qaytarish",
    "orqaga":       "Orqaga",
}

LABEL_TO_KEY = {v: k for k, v in BTN_LABELS.items()}

DEFAULT_DB = {
    "users": {}, "movies": {}, "channels": [], "card_number": "",
    "pending_payments": {},
    "settings": {"install_file_id": None, "install_video_id": None},
    "stats": {"total_views": 0},
    "btn_texts": {},
    "btn_emoji_ids": {},
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DB â€” JSONBIN + LOCAL BACKUP
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def _merge_defaults(data):
    """DEFAULT_DB dagi yetishmayotgan kalitlarni qo'shadi."""
    for k, dv in DEFAULT_DB.items():
        if k not in data:
            data[k] = json.loads(json.dumps(dv))
        elif isinstance(dv, dict) and not isinstance(data[k], dict):
            data[k] = json.loads(json.dumps(dv))
        elif isinstance(dv, list) and not isinstance(data[k], list):
            data[k] = json.loads(json.dumps(dv))
    # ichki kalitlar
    data.setdefault("stats", {}).setdefault("total_views", 0)
    data.setdefault("settings", {})
    data["settings"].setdefault("install_file_id", None)
    data["settings"].setdefault("install_video_id", None)
    return data

def _load_local():
    """Local backup fayldan o'qish."""
    try:
        if os.path.exists(LOCAL_BACKUP):
            with open(LOCAL_BACKUP, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Local backup'dan yuklandi: {LOCAL_BACKUP}")
                return _merge_defaults(data)
    except Exception as e:
        logger.error(f"Local backup load xato: {e}")
    return None

def _save_local(data):
    """Local backup faylga yozish â€” atomic (tmp + rename)."""
    try:
        tmp = LOCAL_BACKUP + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, LOCAL_BACKUP)
        return True
    except Exception as e:
        logger.error(f"Local backup save xato: {e}")
        return False

def db_load():
    """Avval JSONBin'dan, agar xato bo'lsa local backup'dan yuklaydi."""
    # 1) JSONBin
    for attempt in range(3):
        try:
            r = requests.get(
                f"{JSONBIN_URL}/latest",
                headers={"X-Master-Key": JSONBIN_API_KEY},
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json().get("record", {})
                if not isinstance(data, dict):
                    data = {}
                data = _merge_defaults(data)
                # JSONBin'dan kelgan ma'lumotlarni darhol localga ham yozamiz
                _save_local(data)
                logger.info(
                    f"JSONBin'dan yuklandi: "
                    f"{len(data.get('users', {}))} user, "
                    f"{len(data.get('movies', {}))} kino, "
                    f"{data.get('stats', {}).get('total_views', 0)} ko'rishlar"
                )
                return data
            else:
                logger.warning(f"JSONBin GET status: {r.status_code} â€” {r.text[:200]}")
        except Exception as e:
            logger.error(f"DB load #{attempt+1}: {e}")
        if attempt < 2:
            time.sleep(2)

    # 2) JSONBin ishlamadi â€” local backup'ni sinaymiz
    local = _load_local()
    if local is not None:
        logger.warning("JSONBin ishlamadi, local backup ishlatilmoqda")
        return local

    logger.warning("Hech narsa topilmadi â€” bo'sh DB yaratilmoqda")
    return json.loads(json.dumps(DEFAULT_DB))

def db_save(data):
    """JSONBin + local backup. JSONBin xato bersa ham local saqlanadi."""
    # Avvalo HAR DOIM local backup â€” bu hech qachon ma'lumot yo'qolmasligini
    # kafolatlaydi (hostingda fayl tizimi mavjud bo'lsa).
    local_ok = _save_local(data)

    # JSONBin save â€” 5 marta retry
    jsonbin_ok = False
    for attempt in range(5):
        try:
            r = requests.put(
                JSONBIN_URL,
                headers={
                    "X-Master-Key": JSONBIN_API_KEY,
                    "Content-Type": "application/json",
                    "X-Bin-Versioning": "false",
                },
                data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
                timeout=20,
            )
            if r.status_code in (200, 201):
                logger.info(f"JSONBin saqlandi âœ“ (urinish #{attempt+1})")
                jsonbin_ok = True
                break
            else:
                logger.warning(f"JSONBin PUT status: {r.status_code} â€” {r.text[:200]}")
        except Exception as e:
            logger.error(f"JSONBin save #{attempt+1}: {e}")
        if attempt < 4:
            time.sleep(1.5)

    if not jsonbin_ok:
        logger.error("JSONBin saqlash muvaffaqiyatsiz â€” lekin local backup mavjud")

    return jsonbin_ok or local_ok

# â”€â”€ Boshlang'ich yuklash â”€â”€
DB = db_load()

# â”€â”€ Async-safe save (lock) â”€â”€
_save_lock = asyncio.Lock()

def save():
    """Sinxron save â€” har joyda qisqa chaqirish uchun."""
    return db_save(DB)

async def asave():
    """Async-safe save â€” bir vaqtda parallel saqlanmaslik uchun."""
    async with _save_lock:
        # JSONBin sekin bo'lishi mumkin â€” uni alohida threadda chaqirsak yaxshi,
        # lekin oddiyroq ishlash uchun shu yerda sinxron qoldiramiz.
        return db_save(DB)

def bt(key):
    """Tugma matnini qaytaradi (saqlangan yoki default)"""
    return DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")

def get_eid(key):
    """Tugma uchun saqlangan custom emoji ID ni qaytaradi"""
    return DB.get("btn_emoji_ids", {}).get(key)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# EMOJI YORDAMCHILAR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

EMOJI_RE = re.compile(
    r'[\U0001F000-\U0001FFFF'
    r'\U00002600-\U000027BF'
    r'\U0000FE00-\U0000FE0F'
    r'\U00020000-\U0002FA1F'
    r'\u200d'
    r'\ufe0f'
    r']+'
)

def is_only_emoji(text: str) -> bool:
    if not text:
        return False
    cleaned = EMOJI_RE.sub('', text).strip()
    return len(cleaned) == 0 and len(text.strip()) > 0

def strip_emoji_prefix(text: str) -> str:
    if not text:
        return ""
    result = re.sub(
        r'^(?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+',
        '', text
    ).strip()
    return result

def extract_custom_emoji_id(message):
    if not message or not getattr(message, "entities", None):
        return None
    for entity in message.entities:
        if entity.type == "custom_emoji":
            return getattr(entity, "custom_emoji_id", None)
    return None

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TUGMA YARATISH
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# KLAVIATURALAR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
        [rbtn(bt("asosiy"),     style="success", emoji_id=get_eid("asosiy"))],
    ])

def subscription_kb(channels):
    rows = [[ibtn(c['title'], url=c["url"], style="primary")] for c in channels]
    rows.append([ibtn(bt("tekshir"), data="check_sub", style="success", emoji_id=get_eid("tekshir"))])
    return ikb(rows)

def movie_episodes_kb(movie, code, user_id):
    eps = movie.get("episodes", [])
    prices = movie.get("prices", {})
    paid = DB["users"].get(str(user_id), {}).get("paid_episodes", {})
    rows = []
    for i in range(len(eps)):
        ek = str(i + 1)
        price = prices.get(ek)
        locked = price and not paid.get(f"{code}_{ek}")
        if locked:
            rows.append([ibtn(f"{ek}-qism  {price} so'm", data=f"ep|{code}|{ek}", style="danger")])
        else:
            rows.append([ibtn(f"{ek}-qism", data=f"ep|{code}|{ek}", style="success")])
    return ikb(rows)

def payment_admin_kb(pid):
    return ikb([[
        ibtn(bt("tasdiq"), data=f"pay_ok|{pid}", style="success", emoji_id=get_eid("tasdiq")),
        ibtn(bt("bekor"),  data=f"pay_no|{pid}", style="danger",  emoji_id=get_eid("bekor")),
    ]])

def share_kb(url):
    return ikb([[ibtn(bt("ulash"), url=url, style="primary", emoji_id=get_eid("ulash"))]])

def channel_post_kb(bot_username, code):
    return ikb([[ibtn(bt("tomosha"),
        url=f"https://t.me/{bot_username}?start=code_{code}",
        style="success", emoji_id=get_eid("tomosha"))]])

def reply_admin_kb(uid):
    return ikb([[ibtn(bt("javob"), data=f"reply|{uid}", style="primary", emoji_id=get_eid("javob"))]])

def stats_kb():
    return ikb([[ibtn(bt("yangi"), data="refresh_stats", style="primary", emoji_id=get_eid("yangi"))]])

def movie_added_kb(code):
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
            eid = get_eid(key)
            label = BTN_LABELS.get(key, key)
            row.append(rbtn(label, style="primary", emoji_id=eid))
        rows.append(row)
    rows.append([rbtn("ðŸ—‘ Hammasini tiklash", style="danger")])
    rows.append([rbtn("â¬…ï¸ Orqaga",            style="success")])
    return rkb(rows)

def emoji_single_action_kb(key):
    return ikb([
        [ibtn("ðŸ—‘ Defaultga qaytarish", data=f"emoji_reset|{key}", style="danger")],
        [ibtn("â¬…ï¸ Orqaga",              data="emoji_back",          style="success")],
    ])

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# XABAR YUBORISH HELPER'LARI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def sm(bot, chat_id, text, markup=None, pm="HTML"):
    kw = {"chat_id": chat_id, "text": text, "parse_mode": pm}
    if markup: kw["reply_markup"] = markup
    return await bot.send_message(**kw)

async def sp(bot, chat_id, photo, caption, markup=None, pm="HTML"):
    kw = {"chat_id": chat_id, "photo": photo, "caption": caption, "parse_mode": pm}
    if markup: kw["reply_markup"] = markup
    return await bot.send_photo(**kw)

async def sv(bot, chat_id, video, caption, markup=None, pm="HTML"):
    kw = {"chat_id": chat_id, "video": video, "caption": caption, "parse_mode": pm}
    if markup: kw["reply_markup"] = markup
    return await bot.send_video(**kw)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# YORDAMCHI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def check_subscription(user_id, bot):
    not_subbed = []
    for ch in DB.get("channels", []):
        try:
            member = await bot.get_chat_member(ch["username"], user_id)
            if member.status in ("left", "kicked"):
                not_subbed.append(ch)
        except Exception as e:
            logger.warning(f"Sub check {ch}: {e}")
            not_subbed.append(ch)
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
        save()

async def send_movie_menu(src, context, code):
    movie = DB["movies"].get(code)
    chat_id = src.effective_user.id if hasattr(src, "effective_user") else src.from_user.id
    user_id = chat_id
    if not movie:
        await sm(context.bot, chat_id, "Bunday kodli kino topilmadi.")
        return
    eps = movie.get("episodes", [])
    if not eps:
        await sm(context.bot, chat_id, "Bu kinoga hali qism yuklanmagan.")
        return
    markup = movie_episodes_kb(movie, code, user_id)
    caption = (f"<b>{movie.get('title', 'Kino')}</b>\n"
               f"Qismlar soni: <b>{len(eps)}</b>\n\nQaysi qismni ko'rmoqchisiz?")
    poster = movie.get("poster_file_id")
    try:
        if poster:
            await sp(context.bot, chat_id, poster, caption, markup)
        else:
            await sm(context.bot, chat_id, caption, markup)
    except Exception as e:
        logger.error(f"send_movie_menu: {e}")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# /start
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    args = context.args

    if args and args[0].startswith("code_"):
        code = args[0].replace("code_", "")
        ns = await check_subscription(user.id, context.bot)
        if ns:
            await sm(context.bot, user.id,
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                subscription_kb(ns))
            context.user_data["pending_code"] = code
            return
        await send_movie_menu(update, context, code)
        return

    ns = await check_subscription(user.id, context.bot)
    if ns:
        await sm(context.bot, user.id,
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            subscription_kb(ns))
        return

    hello = (f"Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
             f"<b>Kino botga xush kelibsiz!</b>\n\n"
             f"Kino <b>raqamini</b> yuboring â€” video darhol chiqadi.")
    is_admin = (user.id == ADMIN_ID)
    await sm(context.bot, user.id, hello, main_menu_kb(is_admin=is_admin))

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CALLBACK'LAR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def cb_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    await q.answer()

    if data == "emoji_back":
        context.user_data.pop("editing_btn_key", None)
        try:
            await q.edit_message_text("Tugmani pastdan tanlang ðŸ‘‡")
        except Exception:
            pass
        # FIX: oldin parse_mode=... noto'g'ri parametr nomi edi
        await sm(context.bot, uid,
            "<b>Tugma sozlamalari</b>\nO'zgartirmoqchi bo'lgan tugmani tanlang:",
            emoji_menu_kb())
        return

    if data == "emoji_reset_all":
        DB["btn_texts"] = {}
        DB["btn_emoji_ids"] = {}
        save()
        try:
            await q.edit_message_text("âœ… Barcha tugmalar tiklandi!")
        except Exception:
            pass
        await sm(context.bot, uid, "âœ… Tiklandi! Tugmani tanlang:", emoji_menu_kb())
        return

    if data.startswith("emoji_reset|"):
        key = data.split("|", 1)[1]
        DB.setdefault("btn_texts", {}).pop(key, None)
        DB.setdefault("btn_emoji_ids", {}).pop(key, None)
        save()
        default = DEFAULT_BTN.get(key, "")
        context.user_data.pop("editing_btn_key", None)
        try:
            await q.edit_message_text(
                f"âœ… <b>{BTN_LABELS.get(key, key)}</b> tiklandi!\n"
                f"Default: <code>{default}</code>",
                parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return


async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ns = await check_subscription(q.from_user.id, context.bot)
    if ns:
        await q.answer("Hali obuna bo'lmagansiz!", show_alert=True)
        return
    try:
        await q.edit_message_text("Barcha kanallarga obuna bo'ldingiz!")
    except Exception:
        pass
    pending = context.user_data.pop("pending_code", None)
    if pending:
        await send_movie_menu(q, context, pending)
    else:
        await sm(context.bot, q.from_user.id,
            f"Xush kelibsiz, <b>{q.from_user.full_name}</b>!\nKino raqamini yuboring.",
            main_menu_kb(is_admin=(q.from_user.id == ADMIN_ID)))


async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    if len(parts) != 3:
        await q.answer("Xato", show_alert=True)
        return
    _, code, ep = parts
    movie = DB["movies"].get(code)
    if not movie:
        await q.answer("Kino topilmadi", show_alert=True)
        return
    user_id = str(q.from_user.id)
    price = movie.get("prices", {}).get(ep)
    paid = DB["users"].get(user_id, {}).get("paid_episodes", {})
    if price and not paid.get(f"{code}_{ep}"):
        card = DB.get("card_number") or "Admin karta raqamini o'rnatmagan"
        txt = (f"<b>Bu qism pullik</b>\n\nKino: <b>{movie.get('title')}</b>\n"
               f"Qism: <b>{ep}</b>\nNarxi: <b>{price} so'm</b>\n\n"
               f"Karta raqami:\n<code>{card}</code>\n\n"
               f"To'lov qiling va chek rasmini yuboring")
        context.user_data["awaiting_check"] = {"code": code, "ep": ep, "price": price}
        await sm(context.bot, q.from_user.id, txt, payment_sent_kb())
        return

    idx = int(ep) - 1
    eps = movie.get("episodes", [])
    if idx < 0 or idx >= len(eps):
        await q.answer("Qism topilmadi", show_alert=True)
        return

    movie.setdefault("views", {})
    movie["views"][ep] = movie["views"].get(ep, 0) + 1
    DB["users"].setdefault(user_id, {}).setdefault("watched", {})[f"{code}_{ep}"] = True
    DB.setdefault("stats", {})
    DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
    save()  # Statistika va ko'rishlar darhol saqlanadi

    bot_me = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption = (f"<b>{movie.get('title')}</b>\n"
               f"Qism: <b>{ep}</b>\n"
               f"Ko'rishlar: <b>{movie['views'][ep]}</b>")
    await sv(context.bot, q.from_user.id, eps[idx], caption, share_kb(share_url))


async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action, pid = q.data.split("|", 1)
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
                (q.message.caption or "") + "\n\n<b>Bekor qilindi</b>",
                parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, pay["user_id"], "<b>To'lovingiz rad etildi.</b>")
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
            (q.message.caption or "") + "\n\n<b>Tasdiqlandi</b>",
            parse_mode="HTML")
    except Exception:
        pass
    await sm(context.bot, pay["user_id"],
        "<b>Admin to'lovingizni tasdiqladi!</b>\n1 daqiqa kuting...")

    async def send_later():
        await asyncio.sleep(60)
        movie = DB["movies"].get(pay["code"])
        if not movie:
            return
        idx = int(pay["ep"]) - 1
        eps = movie.get("episodes", [])
        if 0 <= idx < len(eps):
            movie.setdefault("views", {})
            movie["views"][pay["ep"]] = movie["views"].get(pay["ep"], 0) + 1
            DB["users"][uid].setdefault("watched", {})[f"{pay['code']}_{pay['ep']}"] = True
            DB.setdefault("stats", {})
            DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
            save()
            try:
                await sv(context.bot, pay["user_id"], eps[idx],
                    f"<b>{movie.get('title')}</b>\nQism: {pay['ep']}")
            except Exception as e:
                logger.error(f"send_later video: {e}")

    context.application.create_task(send_later())


async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, uid = q.data.split("|", 1)
    context.user_data["reply_to"] = int(uid)
    await q.message.reply_text(f"<code>{uid}</code> ga xabar yozing.", parse_mode="HTML")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    uid = update.callback_query.from_user.id

    if data == "check_sub":
        await cb_check_sub(update, context)
    elif data.startswith("ep|"):
        await cb_episode(update, context)
    elif data.startswith("pay_ok|") or data.startswith("pay_no|"):
        await cb_payment(update, context)
    elif data.startswith("reply|"):
        await cb_reply(update, context)
    elif data == "refresh_stats":
        if uid == ADMIN_ID:
            q = update.callback_query
            await q.answer("Yangilandi!")
            u = len(DB.get("users", {}))
            m = len(DB.get("movies", {}))
            v = DB.get("stats", {}).get("total_views", 0)
            try:
                await q.edit_message_text(
                    f"<b>Statistika</b>\n\n"
                    f"Foydalanuvchilar: <b>{u}</b>\n"
                    f"Kinolar: <b>{m}</b>\n"
                    f"Jami ko'rishlar: <b>{v}</b>",
                    parse_mode="HTML", reply_markup=stats_kb())
            except Exception:
                pass
    elif data == "go_home":
        q = update.callback_query
        await q.answer()
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Bosh menyu",
            main_menu_kb(is_admin=(uid == ADMIN_ID)))
    elif data == "waiting_confirm":
        await update.callback_query.answer(
            "Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)
    elif data.startswith("emoji_"):
        if uid == ADMIN_ID:
            await cb_emoji(update, context)
        else:
            await update.callback_query.answer("Ruxsat yo'q", show_alert=True)
    elif data.startswith("quick_add_ep|"):
        if uid == ADMIN_ID:
            code = data.split("|", 1)[1]
            context.user_data["admin_state"] = "add_ep_video"
            context.user_data["ep_movie_code"] = code
            await update.callback_query.answer()
            await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
    elif data.startswith("quick_price|"):
        if uid == ADMIN_ID:
            code = data.split("|", 1)[1]
            context.user_data["admin_state"] = "set_price_ep"
            context.user_data["price_movie_code"] = code
            await update.callback_query.answer()
            await sm(context.bot, uid, "Qism raqamini kiriting:")
    else:
        await update.callback_query.answer()

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TEXT HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = (update.message.text or "").strip()

    # â”€â”€ Emoji menyu rejimi (admin) â”€â”€
    if uid == ADMIN_ID and context.user_data.get("emoji_menu") and not context.user_data.get("editing_btn_key"):
        if text == "â¬…ï¸ Orqaga":
            context.user_data.pop("emoji_menu", None)
            await sm(context.bot, uid, "Admin panel", admin_menu_kb())
            return

        if text == "ðŸ—‘ Hammasini tiklash":
            DB["btn_texts"] = {}
            DB["btn_emoji_ids"] = {}
            save()
            await sm(context.bot, uid, "âœ… Barcha tugmalar tiklandi!", emoji_menu_kb())
            return

        key = LABEL_TO_KEY.get(text)
        if key:
            cur = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
            eid = get_eid(key)
            eid_info = f"\nCustom emoji ID: <code>{eid}</code>" if eid else ""
            context.user_data["editing_btn_key"] = key
            await sm(context.bot, uid,
                f"<b>{BTN_LABELS.get(key, key)}</b>\n\n"
                f"Hozirgi matn: <code>{cur}</code>{eid_info}\n\n"
                f"Yuboring:\n"
                f"â€¢ Faqat emoji â†’ prefiks qo'yiladi\n"
                f"â€¢ Emoji + matn â†’ to'liq yangilanadi\n"
                f"â€¢ Custom emoji â†’ icon sifatida\n"
                f"â€¢ Faqat matn â†’ emoji o'chadi",
                emoji_single_action_kb(key))
            return
        return

    # â”€â”€ Admin tugma matni/emoji o'zgartirish rejimi â”€â”€
    if uid == ADMIN_ID and context.user_data.get("editing_btn_key"):
        key = context.user_data.pop("editing_btn_key")

        if not text:
            await sm(context.bot, uid, "Bo'sh bo'lmasin. Qayta yuboring:")
            context.user_data["editing_btn_key"] = key
            return

        custom_emoji_id = extract_custom_emoji_id(update.message)
        existing = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
        label = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")

        if custom_emoji_id:
            new_text = label
            DB.setdefault("btn_emoji_ids", {})[key] = custom_emoji_id
        elif is_only_emoji(text):
            new_text = f"{text} {label}"
            DB.setdefault("btn_emoji_ids", {}).pop(key, None)
        else:
            new_text = text
            DB.setdefault("btn_emoji_ids", {}).pop(key, None)

        DB.setdefault("btn_texts", {})[key] = new_text
        save()

        eid = get_eid(key)
        eid_info = f"\nCustom emoji ID: <code>{eid}</code>" if eid else ""
        await sm(context.bot, uid,
            f"âœ… <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n"
            f"Ko'rinish: <code>{new_text}</code>{eid_info}")
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    # â”€â”€ Admin tugmalarini aniqlash â”€â”€
    all_admin_btns = {bt(k) for k in [
        "kino_joy", "qism_qosh", "pullik", "stat",
        "kanal_post", "maj_kanal", "karta", "ilova",
        "emoji_soz", "asosiy", "boshqarish"
    ]}

    if uid == ADMIN_ID and text in all_admin_btns:
        if text == bt("emoji_soz"):
            context.user_data["emoji_menu"] = True
            context.user_data.pop("editing_btn_key", None)
            await sm(context.bot, uid,
                "<b>Tugma sozlamalari</b>\n"
                "O'zgartirmoqchi bo'lgan tugmani pastdan tanlang ðŸ‘‡",
                emoji_menu_kb())
            return
        await admin_buttons(update, context, text)
        return

    if text == bt("yordam"):
        await sm(context.bot, uid,
            "Savol yoki muammoingizni matn, rasm yoki video ko'rinishida yuboring.\n"
            "Admin tez orada javob beradi.", help_kb())
        context.user_data["awaiting_help"] = True
        return

    if text == bt("install"):
        s = DB.get("settings", {})
        f_id = s.get("install_file_id")
        v_id = s.get("install_video_id")
        if not f_id and not v_id:
            await sm(context.bot, uid, "Admin hali ilova fayl/video joylamagan.")
            return
        if v_id:
            await sv(context.bot, uid, v_id, "<b>Ilovani o'rnatish videosi</b>")
        if f_id:
            await context.bot.send_document(
                uid, f_id, caption="<b>Ilova fayli</b>", parse_mode="HTML")
        return

    if uid == ADMIN_ID and await admin_state_handler(update, context, text):
        return

    if context.user_data.pop("awaiting_help", False):
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        await sm(context.bot, ADMIN_ID, cap + text, reply_admin_kb(uid))
        await sm(context.bot, uid, "Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"Xato: {e}")
        return

    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos chek rasmini yuboring.")
        return

    code = text.upper().strip()
    if code in DB["movies"]:
        ns = await check_subscription(uid, context.bot)
        if ns:
            await sm(context.bot, uid,
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                subscription_kb(ns))
            context.user_data["pending_code"] = code
            return
        await send_movie_menu(update, context, code)
    else:
        await sm(context.bot, uid, "Kino raqami topilmadi.\nTo'g'ri raqamni yuboring.")


async def admin_buttons(update, context, text):
    uid = update.effective_user.id
    if text == bt("boshqarish"):
        await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb())
        return
    if text == bt("asosiy"):
        await sm(context.bot, uid, "Asosiy menyu", main_menu_kb(is_admin=True))
        return
    if text == bt("stat"):
        u = len(DB.get("users", {}))
        m = len(DB.get("movies", {}))
        v = DB.get("stats", {}).get("total_views", 0)
        await sm(context.bot, uid,
            f"<b>Statistika</b>\n\n"
            f"Foydalanuvchilar: <b>{u}</b>\n"
            f"Kinolar: <b>{m}</b>\n"
            f"Jami ko'rishlar: <b>{v}</b>", stats_kb())
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
        await sm(context.bot, uid, "Kino kodini kiriting:")
        return
    if text == bt("ilova"):
        context.user_data["admin_state"] = "set_install"
        await sm(context.bot, uid, "Ilova fayl yoki video yuboring:")
        return
    if text == bt("maj_kanal"):
        context.user_data["admin_state"] = "add_channel"
        await sm(context.bot, uid,
            "Kanal username va nomi yuboring:\n"
            "<code>@username | Kanal nomi | https://t.me/username</code>")
        return
    if text == bt("kanal_post"):
        context.user_data["admin_state"] = "post_channel_code"
        await sm(context.bot, uid, "Post qilmoqchi bo'lgan kino kodini kiriting:")
        return


async def admin_state_handler(update, context, text):
    state = context.user_data.get("admin_state")
    uid = update.effective_user.id
    if not state:
        return False

    if state == "set_card":
        DB["card_number"] = text
        save()
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, f"Karta saqlandi: <code>{text}</code>")
        return True

    if state == "add_movie_code":
        context.user_data["new_movie_code"] = text.upper()
        context.user_data["admin_state"] = "add_movie_title"
        await sm(context.bot, uid, "Kino nomini kiriting:")
        return True

    if state == "add_movie_title":
        code = context.user_data.get("new_movie_code")
        DB["movies"][code] = {"title": text, "episodes": [], "prices": {}}
        save()  # Kino darhol JSONBin va localga saqlanadi
        context.user_data.pop("admin_state")
        context.user_data.pop("new_movie_code", None)
        await sm(context.bot, uid,
            f"<b>{text}</b> kinosi qo'shildi!\nKod: <code>{code}</code>",
            movie_added_kb(code))
        return True

    if state == "add_ep_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["ep_movie_code"] = code
        context.user_data["admin_state"] = "add_ep_video"
        await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        return True

    if state == "set_price_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"] = "set_price_ep"
        await sm(context.bot, uid, "Qism raqamini kiriting:")
        return True

    if state == "set_price_ep":
        context.user_data["price_ep"] = text
        context.user_data["admin_state"] = "set_price_amount"
        await sm(context.bot, uid, "Narxini kiriting (so'mda):")
        return True

    if state == "set_price_amount":
        code = context.user_data.get("price_movie_code")
        ep = context.user_data.get("price_ep")
        if code and code in DB["movies"]:
            DB["movies"][code].setdefault("prices", {})[ep] = text
            save()
            await sm(context.bot, uid, f"{code} â€” {ep}-qism narxi: {text} so'm")
        else:
            await sm(context.bot, uid, "Kino topilmadi.")
        context.user_data.pop("admin_state", None)
        return True

    if state == "add_channel":
        try:
            parts = [p.strip() for p in text.split("|")]
            uname, title, url = parts[0], parts[1], parts[2]
            DB["channels"].append({"username": uname, "title": title, "url": url})
            save()
            await sm(context.bot, uid, f"Kanal qo'shildi: {title}")
        except Exception:
            await sm(context.bot, uid, "Format xato. Qayta urinib ko'ring.")
        context.user_data.pop("admin_state")
        return True

    if state == "post_channel_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["post_code"] = code
        context.user_data["admin_state"] = "post_channel_target"
        await sm(context.bot, uid, "Kanal username ni kiriting (masalan @mychannel):")
        return True

    if state == "post_channel_target":
        channel = text
        code = context.user_data.get("post_code")
        movie = DB["movies"].get(code, {})
        bot_me = await context.bot.get_me()
        markup = channel_post_kb(bot_me.username, code)
        caption = (f"<b>{movie.get('title', code)}</b>\n\n"
                   f"Qismlar soni: <b>{len(movie.get('episodes', []))}</b>\n\n"
                   f"Tomosha qilish uchun tugmani bosing!")
        poster = movie.get("poster_file_id")
        try:
            if poster:
                await sp(context.bot, channel, poster, caption, markup)
            else:
                await sm(context.bot, channel, caption, markup)
            await sm(context.bot, uid, "Post yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"Xato: {e}")
        context.user_data.pop("admin_state")
        return True

    if state == "set_install":
        # Bu state media kutadi â€” matn kelsa eslatamiz
        await sm(context.bot, uid, "Iltimos fayl yoki video yuboring (matn emas).")
        return True

    return False

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STICKER HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
    existing = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
    label = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
    new_text = f"{emoji} {label}"
    DB.setdefault("btn_texts", {})[key] = new_text
    DB.setdefault("btn_emoji_ids", {}).pop(key, None)
    save()
    await sm(context.bot, uid,
        f"âœ… <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n\n"
        f"Ko'rinish: <code>{new_text}</code>")
    await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MEDIA HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    msg = update.message
    state = context.user_data.get("admin_state")

    if uid == ADMIN_ID and state == "add_ep_video":
        code = context.user_data.get("ep_movie_code")
        if msg.video and code and code in DB["movies"]:
            DB["movies"][code].setdefault("episodes", []).append(msg.video.file_id)
            save()  # Qism darhol JSONBin va localga saqlanadi
            ep_num = len(DB["movies"][code]["episodes"])
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, f"âœ… {ep_num}-qism saqlandi!")
        return

    if uid == ADMIN_ID and state == "set_install":
        if msg.video:
            DB.setdefault("settings", {})["install_video_id"] = msg.video.file_id
            save()
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "âœ… O'rnatish videosi saqlandi!")
        elif msg.document:
            DB.setdefault("settings", {})["install_file_id"] = msg.document.file_id
            save()
            context.user_data.pop("admin_state", None)
            await sm(context.bot, uid, "âœ… O'rnatish fayli saqlandi!")
        return

    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info = context.user_data.pop("awaiting_check")
        pid = f"{uid}_{pay_info['code']}_{pay_info['ep']}_{int(time.time())}"
        DB["pending_payments"][pid] = {
            "user_id": uid, "code": pay_info["code"],
            "ep": pay_info["ep"], "price": pay_info["price"],
            "status": "pending",
        }
        save()
        cap = (f"<b>To'lov cheki</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\nKino: <b>{pay_info['code']}</b>\n"
               f"Qism: <b>{pay_info['ep']}</b>\nNarx: <b>{pay_info['price']} so'm</b>")
        await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, payment_admin_kb(pid))
        await sm(context.bot, uid, "Chek adminga yuborildi! Tasdiqlanishini kuting.")
        return

    if context.user_data.pop("awaiting_help", False):
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        if msg.photo:
            await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, reply_admin_kb(uid))
        elif msg.video:
            await sv(context.bot, ADMIN_ID, msg.video.file_id, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            if msg.photo:
                await sp(context.bot, target, msg.photo[-1].file_id, "<b>Admin javobi</b>")
            elif msg.video:
                await sv(context.bot, target, msg.video.file_id, "<b>Admin javobi</b>")
            await sm(context.bot, uid, "Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"Xato: {e}")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))
    logger.info("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
