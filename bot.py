# -*- coding: utf-8 -*-
"""
Kino Bot - v5
O'ZGARISHLAR:
1. Broadcast — xabar o'sha shaklida yuboriladi (copy_message ishlatiladi)
2. Tugma rangi — haqiqiy rang (emoji yo'q, InlineKeyboardButton)
3. Kino o'chirish — faqat kod kiritib o'chirish (ro'yxat yo'q)
"""
import logging, asyncio, json, time, re
from datetime import datetime
import requests
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

BOT_TOKEN       = "8723400610:AAGID66k5tFnpZZtpZRaSL3h9czRNCkLE1I"
ADMIN_ID        = 8537782289
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

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
}

LABEL_TO_KEY = {v: k for k, v in BTN_LABELS.items()}

DEFAULT_DB = {
    "users": {}, "movies": {}, "channels": [], "card_number": "",
    "pending_payments": {},
    "settings": {"install_file_id": None, "install_video_id": None},
    "stats": {"total_views": 0},
    "btn_texts": {},
}

EMOJI_IDS: dict = {}

# ══════════════════════════════════════════════════════════
# DB
# ══════════════════════════════════════════════════════════

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
                data.pop("btn_emoji_ids", None)
                logger.info(f"Yuklandi: {len(data.get('users', {}))} user, {len(data.get('movies', {}))} kino")
                return data
        except Exception as e:
            logger.error(f"DB load #{attempt+1}: {e}")
            if attempt < 2:
                time.sleep(2)
    return json.loads(json.dumps(DEFAULT_DB))

async def db_save_async(data):
    payload = json.dumps(data, ensure_ascii=False)
    headers = {
        "X-Master-Key": JSONBIN_API_KEY,
        "Content-Type": "application/json",
        "X-Bin-Versioning": "false"
    }
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(JSONBIN_URL, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        logger.info("DB saqlandi ✓")
                        return True
        except Exception as e:
            logger.error(f"DB async save #{attempt+1}: {e}")
            if attempt < 2:
                await asyncio.sleep(1)
    return False

def db_save(data):
    for attempt in range(3):
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
        except Exception as e:
            logger.error(f"DB save #{attempt+1}: {e}")
            if attempt < 2:
                time.sleep(1)
    return False

DB = db_load()

def save():
    asyncio.ensure_future(db_save_async(DB))

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
# TUGMA YARATISH — oddiy InlineKeyboardButton (style yo'q)
# ══════════════════════════════════════════════════════════

def ibtn(text, data=None, url=None):
    """Oddiy InlineKeyboardButton"""
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=data)

def ikb(rows):
    return InlineKeyboardMarkup(rows)

# Reply keyboard (oddiy)
from telegram import ReplyKeyboardMarkup, KeyboardButton

def rbtn(text):
    return KeyboardButton(text)

def rkb(rows, resize=True):
    return ReplyKeyboardMarkup(rows, resize_keyboard=resize)

# ══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ══════════════════════════════════════════════════════════

def main_menu_kb(is_admin=False):
    rows = [[rbtn(bt("yordam")), rbtn(bt("install"))]]
    if is_admin:
        rows.append([rbtn(bt("boshqarish"))])
    return rkb(rows)

def admin_menu_kb():
    return rkb([
        [rbtn(bt("kino_joy")),   rbtn(bt("qism_qosh"))],
        [rbtn(bt("pullik")),     rbtn(bt("stat"))],
        [rbtn(bt("kanal_post")), rbtn(bt("maj_kanal"))],
        [rbtn(bt("karta")),      rbtn(bt("ilova"))],
        [rbtn(bt("emoji_soz"))],
        [rbtn(bt("kino_uch")),   rbtn(bt("broadcast"))],
        [rbtn(bt("asosiy"))],
    ])

def subscription_kb(channels):
    rows = [[ibtn(c['title'], url=c["url"])] for c in channels]
    rows.append([ibtn(bt("tekshir"), data="check_sub")])
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
            rows.append([ibtn(f"🔒 {ek}-qism  {price} so'm", data=f"ep|{code}|{ek}")])
        else:
            rows.append([ibtn(f"▶️ {ek}-qism", data=f"ep|{code}|{ek}")])
    return ikb(rows)

def payment_admin_kb(pid):
    return ikb([[
        ibtn("✅ " + bt("tasdiq"), data=f"pay_ok|{pid}"),
        ibtn("❌ " + bt("bekor"),  data=f"pay_no|{pid}"),
    ]])

def share_kb(url):
    return ikb([[ibtn("🔗 " + bt("ulash"), url=url)]])

def channel_post_kb(bot_username, code):
    return ikb([[ibtn("▶️ " + bt("tomosha"),
        url=f"https://t.me/{bot_username}?start=code_{code}")]])

def reply_admin_kb(uid):
    return ikb([[ibtn("↩️ " + bt("javob"), data=f"reply|{uid}")]])

def stats_kb():
    return ikb([[ibtn("🔄 " + bt("yangi"), data="refresh_stats")]])

def movie_added_kb(code):
    return ikb([[
        ibtn("➕ " + bt("qism_add"), data=f"quick_add_ep|{code}"),
        ibtn("💰 " + bt("narx_bel"), data=f"quick_price|{code}"),
    ]])

def payment_sent_kb():
    return ikb([[ibtn("⏳ " + bt("kut"), data="waiting_confirm")]])

def help_kb():
    return ikb([[ibtn("🏠 " + bt("bosh"), data="go_home")]])

def emoji_menu_kb():
    rows = []
    keys = list(BTN_LABELS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i+2]:
            eid = get_eid(key)
            label = BTN_LABELS.get(key, key)
            row.append(rbtn(label))
        rows.append(row)
    rows.append([rbtn("🗑 Hammasini tiklash")])
    rows.append([rbtn("⬅️ Orqaga")])
    return rkb(rows)

def emoji_single_action_kb(key):
    return ikb([
        [ibtn("🗑 Defaultga qaytarish", data=f"emoji_reset|{key}")],
        [ibtn("⬅️ Orqaga",              data="emoji_back")],
    ])

# ── Broadcast: rang tanlash (haqiqiy rang, emoji bilan nom) ──
def broadcast_color_kb():
    return ikb([
        [
            ibtn("🔵 Ko'k",   data="bc_color|blue"),
            ibtn("🔴 Qizil",  data="bc_color|red"),
            ibtn("🟢 Yashil", data="bc_color|green"),
        ],
        [ibtn("❌ Bekor", data="bc_cancel")],
    ])

def broadcast_preview_kb(has_btn: bool):
    rows = []
    rows.append([ibtn("➕ Tugma qo'shish", data="bc_add_btn")])
    if has_btn:
        rows.append([ibtn("🗑 Tugmani o'chirish", data="bc_remove_btn")])
    rows.append([
        ibtn("✅ Yuborish", data="bc_send"),
        ibtn("❌ Bekor",    data="bc_cancel"),
    ])
    return ikb(rows)

# ── Broadcast tugmasi — rang emoji bilan nomda ko'rsatiladi ──
def build_broadcast_btn(text: str, url: str, color: str) -> InlineKeyboardButton:
    """Rang emoji tugma nomida ko'rsatiladi"""
    color_emoji = {"blue": "🔵", "red": "🔴", "green": "🟢"}.get(color, "")
    display = f"{color_emoji} {text}" if color_emoji else text
    return InlineKeyboardButton(display, url=url)

def build_broadcast_markup(buttons: list) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    rows = []
    for b in buttons:
        rows.append([build_broadcast_btn(b["text"], b["url"], b.get("color", ""))])
    return InlineKeyboardMarkup(rows)

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

async def sv(bot, chat_id, video, caption, markup=None, pm="HTML"):
    kw = {"chat_id": chat_id, "video": video, "caption": caption, "parse_mode": pm}
    if markup:
        kw["reply_markup"] = markup
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
    markup = movie_episodes_kb(movie, code, user_id)
    caption = (f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
               f"📺 Qismlar soni: <b>{len(eps)} ta</b>\n\n"
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
                "bc_from_chat_id", "bc_from_msg_id"]:
        context.user_data.pop(key, None)

# ══════════════════════════════════════════════════════════
# BROADCAST — copy_message ishlatiladi (xabar o'zgarmaydi)
# ══════════════════════════════════════════════════════════

async def send_broadcast_preview(bot, uid, bc: dict):
    """Preview: copy_message yoki oddiy yuborish"""
    buttons = bc.get("buttons", [])
    markup = build_broadcast_markup(buttons)
    preview_kb = broadcast_preview_kb(bool(buttons))

    try:
        from_chat = bc.get("from_chat_id")
        from_msg  = bc.get("from_msg_id")

        if from_chat and from_msg:
            # Asl xabarni copy qilib yuborish
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=from_chat,
                message_id=from_msg,
                reply_markup=markup
            )
        else:
            # Fallback: oddiy yuborish
            if bc.get("type") == "text":
                await bot.send_message(uid, bc["text"], parse_mode="HTML",
                                       reply_markup=markup or InlineKeyboardMarkup([]))
            elif bc.get("type") == "photo":
                await bot.send_photo(uid, bc["file_id"],
                                     caption=bc.get("caption", ""), parse_mode="HTML",
                                     reply_markup=markup or InlineKeyboardMarkup([]))
            elif bc.get("type") == "video":
                await bot.send_video(uid, bc["file_id"],
                                     caption=bc.get("caption", ""), parse_mode="HTML",
                                     reply_markup=markup or InlineKeyboardMarkup([]))
    except Exception as e:
        await bot.send_message(uid, f"❌ Preview xato: {e}")
        return

    btn_info = ""
    if buttons:
        btn_info = "\n\n<b>Tugmalar:</b>\n" + "\n".join(
            f"• {b['text']} ({b.get('color','')}) → {b['url']}" for b in buttons)
    await bot.send_message(uid,
        f"<b>Preview yuqorida ↑</b>{btn_info}\n\nNima qilasiz?",
        parse_mode="HTML", reply_markup=preview_kb)

async def do_broadcast(bot, bc: dict):
    """Broadcast: copy_message bilan yuborish"""
    users = list(DB["users"].keys())
    buttons = bc.get("buttons", [])
    markup = build_broadcast_markup(buttons)
    from_chat = bc.get("from_chat_id")
    from_msg  = bc.get("from_msg_id")
    ok = 0
    fail = 0
    for uid in users:
        try:
            if from_chat and from_msg:
                # Asl xabarni nusxa qilib yuborish — FORWARD EMAS, nusxa
                await bot.copy_message(
                    chat_id=int(uid),
                    from_chat_id=from_chat,
                    message_id=from_msg,
                    reply_markup=markup
                )
            else:
                # Fallback
                if bc.get("type") == "text":
                    await bot.send_message(int(uid), bc["text"], parse_mode="HTML",
                                           reply_markup=markup)
                elif bc.get("type") == "photo":
                    await bot.send_photo(int(uid), bc["file_id"],
                                         caption=bc.get("caption", ""), parse_mode="HTML",
                                         reply_markup=markup)
                elif bc.get("type") == "video":
                    await bot.send_video(int(uid), bc["file_id"],
                                         caption=bc.get("caption", ""), parse_mode="HTML",
                                         reply_markup=markup)
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

    # ── Broadcast ──
    if data.startswith("bc_"):
        await cb_broadcast(update, context)
        return

    # ── Kino o'chirish ──
    if data.startswith("del_confirm|") or data == "del_movie_close":
        await cb_delete_movie(update, context)
        return

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
            await sm(context.bot, uid, f"<b>{code}</b> uchun video yuboring:")
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)

    elif data.startswith("quick_price|"):
        if uid == ADMIN_ID:
            code = data.split("|")[1]
            context.user_data["admin_state"] = "set_price_ep"
            context.user_data["price_movie_code"] = code
            await q.answer()
            await sm(context.bot, uid, "Qism raqamini kiriting:")
        else:
            await q.answer("Ruxsat yo'q", show_alert=True)

    else:
        await q.answer()


# ── Kino o'chirish callback — faqat tasdiqlash/bekor ──
async def cb_delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data

    if uid != ADMIN_ID:
        await q.answer("Ruxsat yo'q", show_alert=True)
        return
    await q.answer()

    if data == "del_movie_close":
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await sm(context.bot, uid, "Admin panel", admin_menu_kb())
        return

    if data.startswith("del_confirm|"):
        code = data.split("|")[1]
        if code in DB["movies"]:
            title = DB["movies"][code].get("title", code)
            del DB["movies"][code]
            save()
            try:
                await q.edit_message_text(
                    f"✅ <b>{title}</b> (<code>{code}</code>) o'chirildi!",
                    parse_mode="HTML")
            except Exception:
                pass
            await sm(context.bot, uid, "Admin panel", admin_menu_kb())
        else:
            await q.answer("Kino topilmadi", show_alert=True)
        return


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

    # ── Rang tanlash ──
    if data.startswith("bc_color|"):
        color = data.split("|")[1]
        bc["btn_color"] = color
        context.user_data["bc_msg"] = bc
        context.user_data["bc_adding_btn"] = "text"
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        color_names = {"blue": "🔵 Ko'k", "red": "🔴 Qizil", "green": "🟢 Yashil"}
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


async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
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
        await sv(context.bot, q.from_user.id, eps[idx], caption, share_kb(share_url))
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

    asyncio.ensure_future(update_stats())


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
            await sm(context.bot, pay["user_id"], "<b>Admin to'lovingizni tasdiqladi!</b>")
            await sv(context.bot, pay["user_id"], eps[idx],
                f"<b>{movie.get('title')}</b>\nQism: {pay['ep']}")
            async def update_pay_stats():
                movie.setdefault("views", {})
                movie["views"][pay["ep"]] = movie["views"].get(pay["ep"], 0) + 1
                DB["users"][uid].setdefault("watched", {})[f"{pay['code']}_{pay['ep']}"] = True
                DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
                await db_save_async(DB)
            asyncio.ensure_future(update_pay_stats())
    else:
        await sm(context.bot, pay["user_id"], "<b>Admin to'lovingizni tasdiqladi!</b>")


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
            eid_info = f"\nCustom emoji ID: <code>{custom_emoji_id}</code>"
        elif is_only_emoji(text):
            if existing_emoji_prefix:
                new_emoji_prefix = existing_emoji_prefix + text
            else:
                new_emoji_prefix = text
            new_text = f"{new_emoji_prefix} {existing_label}"
            EMOJI_IDS.pop(key, None)
            eid_info = ""
        else:
            new_text = text
            EMOJI_IDS.pop(key, None)
            eid_info = ""

        DB.setdefault("btn_texts", {})[key] = new_text
        save()
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
            color = bc.pop("btn_color", "")
            context.user_data.pop("bc_adding_btn", None)
            bc.setdefault("buttons", []).append({"text": btn_text_val, "url": text, "color": color})
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

    # ── 4. Admin reply_to ──
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await sm(context.bot, target, f"<b>Admin javobi:</b>\n{text}")
            await sm(context.bot, uid, "✅ Yuborildi!")
        except Exception as e:
            await sm(context.bot, uid, f"❌ Xato: {e}")
        return

    # ── 5. Broadcast rejimi ──
    if uid == ADMIN_ID and context.user_data.get("admin_state") == "broadcast_msg":
        # Matnli xabarni to'g'ridan-to'g'ri copy_message uchun saqlash
        bc = {
            "type": "text",
            "text": text,
            "buttons": [],
            "from_chat_id": msg.chat_id,
            "from_msg_id": msg.message_id,
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
        return

    # ── 6. Admin tugmalarini aniqlash ──
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
                "✅ Xabar <b>aynan o'sha ko'rinishda</b> yuboriladi.\n"
                "Bekor qilish uchun /start bosing.")
            context.user_data["admin_state"] = "broadcast_msg"
            return

        # ── Kino o'chirish — faqat kod kiritish ──
        if text == bt("kino_uch"):
            context.user_data.pop("admin_state", None)
            context.user_data.pop("emoji_menu", None)
            movies = DB.get("movies", {})
            if not movies:
                await sm(context.bot, uid, "❌ Hozircha kinolar yo'q.")
                return
            await sm(context.bot, uid,
                f"🗑 <b>Kino o'chirish</b>\n\n"
                f"Mavjud kinolar: <b>{len(movies)} ta</b>\n\n"
                f"O'chirmoqchi bo'lgan kinoning <b>kodini</b> kiriting:")
            context.user_data["admin_state"] = "delete_movie_code"
            return

        context.user_data.pop("emoji_menu", None)
        context.user_data.pop("editing_btn_key", None)
        await admin_buttons(update, context, text)
        return

    # ── 7. Foydalanuvchi tugmalari ──
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

    # ── 8. Admin holat handler ──
    if uid == ADMIN_ID:
        handled = await admin_state_handler(update, context, text)
        if handled:
            return

    # ── 9. Yordam so'rovi ──
    if context.user_data.get("awaiting_help"):
        context.user_data.pop("awaiting_help", None)
        cap = (f"<b>Yordam so'rovi</b>\n{user.full_name} (@{user.username or '-'})\n"
               f"<code>{uid}</code>\n\n")
        await sm(context.bot, ADMIN_ID, cap + text, reply_admin_kb(uid))
        await sm(context.bot, uid, "✅ Xabaringiz adminga yuborildi!")
        return

    # ── 10. To'lov cheki ──
    if context.user_data.get("awaiting_check"):
        await sm(context.bot, uid, "Iltimos, chek <b>rasmini</b> yuboring.")
        return

    # ── 11. Kino kodi ──
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
        await sm(context.bot, uid, "❌ Bunday kod topilmadi.\n\nTo'g'ri kino kodini yuboring 👇")


async def admin_buttons(update, context, text):
    uid = update.effective_user.id

    if text == bt("boshqarish"):
        context.user_data.pop("admin_state", None)
        await sm(context.bot, uid, "<b>Admin panel</b>", admin_menu_kb())
        return

    if text == bt("asosiy"):
        context.user_data.pop("admin_state", None)
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
    msg = update.message
    if not state:
        return False

    # ── Kino o'chirish — kod kiritish ──
    if state == "delete_movie_code":
        code = text.upper().strip()
        movies = DB.get("movies", {})
        if code not in movies:
            # Topilmadi — mavjud kinolarni ko'rsatish
            lines = [f"❌ <b>{code}</b> kodli kino topilmadi.\n\nMavjud kinolar:"]
            for c, m in movies.items():
                lines.append(f"  • <code>{c}</code> — {m.get('title', '')}")
            lines.append("\nQayta kino kodini kiriting:")
            await sm(context.bot, uid, "\n".join(lines))
            return True
        # Topildi — tasdiqlash so'rash
        movie = movies[code]
        title = movie.get("title", code)
        eps = len(movie.get("episodes", []))
        added = movie.get("added_date", "—")
        await sm(context.bot, uid,
            f"⚠️ <b>Tasdiqlang</b>\n\n"
            f"🎬 <b>{title}</b>\n"
            f"📌 Kod: <code>{code}</code>\n"
            f"📺 Qismlar: <b>{eps} ta</b>\n"
            f"📅 Qo'shilgan: <b>{added}</b>\n\n"
            f"O'chirishni tasdiqlaysizmi?",
            ikb([
                [ibtn("✅ Ha, o'chir", data=f"del_confirm|{code}"),
                 ibtn("❌ Bekor",       data="del_movie_close")],
            ]))
        context.user_data.pop("admin_state")
        return True

    if state == "broadcast_msg":
        # Matnli xabar — copy_message uchun saqlash
        bc = {
            "type": "text",
            "text": text,
            "buttons": [],
            "from_chat_id": msg.chat_id,
            "from_msg_id": msg.message_id,
        }
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
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
        context.user_data.pop("admin_state")
        context.user_data.pop("new_movie_code", None)
        await sm(context.bot, uid,
            f"✅ <b>{text}</b> kinosi qo'shildi!\nKod: <code>{code}</code>",
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
        code = text.upper()
        if code not in DB["movies"]:
            await sm(context.bot, uid, "❌ Bunday kod yo'q. Qayta kiriting yoki bekor qiling.")
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
        await sm(context.bot, uid, f"✅ {code} — {ep}-qism narxi: <b>{text} so'm</b>")
        return True

    if state == "add_channel":
        try:
            parts = [p.strip() for p in text.split("|")]
            uname, title, url = parts[0], parts[1], parts[2]
            DB["channels"].append({"username": uname, "title": title, "url": url})
            save()
            await sm(context.bot, uid, f"✅ Kanal qo'shildi: <b>{title}</b>")
        except Exception:
            await sm(context.bot, uid, "❌ Format xato!\n<code>@username | Kanal nomi | https://t.me/username</code>")
        context.user_data.pop("admin_state")
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
        caption = (f"<b>{movie.get('title', code)}</b>\n\n"
                   f"Qismlar soni: <b>{len(movie.get('episodes', []))}</b>\n\n"
                   f"Tomosha qilish uchun tugmani bosing!")
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

    # ── Broadcast rasm/video — copy_message uchun saqlash ──
    if uid == ADMIN_ID and state == "broadcast_msg":
        bc = {}
        if msg.photo:
            bc = {
                "type": "photo",
                "file_id": msg.photo[-1].file_id,
                "caption": msg.caption or "",
                "buttons": [],
                "from_chat_id": msg.chat_id,
                "from_msg_id": msg.message_id,
            }
        elif msg.video:
            bc = {
                "type": "video",
                "file_id": msg.video.file_id,
                "caption": msg.caption or "",
                "buttons": [],
                "from_chat_id": msg.chat_id,
                "from_msg_id": msg.message_id,
            }
        else:
            await sm(context.bot, uid, "⚠️ Faqat matn, rasm yoki video yuboring.")
            return
        context.user_data["bc_msg"] = bc
        context.user_data.pop("admin_state")
        await sm(context.bot, uid, "✅ Xabar qabul qilindi. Preview:")
        await send_broadcast_preview(context.bot, uid, bc)
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
    logger.info("Bot ishga tushdi! v5")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
