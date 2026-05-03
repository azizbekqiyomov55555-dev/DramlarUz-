# -*- coding: utf-8 -*-
"""
Kino Bot - v10
TUZATISHLAR (v9):
1. Majburiy kanal to'liq ishlaydi:
   - Kanal qo'shish (format tekshiriladi)
   - Kanal o'chirish (ro'yxatdan tanlash)
   - Kanallar ro'yxatini ko'rish
2. admin_buttons da maj_kanal uchun submenu qo'shildi
AVVALGI (v8):
3. Pullik qilish to'liq ishlaydi
4. Qismlar sahifalar bo'yicha ko'rsatiladi
5. Broadcast, emoji sozlamalari
"""
import logging, asyncio, json, time, re, os, threading, copy
from datetime import datetime
import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

BOT_TOKEN       = "8723400610:AAHgNzcIGvyIWfJZBAwCAyT_0X41Utr9prY"
ADMIN_ID        = 8537782289
GIST_TOKEN    = "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"
GIST_ID       = "50f61ab4f6ac4d70ba44e2e300102ff7"
GIST_FILENAME = "db.json"
GIST_URL      = f"https://api.github.com/gists/{GIST_ID}"
GIST_HEADERS  = {
    "Authorization": f"Bearer {GIST_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Lokal backup fayl — JSONBin ishlamasa ham ma'lumot saqlanadi
LOCAL_BACKUP_FILE = "db_backup.json"

# Saqlash uchun lock (parallel yozishlardan himoya)
_save_lock = threading.Lock()
_load_ok = False  # JSONBin'dan muvaffaqiyatli yuklanganmi?

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
    "boshqarish":   "⚙️ Boshqarish",
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
    "broadcast":    "📢 Barchaga xabar",
    "kino_uch":     "🗑 Kino o'chirish",
    "prev_qism":    "Oldingi qismlar",
    "next_qism":    "Boshqa qismlar",
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
    "boshqarish":   "⚙️ Boshqarish",
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
    "broadcast":    "Barchaga xabar",
    "kino_uch":     "Kino o'chirish",
    "prev_qism":    "Oldingi qismlar tugmasi",
    "next_qism":    "Boshqa qismlar tugmasi",
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

# ══════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════

def db_load():
    global _load_ok
    for attempt in range(3):
        try:
            r = requests.get(GIST_URL, headers=GIST_HEADERS, timeout=20)
            if r.status_code == 200:
                files = r.json().get("files", {})
                f_obj = files.get(GIST_FILENAME) or (next(iter(files.values())) if files else None)
                content = (f_obj or {}).get("content", "").strip() or "{}"
                try:
                    data = json.loads(content)
                except Exception:
                    data = {}
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
                EMOJI_IDS.clear()
                EMOJI_IDS.update(data.get("emoji_ids", {}))
                # Lokal backupga ham yozib qo'yamiz
                try:
                    with open(LOCAL_BACKUP_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                except Exception as e:
                    logger.error(f"Backup yozishda xato: {e}")
                _load_ok = True
                logger.info(f"Yuklandi: {len(data.get('users', {}))} user, "
                            f"{len(data.get('movies', {}))} kino, "
                            f"{len(EMOJI_IDS)} emoji")
                return data
        except Exception as e:
            logger.error(f"DB load #{attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2)
    # JSONBin ishlamadi — lokal backupdan yuklashga harakat qilamiz
    if os.path.exists(LOCAL_BACKUP_FILE):
        try:
            with open(LOCAL_BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, dv in DEFAULT_DB.items():
                if k not in data:
                    data[k] = json.loads(json.dumps(dv))
            EMOJI_IDS.clear()
            EMOJI_IDS.update(data.get("emoji_ids", {}))
            logger.warning("⚠️ Gist ishlamadi — LOKAL BACKUPDAN yuklandi!")
            _load_ok = True  # Backup ham haqiqiy ma'lumot
            return data
        except Exception as e:
            logger.error(f"Lokal backup yuklashda xato: {e}")
    # Hech qaerdan yuklab bo'lmadi — _load_ok = False qoladi
    # Bu holatda save() ishlamaydi (ma'lumot yo'qolmasligi uchun)
    logger.error("❌ DB yuklab bo'lmadi! Saqlash bloklandi.")
    return json.loads(json.dumps(DEFAULT_DB))


async def db_save_async(data):
    """Async saqlash — JSONBin + lokal backup."""
    if not _load_ok:
        logger.error("⛔ DB yuklanmagan — saqlash bloklandi (ma'lumot yo'qolmasin)")
        return False
    data["emoji_ids"] = dict(EMOJI_IDS)
    payload = json.dumps(data, ensure_ascii=False)
    # 1) Lokal backupga DARHOL yozamiz (eng ishonchli)
    try:
        tmp = LOCAL_BACKUP_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, LOCAL_BACKUP_FILE)
    except Exception as e:
        logger.error(f"Lokal backup yozishda xato: {e}")
    # 2) Gist'ga yuboramiz
    headers = {**GIST_HEADERS, "Content-Type": "application/json"}
    body = json.dumps({"files": {GIST_FILENAME: {"content": payload}}}, ensure_ascii=False)
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    GIST_URL, data=body, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        logger.info("DB saqlandi ✓ (Gist + backup)")
                        return True
                    else:
                        txt = await resp.text()
                        logger.error(f"Gist status {resp.status}: {txt[:200]}")
        except Exception as e:
            logger.error(f"DB async save #{attempt+1}: {e}")
        if attempt < 2:
            await asyncio.sleep(2)
    logger.warning("⚠️ Gist'ga saqlanmadi, ammo lokal backup mavjud")
    return False


def db_save(data):
    """Sinxron saqlash — JSONBin + lokal backup."""
    if not _load_ok:
        logger.error("⛔ DB yuklanmagan — saqlash bloklandi")
        return False
    with _save_lock:
        data["emoji_ids"] = dict(EMOJI_IDS)
        payload = json.dumps(data, ensure_ascii=False)
        # 1) Lokal backup
        try:
            tmp = LOCAL_BACKUP_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp, LOCAL_BACKUP_FILE)
        except Exception as e:
            logger.error(f"Lokal backup yozishda xato: {e}")
        # 2) Gist
        body = json.dumps({"files": {GIST_FILENAME: {"content": payload}}}, ensure_ascii=False)
        for attempt in range(3):
            try:
                r = requests.patch(GIST_URL,
                    headers={**GIST_HEADERS, "Content-Type": "application/json"},
                    data=body, timeout=30)
                if r.status_code == 200:
                    logger.info("DB saqlandi ✓ (sync Gist)")
                    return True
                else:
                    logger.error(f"Gist status {r.status_code}: {r.text[:200]}")
            except Exception as e:
                logger.error(f"DB save #{attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2)
        return False


DB = db_load()


def save():
    """Asosiy saqlash funksiyasi — har doim chaqirsa bo'ladi."""
    try:
        loop = asyncio.get_running_loop()
        # Event loop ishlayapti — task yaratamiz, lekin uni TRACK qilamiz
        task = loop.create_task(db_save_async(DB))
        # Xatolarni log'ga chiqarish uchun
        def _done(t):
            try:
                t.result()
            except Exception as e:
                logger.error(f"save() task xato: {e}")
        task.add_done_callback(_done)
    except RuntimeError:
        # Event loop yo'q — sinxron saqlaymiz
        db_save(DB)


def save_sync():
    db_save(DB)


def bt(key):
    return DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")


def get_eid(key):
    return EMOJI_IDS.get(key)

# ══════════════════════════════════════════════════════════
# EMOJI
# ══════════════════════════════════════════════════════════

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
    cleaned = EMOJI_RE.sub('', text).strip()
    return len(cleaned) == 0 and len(text.strip()) > 0


def extract_emoji_prefix(text: str) -> str:
    match = re.match(
        r'^((?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+)',
        text
    )
    return match.group(1).rstrip() if match else ""


def strip_emoji_prefix(text: str) -> str:
    result = re.sub(
        r'^(?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+',
        '', text
    ).strip()
    return result


def extract_custom_emoji_id(message) -> str | None:
    if not message.entities:
        return None
    for entity in message.entities:
        if entity.type == "custom_emoji":
            return entity.custom_emoji_id
    return None


def find_key_by_text(text: str) -> str | None:
    if text in LABEL_TO_KEY:
        return LABEL_TO_KEY[text]
    for key in BTN_LABELS:
        current = bt(key)
        if current == text:
            return key
        if strip_emoji_prefix(current) == strip_emoji_prefix(text) and strip_emoji_prefix(text):
            return key
    return None

# ══════════════════════════════════════════════════════════
# TUGMA YARATISH
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


# ══════════════════════════════════════════════════════════
# MAJBURIY KANAL KLAVIATURALARI (YANGI)
# ══════════════════════════════════════════════════════════

def channel_manage_kb():
    """Majburiy kanal boshqarish submenu klaviaturasi"""
    return rkb([
        [rbtn("➕ Kanal qo'shish",  style="success"),
         rbtn("🗑 Kanal o'chirish",  style="danger")],
        [rbtn("📋 Kanallar ro'yxati", style="primary")],
        [rbtn("⬅️ Admin panel",       style="success")],
    ])


def channel_delete_inline_kb(channels):
    """O'chirish uchun inline tugmalar ro'yxati"""
    rows = []
    for i, ch in enumerate(channels):
        rows.append([ibtn(
            f"🗑 {ch['title']} ({ch['username']})",
            data=f"ch_del|{i}",
            style="danger"
        )])
    rows.append([ibtn("❌ Bekor", data="ch_del_cancel", style="primary")])
    return ikb(rows)


def subscription_kb(channels):
    rows = [[ibtn(c['title'], url=c["url"], style="primary")] for c in channels]
    rows.append([ibtn(bt("tekshir"), data="check_sub", style="success", emoji_id=get_eid("tekshir"))])
    return ikb(rows)


PAGE_SIZE = 5


def movie_episodes_kb(movie, code, user_id, page: int = 0):
    eps = movie.get("episodes", [])
    prices = movie.get("prices", {})
    paid = DB["users"].get(str(user_id), {}).get("paid_episodes", {})
    total = len(eps)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    end   = min(start + PAGE_SIZE, total)

    rows = []
    for i in range(start, end):
        ek = str(i + 1)
        price = prices.get(ek)
        locked = price and not paid.get(f"{code}_{ek}")
        if locked:
            rows.append([ibtn(f"{ek}-qism  💰 {price} so'm",
                              data=f"ep|{code}|{ek}", style="danger")])
        else:
            rows.append([ibtn(f"{ek}-qism",
                              data=f"ep|{code}|{ek}", style="success")])

    nav = []
    if page > 0:
        nav.append(ibtn(bt("prev_qism"),
                        data=f"page|{code}|{page - 1}",
                        style="primary",
                        emoji_id=get_eid("prev_qism")))
    if page < total_pages - 1:
        nav.append(ibtn(bt("next_qism"),
                        data=f"page|{code}|{page + 1}",
                        style="primary",
                        emoji_id=get_eid("next_qism")))
    if nav:
        rows.append(nav)

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
        url=f"https://t.me/{bot_username}?start=code_{code}", style="success",
        emoji_id=get_eid("tomosha"))]])


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
    rows.append([rbtn("🗑 Hammasini tiklash", style="danger")])
    rows.append([rbtn("⬅️ Orqaga",            style="success")])
    return rkb(rows)


def emoji_single_action_kb(key):
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
    rows = []
    rows.append([ibtn("➕ Tugma qo'shish", data="bc_add_btn", style="primary")])
    if has_btn:
        rows.append([ibtn("🗑 Tugmani o'chirish", data="bc_remove_btn", style="danger")])
    rows.append([
        ibtn("✅ Yuborish", data="bc_send",   style="success"),
        ibtn("❌ Bekor",    data="bc_cancel", style="danger"),
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
# YORDAMCHI
# ══════════════════════════════════════════════════════════

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
            "name": user.full_name, "username": user.username or "",
            "joined": datetime.now().isoformat(), "paid_episodes": {}, "watched": {}
        }
        save()


async def send_movie_menu(src, context, code):
    movie = DB["movies"].get(code)
    chat_id = src.effective_user.id if hasattr(src, "effective_user") else src.from_user.id
    user_id = chat_id
    if not movie:
        await sm(context.bot, chat_id, "❌ Bunday kodli kino topilmadi.")
        return
    eps = movie.get("episodes", [])
    if not eps:
        await sm(context.bot, chat_id, "⏳ Bu kinoga hali qism yuklanmagan.")
        return
    markup = movie_episodes_kb(movie, code, user_id, page=0)
    total_pages = max(1, (len(eps) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_info = f"  (1/{total_pages} sahifa)" if total_pages > 1 else ""
    caption = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
               f"📺 Qismlar soni: <b>{len(eps)} ta</b>{page_info}\n\n"
               f"👇 Qaysi qismni ko'rmoqchisiz?")
    poster = movie.get("poster_file_id")
    try:
        if poster:
            await sp(context.bot, chat_id, poster, caption, markup)
        else:
            await sm(context.bot, chat_id, caption, markup)
    except Exception as e:
        logger.error(f"send_movie_menu: {e}")


def clear_admin_state(context):
    for key in ["admin_state", "new_movie_code", "ep_movie_code",
                "price_movie_code", "price_ep", "post_code",
                "reply_to", "awaiting_help", "awaiting_check",
                "editing_btn_key", "emoji_menu",
                "bc_msg", "bc_buttons", "bc_adding_btn",
                "del_movie_code", "poster_code",
                "channel_manage_menu"]:
        context.user_data.pop(key, None)


def _build_ep_price_list(code: str, eps: list, prices: dict) -> str:
    if not eps:
        return "⚠️ Bu kinoda hali qism yo'q."
    lines = []
    for i, _ in enumerate(eps):
        ek = str(i + 1)
        price = prices.get(ek)
        if price:
            lines.append(f"  {ek}-qism — 💰 <b>{price} so'm</b>")
        else:
            lines.append(f"  {ek}-qism — bepul")
    return f"📺 Qismlar ({len(eps)} ta):\n" + "\n".join(lines)


def _channels_list_text() -> str:
    """Kanallar ro'yxatini matn ko'rinishida chiqaradi."""
    channels = DB.get("channels", [])
    if not channels:
        return "📭 Hozircha majburiy kanal yo'q."
    lines = []
    for i, ch in enumerate(channels, 1):
        lines.append(f"  {i}. <b>{ch['title']}</b> — {ch['username']}")
    return f"📋 <b>Majburiy kanallar</b> ({len(channels)} ta):\n\n" + "\n".join(lines)

# ══════════════════════════════════════════════════════════
# BROADCAST
# ══════════════════════════════════════════════════════════

def build_broadcast_markup(buttons: list):
    if not buttons:
        return None
    rows = []
    for b in buttons:
        btn_style = b.get("style", "primary")
        rows.append([ibtn(b["text"], url=b["url"], style=btn_style)])
    return ikb(rows)


async def send_broadcast_preview(bot, uid, bc: dict):
    buttons = bc.get("buttons", [])
    markup = build_broadcast_markup(buttons)
    preview_kb = broadcast_preview_kb(bool(buttons))
    try:
        kw = {}
        if markup:
            kw["reply_markup"] = markup
        await bot.copy_message(
            chat_id=uid,
            from_chat_id=bc["from_chat_id"],
            message_id=bc["message_id"],
            **kw
        )
    except Exception as e:
        await bot.send_message(uid, f"❌ Preview xato: {e}")
        return

    btn_info = ""
    if buttons:
        btn_info = "\n\n<b>Tugmalar:</b>\n" + "\n".join(
            f"• {b['text']} → {b['url']}" for b in buttons)
    await bot.send_message(uid,
        f"<b>Preview yuqorida ↑</b>{btn_info}\n\nNima qilasiz?",
        parse_mode="HTML", reply_markup=preview_kb)


async def do_broadcast(bot, bc: dict):
    users = list(DB["users"].keys())
    buttons = bc.get("buttons", [])
    markup = build_broadcast_markup(buttons)
    ok = 0
    fail = 0
    for uid in users:
        try:
            kw = {}
            if markup:
                kw["reply_markup"] = markup
            await bot.copy_message(
                chat_id=int(uid),
                from_chat_id=bc["from_chat_id"],
                message_id=bc["message_id"],
                **kw
            )
            ok += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail += 1
            logger.warning(f"Broadcast uid={uid}: {e}")
    return ok, fail

# ══════════════════════════════════════════════════════════
# START
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    clear_admin_state(context)
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
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling 👇\n"
            "Obuna bo'lgach <b>Tekshirish</b> tugmasini bosing.",
            subscription_kb(ns))
        return

    hello = (f"Assalomu alaykum, <b>{user.full_name}</b>! 👋\n\n"
             f"🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
             f"Kino <b>kodini</b> yuboring — video <b>darhol</b> keladi! ⚡")
    is_admin = (user.id == ADMIN_ID)
    await sm(context.bot, user.id, hello, main_menu_kb(is_admin=is_admin))

# ══════════════════════════════════════════════════════════
# CALLBACK HANDLER
# ══════════════════════════════════════════════════════════

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id

    if data.startswith("bc_"):
        await cb_broadcast(update, context)
        return

    # ══════════════════════════════════════════════════
    # KANAL O'CHIRISH CALLBACK (YANGI)
    # ══════════════════════════════════════════════════
    if data.startswith("ch_del|"):
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True)
            return
        await q.answer()
        idx = int(data.split("|")[1])
        channels = DB.get("channels", [])
        if idx < 0 or idx >= len(channels):
            try:
                await q.edit_message_text("❌ Kanal topilmadi.")
            except Exception:
                pass
            return
        removed = channels.pop(idx)
        save()
        try:
            await q.edit_message_text(
                f"✅ <b>{removed['title']}</b> ({removed['username']}) o'chirildi!\n\n"
                f"{_channels_list_text()}",
                parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, uid, "Majburiy kanal boshqaruvi:", channel_manage_kb())
        return

    if data == "ch_del_cancel":
        await q.answer()
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Bekor qilindi.", channel_manage_kb())
        return

    if data == "check_sub":
        await cb_check_sub(update, context)

    elif data.startswith("page|"):
        await cb_page(update, context)

    elif data.startswith("ep|"):
        await cb_episode(update, context)

    elif data.startswith("pay_ok|") or data.startswith("pay_no|"):
        await cb_payment(update, context)

    elif data.startswith("reply|"):
        await cb_reply(update, context)

    elif data == "refresh_stats":
        if uid == ADMIN_ID:
            await q.answer("Yangilandi!")
            u = len(DB.get("users", {}))
            m = len(DB.get("movies", {}))
            v = DB.get("stats", {}).get("total_views", 0)
            await q.edit_message_text(
                f"<b>Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
                f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>",
                parse_mode="HTML", reply_markup=stats_kb())
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)

    elif data == "go_home":
        await q.answer()
        await context.bot.send_chat_action(uid, action="typing")
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Bosh menyu",
            main_menu_kb(is_admin=(uid == ADMIN_ID)))

    elif data == "waiting_confirm":
        await q.answer("Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)

    elif data == "emoji_back":
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True)
            return
        await q.answer()
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        try:
            await q.edit_message_text("Tugmani pastdan tanlang 👇")
        except Exception:
            pass
        await sm(context.bot, uid,
            "<b>Tugma sozlamalari</b>\nO'zgartirmoqchi bo'lgan tugmani pastdan tanlang 👇",
            emoji_menu_kb())

    elif data == "emoji_reset_all":
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True)
            return
        await q.answer()
        DB["btn_texts"] = {}
        DB["emoji_ids"] = {}
        EMOJI_IDS.clear()
        save()
        try:
            await q.edit_message_text("✅ Barcha tugmalar tiklandi!")
        except Exception:
            pass
        context.user_data["emoji_menu"] = True
        context.user_data.pop("editing_btn_key", None)
        await sm(context.bot, uid, "✅ Tiklandi! Tugmani tanlang:", emoji_menu_kb())

    elif data.startswith("emoji_reset|"):
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True)
            return
        await q.answer()
        key = data.split("|")[1]
        DB.get("btn_texts", {}).pop(key, None)
        DB.get("emoji_ids", {}).pop(key, None)
        EMOJI_IDS.pop(key, None)
        save()
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

    elif data.startswith("quick_add_ep|"):
        if uid == ADMIN_ID:
            code = data.split("|")[1]
            context.user_data["admin_state"] = "add_ep_video"
            context.user_data["ep_movie_code"] = code
            await q.answer()
            await context.bot.send_chat_action(uid, action="typing")
            await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)

    elif data.startswith("quick_price|"):
        if uid == ADMIN_ID:
            code = data.split("|")[1]
            movie = DB["movies"].get(code)
            if not movie:
                await q.answer("Kino topilmadi!", show_alert=True)
                return
            eps = movie.get("episodes", [])
            if not eps:
                await q.answer()
                await sm(context.bot, uid,
                    f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.\n\n"
                    f"Avval qism qo'shing, so'ng narx belgilang.")
                return
            prices = movie.get("prices", {})
            ep_list = _build_ep_price_list(code, eps, prices)
            context.user_data["price_movie_code"] = code
            context.user_data["admin_state"] = "set_price_ep"
            await q.answer()
            await context.bot.send_chat_action(uid, action="typing")
            await sm(context.bot, uid,
                f"💰 <b>{movie.get('title', code)}</b> — narx belgilash\n"
                f"Kod: <code>{code}</code>\n\n"
                f"{ep_list}\n\n"
                f"Qaysi qismni pullik qilmoqchisiz?\n"
                f"Qism <b>raqamini</b> kiriting (1 dan {len(eps)} gacha):")
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)

    else:
        await q.answer()


async def cb_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data
    if uid != ADMIN_ID:
        await q.answer("Ruxsat yo'q", show_alert=True)
        return
    await q.answer()

    bc = context.user_data.get("bc_msg", {})

    if data == "bc_cancel":
        context.user_data.pop("bc_msg", None)
        context.user_data.pop("bc_buttons", None)
        context.user_data.pop("bc_adding_btn", None)
        try:
            await q.edit_message_text("❌ Broadcast bekor qilindi.")
        except Exception:
            pass
        await sm(context.bot, uid, "Admin panel", admin_menu_kb())
        return

    if data.startswith("bc_color|"):
        color = data.split("|")[1]
        bc["btn_color"] = color
        context.user_data["bc_msg"] = bc
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


async def cb_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
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
        await q.answer("Kino topilmadi", show_alert=True)
        return

    user_id = q.from_user.id
    eps = movie.get("episodes", [])
    markup = movie_episodes_kb(movie, code, user_id, page=page)
    total_pages = max(1, (len(eps) + PAGE_SIZE - 1) // PAGE_SIZE)
    caption = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
               f"📺 Qismlar soni: <b>{len(eps)} ta</b>  "
               f"({page + 1}/{total_pages} sahifa)\n\n"
               f"👇 Qaysi qismni ko'rmoqchisiz?")
    try:
        await q.edit_message_caption(caption=caption, parse_mode="HTML",
                                     reply_markup=markup)
    except Exception:
        try:
            await q.edit_message_text(caption, parse_mode="HTML",
                                      reply_markup=markup)
        except Exception as e:
            logger.error(f"cb_page edit error: {e}")


async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await context.bot.send_chat_action(q.from_user.id, action="typing")
    ns = await check_subscription(q.from_user.id, context.bot)
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
        await sm(context.bot, q.from_user.id,
            f"🎉 Xush kelibsiz, <b>{q.from_user.full_name}</b>!\n\nKino kodini yuboring 👇",
            main_menu_kb(is_admin=(q.from_user.id == ADMIN_ID)))


async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
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
        await q.answer()
        card = DB.get("card_number") or "Admin karta raqamini o'rnatmagan"
        txt = (f"🔒 <b>Bu qism pullik</b>\n\n"
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

    await q.answer()
    await context.bot.send_chat_action(q.from_user.id, action="upload_video")

    bot_me = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption = f"🎬 <b>{movie.get('title')}</b>\n📺 Qism: <b>{ep}</b>"

    try:
        await sv(context.bot, q.from_user.id, eps[idx], caption, share_kb(share_url), protect=True)
    except Exception as e:
        logger.error(f"Video yuborishda xato: {e}")
        await sm(context.bot, q.from_user.id, f"❌ Video yuborishda xato: {e}")
        return

    async def update_stats():
        movie.setdefault("views", {})
        movie["views"][ep] = movie["views"].get(ep, 0) + 1
        DB["users"].setdefault(user_id, {}).setdefault("watched", {})[f"{code}_{ep}"] = True
        DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
        await db_save_async(DB)

    asyncio.create_task(update_stats())


async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action, pid = q.data.split("|")
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
            (q.message.caption or "") + "\n\n<b>Tasdiqlandi</b>", parse_mode="HTML")
    except Exception:
        pass

    movie = DB["movies"].get(pay["code"])
    if movie:
        idx = int(pay["ep"]) - 1
        eps = movie.get("episodes", [])
        if 0 <= idx < len(eps):
            await sm(context.bot, pay["user_id"],
                "<b>Admin to'lovingizni tasdiqladi!</b>")
            await sv(context.bot, pay["user_id"], eps[idx],
                f"<b>{movie.get('title')}</b>\nQism: {pay['ep']}", protect=True)

            async def update_pay_stats():
                movie.setdefault("views", {})
                movie["views"][pay["ep"]] = movie["views"].get(pay["ep"], 0) + 1
                DB["users"][uid].setdefault("watched", {})[f"{pay['code']}_{pay['ep']}"] = True
                DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
                await db_save_async(DB)

            asyncio.create_task(update_pay_stats())
    else:
        await sm(context.bot, pay["user_id"],
            "<b>Admin to'lovingizni tasdiqladi!</b>")


async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, uid = q.data.split("|")
    context.user_data["reply_to"] = int(uid)
    await q.message.reply_text(f"<code>{uid}</code> ga xabar yozing.", parse_mode="HTML")

# ══════════════════════════════════════════════════════════
# TEXT HANDLER
# ══════════════════════════════════════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    msg = update.message
    text = (msg.text or "").strip()

    # ── 1. editing_btn_key ──
    if uid == ADMIN_ID and context.user_data.get("editing_btn_key"):
        key = context.user_data.pop("editing_btn_key")
        if not text:
            await sm(context.bot, uid, "Bo'sh bo'lmasin. Qayta yuboring:")
            context.user_data["editing_btn_key"] = key
            return

        custom_emoji_id = extract_custom_emoji_id(msg)
        existing = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
        existing_label = strip_emoji_prefix(existing)
        existing_emoji_prefix = extract_emoji_prefix(existing)
        if not existing_label:
            existing_label = DEFAULT_BTN.get(key, "")

        if custom_emoji_id:
            new_text = existing_label
            EMOJI_IDS[key] = custom_emoji_id
            DB.setdefault("emoji_ids", {})[key] = custom_emoji_id
            eid_info = f"\nCustom emoji ID: <code>{custom_emoji_id}</code>"
        elif is_only_emoji(text):
            if existing_emoji_prefix:
                new_emoji_prefix = existing_emoji_prefix + text
            else:
                new_emoji_prefix = text
            new_text = f"{new_emoji_prefix} {existing_label}"
            EMOJI_IDS.pop(key, None)
            DB.get("emoji_ids", {}).pop(key, None)
            eid_info = ""
        else:
            new_text = text
            EMOJI_IDS.pop(key, None)
            DB.get("emoji_ids", {}).pop(key, None)
            eid_info = ""

        DB.setdefault("btn_texts", {})[key] = new_text
        save()

        eid = get_eid(key)
        if eid:
            eid_info = f"\nCustom emoji ID: <code>{eid}</code>"

        await sm(context.bot, uid,
            f"✅ <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n"
            f"Ko'rinish: <code>{new_text}</code>{eid_info}\n\n"
            f"Yana emoji qo'shish uchun emoji yuboring yoki boshqa tugmani tanlang 👇")
        context.user_data["emoji_menu"] = True
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    # ── 2. Broadcast tugma qo'shish ──
    if uid == ADMIN_ID and context.user_data.get("bc_adding_btn"):
        stage = context.user_data["bc_adding_btn"]
        bc = context.user_data.get("bc_msg", {})

        if stage == "text":
            context.user_data["bc_btn_name"] = text
            context.user_data["bc_adding_btn"] = "url"
            await sm(context.bot, uid,
                f"Tugma nomi: <b>{text}</b>\n\nEndi tugma linkini kiriting (https:// bilan):")
        elif stage == "url":
            btn_text_val = context.user_data.pop("bc_btn_name", "Tugma")
            color = bc.pop("btn_color", "primary")
            context.user_data.pop("bc_adding_btn", None)
            bc.setdefault("buttons", []).append({"text": btn_text_val, "url": text, "style": color})
            context.user_data["bc_msg"] = bc
            await sm(context.bot, uid, "✅ Tugma qo'shildi! Preview:")
            await send_broadcast_preview(context.bot, uid, bc)
        return

    # ── 3. Emoji menyu ──
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
            save()
            await sm(context.bot, uid, "✅ Barcha tugmalar tiklandi!", emoji_menu_kb())
            return

        key = find_key_by_text(text)
        if key:
            cur = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
            eid = get_eid(key)
            cur_emoji = extract_emoji_prefix(cur)
            eid_info = f"\nCustom emoji ID: <code>{eid}</code>" if eid else ""
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
        return

    # ── 4. Kanal boshqarish submenu ──
    if uid == ADMIN_ID and context.user_data.get("channel_manage_menu"):
        # Agar kanal qo'shish jarayonida bo'lsa — admin_state_handler ga yuboramiz
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
                "➕ <b>Kanal qo'shish</b> (1/3)\n\n"
                "Kanal <b>username</b>ini kiriting:\n"
                "<i>(Misol: @mykinochannel)</i>")
            return

        if text == "🗑 Kanal o'chirish":
            channels = DB.get("channels", [])
            if not channels:
                await sm(context.bot, uid,
                    "❌ Hozircha kanal yo'q. Avval kanal qo'shing.",
                    channel_manage_kb())
                return
            await sm(context.bot, uid,
                f"{_channels_list_text()}\n\nO'chirmoqchi bo'lgan kanalni tanlang 👇",
                channel_delete_inline_kb(channels))
            return

        if text == "📋 Kanallar ro'yxati":
            await sm(context.bot, uid, _channels_list_text(), channel_manage_kb())
            return
        return

    # ── 5. Admin reply_to ──
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        return

    # ── 6. Admin holat handler (price state'lari) ──
    if uid == ADMIN_ID:
        state = context.user_data.get("admin_state")
        if state in ("set_price_code", "set_price_ep", "set_price_amount"):
            handled = await admin_state_handler(update, context, text)
            if handled:
                return

    # ── 7. Admin tugmalarini aniqlash ──
    all_admin_btns = {bt(k) for k in [
        "kino_joy", "qism_qosh", "pullik", "stat",
        "kanal_post", "maj_kanal", "karta", "ilova",
        "emoji_soz", "asosiy", "boshqarish", "broadcast", "kino_uch"
    ]}

    if uid == ADMIN_ID and text in all_admin_btns:
        if text == bt("emoji_soz"):
            context.user_data.pop("admin_state", None)
            context.user_data.pop("editing_btn_key", None)
            context.user_data.pop("reply_to", None)
            context.user_data["emoji_menu"] = True
            await sm(context.bot, uid,
                "<b>Tugma sozlamalari</b>\n"
                "O'zgartirmoqchi bo'lgan tugmani pastdan tanlang 👇",
                emoji_menu_kb())
            return

        if text == bt("broadcast"):
            context.user_data.pop("admin_state", None)
            context.user_data.pop("emoji_menu", None)
            context.user_data.pop("editing_btn_key", None)
            await sm(context.bot, uid,
                "📢 <b>Barchaga xabar yuborish</b>\n\n"
                "Xabar yuboring — matn, rasm yoki video.\n\n"
                "⚠️ <b>Muhim:</b> Agar iqtibos (quote) xabar yuborsangiz,\n"
                "faqat asosiy matn yuboriladi, iqtibos qismi o'tkazib yuboriladi.\n\n"
                "Bekor qilish uchun /start bosing.")
            context.user_data["admin_state"] = "broadcast_msg"
            return

        if text == bt("kino_uch"):
            context.user_data.pop("emoji_menu", None)
            context.user_data["admin_state"] = "delete_movie_code"
            await sm(context.bot, uid,
                "🗑 <b>Kino o'chirish</b>\n\nKino kodini kiriting:")
            return

        context.user_data.pop("emoji_menu", None)
        context.user_data.pop("editing_btn_key", None)
        await admin_buttons(update, context, text)
        return

    # ── 8. Admin holat handler (boshqa state'lar) ──
    if uid == ADMIN_ID:
        handled = await admin_state_handler(update, context, text)
        if handled:
            return

    # ── 9. Foydalanuvchi tugmalari ──
    if text == bt("yordam"):
        await context.bot.send_chat_action(uid, action="typing")
        await sm(context.bot, uid,
            "💬 <b>Yordam kerakmi?</b>\n\n"
            "Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\n"
            "Admin tez orada javob beradi! 🙂",
            help_kb(),
            reply_to_message_id=msg.message_id)
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
            await context.bot.send_chat_action(uid, action="upload_video")
            await sv(context.bot, uid, v_id, "<b>Ilovani o'rnatish videosi</b>")
        if f_id:
            await context.bot.send_chat_action(uid, action="upload_document")
            await context.bot.send_document(
                uid, f_id, caption="<b>Ilova fayli</b>", parse_mode="HTML")
        return

    # ── 10. Yordam so'rovi ──
    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        await sm(context.bot, ADMIN_ID, cap + text, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    # ── 11. To'lov cheki ──
    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos, chek <b>rasmini</b> yuboring.")
        return

    # ── 12. Kino kodi ──
    code = text.upper().strip()
    if code in DB["movies"]:
        ns = await check_subscription(uid, context.bot)
        if ns:
            await sm(context.bot, uid,
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                subscription_kb(ns))
            context.user_data["pending_code"] = code
            return
        await context.bot.send_chat_action(uid, action="upload_video")
        await send_movie_menu(update, context, code)
    else:
        await sm(context.bot, uid, "❌ Bunday kod topilmadi.\n\nTo'g'ri kino kodini yuboring 👇")


async def admin_buttons(update, context, text):
    uid = update.effective_user.id
    await context.bot.send_chat_action(uid, action="typing")

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
            "💰 <b>Qismni pullik qilish</b>\n\n"
            "Kino <b>kodini</b> kiriting:")
        return

    if text == bt("ilova"):
        context.user_data["admin_state"] = "set_install"
        await sm(context.bot, uid, "Ilova fayl yoki video yuboring:")
        return

    # ══════════════════════════════════════════════════
    # TUZATISH: maj_kanal — submenu ochadi
    # ══════════════════════════════════════════════════
    if text == bt("maj_kanal"):
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True
        channels = DB.get("channels", [])
        await sm(context.bot, uid,
            f"📡 <b>Majburiy kanal boshqaruvi</b>\n\n"
            f"{_channels_list_text()}\n\n"
            f"Nima qilmoqchisiz?",
            channel_manage_kb())
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

    if state == "broadcast_msg":
        bc = {
            "type": "copy",
            "from_chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
            "buttons": [],
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return True

    if state == "delete_movie_code":
        code = text.upper().strip()
        if code not in DB["movies"]:
            await sm(context.bot, uid,
                f"❌ <code>{code}</code> kodli kino topilmadi.\n\nQayta kiriting yoki /start bosing:")
            return True
        movie = DB["movies"][code]
        title = movie.get("title", code)
        eps = movie.get("episodes", [])
        context.user_data["del_movie_code"] = code
        context.user_data["admin_state"] = "delete_movie_ep"
        ep_list = "\n".join([f"  {i+1}-qism" for i in range(len(eps))]) if eps else "  (qismlar yo'q)"
        await sm(context.bot, uid,
            f"🎬 <b>{title}</b>  |  <code>{code}</code>\n"
            f"📺 Qismlar soni: <b>{len(eps)} ta</b>\n\n"
            f"{ep_list}\n\n"
            f"Qaysi qismni o'chirmoqchisiz?\n"
            f"• Raqam kiriting (masalan: <code>3</code>)\n"
            f"• Barcha qismlarni o'chirish: <code>hammasi</code>\n"
            f"• Kinoni butunlay o'chirish: <code>kino</code>")
        return True

    if state == "delete_movie_ep":
        code = context.user_data.get("del_movie_code")
        movie = DB["movies"].get(code)
        if not movie:
            await sm(context.bot, uid, "❌ Kino topilmadi. /start bosing.")
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            return True

        title = movie.get("title", code)
        eps = movie.get("episodes", [])
        val = text.strip().lower()

        if val == "kino":
            del DB["movies"][code]
            save()
            context.user_data.pop("admin_state", None)
            context.user_data.pop("del_movie_code", None)
            await sm(context.bot, uid,
                f"✅ <b>{title}</b> (<code>{code}</code>) butunlay o'chirildi!",
                admin_menu_kb())
            return True

        if val == "hammasi":
            DB["movies"][code]["episodes"] = []
            DB["movies"][code]["prices"] = {}
            save()
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
            save()
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
        save()
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, f"✅ Karta saqlandi: <code>{text}</code>")
        return True

    if state == "add_movie_code":
        context.user_data["new_movie_code"] = text.upper()
        context.user_data["admin_state"] = "add_movie_title"
        await sm(context.bot, uid, "Kino nomini kiriting:")
        return True

    if state == "add_movie_title":
        code = context.user_data.get("new_movie_code")
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        DB["movies"][code] = {
            "title": text,
            "episodes": [],
            "prices": {},
            "added_date": now,
        }
        save()
        context.user_data["admin_state"] = "add_movie_poster"
        context.user_data["poster_code"] = code
        await sm(context.bot, uid,
            f"✅ <b>{text}</b> kinosi qo'shildi!\nKod: <code>{code}</code>\n\n"
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
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Bunday kod yo'q. Qayta kiriting yoki bekor qiling.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["ep_movie_code"] = code
        context.user_data["admin_state"] = "add_ep_video"
        await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        return True

    if state == "set_price_code":
        code = text.upper().strip()
        if code not in DB["movies"]:
            await sm(context.bot, uid,
                f"❌ <code>{code}</code> kodli kino topilmadi.\n\n"
                f"Qayta kino kodini kiriting:")
            return True

        movie = DB["movies"][code]
        eps = movie.get("episodes", [])
        prices = movie.get("prices", {})

        if not eps:
            await sm(context.bot, uid,
                f"⚠️ <b>{movie.get('title', code)}</b> kinoda hali qism yo'q.\n\n"
                f"Avval qism qo'shing, so'ng narx belgilang.")
            context.user_data.pop("admin_state", None)
            return True

        ep_list = _build_ep_price_list(code, eps, prices)
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"] = "set_price_ep"

        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b> — narx belgilash\n"
            f"Kod: <code>{code}</code>\n\n"
            f"{ep_list}\n\n"
            f"Qaysi qismni pullik qilmoqchisiz?\n"
            f"Qism <b>raqamini</b> kiriting (1 dan {len(eps)} gacha):")
        return True

    if state == "set_price_ep":
        code = context.user_data.get("price_movie_code")

        if not code or code not in DB["movies"]:
            await sm(context.bot, uid,
                "❌ Xatolik yuz berdi. Qaytadan kino kodini kiriting:")
            context.user_data["admin_state"] = "set_price_code"
            context.user_data.pop("price_movie_code", None)
            context.user_data.pop("price_ep", None)
            return True

        movie = DB["movies"][code]
        eps = movie.get("episodes", [])

        if not text.strip().isdigit():
            await sm(context.bot, uid,
                "❌ Faqat <b>raqam</b> kiriting (masalan: <code>3</code>):")
            return True

        ep_num = int(text.strip())
        if ep_num < 1 or ep_num > len(eps):
            await sm(context.bot, uid,
                f"❌ <b>{ep_num}</b>-qism mavjud emas.\n"
                f"1 dan {len(eps)} gacha raqam kiriting:")
            return True

        context.user_data["price_ep"] = str(ep_num)
        context.user_data["admin_state"] = "set_price_amount"

        cur_price = movie.get("prices", {}).get(str(ep_num))
        cur_info = f"\nHozirgi narx: <b>{cur_price} so'm</b>" if cur_price else "\nHozir: <b>bepul</b>"

        await sm(context.bot, uid,
            f"💰 <b>{movie.get('title', code)}</b>\n"
            f"<b>{ep_num}-qism</b> narxi{cur_info}\n\n"
            f"Yangi narxni kiriting (so'mda):\n"
            f"<i>Bepul qilish uchun <code>0</code> kiriting</i>")
        return True

    if state == "set_price_amount":
        code = context.user_data.get("price_movie_code")
        ep = context.user_data.get("price_ep")

        if not code or not ep or code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Xatolik. /start bosing.")
            context.user_data.pop("admin_state", None)
            context.user_data.pop("price_movie_code", None)
            context.user_data.pop("price_ep", None)
            return True

        movie = DB["movies"][code]
        movie_title = movie.get("title", code)

        if not text.strip().isdigit():
            await sm(context.bot, uid,
                "❌ Faqat <b>raqam</b> kiriting (so'mda).\n"
                "<i>Bepul qilish uchun <code>0</code> kiriting</i>")
            return True

        amount = text.strip()

        context.user_data.pop("admin_state", None)
        context.user_data.pop("price_movie_code", None)
        context.user_data.pop("price_ep", None)

        if amount == "0":
            DB["movies"][code].setdefault("prices", {}).pop(ep, None)
            save()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> endi <b>bepul</b>!",
                admin_menu_kb())
        else:
            DB["movies"][code].setdefault("prices", {})[ep] = amount
            save()
            await sm(context.bot, uid,
                f"✅ <b>{movie_title}</b> — <b>{ep}-qism</b> narxi: <b>{amount} so'm</b>",
                admin_menu_kb())
        return True

    # ══════════════════════════════════════════════════
    # TUZATISH: add_channel — to'g'ri format tekshiruvi
    # ══════════════════════════════════════════════════
    if state == "add_channel_username":
        # Username qabul qilish
        uname = text.strip()
        if not uname.startswith("@"):
            uname = "@" + uname
        # Faqat username qolsin (link bo'lsa ham)
        uname = uname.split("/")[-1]
        if not uname.startswith("@"):
            uname = "@" + uname

        # Dublikat tekshiruvi
        existing = DB.get("channels", [])
        for ch in existing:
            if ch["username"].lower() == uname.lower():
                context.user_data.pop("admin_state", None)
                context.user_data["channel_manage_menu"] = True
                await sm(context.bot, uid,
                    f"⚠️ <b>{uname}</b> allaqachon qo'shilgan!\n\n"
                    f"{_channels_list_text()}",
                    channel_manage_kb())
                return True

        context.user_data["ch_username"] = uname
        context.user_data["admin_state"] = "add_channel_title"
        await sm(context.bot, uid,
            f"✅ Username: <b>{uname}</b>\n\nEndi kanal <b>nomini</b> kiriting:\n"
            f"<i>(Misol: DramlarUz Kanali)</i>")
        return True

    if state == "add_channel_title":
        title = text.strip()
        if not title:
            await sm(context.bot, uid, "❌ Nom bo'sh bo'lmasin. Qayta kiriting:")
            return True
        context.user_data["ch_title"] = title
        context.user_data["admin_state"] = "add_channel_url"
        uname = context.user_data.get("ch_username", "")
        await sm(context.bot, uid,
            f"✅ Nom: <b>{title}</b>\n\nEndi kanal <b>linkini</b> kiriting:\n"
            f"<i>(Misol: https://t.me/mykinochannel)</i>")
        return True

    if state == "add_channel_url":
        url = text.strip()
        # link preview kelsa entities dan olishga harakat
        if not url.startswith("http") and update.message.entities:
            for ent in update.message.entities:
                if ent.type in ("url", "text_link"):
                    url = getattr(ent, "url", url) or url
                    break
        if not url.startswith("http"):
            url = "https://t.me/" + url.lstrip("@")

        uname = context.user_data.pop("ch_username", "")
        title = context.user_data.pop("ch_title", "")
        context.user_data.pop("admin_state", None)
        context.user_data["channel_manage_menu"] = True

        DB["channels"].append({"username": uname, "title": title, "url": url})
        save()
        await sm(context.bot, uid,
            f"✅ Kanal qo'shildi!\n\n"
            f"📛 Nom: <b>{title}</b>\n"
            f"👤 Username: <b>{uname}</b>\n"
            f"🔗 Link: {url}\n\n"
            f"{_channels_list_text()}",
            channel_manage_kb())
        return True

    if state == "add_channel":
        # Eski format qo'llab-quvvatlash (fallback)
        try:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) < 3:
                raise ValueError("Format xato")
            uname, title, url = parts[0], parts[1], parts[2]
            if not uname.startswith("@"):
                uname = "@" + uname
            existing = DB.get("channels", [])
            for ch in existing:
                if ch["username"].lower() == uname.lower():
                    context.user_data.pop("admin_state", None)
                    context.user_data["channel_manage_menu"] = True
                    await sm(context.bot, uid,
                        f"⚠️ <b>{uname}</b> allaqachon qo'shilgan!\n\n"
                        f"{_channels_list_text()}",
                        channel_manage_kb())
                    return True
            DB["channels"].append({"username": uname, "title": title, "url": url})
            save()
            context.user_data.pop("admin_state", None)
            context.user_data["channel_manage_menu"] = True
            await sm(context.bot, uid,
                f"✅ Kanal qo'shildi: <b>{title}</b> ({uname})\n\n"
                f"{_channels_list_text()}",
                channel_manage_kb())
        except Exception:
            await sm(context.bot, uid,
                "❌ Xatolik. Qayta urinib ko'ring.")
            return True
        return True

    if state == "post_channel_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Bunday kod yo'q.")
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
        title = movie.get('title', code)
        ep_count = len(movie.get('episodes', []))
        caption = (
            "┏╋━━━━━━◥◣◆◢◤━━━━━━╋┓\n"
            f"        <b>{title}</b>\n"
            "┗╋━━━━━━◢◤◆◥◣━━━━━━╋┛\n"
            "\n"
            "╭═━═━═━═━═━═╮\n"
            f"     <b>Qismlar soni: {ep_count}</b>\n"
            "╰═━═━═━═━═━═╯\n"
            "\n"
            "┏━━━〔 ✪ 〕━━━┓\n"
            f"      <b>KINO KODI: {code}</b>\n"
            "┗━━━〔 ✦ 〕━━━┛\n"
            "\n"
            "╭━━━〔 ▼ 〕━━━╮\n"
            "   <b>Tomosha qiling</b>\n"
            "  <b>uchun tugmani</b>\n"
            "      <b>bosing!</b>\n"
            "╰━━━〔 ▼ 〕━━━╯"
        )
        poster = movie.get("poster_file_id")
        try:
            if poster:
                await sp(context.bot, channel, poster, caption, markup)
            else:
                await sm(context.bot, channel, caption, markup)
            await sm(context.bot, uid, "✅ Post yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        context.user_data.pop("admin_state")
        context.user_data.pop("post_code", None)
        return True

    if state == "set_install":
        await sm(context.bot, uid, "⚠️ Iltimos, matn emas — <b>fayl yoki video</b> yuboring:")
        return True

    if state == "add_ep_video":
        await sm(context.bot, uid, "⚠️ Iltimos, matn emas — <b>video fayl</b> yuboring:")
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

    context.user_data.pop("editing_btn_key")

    existing = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
    existing_label = strip_emoji_prefix(existing)
    existing_emoji_prefix = extract_emoji_prefix(existing)
    if not existing_label:
        existing_label = DEFAULT_BTN.get(key, "")

    if existing_emoji_prefix:
        new_emoji_prefix = existing_emoji_prefix + emoji
    else:
        new_emoji_prefix = emoji

    new_text = f"{new_emoji_prefix} {existing_label}"
    DB.setdefault("btn_texts", {})[key] = new_text
    EMOJI_IDS.pop(key, None)
    DB.get("emoji_ids", {}).pop(key, None)
    save()

    await sm(context.bot, uid,
        f"✅ <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n\n"
        f"Ko'rinish: <code>{new_text}</code>")
    context.user_data["emoji_menu"] = True
    await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())

# ══════════════════════════════════════════════════════════
# MEDIA HANDLER
# ══════════════════════════════════════════════════════════

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    msg = update.message
    state = context.user_data.get("admin_state")

    if uid == ADMIN_ID and state == "broadcast_msg":
        bc = {
            "type": "copy",
            "from_chat_id": msg.chat_id,
            "message_id": msg.message_id,
            "buttons": [],
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return

    if uid == ADMIN_ID and state == "add_movie_poster":
        code = context.user_data.pop("poster_code", None)
        context.user_data.pop("admin_state", None)
        context.user_data.pop("new_movie_code", None)
        if msg.photo and code:
            DB["movies"][code]["poster_file_id"] = msg.photo[-1].file_id
            save()
            await sm(context.bot, uid,
                f"✅ Poster saqlandi!\nKod: <code>{code}</code>",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid,
                "⚠️ Rasm yuboring! Yoki matn '0' kiriting.",
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
            save()
            ep_num = len(DB["movies"][code]["episodes"])
            context.user_data.pop("admin_state")
            context.user_data.pop("ep_movie_code", None)
            await sm(context.bot, uid,
                f"✅ <b>{ep_num}-qism</b> saqlandi!\n"
                f"Kino: <code>{code}</code>",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "⚠️ Faqat video yuboring!")
        return

    if uid == ADMIN_ID and state == "set_install":
        if msg.video:
            DB["settings"]["install_video_id"] = msg.video.file_id
            save()
            context.user_data.pop("admin_state")
            await sm(context.bot, uid, "✅ O'rnatish videosi saqlandi!")
        elif msg.document:
            DB["settings"]["install_file_id"] = msg.document.file_id
            save()
            context.user_data.pop("admin_state")
            await sm(context.bot, uid, "✅ O'rnatish fayli saqlandi!")
        else:
            await sm(context.bot, uid, "⚠️ Video yoki fayl yuboring!")
        return

    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info = context.user_data.pop("awaiting_check")
        pid = f"{uid}_{pay_info['code']}_{pay_info['ep']}_{int(time.time())}"
        DB["pending_payments"][pid] = {
            "user_id": uid, "code": pay_info["code"],
            "ep": pay_info["ep"], "price": pay_info["price"], "status": "pending"
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
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        if msg.photo:
            await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, reply_admin_kb(uid))
        elif msg.video:
            await sv(context.bot, ADMIN_ID, msg.video.file_id, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            if msg.photo:
                await sp(context.bot, target, msg.photo[-1].file_id, "<b>Admin javobi</b>")
            elif msg.video:
                await sv(context.bot, target, msg.video.file_id, "<b>Admin javobi</b>")
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))
    logger.info("Bot ishga tushdi! v9")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()