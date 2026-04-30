# -*- coding: utf-8 -*-
"""
🎬 Kino Bot — To'liq versiya
Fly.io + JSONBin | Bot API 9.4 rangli tugmalar + premium emoji
Admin paneldan emoji IDlarini o'zgartirish imkoniyati
"""

import logging, asyncio, json, os, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

import requests
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# ═══════════════════════ SOZLAMALAR ═══════════════════════
BOT_TOKEN       = "8622992113:AAHif8dJz3eq_Zm8PTafxpSiNsEqE5VmoMc"
ADMIN_ID        = 8537782289
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# ═══════════════ DEFAULT PREMIUM EMOJI IDlar ══════════════
DEFAULT_PE = {
    "film":    "5374062524014462236",  # 🎬
    "search":  "5373141891321699086",  # 🔍
    "help":    "5379748062124056162",  # 🆘
    "install": "5361540739737993513",  # 📥
    "home":    "5368324170671202286",  # 🏠
    "add":     "5373141891321699086",  # ➕
    "money":   "5361540739737993513",  # 💰
    "stats":   "5373141891321699086",  # 📊
    "post":    "5373141891321699086",  # 📢
    "lock":    "5361540739737993513",  # 🔒
    "card":    "5373141891321699086",  # 💳
    "phone":   "5373141891321699086",  # 📲
    "play":    "5373141891321699086",  # ▶️
    "share":   "5373141891321699086",  # 📤
    "check":   "5373141891321699086",  # ✅
    "reply":   "5373141891321699086",  # ✉️
    "watch":   "5373141891321699086",  # 🎬
    "emoji":   "5373141891321699086",  # 🎭
    "channel": "5373141891321699086",  # 📢
    "price":   "5361540739737993513",  # 💰
    "admin":   "5368324170671202286",  # 👑
    "back":    "5373141891321699086",  # ⬅️
    "close":   "5373141891321699086",  # ✅
    "reset":   "5361540739737993513",  # 🔄
}

PE_LABELS = {
    "film":    "🎬 Kino (film)",
    "search":  "🔍 Qidirish (search)",
    "help":    "🆘 Yordam (help)",
    "install": "📥 O'rnatish (install)",
    "home":    "🏠 Bosh menyu (home)",
    "add":     "➕ Qo'shish (add)",
    "money":   "💰 Pul (money)",
    "stats":   "📊 Statistika (stats)",
    "post":    "📢 Post (post)",
    "lock":    "🔒 Qulf (lock)",
    "card":    "💳 Karta (card)",
    "phone":   "📲 Telefon (phone)",
    "play":    "▶️ O'ynatish (play)",
    "share":   "📤 Ulashish (share)",
    "check":   "✅ Tasdiqlash (check)",
    "reply":   "✉️ Javob (reply)",
    "watch":   "🎬 Tomosha (watch)",
    "emoji":   "🎭 Emoji (emoji)",
    "channel": "📢 Kanal (channel)",
    "price":   "💰 Narx (price)",
    "admin":   "👑 Admin (admin)",
    "back":    "⬅️ Orqaga (back)",
    "close":   "✅ Yopish (close)",
    "reset":   "🔄 Tiklash (reset)",
}

# ═══════════════════════ LOGGING ══════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════ DATABASE ═════════════════════════
DEFAULT_DB = {
    "users":            {},
    "movies":           {},
    "channels":         [],
    "card_number":      "",
    "pending_payments": {},
    "settings":         {"install_file_id": None, "install_video_id": None},
    "stats":            {"total_views": 0},
    "emoji_ids":        {},
}

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
                logger.info(f"✅ Yuklandi: {len(data.get('users',{}))} user, {len(data.get('movies',{}))} kino")
                return data
        except Exception as e:
            logger.error(f"DB load #{attempt+1}: {e}")
    return json.loads(json.dumps(DEFAULT_DB))

def db_save(data):
    for attempt in range(3):
        try:
            r = requests.put(JSONBIN_URL,
                headers={"X-Master-Key": JSONBIN_API_KEY,
                         "Content-Type": "application/json",
                         "X-Bin-Versioning": "false"},
                data=json.dumps(data, ensure_ascii=False), timeout=20)
            if r.status_code == 200:
                return True
        except Exception as e:
            logger.error(f"DB save #{attempt+1}: {e}")
    return False

DB = db_load()

def save():
    ok = db_save(DB)
    if not ok:
        logger.error("❌ Saqlash muvaffaqiyatsiz!")
    return ok

# ═══════════════════ EMOJI ID OLISH ═══════════════════════
def pe(key: str) -> str:
    return DB.get("emoji_ids", {}).get(key) or DEFAULT_PE.get(key, "")

# ═══════════════════ TUGMA YORDAMCHISI ════════════════════
def ibtn(text, data=None, url=None, style=None, emoji_key=None):
    """
    InlineKeyboardButton — Bot API 9.4 rangli + premium emoji.
    style:     'primary'(ko'k) | 'success'(yashil) | 'danger'(qizil)
    emoji_key: PE lug'atidagi kalit
    """
    kwargs = {"text": text}
    if data:
        kwargs["callback_data"] = data
    if url:
        kwargs["url"] = url
    btn = InlineKeyboardButton(**kwargs)
    if style:
        try:
            btn.style = style
        except Exception:
            pass
    if emoji_key:
        eid = pe(emoji_key)
        if eid:
            try:
                btn.icon_custom_emoji_id = eid
            except Exception:
                pass
    return btn

# ═══════════════════ REPLY KLAVIATURALAR ══════════════════
def main_menu_kb():
    """
    Foydalanuvchi uchun asosiy menyu.
    Kino qidirish tugmasi YO'Q — faqat raqam yuborilsa kino chiqadi.
    """
    kb = [
        [KeyboardButton("🆘 Yordam"),
         KeyboardButton("📥 Ilovani o'rnatish")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def admin_menu_kb():
    kb = [
        [KeyboardButton("🎬 Kino joylash"),
         KeyboardButton("➕ Qism qo'shish")],
        [KeyboardButton("💰 Qismni pullik qilish"),
         KeyboardButton("📊 Statistika")],
        [KeyboardButton("📢 Kanalga post"),
         KeyboardButton("🔒 Majburiy kanal")],
        [KeyboardButton("💳 Karta raqami"),
         KeyboardButton("📲 Ilova fayl/video")],
        [KeyboardButton("🎭 Emoji sozlamalari")],
        [KeyboardButton("🏠 Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ═══════════════════ INLINE KLAVIATURALAR ═════════════════
def subscription_kb(channels):
    kb = [[ibtn(f"📢 {c['title']}", url=c["url"],
                style="primary", emoji_key="post")]
          for c in channels]
    kb.append([ibtn("✅ Tekshirish", data="check_sub",
                    style="success", emoji_key="check")])
    return InlineKeyboardMarkup(kb)

def movie_episodes_kb(movie, code, user_id):
    eps    = movie.get("episodes", [])
    prices = movie.get("prices", {})
    paid   = DB["users"].get(str(user_id), {}).get("paid_episodes", {})
    kb = []
    for i in range(len(eps)):
        ep_key    = str(i + 1)
        price     = prices.get(ep_key)
        is_locked = price and not paid.get(f"{code}_{ep_key}")
        if is_locked:
            label = f"🔒 {ep_key}-qism  💰 {price} so'm"
            style = "danger"
            ekey  = "lock"
        else:
            label = f"▶️ {ep_key}-qism"
            style = "success"
            ekey  = "play"
        kb.append([ibtn(label, data=f"ep|{code}|{ep_key}",
                        style=style, emoji_key=ekey)])
    return InlineKeyboardMarkup(kb)

def payment_admin_kb(pid):
    return InlineKeyboardMarkup([[
        ibtn("✅ Tasdiqlash",   data=f"pay_ok|{pid}",
             style="success", emoji_key="check"),
        ibtn("❌ Bekor qilish", data=f"pay_no|{pid}",
             style="danger",  emoji_key="lock"),
    ]])

def share_kb(share_url):
    return InlineKeyboardMarkup([[
        ibtn("📤 Do'stlarga ulashish", url=share_url,
             style="primary", emoji_key="share"),
    ]])

def channel_post_kb(bot_username, code):
    return InlineKeyboardMarkup([[
        ibtn("🎬 Tomosha qilish",
             url=f"https://t.me/{bot_username}?start=code_{code}",
             style="success", emoji_key="watch"),
    ]])

def reply_admin_kb(uid):
    return InlineKeyboardMarkup([[
        ibtn("✉️ Javob berish", data=f"reply|{uid}",
             style="primary", emoji_key="reply"),
    ]])

# ── Statistika inline KB ──
def stats_kb():
    return InlineKeyboardMarkup([[
        ibtn("🔄 Yangilash", data="refresh_stats",
             style="primary", emoji_key="stats"),
    ]])

# ── Kino qo'shildi KB ──
def movie_added_kb(code):
    return InlineKeyboardMarkup([[
        ibtn("📹 Qism qo'shish", data=f"quick_add_ep|{code}",
             style="success", emoji_key="add"),
        ibtn("💰 Narx belgilash", data=f"quick_price|{code}",
             style="primary", emoji_key="price"),
    ]])

# ── To'lov yuborildi KB (foydalanuvchi uchun) ──
def payment_sent_kb():
    return InlineKeyboardMarkup([[
        ibtn("⏳ Tasdiqlanishini kuting", data="waiting_confirm",
             style="primary", emoji_key="check"),
    ]])

# ── Yordam KB ──
def help_kb():
    return InlineKeyboardMarkup([[
        ibtn("🏠 Bosh menyu", data="go_home",
             style="success", emoji_key="home"),
    ]])

# ══════════════ EMOJI SOZLAMALARI KLAVIATURASI ═════════════
def emoji_list_kb():
    kb = []
    keys = list(PE_LABELS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for key in keys[i:i+2]:
            current = DB.get("emoji_ids", {}).get(key) or DEFAULT_PE.get(key, "")
            short   = f"…{current[-6:]}" if current else "yo'q"
            label   = f"{PE_LABELS[key]}  [{short}]"
            row.append(ibtn(label, data=f"emoji_edit|{key}",
                            style="primary", emoji_key="emoji"))
        kb.append(row)
    kb.append([ibtn("🔄 Hammasini tiklash", data="emoji_reset_all",
                    style="danger", emoji_key="reset")])
    kb.append([ibtn("✅ Yopish", data="emoji_close",
                    style="success", emoji_key="close")])
    return InlineKeyboardMarkup(kb)

def emoji_single_kb(key):
    current = DB.get("emoji_ids", {}).get(key) or DEFAULT_PE.get(key, "")
    default = DEFAULT_PE.get(key, "")
    kb = [
        [ibtn("🔄 Defaultga qaytarish", data=f"emoji_reset|{key}",
              style="danger", emoji_key="reset")],
        [ibtn("⬅️ Orqaga", data="emoji_back",
              style="success", emoji_key="back")],
    ]
    return InlineKeyboardMarkup(kb), current, default

# ═══════════════════ YORDAMCHI FUNKSIYALAR ════════════════
async def check_subscription(user_id: int, bot) -> list:
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
            "name":          user.full_name,
            "username":      user.username or "",
            "joined":        datetime.now().isoformat(),
            "paid_episodes": {},
            "watched":       {},
        }
        save()

async def send_movie_menu(src, context, code):
    movie = DB["movies"].get(code)
    if hasattr(src, "effective_user"):
        chat_id = src.effective_user.id
        user_id = src.effective_user.id
    else:
        chat_id = src.from_user.id
        user_id = src.from_user.id

    if not movie:
        txt = "❓ Bunday kodli kino topilmadi."
        try:
            if hasattr(src, "message") and src.message:
                await src.edit_message_text(txt)
            else:
                await context.bot.send_message(chat_id, txt)
        except Exception:
            await context.bot.send_message(chat_id, txt)
        return

    eps = movie.get("episodes", [])
    if not eps:
        await context.bot.send_message(chat_id, "⏳ Bu kinoga hali qism yuklanmagan.")
        return

    markup  = movie_episodes_kb(movie, code, user_id)
    caption = (
        f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
        f"📺 Qismlar soni: <b>{len(eps)}</b>\n\n"
        f"Qaysi qismni ko'rmoqchisiz? 👇"
    )
    poster = movie.get("poster_file_id")
    try:
        if poster:
            await context.bot.send_photo(chat_id=chat_id, photo=poster,
                caption=caption, parse_mode="HTML", reply_markup=markup)
        else:
            await context.bot.send_message(chat_id=chat_id, text=caption,
                parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logger.error(f"send_movie_menu: {e}")

# ═══════════════════════ /start ═══════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    args = context.args

    if args and args[0].startswith("code_"):
        code = args[0].replace("code_", "")
        not_subbed = await check_subscription(user.id, context.bot)
        if not_subbed:
            await update.message.reply_text(
                "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                reply_markup=subscription_kb(not_subbed))
            context.user_data["pending_code"] = code
            return
        await send_movie_menu(update, context, code)
        return

    not_subbed = await check_subscription(user.id, context.bot)
    if not_subbed:
        await update.message.reply_text(
            "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_kb(not_subbed))
        return

    hello = (
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        f"🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
        f"🔢 Kino <b>raqamini</b> yuboring — video darhol chiqadi.\n\n"
        f"👇 Quyidagi tugmalardan foydalaning:"
    )
    await update.message.reply_text(hello, parse_mode="HTML",
        reply_markup=main_menu_kb())
    if user.id == ADMIN_ID:
        await update.message.reply_text("👑 <b>Admin panel</b>",
            parse_mode="HTML", reply_markup=admin_menu_kb())

# ══════════════ EMOJI SOZLAMALARI CALLBACK ═════════════════
async def cb_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    if data == "emoji_back":
        await q.edit_message_text(
            "🎭 <b>Emoji sozlamalari</b>\n\n"
            "O'zgartirmoqchi bo'lgan emoji tugmasini tanlang.\n"
            "<i>Qavs ichida — joriy ID ning oxirgi 6 raqami</i>",
            parse_mode="HTML",
            reply_markup=emoji_list_kb())
        return

    if data == "emoji_close":
        await q.edit_message_text("✅ Emoji sozlamalari yopildi.")
        return

    if data == "emoji_reset_all":
        DB["emoji_ids"] = {}
        save()
        await q.edit_message_text(
            "🔄 <b>Barcha emoji IDlar default ga qaytarildi!</b>",
            parse_mode="HTML",
            reply_markup=emoji_list_kb())
        return

    if data.startswith("emoji_reset|"):
        key = data.split("|")[1]
        DB["emoji_ids"].pop(key, None)
        save()
        markup, current, default = emoji_single_kb(key)
        await q.edit_message_text(
            f"🔄 <b>{PE_LABELS.get(key, key)}</b> default ga qaytarildi!\n\n"
            f"📌 Default ID:\n<code>{default}</code>",
            parse_mode="HTML", reply_markup=markup)
        return

    if data.startswith("emoji_edit|"):
        key = data.split("|")[1]
        markup, current, default = emoji_single_kb(key)
        context.user_data["editing_emoji_key"] = key
        await q.edit_message_text(
            f"✏️ <b>{PE_LABELS.get(key, key)}</b>\n\n"
            f"📌 Joriy ID:\n<code>{current}</code>\n\n"
            f"📎 Default ID:\n<code>{default}</code>\n\n"
            f"🔽 Yangi premium emoji IDni yuboring\n"
            f"<i>(Emoji IDni @getidsbot orqali topish mumkin)</i>",
            parse_mode="HTML", reply_markup=markup)
        return

# ════════════════════ CALLBACK HANDLERLAR ═════════════════
async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    not_subbed = await check_subscription(q.from_user.id, context.bot)
    if not_subbed:
        await q.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)
        return
    await q.edit_message_text("✅ Barcha kanallarga obuna bo'ldingiz!")
    pending = context.user_data.pop("pending_code", None)
    if pending:
        await send_movie_menu(q, context, pending)
    else:
        await context.bot.send_message(q.from_user.id,
            f"👋 Xush kelibsiz, <b>{q.from_user.full_name}</b>!\n"
            f"🔢 Kino raqamini yuboring.",
            parse_mode="HTML", reply_markup=main_menu_kb())

async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    if len(parts) != 3:
        await q.answer("❌ Xato", show_alert=True)
        return
    _, code, ep = parts
    movie = DB["movies"].get(code)
    if not movie:
        await q.answer("❌ Kino topilmadi", show_alert=True)
        return

    user_id = str(q.from_user.id)
    price   = movie.get("prices", {}).get(ep)
    paid    = DB["users"].get(user_id, {}).get("paid_episodes", {})

    if price and not paid.get(f"{code}_{ep}"):
        card = DB.get("card_number") or "Admin karta raqamini o'rnatmagan"
        txt  = (
            f"💰 <b>Bu qism pullik</b>\n\n"
            f"🎬 Kino: <b>{movie.get('title')}</b>\n"
            f"🎞 Qism: <b>{ep}</b>\n"
            f"💵 Narxi: <b>{price} so'm</b>\n\n"
            f"💳 Karta raqami:\n<code>{card}</code>\n\n"
            f"To'lov qiling va chek rasmini yuboring 📸"
        )
        context.user_data["awaiting_check"] = {"code": code, "ep": ep, "price": price}
        await q.message.reply_text(txt, parse_mode="HTML",
            reply_markup=payment_sent_kb())
        return

    idx = int(ep) - 1
    eps = movie.get("episodes", [])
    if idx < 0 or idx >= len(eps):
        await q.answer("❌ Qism topilmadi", show_alert=True)
        return

    movie.setdefault("views", {})
    movie["views"][ep] = movie["views"].get(ep, 0) + 1
    DB["users"].setdefault(user_id, {}).setdefault("watched", {})[f"{code}_{ep}"] = True
    DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
    save()

    bot_me    = await context.bot.get_me()
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption   = (
        f"🎬 <b>{movie.get('title')}</b>\n"
        f"🎞 Qism: <b>{ep}</b>\n"
        f"👁 Ko'rishlar: <b>{movie['views'][ep]}</b>"
    )
    await context.bot.send_video(chat_id=q.from_user.id, video=eps[idx],
        caption=caption, parse_mode="HTML", reply_markup=share_kb(share_url))

async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action, pid = q.data.split("|")
    pay = DB["pending_payments"].get(pid)
    if not pay:
        await q.edit_message_caption("⚠️ To'lov topilmadi.")
        return

    if action == "pay_no":
        pay["status"] = "rejected"
        save()
        await q.edit_message_caption(
            (q.message.caption or "") + "\n\n❌ <b>Bekor qilindi</b>",
            parse_mode="HTML")
        await context.bot.send_message(pay["user_id"],
            "❌ <b>To'lovingiz rad etildi.</b>\n"
            "Qayta urinib ko'ring yoki 🆘 Yordam orqali murojaat qiling.",
            parse_mode="HTML")
        return

    pay["status"] = "approved"
    uid = str(pay["user_id"])
    DB["users"].setdefault(uid, {}).setdefault("paid_episodes", {})[
        f"{pay['code']}_{pay['ep']}"] = True
    try:
        next_ep = str(int(pay["ep"]) + 1)
        DB["users"][uid]["paid_episodes"][f"{pay['code']}_{next_ep}"] = True
    except Exception:
        pass
    save()
    await q.edit_message_caption(
        (q.message.caption or "") + "\n\n✅ <b>Tasdiqlandi</b>",
        parse_mode="HTML")
    await context.bot.send_message(pay["user_id"],
        "✅ <b>Admin to'lovingizni tasdiqladi!</b>\n"
        "⏳ 1 daqiqa kuting, video avtomatik yuboriladi...",
        parse_mode="HTML")

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
            DB["users"][uid].setdefault("watched", {})[
                f"{pay['code']}_{pay['ep']}"] = True
            DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
            save()
            await context.bot.send_video(pay["user_id"], eps[idx],
                caption=f"🎬 <b>{movie.get('title')}</b>\n🎞 Qism: {pay['ep']}",
                parse_mode="HTML")
    context.application.create_task(send_later())

async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, uid = q.data.split("|")
    context.user_data["reply_to"] = int(uid)
    await q.message.reply_text(
        f"✍️ <code>{uid}</code> ga xabar yozing (matn/rasm/video).",
        parse_mode="HTML")

async def cb_refresh_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("📊 Yangilandi!")
    u = len(DB.get("users", {}))
    m = len(DB.get("movies", {}))
    v = DB.get("stats", {}).get("total_views", 0)
    await q.edit_message_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{u}</b>\n"
        f"🎬 Kinolar: <b>{m}</b>\n"
        f"👁 Jami ko'rishlar: <b>{v}</b>",
        parse_mode="HTML",
        reply_markup=stats_kb())

async def cb_go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(q.from_user.id,
        "🏠 Bosh menyu", reply_markup=main_menu_kb())

async def cb_waiting_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("⏳ Admin ko'rib chiqmoqda, sabrli bo'ling!", show_alert=True)

# ══════════════════ MASTER CALLBACK HANDLER ═══════════════
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    if data == "check_sub":
        await cb_check_sub(update, context)
    elif data.startswith("ep|"):
        await cb_episode(update, context)
    elif data.startswith("pay_ok|") or data.startswith("pay_no|"):
        await cb_payment(update, context)
    elif data.startswith("reply|"):
        await cb_reply(update, context)
    elif data == "refresh_stats":
        if update.callback_query.from_user.id == ADMIN_ID:
            await cb_refresh_stats(update, context)
    elif data == "go_home":
        await cb_go_home(update, context)
    elif data == "waiting_confirm":
        await cb_waiting_confirm(update, context)
    elif (data.startswith("emoji_") or data.startswith("emoji_edit|")):
        if update.callback_query.from_user.id == ADMIN_ID:
            await cb_emoji(update, context)
        else:
            await update.callback_query.answer("🚫 Ruxsat yo'q", show_alert=True)

# ═══════════════════════ /help ════════════════════════════
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✍️ Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\n"
        "Admin tez orada javob beradi.",
        parse_mode="HTML",
        reply_markup=help_kb())
    context.user_data["awaiting_help"] = True

# ═══════════════════ ILOVA O'RNATISH ══════════════════════
async def handle_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s    = DB.get("settings", {})
    f_id = s.get("install_file_id")
    v_id = s.get("install_video_id")
    if not f_id and not v_id:
        await update.message.reply_text("⏳ Admin hali ilova fayl/video joylamagan.")
        return
    if v_id:
        await update.message.reply_video(v_id,
            caption="📲 <b>Ilovani o'rnatish videosi</b>", parse_mode="HTML")
    if f_id:
        await update.message.reply_document(f_id,
            caption="📦 <b>Ilova fayli</b>", parse_mode="HTML")

# ═══════════════════ EMOJI SOZLAMALAR PANELI ══════════════
async def show_emoji_panel(update: Update):
    await update.message.reply_text(
        "🎭 <b>Emoji sozlamalari</b>\n\n"
        "O'zgartirmoqchi bo'lgan emoji tugmasini tanlang.\n"
        "<i>Qavs ichida — joriy ID ning oxirgi 6 raqami</i>",
        parse_mode="HTML",
        reply_markup=emoji_list_kb())

# ════════════════════ MATN HANDLER ════════════════════════
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    text = (update.message.text or "").strip()

    ADMIN_BTNS = (
        "🎬 Kino joylash", "➕ Qism qo'shish", "💰 Qismni pullik qilish",
        "📊 Statistika",   "📢 Kanalga post",  "🔒 Majburiy kanal",
        "💳 Karta raqami", "📲 Ilova fayl/video", "🏠 Asosiy menyu",
        "🎭 Emoji sozlamalari",
    )
    if uid == ADMIN_ID and text in ADMIN_BTNS:
        if text == "🎭 Emoji sozlamalari":
            await show_emoji_panel(update)
            return
        await admin_buttons(update, context, text)
        return

    if text == "🆘 Yordam":
        await handle_help(update, context)
        return
    if text == "📥 Ilovani o'rnatish":
        await handle_install(update, context)
        return

    # ── Emoji ID ni saqlash ──
    if uid == ADMIN_ID and context.user_data.get("editing_emoji_key"):
        key    = context.user_data.pop("editing_emoji_key")
        new_id = text.strip()
        if not new_id.isdigit() or len(new_id) < 10:
            await update.message.reply_text(
                "❌ Noto'g'ri ID format. Faqat raqamlardan iborat bo'lishi kerak.\n"
                "<i>Masalan: 5368324170671202286</i>",
                parse_mode="HTML")
            context.user_data["editing_emoji_key"] = key
            return
        DB.setdefault("emoji_ids", {})[key] = new_id
        save()
        await update.message.reply_text(
            f"✅ <b>{PE_LABELS.get(key, key)}</b> emoji IDsi yangilandi!\n\n"
            f"🆕 Yangi ID:\n<code>{new_id}</code>",
            parse_mode="HTML",
            reply_markup=emoji_list_kb())
        return

    if uid == ADMIN_ID and await admin_state_handler(update, context, text):
        return

    if context.user_data.pop("awaiting_help", False):
        cap = (f"🆘 <b>Yordam so'rovi</b>\n"
               f"👤 {user.full_name} (@{user.username or '-'})\n"
               f"🆔 <code>{uid}</code>\n\n")
        await context.bot.send_message(ADMIN_ID, cap + text,
            parse_mode="HTML", reply_markup=reply_admin_kb(uid))
        await update.message.reply_text("✅ Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await context.bot.send_message(target,
                f"✉️ <b>Admin javobi:</b>\n{text}", parse_mode="HTML")
            await update.message.reply_text("✅ Yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        return

    if context.user_data.get("awaiting_check"):
        await update.message.reply_text(
            "📸 Iltimos chek <b>rasmini</b> yuboring.", parse_mode="HTML")
        return

    # ── Kino raqami / kodi ──
    code = text.upper().strip()
    if code in DB["movies"]:
        not_subbed = await check_subscription(uid, context.bot)
        if not_subbed:
            await update.message.reply_text(
                "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                reply_markup=subscription_kb(not_subbed))
            context.user_data["pending_code"] = code
            return
        await send_movie_menu(update, context, code)
    else:
        await update.message.reply_text(
            "❓ Kino raqami topilmadi.\n🔢 To'g'ri raqamni yuboring.")

# ════════════════════ ADMIN TUGMALARI ═════════════════════
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if text == "🏠 Asosiy menyu":
        await update.message.reply_text("🏠 Asosiy menyu",
            reply_markup=main_menu_kb())
        return
    if text == "📊 Statistika":
        u = len(DB.get("users", {}))
        m = len(DB.get("movies", {}))
        v = DB.get("stats", {}).get("total_views", 0)
        await update.message.reply_text(
            f"📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{u}</b>\n"
            f"🎬 Kinolar: <b>{m}</b>\n"
            f"👁 Jami ko'rishlar: <b>{v}</b>",
            parse_mode="HTML",
            reply_markup=stats_kb())
        return
    if text == "💳 Karta raqami":
        context.user_data["admin_state"] = "set_card"
        cur = DB.get("card_number") or "Kiritilmagan"
        await update.message.reply_text(
            f"💳 Joriy karta: <code>{cur}</code>\n\nYangi karta raqamini yuboring:",
            parse_mode="HTML")
        return
    if text == "🎬 Kino joylash":
        context.user_data["admin_state"] = "add_movie_code"
        await update.message.reply_text("🎬 Kino kodini kiriting (masalan: AVATAR yoki 001):")
        return
    if text == "➕ Qism qo'shish":
        context.user_data["admin_state"] = "add_ep_code"
        await update.message.reply_text("🎬 Qism qo'shmoqchi bo'lgan kino kodini kiriting:")
        return
    if text == "💰 Qismni pullik qilish":
        context.user_data["admin_state"] = "set_price_code"
        await update.message.reply_text("🎬 Kino kodini kiriting:")
        return
    if text == "📲 Ilova fayl/video":
        context.user_data["admin_state"] = "set_install"
        await update.message.reply_text("📲 Ilova fayl yoki video yuboring:")
        return
    if text == "🔒 Majburiy kanal":
        context.user_data["admin_state"] = "add_channel"
        await update.message.reply_text(
            "📢 Kanal username va nomi yuboring:\n"
            "<code>@username | Kanal nomi | https://t.me/username</code>",
            parse_mode="HTML")
        return
    if text == "📢 Kanalga post":
        context.user_data["admin_state"] = "post_channel_code"
        await update.message.reply_text("🎬 Post qilmoqchi bo'lgan kino kodini kiriting:")
        return

async def admin_state_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    state = context.user_data.get("admin_state")
    if not state:
        return False

    if state == "set_card":
        DB["card_number"] = text
        save()
        context.user_data.pop("admin_state")
        await update.message.reply_text(f"✅ Karta saqlandi: <code>{text}</code>", parse_mode="HTML")
        return True

    if state == "add_movie_code":
        context.user_data["new_movie_code"] = text.upper()
        context.user_data["admin_state"]    = "add_movie_title"
        await update.message.reply_text("📝 Kino nomini kiriting:")
        return True

    if state == "add_movie_title":
        code = context.user_data.get("new_movie_code")
        DB["movies"][code] = {"title": text, "episodes": [], "prices": {}}
        save()
        context.user_data.pop("admin_state")
        context.user_data.pop("new_movie_code", None)
        await update.message.reply_text(
            f"✅ <b>{text}</b> kinosi qo'shildi!\nKod: <code>{code}</code>",
            parse_mode="HTML",
            reply_markup=movie_added_kb(code))
        return True

    if state == "add_ep_code":
        code = text.upper()
        if code not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["ep_movie_code"] = code
        context.user_data["admin_state"]   = "add_ep_video"
        await update.message.reply_text(f"📹 <b>{code}</b> uchun video yuboring:", parse_mode="HTML")
        return True

    if state == "set_price_code":
        code = text.upper()
        if code not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["price_movie_code"] = code
        context.user_data["admin_state"]      = "set_price_ep"
        await update.message.reply_text(f"🎞 Qism raqamini kiriting:")
        return True

    if state == "set_price_ep":
        context.user_data["price_ep"]    = text
        context.user_data["admin_state"] = "set_price_amount"
        await update.message.reply_text("💰 Narxini kiriting (so'mda):")
        return True

    if state == "set_price_amount":
        code = context.user_data.get("price_movie_code")
        ep   = context.user_data.get("price_ep")
        DB["movies"][code].setdefault("prices", {})[ep] = text
        save()
        context.user_data.pop("admin_state")
        await update.message.reply_text(f"✅ {code} — {ep}-qism narxi: {text} so'm", parse_mode="HTML")
        return True

    if state == "add_channel":
        try:
            parts = [p.strip() for p in text.split("|")]
            uname, title, url = parts[0], parts[1], parts[2]
            DB["channels"].append({"username": uname, "title": title, "url": url})
            save()
            await update.message.reply_text(f"✅ Kanal qo'shildi: {title}")
        except Exception:
            await update.message.reply_text("❌ Format xato. Qayta urinib ko'ring.")
        context.user_data.pop("admin_state")
        return True

    if state == "post_channel_code":
        code = text.upper()
        if code not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            context.user_data.pop("admin_state")
            return True
        context.user_data["post_code"]   = code
        context.user_data["admin_state"] = "post_channel_target"
        await update.message.reply_text("📢 Kanal username ni kiriting (masalan @mychannel):")
        return True

    if state == "post_channel_target":
        channel  = text
        code     = context.user_data.get("post_code")
        movie    = DB["movies"].get(code, {})
        bot_me   = await context.bot.get_me()
        markup   = channel_post_kb(bot_me.username, code)
        caption  = (
            f"🎬 <b>{movie.get('title', code)}</b>\n\n"
            f"📺 Qismlar soni: <b>{len(movie.get('episodes', []))}</b>\n\n"
            f"👇 Tomosha qilish uchun tugmani bosing!"
        )
        poster = movie.get("poster_file_id")
        try:
            if poster:
                await context.bot.send_photo(channel, poster, caption=caption,
                    parse_mode="HTML", reply_markup=markup)
            else:
                await context.bot.send_message(channel, caption,
                    parse_mode="HTML", reply_markup=markup)
            await update.message.reply_text("✅ Post yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        context.user_data.pop("admin_state")
        return True

    if state == "set_install":
        return False

    return False

# ══════════════════ MEDIA HANDLER (Admin) ═════════════════
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    msg   = update.message
    state = context.user_data.get("admin_state")

    if uid == ADMIN_ID and state == "add_movie_poster":
        code = context.user_data.get("new_movie_code2")
        if msg.photo:
            DB["movies"][code]["poster_file_id"] = msg.photo[-1].file_id
            save()
            context.user_data.pop("admin_state")
            context.user_data.pop("new_movie_code2", None)
            await msg.reply_text(f"✅ Poster saqlandi!")
        return

    if uid == ADMIN_ID and state == "add_ep_video":
        code = context.user_data.get("ep_movie_code")
        if msg.video:
            DB["movies"][code]["episodes"].append(msg.video.file_id)
            save()
            ep_num = len(DB["movies"][code]["episodes"])
            context.user_data.pop("admin_state")
            await msg.reply_text(f"✅ {ep_num}-qism saqlandi!")
        return

    if uid == ADMIN_ID and state == "set_install":
        if msg.video:
            DB["settings"]["install_video_id"] = msg.video.file_id
            save()
            context.user_data.pop("admin_state")
            await msg.reply_text("✅ O'rnatish videosi saqlandi!")
        elif msg.document:
            DB["settings"]["install_file_id"] = msg.document.file_id
            save()
            context.user_data.pop("admin_state")
            await msg.reply_text("✅ O'rnatish fayli saqlandi!")
        return

    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info = context.user_data.pop("awaiting_check")
        pid = f"{uid}_{pay_info['code']}_{pay_info['ep']}_{int(time.time())}"
        DB["pending_payments"][pid] = {
            "user_id": uid, "code": pay_info["code"],
            "ep": pay_info["ep"], "price": pay_info["price"], "status": "pending"
        }
        save()
        cap = (
            f"💳 <b>To'lov cheki</b>\n"
            f"👤 {user.full_name} (@{user.username or '-'})\n"
            f"🆔 <code>{uid}</code>\n"
            f"🎬 Kino: <b>{pay_info['code']}</b>\n"
            f"🎞 Qism: <b>{pay_info['ep']}</b>\n"
            f"💰 Narx: <b>{pay_info['price']} so'm</b>"
        )
        await context.bot.send_photo(ADMIN_ID, msg.photo[-1].file_id,
            caption=cap, parse_mode="HTML",
            reply_markup=payment_admin_kb(pid))
        await msg.reply_text("✅ Chek adminga yuborildi! Tasdiqlanishini kuting.")
        return

    if context.user_data.pop("awaiting_help", False):
        cap = (f"🆘 <b>Yordam so'rovi</b>\n"
               f"👤 {user.full_name} (@{user.username or '-'})\n"
               f"🆔 <code>{uid}</code>\n\n")
        if msg.photo:
            await context.bot.send_photo(ADMIN_ID, msg.photo[-1].file_id,
                caption=cap, parse_mode="HTML",
                reply_markup=reply_admin_kb(uid))
        elif msg.video:
            await context.bot.send_video(ADMIN_ID, msg.video.file_id,
                caption=cap, parse_mode="HTML",
                reply_markup=reply_admin_kb(uid))
        await msg.reply_text("✅ Xabaringiz adminga yuborildi!")
        return

    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            if msg.photo:
                await context.bot.send_photo(target, msg.photo[-1].file_id,
                    caption="✉️ <b>Admin javobi</b>", parse_mode="HTML")
            elif msg.video:
                await context.bot.send_video(target, msg.video.file_id,
                    caption="✉️ <b>Admin javobi</b>", parse_mode="HTML")
            await msg.reply_text("✅ Yuborildi!")
        except Exception as e:
            await msg.reply_text(f"❌ Xato: {e}")

# ═══════════════════════ MAIN ═════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))

    logger.info("🚀 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
