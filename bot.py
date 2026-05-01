# -*- coding: utf-8 -*-
"""
Kino Bot - TUZATILGAN VERSIYA v4
TUZATISHLAR:
1. Tugmalar endi to'g'ri ishlaydi (Telegram Bot API ga mos: 'style', 'icon_custom_emoji_id' olib tashlandi).
2. "Yordam" tugmasi qizil rangda ko'rinadi (ðŸ”´ emoji bilan â€” Bot API rangni qo'llamaydi).
3. Broadcast: matn/rasm/video/sticker, premium emoji saqlanadi (copy_message), inline tugma (nom+link) ixtiyoriy.
4. Tezlik: parallel obuna tekshiruvi (asyncio.gather), JSONBin background save (debounce 1.5s).
5. To'lov tasdiqlangach video DARHOL.
6. Kino kodi yuborilganda darhol javob.
"""
import logging, asyncio, json, time, re, threading, copy
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from telegram.error import TelegramError

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SOZLAMALAR
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
BOT_TOKEN       = "8591630784:AAHablTRlXLeWpn2ipxbBUHQeoYWNDigygo"
ADMIN_ID        = 8537782289
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TUGMA NOMLARI (sof o'zbek tilida, chiroyli)
# "yordam" â€” qizil ko'rinish uchun ðŸ”´ prefiks
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
DEFAULT_BTN = {
    "yordam":     "ðŸ”´ Yordam",
    "install":    "ðŸ“² Ilovani o'rnatish",
    "kino_joy":   "ðŸŽ¬ Kino joylash",
    "qism_qosh":  "âž• Qism qo'shish",
    "pullik":     "ðŸ’° Qismni pullik qilish",
    "stat":       "ðŸ“Š Statistika",
    "kanal_post": "ðŸ“¤ Kanalga post",
    "maj_kanal":  "ðŸ”” Majburiy kanal",
    "karta":      "ðŸ’³ Karta raqami",
    "ilova":      "ðŸ“ Ilova fayl/video",
    "emoji_soz":  "ðŸŽ¨ Tugma sozlamalari",
    "broadcast":  "ðŸ“¢ Hammaga xabar",
    "asosiy":     "ðŸ  Asosiy menyu",
    "boshqarish": "âš™ï¸ Boshqarish",
    "tekshir":    "âœ… Tekshirish",
    "tasdiq":     "âœ… Tasdiqlash",
    "bekor":      "âŒ Bekor qilish",
    "ulash":      "ðŸ“¤ Do'stlarga ulashish",
    "tomosha":    "ðŸŽ¥ Tomosha qilish",
    "javob":      "âœ‰ï¸ Javob berish",
    "yangi":      "ðŸ”„ Yangilash",
    "qism_add":   "âž• Qism qo'shish",
    "narx_bel":   "ðŸ’° Narx belgilash",
    "kut":        "â³ Tasdiqlanishini kuting",
    "bosh":       "ðŸ  Bosh menyu",
    "tiklash":    "ðŸ—‘ Hammasini tiklash",
    "yopish":     "âŒ Yopish",
    "default_q":  "â†©ï¸ Defaultga qaytarish",
    "orqaga":     "â¬…ï¸ Orqaga",
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
    "emoji_soz":  "Tugma sozlamalari",
    "broadcast":  "Hammaga xabar",
    "asosiy":     "Asosiy menyu",
    "boshqarish": "Boshqarish",
    "tekshir":    "Tekshirish",
    "tasdiq":     "Tasdiqlash",
    "bekor":      "Bekor qilish",
    "ulash":      "Ulashish",
    "tomosha":    "Tomosha",
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
}

LABEL_TO_KEY = {v: k for k, v in BTN_LABELS.items()}

DEFAULT_DB = {
    "users": {}, "movies": {}, "channels": [], "card_number": "",
    "pending_payments": {},
    "settings": {"install_file_id": None, "install_video_id": None},
    "stats": {"total_views": 0},
    "btn_texts": {},
}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# DB â€” Background save (debounce 1.5s)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def db_load():
    for attempt in range(3):
        try:
            r = requests.get(f"{JSONBIN_URL}/latest",
                headers={"X-Master-Key": JSONBIN_API_KEY}, timeout=20)
            if r.status_code == 200:
                data = r.json().get("record", {})
                for k, dv in DEFAULT_DB.items():
                    if k not in data:
                        data[k] = json.loads(json.dumps(dv))
                    elif isinstance(dv, dict) and not isinstance(data[k], dict):
                        data[k] = json.loads(json.dumps(dv))
                    elif isinstance(dv, list) and not isinstance(data[k], list):
                        data[k] = json.loads(json.dumps(dv))
                logger.info(f"Yuklandi: {len(data.get('users', {}))} user, {len(data.get('movies', {}))} kino")
                return data
        except Exception as e:
            logger.error(f"DB load #{attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2)
    return json.loads(json.dumps(DEFAULT_DB))

def _db_save_sync(data):
    try:
        r = requests.put(JSONBIN_URL,
            headers={
                "X-Master-Key": JSONBIN_API_KEY,
                "Content-Type": "application/json",
                "X-Bin-Versioning": "false"
            },
            data=json.dumps(data, ensure_ascii=False), timeout=20)
        if r.status_code == 200:
            return True
        logger.error(f"DB save status: {r.status_code}")
    except Exception as e:
        logger.error(f"DB save: {e}")
    return False

DB = db_load()

_save_lock = threading.Lock()
_save_pending = threading.Event()
_save_thread_started = False

def _save_worker():
    while True:
        _save_pending.wait()
        time.sleep(1.5)
        with _save_lock:
            _save_pending.clear()
            snapshot = copy.deepcopy(DB)
        ok = _db_save_sync(snapshot)
        if ok:
            logger.info("DB saqlandi âœ“")
        else:
            logger.error("DB saqlash xato!")
            time.sleep(5)
            _save_pending.set()

def _start_save_thread():
    global _save_thread_started
    if not _save_thread_started:
        threading.Thread(target=_save_worker, daemon=True).start()
        _save_thread_started = True

def save():
    _start_save_thread()
    _save_pending.set()
    return True

def bt(key):
    """Tugma matni â€” agar admin o'zgartirgan bo'lsa, o'sha; aks holda default."""
    return DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# EMOJI HELPERS
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
    cleaned = EMOJI_RE.sub('', text).strip()
    return len(cleaned) == 0 and len(text.strip()) > 0

def extract_emoji_prefix(text: str) -> str:
    m = re.match(
        r'^((?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+)',
        text)
    return m.group(1).rstrip() if m else ""

def strip_emoji_prefix(text: str) -> str:
    return re.sub(
        r'^(?:[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F\u200d\ufe0f]+\s*)+',
        '', text).strip()

def find_key_by_text(text: str) -> str | None:
    """Foydalanuvchi bosgan tugma nomidan key ni topish."""
    if text in LABEL_TO_KEY:
        return LABEL_TO_KEY[text]
    for key in BTN_LABELS:
        current = bt(key)
        if current == text:
            return key
        # Emoji'siz solishtirish â€” agar prefix farq qilsa ham
        sc, st = strip_emoji_prefix(current), strip_emoji_prefix(text)
        if sc and sc == st:
            return key
    return None

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# KEYBOARDS â€” TOZA Telegram Bot API formati (style, icon_custom_emoji_id YO'Q!)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def ikb(rows):
    """Inline keyboard. rows = [[InlineKeyboardButton, ...], ...]"""
    return InlineKeyboardMarkup(rows)

def rkb(rows):
    """Reply keyboard. rows = [[str yoki KeyboardButton, ...], ...]"""
    kb = []
    for row in rows:
        kb_row = []
        for cell in row:
            if isinstance(cell, KeyboardButton):
                kb_row.append(cell)
            else:
                kb_row.append(KeyboardButton(str(cell)))
        kb.append(kb_row)
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def main_menu_kb(is_admin=False):
    rows = [[bt("yordam"), bt("install")]]
    if is_admin:
        rows.append([bt("boshqarish")])
    return rkb(rows)

def admin_menu_kb():
    return rkb([
        [bt("kino_joy"),   bt("qism_qosh")],
        [bt("pullik"),     bt("stat")],
        [bt("kanal_post"), bt("maj_kanal")],
        [bt("karta"),      bt("ilova")],
        [bt("broadcast")],
        [bt("emoji_soz")],
        [bt("asosiy")],
    ])

def subscription_kb(channels):
    rows = [[InlineKeyboardButton(c['title'], url=c["url"])] for c in channels]
    rows.append([InlineKeyboardButton(bt("tekshir"), callback_data="check_sub")])
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
            label = f"ðŸ”’ {ek}-qism  ({price} so'm)"
        else:
            label = f"â–¶ï¸ {ek}-qism"
        rows.append([InlineKeyboardButton(label, callback_data=f"ep|{code}|{ek}")])
    return ikb(rows)

def payment_admin_kb(pid):
    return ikb([[
        InlineKeyboardButton(bt("tasdiq"), callback_data=f"pay_ok|{pid}"),
        InlineKeyboardButton(bt("bekor"),  callback_data=f"pay_no|{pid}"),
    ]])

def share_kb(url):
    return ikb([[InlineKeyboardButton(bt("ulash"), url=url)]])

def channel_post_kb(bot_username, code):
    return ikb([[InlineKeyboardButton(
        bt("tomosha"),
        url=f"https://t.me/{bot_username}?start=code_{code}")]])

def reply_admin_kb(uid):
    return ikb([[InlineKeyboardButton(bt("javob"), callback_data=f"reply|{uid}")]])

def stats_kb():
    return ikb([[InlineKeyboardButton(bt("yangi"), callback_data="refresh_stats")]])

def movie_added_kb(code):
    return ikb([[
        InlineKeyboardButton(bt("qism_add"), callback_data=f"quick_add_ep|{code}"),
        InlineKeyboardButton(bt("narx_bel"), callback_data=f"quick_price|{code}"),
    ]])

def payment_sent_kb():
    return ikb([[InlineKeyboardButton(bt("kut"), callback_data="waiting_confirm")]])

def help_kb():
    return ikb([[InlineKeyboardButton(bt("bosh"), callback_data="go_home")]])

def emoji_menu_kb():
    rows = []
    keys = list(BTN_LABELS.keys())
    for i in range(0, len(keys), 2):
        row = [BTN_LABELS.get(k, k) for k in keys[i:i+2]]
        rows.append(row)
    rows.append(["ðŸ—‘ Hammasini tiklash"])
    rows.append(["â¬…ï¸ Orqaga"])
    return rkb(rows)

def emoji_single_action_kb(key):
    return ikb([
        [InlineKeyboardButton("ðŸ—‘ Defaultga qaytarish", callback_data=f"emoji_reset|{key}")],
        [InlineKeyboardButton("â¬…ï¸ Orqaga", callback_data="emoji_back")],
    ])

def broadcast_menu_kb(has_msg=False, has_buttons=False):
    rows = []
    if has_msg:
        rows.append(["âœ… Yuborish"])
    rows.append(["âž• Tugma qo'shish"])
    if has_buttons:
        rows.append(["ðŸ—‘ Tugmalarni o'chirish"])
    rows.append(["âŒ Bekor qilish"])
    return rkb(rows)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SEND HELPERS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def sm(bot, chat_id, text, markup=None, pm="HTML"):
    return await bot.send_message(chat_id=chat_id, text=text,
        parse_mode=pm, reply_markup=markup)

async def sp(bot, chat_id, photo, caption, markup=None, pm="HTML"):
    return await bot.send_photo(chat_id=chat_id, photo=photo,
        caption=caption, parse_mode=pm, reply_markup=markup)

async def sv(bot, chat_id, video, caption, markup=None, pm="HTML"):
    return await bot.send_video(chat_id=chat_id, video=video,
        caption=caption, parse_mode=pm, reply_markup=markup)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# OBUNA â€” parallel tekshiruv (TEZ)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def _check_one_channel(bot, ch, user_id):
    try:
        member = await bot.get_chat_member(ch["username"], user_id)
        if member.status in ("left", "kicked"):
            return ch
    except Exception as e:
        logger.warning(f"Sub check {ch.get('username')}: {e}")
        return ch
    return None

async def check_subscription(user_id, bot):
    channels = DB.get("channels", [])
    if not channels:
        return []
    results = await asyncio.gather(
        *[_check_one_channel(bot, ch, user_id) for ch in channels],
        return_exceptions=True
    )
    return [r for r in results if r and not isinstance(r, Exception)]

def register_user(user):
    uid = str(user.id)
    if uid not in DB["users"]:
        DB["users"][uid] = {
            "name": user.full_name, "username": user.username or "",
            "joined": datetime.now().isoformat(),
            "paid_episodes": {}, "watched": {}
        }
        save()

async def send_movie_menu(src, context, code):
    movie = DB["movies"].get(code)
    chat_id = src.effective_user.id if hasattr(src, "effective_user") else src.from_user.id
    if not movie:
        await sm(context.bot, chat_id, "Bunday kodli kino topilmadi.")
        return
    eps = movie.get("episodes", [])
    if not eps:
        await sm(context.bot, chat_id, "Bu kinoga hali qism yuklanmagan.")
        return
    markup = movie_episodes_kb(movie, code, chat_id)
    caption = (f"<b>ðŸŽ¬ {movie.get('title', 'Kino')}</b>\n"
               f"Qismlar soni: <b>{len(eps)}</b>\n\nQaysi qismni ko'rmoqchisiz?")
    poster = movie.get("poster_file_id")
    try:
        if poster:
            await sp(context.bot, chat_id, poster, caption, markup)
        else:
            await sm(context.bot, chat_id, caption, markup)
    except Exception as e:
        logger.error(f"send_movie_menu: {e}")

def clear_admin_state(context):
    for k in ["admin_state", "new_movie_code", "ep_movie_code",
              "price_movie_code", "price_ep", "post_code",
              "reply_to", "awaiting_help", "awaiting_check",
              "editing_btn_key", "emoji_menu", "broadcast"]:
        context.user_data.pop(k, None)

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# /start
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            subscription_kb(ns))
        return

    hello = (f"Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
             f"<b>ðŸŽ¬ Kino botga xush kelibsiz!</b>\n\n"
             f"Kino <b>kodini</b> yuboring â€” video darhol chiqadi.")
    is_admin = (user.id == ADMIN_ID)
    await sm(context.bot, user.id, hello, main_menu_kb(is_admin=is_admin))

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CALLBACK HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id

    if data == "check_sub":
        await cb_check_sub(update, context); return
    if data.startswith("ep|"):
        await cb_episode(update, context); return
    if data.startswith("pay_ok|") or data.startswith("pay_no|"):
        await cb_payment(update, context); return
    if data.startswith("reply|"):
        await cb_reply(update, context); return

    if data == "refresh_stats":
        if uid == ADMIN_ID:
            await q.answer("Yangilandi!")
            u = len(DB.get("users", {}))
            m = len(DB.get("movies", {}))
            v = DB.get("stats", {}).get("total_views", 0)
            await q.edit_message_text(
                f"<b>ðŸ“Š Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
                f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>",
                parse_mode="HTML", reply_markup=stats_kb())
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)
        return

    if data == "go_home":
        await q.answer()
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "ðŸ  Bosh menyu",
            main_menu_kb(is_admin=(uid == ADMIN_ID)))
        return

    if data == "waiting_confirm":
        await q.answer("Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)
        return

    if data == "emoji_back":
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True); return
        await q.answer()
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        await sm(context.bot, uid,
            "<b>ðŸŽ¨ Tugma sozlamalari</b>\nTugmani pastdan tanlang ðŸ‘‡",
            emoji_menu_kb())
        return

    if data.startswith("emoji_reset|"):
        if uid != ADMIN_ID:
            await q.answer("Ruxsat yo'q", show_alert=True); return
        await q.answer()
        key = data.split("|")[1]
        DB.get("btn_texts", {}).pop(key, None)
        save()
        default = DEFAULT_BTN.get(key, "")
        context.user_data.pop("editing_btn_key", None)
        context.user_data["emoji_menu"] = True
        try:
            await q.edit_message_text(
                f"âœ… <b>{BTN_LABELS.get(key, key)}</b> tiklandi!\nDefault: <code>{default}</code>",
                parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    if data.startswith("quick_add_ep|"):
        if uid == ADMIN_ID:
            code = data.split("|")[1]
            context.user_data["admin_state"] = "add_ep_video"
            context.user_data["ep_movie_code"] = code
            await q.answer()
            await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)
        return

    if data.startswith("quick_price|"):
        if uid == ADMIN_ID:
            code = data.split("|")[1]
            context.user_data["admin_state"] = "set_price_ep"
            context.user_data["price_movie_code"] = code
            await q.answer()
            await sm(context.bot, uid, "Qism raqamini kiriting:")
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)
        return

    await q.answer()


async def cb_check_sub(update, context):
    q = update.callback_query
    await q.answer("Tekshirilmoqda...")
    ns = await check_subscription(q.from_user.id, context.bot)
    if ns:
        await q.answer("Hali obuna bo'lmagansiz!", show_alert=True)
        return
    try:
        await q.edit_message_text("âœ… Barcha kanallarga obuna bo'ldingiz!")
    except Exception:
        pass
    pending = context.user_data.pop("pending_code", None)
    if pending:
        await send_movie_menu(q, context, pending)
    else:
        await sm(context.bot, q.from_user.id,
            f"Xush kelibsiz, <b>{q.from_user.full_name}</b>!\nKino kodini yuboring.",
            main_menu_kb(is_admin=(q.from_user.id == ADMIN_ID)))

async def cb_episode(update, context):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    if len(parts) != 3:
        await q.answer("Xato", show_alert=True); return
    _, code, ep = parts
    movie = DB["movies"].get(code)
    if not movie:
        await q.answer("Kino topilmadi", show_alert=True); return
    user_id = str(q.from_user.id)
    price = movie.get("prices", {}).get(ep)
    paid = DB["users"].get(user_id, {}).get("paid_episodes", {})

    if price and not paid.get(f"{code}_{ep}"):
        card = DB.get("card_number") or "Admin karta raqamini o'rnatmagan"
        txt = (f"<b>ðŸ’° Bu qism pullik</b>\n\nKino: <b>{movie.get('title')}</b>\n"
               f"Qism: <b>{ep}</b>\nNarxi: <b>{price} so'm</b>\n\n"
               f"ðŸ’³ Karta raqami:\n<code>{card}</code>\n\n"
               f"To'lov qiling va chek <b>rasmini</b> yuboring.")
        context.user_data["awaiting_check"] = {"code": code, "ep": ep, "price": price}
        await sm(context.bot, q.from_user.id, txt, payment_sent_kb())
        return

    idx = int(ep) - 1
    eps = movie.get("episodes", [])
    if idx < 0 or idx >= len(eps):
        await q.answer("Qism topilmadi", show_alert=True); return

    movie.setdefault("views", {})
    movie["views"][ep] = movie["views"].get(ep, 0) + 1
    DB["users"].setdefault(user_id, {}).setdefault("watched", {})[f"{code}_{ep}"] = True
    DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
    save()

    bot_me = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption = (f"<b>ðŸŽ¬ {movie.get('title')}</b>\n"
               f"Qism: <b>{ep}</b>\nKo'rishlar: <b>{movie['views'][ep]}</b>")
    await sv(context.bot, q.from_user.id, eps[idx], caption, share_kb(share_url))

async def cb_payment(update, context):
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
                (q.message.caption or "") + "\n\n<b>âŒ Bekor qilindi</b>",
                parse_mode="HTML")
        except Exception:
            pass
        await sm(context.bot, pay["user_id"], "<b>âŒ To'lovingiz rad etildi.</b>")
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
            (q.message.caption or "") + "\n\n<b>âœ… Tasdiqlandi</b>",
            parse_mode="HTML")
    except Exception:
        pass

    # DARHOL yuboriladi
    await sm(context.bot, pay["user_id"], "<b>âœ… To'lov tasdiqlandi!</b>")

    movie = DB["movies"].get(pay["code"])
    if movie:
        idx = int(pay["ep"]) - 1
        eps = movie.get("episodes", [])
        if 0 <= idx < len(eps):
            movie.setdefault("views", {})
            movie["views"][pay["ep"]] = movie["views"].get(pay["ep"], 0) + 1
            DB["users"][uid].setdefault("watched", {})[f"{pay['code']}_{pay['ep']}"] = True
            DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
            save()
            try:
                await sv(context.bot, pay["user_id"], eps[idx],
                    f"<b>ðŸŽ¬ {movie.get('title')}</b>\nQism: {pay['ep']}")
            except Exception as e:
                logger.error(f"send paid video: {e}")

async def cb_reply(update, context):
    q = update.callback_query
    await q.answer()
    _, uid = q.data.split("|")
    context.user_data["reply_to"] = int(uid)
    await q.message.reply_text(f"<code>{uid}</code> ga xabar yozing.", parse_mode="HTML")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# BROADCAST â€” copy_message premium emojini saqlaydi
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def broadcast_send_to_all(context, src_chat_id, src_message_id, inline_btns):
    users = list(DB.get("users", {}).keys())
    total = len(users)
    success = failed = blocked = 0

    reply_markup = None
    if inline_btns:
        rows = [[InlineKeyboardButton(t, url=u)] for (t, u) in inline_btns]
        reply_markup = InlineKeyboardMarkup(rows)

    progress_msg = await sm(context.bot, ADMIN_ID,
        f"ðŸ“¢ Broadcast boshlandi...\nJami: <b>{total}</b>")

    for i, uid in enumerate(users, 1):
        try:
            await context.bot.copy_message(
                chat_id=int(uid),
                from_chat_id=src_chat_id,
                message_id=src_message_id,
                reply_markup=reply_markup,
            )
            success += 1
        except TelegramError as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err:
                blocked += 1
            else:
                failed += 1
                logger.warning(f"Broadcast {uid}: {e}")
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast {uid}: {e}")

        await asyncio.sleep(0.04)

        if i % 25 == 0 or i == total:
            try:
                await context.bot.edit_message_text(
                    chat_id=ADMIN_ID,
                    message_id=progress_msg.message_id,
                    text=(f"ðŸ“¢ Broadcast: <b>{i}/{total}</b>\n"
                          f"âœ… Yuborildi: {success}\n"
                          f"ðŸš« Bloklagan: {blocked}\n"
                          f"âŒ Xato: {failed}"),
                    parse_mode="HTML")
            except Exception:
                pass

    await sm(context.bot, ADMIN_ID,
        f"<b>âœ… Broadcast tugadi!</b>\n\n"
        f"Jami: <b>{total}</b>\n"
        f"âœ… Yuborildi: <b>{success}</b>\n"
        f"ðŸš« Bloklagan: <b>{blocked}</b>\n"
        f"âŒ Xato: <b>{failed}</b>")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TEXT HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = (update.message.text or "").strip()

    # 0. BROADCAST rejimi
    if uid == ADMIN_ID and context.user_data.get("broadcast"):
        bc = context.user_data["broadcast"]
        stage = bc.get("stage", "wait_msg")

        if text == "âŒ Bekor qilish":
            context.user_data.pop("broadcast", None)
            await sm(context.bot, uid, "Broadcast bekor qilindi.", admin_menu_kb())
            return

        if stage == "wait_btn_text":
            bc["pending_btn_text"] = text
            bc["stage"] = "wait_btn_url"
            await sm(context.bot, uid, "Endi tugma <b>linkini</b> yuboring (https://...):")
            return

        if stage == "wait_btn_url":
            if not (text.startswith("http://") or text.startswith("https://") or text.startswith("tg://")):
                await sm(context.bot, uid, "âŒ Link http(s):// yoki tg:// bilan boshlanishi kerak. Qayta yuboring:")
                return
            bc.setdefault("buttons", []).append((bc.pop("pending_btn_text"), text))
            bc["stage"] = "wait_action"
            btns = "\n".join([f"â€¢ {t} â†’ {u}" for t, u in bc["buttons"]])
            await sm(context.bot, uid,
                f"âœ… Tugma qo'shildi.\n\n<b>Tugmalar:</b>\n{btns}\n\n"
                f"Yana tugma qo'shasizmi yoki âœ… Yuborish bosing.",
                broadcast_menu_kb(has_msg=True, has_buttons=True))
            return

        if text == "âž• Tugma qo'shish":
            if not bc.get("msg"):
                await sm(context.bot, uid, "âš ï¸ Avval xabar (matn/rasm/video) yuboring.")
                return
            bc["stage"] = "wait_btn_text"
            await sm(context.bot, uid, "Tugma <b>nomini</b> yuboring:")
            return

        if text == "ðŸ—‘ Tugmalarni o'chirish":
            bc["buttons"] = []
            await sm(context.bot, uid, "Barcha tugmalar o'chirildi.",
                broadcast_menu_kb(has_msg=bool(bc.get("msg")), has_buttons=False))
            return

        if text == "âœ… Yuborish":
            if not bc.get("msg"):
                await sm(context.bot, uid, "âš ï¸ Avval xabar yuboring!")
                return
            msg_info = bc["msg"]
            buttons = bc.get("buttons") or None
            context.user_data.pop("broadcast", None)
            await sm(context.bot, uid, "ðŸ“¢ Yuborish boshlandi...", admin_menu_kb())
            asyncio.create_task(broadcast_send_to_all(
                context, msg_info["chat_id"], msg_info["message_id"], buttons))
            return

        # Aks holda â€” matnli xabarni saqlash
        if stage in ("wait_msg", "wait_action"):
            bc["msg"] = {
                "chat_id": update.message.chat_id,
                "message_id": update.message.message_id,
            }
            bc["stage"] = "wait_action"
            await sm(context.bot, uid,
                "âœ… Xabar saqlandi.\n\n"
                "Endi:\n"
                "â€¢ âž• Tugma qo'shish â€” nom va link\n"
                "â€¢ âœ… Yuborish â€” barcha foydalanuvchilarga\n"
                "â€¢ âŒ Bekor qilish",
                broadcast_menu_kb(has_msg=True, has_buttons=bool(bc.get("buttons"))))
            return

    # 1. editing_btn_key â€” admin tugma matnini o'zgartirmoqda
    if uid == ADMIN_ID and context.user_data.get("editing_btn_key"):
        key = context.user_data.pop("editing_btn_key")
        if not text:
            await sm(context.bot, uid, "Bo'sh bo'lmasin. Qayta yuboring:")
            context.user_data["editing_btn_key"] = key
            return

        existing = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
        existing_label = strip_emoji_prefix(existing) or DEFAULT_BTN.get(key, "")
        existing_emoji = extract_emoji_prefix(existing)

        if is_only_emoji(text):
            new_emoji = (existing_emoji + text) if existing_emoji else text
            new_text = f"{new_emoji} {existing_label}".strip()
        else:
            new_text = text

        DB.setdefault("btn_texts", {})[key] = new_text
        save()
        await sm(context.bot, uid,
            f"âœ… <b>{BTN_LABELS.get(key, key)}</b> yangilandi!\n"
            f"Ko'rinish: <code>{new_text}</code>")
        context.user_data["emoji_menu"] = True
        await sm(context.bot, uid, "Tugmani tanlang:", emoji_menu_kb())
        return

    # 2. Emoji menyu
    if uid == ADMIN_ID and context.user_data.get("emoji_menu"):
        if text == "â¬…ï¸ Orqaga":
            context.user_data.pop("emoji_menu", None)
            context.user_data.pop("editing_btn_key", None)
            await sm(context.bot, uid, "âš™ï¸ Admin panel", admin_menu_kb())
            return
        if text == "ðŸ—‘ Hammasini tiklash":
            DB["btn_texts"] = {}
            save()
            await sm(context.bot, uid, "âœ… Barcha tugmalar tiklandi!", emoji_menu_kb())
            return
        # BTN_LABELS dan key topish
        key = None
        if text in LABEL_TO_KEY:
            key = LABEL_TO_KEY[text]
        if key:
            cur = DB.get("btn_texts", {}).get(key) or DEFAULT_BTN.get(key, "")
            context.user_data["editing_btn_key"] = key
            await sm(context.bot, uid,
                f"<b>{BTN_LABELS.get(key, key)}</b>\n\n"
                f"Hozirgi: <code>{cur}</code>\n\n"
                f"Yangi matn yoki emoji yuboring:\n"
                f"â€¢ Faqat emoji â†’ qo'shiladi\n"
                f"â€¢ Matn â†’ to'liq almashadi",
                emoji_single_action_kb(key))
            return
        return

    # 3. Admin reply_to
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>ðŸ“© Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "âœ… Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"âŒ Xato: {e}")
        return

    # 4. Admin tugmalari
    all_admin_btns = {bt(k) for k in [
        "kino_joy", "qism_qosh", "pullik", "stat",
        "kanal_post", "maj_kanal", "karta", "ilova",
        "emoji_soz", "broadcast", "asosiy", "boshqarish"
    ]}
    if uid == ADMIN_ID and text in all_admin_btns:
        if text == bt("emoji_soz"):
            clear_admin_state(context)
            context.user_data["emoji_menu"] = True
            await sm(context.bot, uid,
                "<b>ðŸŽ¨ Tugma sozlamalari</b>\n"
                "O'zgartirmoqchi bo'lgan tugmani pastdan tanlang ðŸ‘‡",
                emoji_menu_kb())
            return

        if text == bt("broadcast"):
            clear_admin_state(context)
            context.user_data["broadcast"] = {"stage": "wait_msg", "buttons": []}
            await sm(context.bot, uid,
                "<b>ðŸ“¢ Hammaga xabar yuborish</b>\n\n"
                "Yubormoqchi bo'lgan xabarni jo'nating:\n"
                "â€¢ Matn (premium emoji bilan)\n"
                "â€¢ Rasm + matn\n"
                "â€¢ Video + matn\n"
                "â€¢ Sticker / hujjat / GIF\n\n"
                "Xabar QANDAY yuborilsa, foydalanuvchilarga ham SHUNDAY yetadi "
                "(premium emoji ham saqlanadi).",
                broadcast_menu_kb(has_msg=False, has_buttons=False))
            return

        context.user_data.pop("emoji_menu", None)
        context.user_data.pop("editing_btn_key", None)
        await admin_buttons(update, context, text)
        return

    # 5. Foydalanuvchi tugmalari
    if text == bt("yordam"):
        await sm(context.bot, uid,
            "<b>ðŸ†˜ Yordam</b>\n\n"
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
            await sv(context.bot, uid, v_id, "<b>ðŸ“² Ilovani o'rnatish videosi</b>")
        if f_id:
            await context.bot.send_document(
                uid, f_id, caption="<b>ðŸ“ Ilova fayli</b>", parse_mode="HTML")
        return

    # 6. Admin holat
    if uid == ADMIN_ID:
        handled = await admin_state_handler(update, context, text)
        if handled:
            return

    # 7. Yordam so'rovi
    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>ðŸ†˜ Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        await sm(context.bot, ADMIN_ID, cap + text, reply_admin_kb(uid))
        await sm(context.bot, uid, "âœ… Xabaringiz adminga yuborildi!")
        return

    # 8. To'lov cheki kutilmoqda
    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos, chek <b>rasmini</b> yuboring.")
        return

    # 9. Kino kodi qidirish
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
        await sm(context.bot, uid, "âŒ Kino kodi topilmadi.\nTo'g'ri kodni yuboring.")


async def admin_buttons(update, context, text):
    uid = update.effective_user.id

    if text == bt("boshqarish"):
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "<b>âš™ï¸ Admin panel</b>", admin_menu_kb())
        return
    if text == bt("asosiy"):
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "ðŸ  Asosiy menyu", main_menu_kb(is_admin=True))
        return
    if text == bt("stat"):
        context.user_data.pop("admin_state", None)
        u = len(DB.get("users", {}))
        m = len(DB.get("movies", {}))
        v = DB.get("stats", {}).get("total_views", 0)
        await sm(context.bot, uid,
            f"<b>ðŸ“Š Statistika</b>\n\nFoydalanuvchilar: <b>{u}</b>\n"
            f"Kinolar: <b>{m}</b>\nJami ko'rishlar: <b>{v}</b>", stats_kb())
        return
    if text == bt("karta"):
        context.user_data["admin_state"] = "set_card"
        cur = DB.get("card_number") or "Kiritilmagan"
        await sm(context.bot, uid,
            f"ðŸ’³ Joriy karta: <code>{cur}</code>\n\nYangi karta raqamini yuboring:")
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
            "Kanal username, nomi va linkini yuboring:\n"
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
        await sm(context.bot, uid, f"âœ… Karta saqlandi: <code>{text}</code>")
        return True

    if state == "add_movie_code":
        context.user_data["new_movie_code"] = text.upper()
        context.user_data["admin_state"] = "add_movie_title"
        await sm(context.bot, uid, "Kino nomini kiriting:")
        return True

    if state == "add_movie_title":
        code = context.user_data.get("new_movie_code")
        DB["movies"][code] = {"title": text, "episodes": [], "prices": {}}
        save()
        context.user_data.pop("admin_state")
        context.user_data.pop("new_movie_code", None)
        await sm(context.bot, uid,
            f"âœ… <b>{text}</b> kinosi qo'shildi!\nKod: <code>{code}</code>",
            movie_added_kb(code))
        return True

    if state == "add_ep_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "âŒ Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["ep_movie_code"] = code
        context.user_data["admin_state"] = "add_ep_video"
        await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        return True

    if state == "set_price_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "âŒ Bunday kod yo'q.")
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
        DB["movies"][code].setdefault("prices", {})[ep] = text
        save()
        context.user_data.pop("admin_state")
        context.user_data.pop("price_movie_code", None)
        context.user_data.pop("price_ep", None)
        await sm(context.bot, uid, f"âœ… {code} â€” {ep}-qism narxi: <b>{text} so'm</b>")
        return True

    if state == "add_channel":
        try:
            parts = [p.strip() for p in text.split("|")]
            uname, title, url = parts[0], parts[1], parts[2]
            DB["channels"].append({"username": uname, "title": title, "url": url})
            save()
            await sm(context.bot, uid, f"âœ… Kanal qo'shildi: <b>{title}</b>")
        except Exception:
            await sm(context.bot, uid,
                "âŒ Format xato!\n<code>@username | Kanal nomi | https://t.me/username</code>")
        context.user_data.pop("admin_state")
        return True

    if state == "post_channel_code":
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "âŒ Bunday kod yo'q.")
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
        caption = (f"<b>ðŸŽ¬ {movie.get('title', code)}</b>\n\n"
                   f"Qismlar soni: <b>{len(movie.get('episodes', []))}</b>\n\n"
                   f"Tomosha qilish uchun tugmani bosing!")
        poster = movie.get("poster_file_id")
        try:
            if poster:
                await sp(context.bot, channel, poster, caption, markup)
            else:
                await sm(context.bot, channel, caption, markup)
            await sm(context.bot, uid, "âœ… Post yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"âŒ Xato: {e}")
        context.user_data.pop("admin_state")
        context.user_data.pop("post_code", None)
        return True

    if state == "set_install":
        await sm(context.bot, uid, "âš ï¸ Iltimos, matn emas â€” <b>fayl yoki video</b> yuboring:")
        return True

    if state == "add_ep_video":
        await sm(context.bot, uid, "âš ï¸ Iltimos, matn emas â€” <b>video fayl</b> yuboring:")
        return True

    return False

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# STICKER HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def sticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return

    # Broadcast rejimida sticker â€” xabar sifatida saqlash
    if context.user_data.get("broadcast"):
        bc = context.user_data["broadcast"]
        bc["msg"] = {
            "chat_id": update.message.chat_id,
            "message_id": update.message.message_id,
        }
        bc["stage"] = "wait_action"
        await sm(context.bot, uid,
            "âœ… Sticker saqlandi.\nEndi âž• Tugma qo'shish yoki âœ… Yuborish.",
            broadcast_menu_kb(has_msg=True, has_buttons=bool(bc.get("buttons"))))
        return

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MEDIA HANDLER
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    msg = update.message
    state = context.user_data.get("admin_state")

    # BROADCAST media
    if uid == ADMIN_ID and context.user_data.get("broadcast"):
        bc = context.user_data["broadcast"]
        bc["msg"] = {
            "chat_id": msg.chat_id,
            "message_id": msg.message_id,
        }
        bc["stage"] = "wait_action"
        await sm(context.bot, uid,
            "âœ… Media saqlandi.\nEndi âž• Tugma qo'shish yoki âœ… Yuborish.",
            broadcast_menu_kb(has_msg=True, has_buttons=bool(bc.get("buttons"))))
        return

    if uid == ADMIN_ID and state == "add_ep_video":
        code = context.user_data.get("ep_movie_code")
        if msg.video:
            DB["movies"][code]["episodes"].append(msg.video.file_id)
            save()
            ep_num = len(DB["movies"][code]["episodes"])
            context.user_data.pop("admin_state")
            context.user_data.pop("ep_movie_code", None)
            await sm(context.bot, uid,
                f"âœ… <b>{ep_num}-qism</b> saqlandi!\nKino: <code>{code}</code>",
                movie_added_kb(code))
        else:
            await sm(context.bot, uid, "âš ï¸ Faqat video yuboring!")
        return

    if uid == ADMIN_ID and state == "set_install":
        if msg.video:
            DB["settings"]["install_video_id"] = msg.video.file_id
            save()
            context.user_data.pop("admin_state")
            await sm(context.bot, uid, "âœ… O'rnatish videosi saqlandi!")
        elif msg.document:
            DB["settings"]["install_file_id"] = msg.document.file_id
            save()
            context.user_data.pop("admin_state")
            await sm(context.bot, uid, "âœ… O'rnatish fayli saqlandi!")
        else:
            await sm(context.bot, uid, "âš ï¸ Video yoki fayl yuboring!")
        return

    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info = context.user_data.pop("awaiting_check")
        pid = f"{uid}_{pay_info['code']}_{pay_info['ep']}_{int(time.time())}"
        DB["pending_payments"][pid] = {
            "user_id": uid, "code": pay_info["code"],
            "ep": pay_info["ep"], "price": pay_info["price"], "status": "pending"
        }
        save()
        cap = (f"<b>ðŸ’³ To'lov cheki</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\nKino: <b>{pay_info['code']}</b>\n"
               f"Qism: <b>{pay_info['ep']}</b>\nNarx: <b>{pay_info['price']} so'm</b>")
        await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, payment_admin_kb(pid))
        await sm(context.bot, uid, "âœ… Chek adminga yuborildi! Tasdiqlanishini kuting.")
        return

    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>ðŸ†˜ Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        if msg.photo:
            await sp(context.bot, ADMIN_ID, msg.photo[-1].file_id, cap, reply_admin_kb(uid))
        elif msg.video:
            await sv(context.bot, ADMIN_ID, msg.video.file_id, cap, reply_admin_kb(uid))
        await sm(context.bot, uid, "âœ… Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            if msg.photo:
                await sp(context.bot, target, msg.photo[-1].file_id, "<b>ðŸ“© Admin javobi</b>")
            elif msg.video:
                await sv(context.bot, target, msg.video.file_id, "<b>ðŸ“© Admin javobi</b>")
            await sm(context.bot, uid, "âœ… Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"âŒ Xato: {e}")

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# MAIN
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def main():
    _start_save_thread()
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Sticker.ALL, sticker_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.ANIMATION,
        media_handler))
    logger.info("Bot ishga tushdi! ðŸš€")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
