# -*- coding: utf-8 -*-
"""
🎬 Kino Bot — To'liq versiya
Fly.io + JSONBin | Bot API 9.4 rangli tugmalar + premium emoji
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

# ═══════════════════ PREMIUM EMOJI IDlar ══════════════════
# Telegram'ning bepul animatsiyali custom emoji IDlari
# (Bot API 9.4 — icon_custom_emoji_id orqali tugmalarda ko'rinadi)
PE = {
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

# ═══════════════════ TUGMA YORDAMCHISI ════════════════════

def ibtn(text, data=None, url=None, style=None, emoji_id=None):
    """
    InlineKeyboardButton — Bot API 9.4 rangli + premium emoji.
    style: 'primary'(ko'k) | 'success'(yashil) | 'danger'(qizil)
    """
    kwargs = {"text": text}
    if data: kwargs["callback_data"] = data
    if url:  kwargs["url"] = url
    btn = InlineKeyboardButton(**kwargs)
    if style:
        try: btn.style = style
        except Exception: pass
    if emoji_id:
        try: btn.icon_custom_emoji_id = emoji_id
        except Exception: pass
    return btn

# ═══════════════════ REPLY KLAVIATURALAR ══════════════════

def main_menu_kb():
    """Foydalanuvchi asosiy menyu — oddiy ReplyKeyboard."""
    kb = [
        [KeyboardButton("🆘 Yordam"),
         KeyboardButton("📥 Ilovani o'rnatish")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def admin_menu_kb():
    """Admin panel — oddiy ReplyKeyboard."""
    kb = [
        [KeyboardButton("🎬 Kino joylash"),
         KeyboardButton("➕ Qism qo'shish")],
        [KeyboardButton("💰 Qismni pullik qilish"),
         KeyboardButton("📊 Statistika")],
        [KeyboardButton("📢 Kanalga post"),
         KeyboardButton("🔒 Majburiy kanal")],
        [KeyboardButton("💳 Karta raqami"),
         KeyboardButton("📲 Ilova fayl/video")],
        [KeyboardButton("🏠 Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ═══════════════════ INLINE KLAVIATURALAR ═════════════════

def subscription_kb(channels):
    """Obuna bo'lish + tekshirish — rangli inline."""
    kb = [[ibtn(f"📢 {c['title']}", url=c["url"],
                style="primary", emoji_id=PE["post"])]
          for c in channels]
    kb.append([ibtn("✅ Tekshirish", data="check_sub",
                    style="success", emoji_id=PE["check"])])
    return InlineKeyboardMarkup(kb)

def movie_episodes_kb(movie, code, user_id):
    """
    Qismlar klaviaturasi:
      bepul  → yashil ▶️
      pullik → qizil  🔒
    """
    eps    = movie.get("episodes", [])
    prices = movie.get("prices", {})
    paid   = DB["users"].get(str(user_id), {}).get("paid_episodes", {})
    kb = []
    for i in range(len(eps)):
        ep_key    = str(i + 1)
        price     = prices.get(ep_key)
        is_locked = price and not paid.get(f"{code}_{ep_key}")
        if is_locked:
            label  = f"🔒 {ep_key}-qism  💰 {price} so'm"
            style  = "danger"
            eid    = PE["lock"]
        else:
            label  = f"▶️ {ep_key}-qism"
            style  = "success"
            eid    = PE["play"]
        kb.append([ibtn(label, data=f"ep|{code}|{ep_key}",
                        style=style, emoji_id=eid)])
    return InlineKeyboardMarkup(kb)

def payment_admin_kb(pid):
    return InlineKeyboardMarkup([[
        ibtn("✅ Tasdiqlash",   data=f"pay_ok|{pid}",
             style="success", emoji_id=PE["check"]),
        ibtn("❌ Bekor qilish", data=f"pay_no|{pid}",
             style="danger",  emoji_id=PE["lock"]),
    ]])

def share_kb(share_url):
    return InlineKeyboardMarkup([[
        ibtn("📤 Do'stlarga ulashish", url=share_url,
             style="primary", emoji_id=PE["share"]),
    ]])

def channel_post_kb(bot_username, code):
    return InlineKeyboardMarkup([[
        ibtn("🎬 Tomosha qilish",
             url=f"https://t.me/{bot_username}?start=code_{code}",
             style="success", emoji_id=PE["watch"]),
    ]])

def reply_admin_kb(uid):
    return InlineKeyboardMarkup([[
        ibtn("✉️ Javob berish", data=f"reply|{uid}",
             style="primary", emoji_id=PE["reply"]),
    ]])

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
            "name":           user.full_name,
            "username":       user.username or "",
            "joined":         datetime.now().isoformat(),
            "paid_episodes":  {},
            "watched":        {},
        }
        save()

async def send_movie_menu(src, context, code):
    """Kino poster + qismlar inline klaviaturasini yuborish."""
    movie = DB["movies"].get(code)

    if hasattr(src, "effective_user"):
        chat_id = src.effective_user.id
        user_id = src.effective_user.id
    else:
        chat_id = src.from_user.id
        user_id = src.from_user.id

    if not movie:
        txt = "❓ Bunday kodli kino topilmadi. Kodni tekshirib qayta yuboring."
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
        f"📥 Kino <b>kodini</b> yuboring — video darhol chiqadi.\n\n"
        f"👇 Quyidagi tugmalardan foydalaning:"
    )
    await update.message.reply_text(hello, parse_mode="HTML",
        reply_markup=main_menu_kb())
    if user.id == ADMIN_ID:
        await update.message.reply_text("👑 <b>Admin panel</b>",
            parse_mode="HTML", reply_markup=admin_menu_kb())

# ═══════════════════ CALLBACK HANDLERLAR ══════════════════

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
            f"📥 Kino kodini yuboring.",
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
        await q.message.reply_text(txt, parse_mode="HTML")
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

# ═══════════════════════ /help ════════════════════════════

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✍️ Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\n"
        "Admin tez orada javob beradi.",
        parse_mode="HTML")
    context.user_data["awaiting_help"] = True

# ═══════════════════ ILOVA O'RNATISH ══════════════════════

async def handle_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s   = DB.get("settings", {})
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

# ════════════════════ MATN HANDLER ════════════════════════

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    text = (update.message.text or "").strip()

    # ── Admin tugmalari ──
    ADMIN_BTNS = (
        "🎬 Kino joylash", "➕ Qism qo'shish", "💰 Qismni pullik qilish",
        "📊 Statistika",   "📢 Kanalga post",  "🔒 Majburiy kanal",
        "💳 Karta raqami", "📲 Ilova fayl/video", "🏠 Asosiy menyu",
    )
    if uid == ADMIN_ID and text in ADMIN_BTNS:
        await admin_buttons(update, context, text)
        return

    # ── Foydalanuvchi tugmalari ──
    if text == "🆘 Yordam":
        await handle_help(update, context)
        return
    if text == "📥 Ilovani o'rnatish":
        await handle_install(update, context)
        return

    # ── Admin state ──
    if uid == ADMIN_ID and await admin_state_handler(update, context, text):
        return

    # ── Yordam xabari ──
    if context.user_data.pop("awaiting_help", False):
        cap = (f"🆘 <b>Yordam so'rovi</b>\n"
               f"👤 {user.full_name} (@{user.username or '-'})\n"
               f"🆔 <code>{uid}</code>\n\n")
        await context.bot.send_message(ADMIN_ID, cap + text,
            parse_mode="HTML", reply_markup=reply_admin_kb(uid))
        await update.message.reply_text("✅ Xabaringiz adminga yuborildi!")
        return

    # ── Admin javob ──
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            await context.bot.send_message(target,
                f"✉️ <b>Admin javobi:</b>\n{text}", parse_mode="HTML")
            await update.message.reply_text("✅ Yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        return

    # ── Chek kutilmoqda ──
    if context.user_data.get("awaiting_check"):
        await update.message.reply_text(
            "📸 Iltimos chek <b>rasmini</b> yuboring.", parse_mode="HTML")
        return

    # ── Kino kodi ──
    code = text
    if code in DB["movies"]:
        await send_movie_menu(update, context, code)
        return

    # ── Topilmadi ──
    await update.message.reply_text(
        f"❓ <b>«{text}»</b> kodli kino topilmadi.\n"
        f"Kodni tekshirib qayta yuboring.",
        parse_mode="HTML")

# ══════════════════ MEDIA HANDLER ═════════════════════════

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    user = update.effective_user
    ud   = context.user_data
    state = ud.get("admin_state")

    # Yordam — media
    if ud.pop("awaiting_help", False):
        cap = (f"🆘 <b>Yordam so'rovi</b>\n"
               f"👤 {user.full_name} (@{user.username or '-'})\n"
               f"🆔 <code>{uid}</code>\n\n")
        kb = reply_admin_kb(uid)
        if update.message.photo:
            await context.bot.send_photo(ADMIN_ID,
                update.message.photo[-1].file_id,
                caption=cap + (update.message.caption or ""),
                parse_mode="HTML", reply_markup=kb)
        elif update.message.video:
            await context.bot.send_video(ADMIN_ID,
                update.message.video.file_id,
                caption=cap + (update.message.caption or ""),
                parse_mode="HTML", reply_markup=kb)
        await update.message.reply_text("✅ Xabaringiz adminga yuborildi!")
        return

    # Admin javob — media
    if uid == ADMIN_ID and "reply_to" in ud:
        target = ud.pop("reply_to")
        try:
            if update.message.photo:
                await context.bot.send_photo(target,
                    update.message.photo[-1].file_id,
                    caption=update.message.caption or "")
            elif update.message.video:
                await context.bot.send_video(target,
                    update.message.video.file_id,
                    caption=update.message.caption or "")
            await update.message.reply_text("✅ Yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        return

    # Chek rasmi
    if ud.get("awaiting_check") and update.message.photo:
        info = ud.pop("awaiting_check")
        pid  = f"{uid}_{datetime.now().timestamp()}"
        DB["pending_payments"][pid] = {
            "user_id": uid, "code": info["code"],
            "ep": info["ep"], "price": info["price"], "status": "pending",
        }
        save()
        cap = (f"💳 <b>Yangi to'lov cheki</b>\n"
               f"👤 {user.full_name} (@{user.username or '-'})\n"
               f"🆔 <code>{uid}</code>\n"
               f"🎬 Kino: <b>{info['code']}</b>\n"
               f"🎞 Qism: <b>{info['ep']}</b>\n"
               f"💰 Narx: <b>{info['price']} so'm</b>")
        await context.bot.send_photo(ADMIN_ID,
            update.message.photo[-1].file_id,
            caption=cap, parse_mode="HTML",
            reply_markup=payment_admin_kb(pid))
        await update.message.reply_text(
            "✅ Chekingiz qabul qilindi!\n"
            "⏳ Admin tekshiradi. Tasdiqlangach video avtomatik yuboriladi.")
        return

    if uid != ADMIN_ID:
        return

    # ── Admin media statelari ──
    if state == "install_file":
        if update.message.document:
            DB["settings"]["install_file_id"] = update.message.document.file_id
            save()
            ud["admin_state"] = "install_video"
            await update.message.reply_text(
                "✅ Fayl saqlandi. Endi <b>videoni</b> yuboring:", parse_mode="HTML")
        else:
            await update.message.reply_text("📦 Document turidagi fayl yuboring.")
        return

    if state == "install_video":
        if update.message.video:
            DB["settings"]["install_video_id"] = update.message.video.file_id
            save()
            ud.pop("admin_state", None)
            await update.message.reply_text(
                "✅ Ilova fayl va video saqlandi!", reply_markup=admin_menu_kb())
        else:
            await update.message.reply_text("🎥 Video yuboring.")
        return

    if state == "movie_poster":
        if not update.message.photo:
            await update.message.reply_text("🖼 Rasm yuboring.")
            return
        ud["new_movie"]["poster_file_id"] = update.message.photo[-1].file_id
        ud["admin_state"] = "movie_title"
        await update.message.reply_text(
            "✍️ Kino <b>nomini</b> yuboring:", parse_mode="HTML")
        return

    if state == "movie_episodes" and update.message.video:
        ud["new_movie"]["episodes"].append(update.message.video.file_id)
        n = len(ud["new_movie"]["episodes"])
        await update.message.reply_text(
            f"✅ Qism qo'shildi ({n} ta). Yana yuboring yoki <b>NEXT</b> yozing.",
            parse_mode="HTML")
        return

    if state == "addep_video" and update.message.video:
        code = ud.get("addep_code")
        if code and code in DB["movies"]:
            DB["movies"][code]["episodes"].append(update.message.video.file_id)
            save()
            n = len(DB["movies"][code]["episodes"])
            await update.message.reply_text(
                f"✅ Qism qo'shildi ({n}-qism). Yana yuboring yoki <b>NEXT</b> deb yozing.",
                parse_mode="HTML")
        return

# ════════════════ ADMIN TUGMALARI ═════════════════════════

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    ud = context.user_data
    ud.pop("admin_state", None)

    if text == "🏠 Asosiy menyu":
        await update.message.reply_text("🏠 Asosiy menyu", reply_markup=main_menu_kb())
        return

    if text == "🎬 Kino joylash":
        ud["admin_state"] = "movie_poster"
        ud["new_movie"]   = {"episodes": []}
        await update.message.reply_text(
            "🖼 Avval kino uchun <b>rasm (poster)</b> yuboring.", parse_mode="HTML")
        return

    if text == "➕ Qism qo'shish":
        ud["admin_state"] = "addep_code"
        await update.message.reply_text(
            "🔢 Mavjud kino <b>kodini</b> yuboring:", parse_mode="HTML")
        return

    if text == "💰 Qismni pullik qilish":
        ud["admin_state"] = "paid_code"
        await update.message.reply_text(
            "🔢 Kino <b>kodini</b> yuboring:", parse_mode="HTML")
        return

    if text == "📊 Statistika":
        lines = [
            "📊 <b>Statistika</b>\n",
            f"👥 Foydalanuvchilar: <b>{len(DB['users'])}</b>",
            f"🎬 Kinolar: <b>{len(DB['movies'])}</b>",
            f"👁 Umumiy ko'rishlar: <b>{DB.get('stats',{}).get('total_views',0)}</b>\n",
            "<b>Kinolar bo'yicha:</b>",
        ]
        for code, m in DB["movies"].items():
            total = sum(m.get("views", {}).values())
            lines.append(
                f"• <code>{code}</code> — {m.get('title','?')} "
                f"({len(m.get('episodes',[]))} qism, 👁 {total})")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if text == "📢 Kanalga post":
        ud["admin_state"] = "post_code"
        await update.message.reply_text(
            "🔢 Kanalga yuboriladigan kino <b>kodini</b> yuboring:", parse_mode="HTML")
        return

    if text == "🔒 Majburiy kanal":
        lines = ["🔒 <b>Majburiy kanallar</b>\n"]
        for i, c in enumerate(DB.get("channels", []), 1):
            lines.append(f"{i}. {c['title']} — {c['username']}")
        lines.append("\nYangi qo'shish: <code>@username | Kanal nomi | https://t.me/...</code>")
        lines.append("O'chirish: <code>/delch raqam</code>")
        ud["admin_state"] = "add_channel"
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if text == "💳 Karta raqami":
        ud["admin_state"] = "set_card"
        await update.message.reply_text(
            f"💳 Hozirgi: <code>{DB.get('card_number') or 'yoq'}</code>\n"
            "Yangi karta raqamini yuboring:", parse_mode="HTML")
        return

    if text == "📲 Ilova fayl/video":
        ud["admin_state"] = "install_file"
        await update.message.reply_text(
            "📦 Ilova <b>faylini</b> (document) yuboring:", parse_mode="HTML")
        return

# ═══════════════ ADMIN STATE HANDLER ══════════════════════

async def admin_state_handler(update: Update,
                               context: ContextTypes.DEFAULT_TYPE,
                               text: str) -> bool:
    ud    = context.user_data
    state = ud.get("admin_state")
    if not state:
        return False

    if state == "add_channel":
        try:
            parts = [p.strip() for p in text.split("|")]
            DB.setdefault("channels", []).append(
                {"username": parts[0], "title": parts[1], "url": parts[2]})
            save()
            await update.message.reply_text(f"✅ Qo'shildi: {parts[1]}")
        except Exception:
            await update.message.reply_text("❌ Format: @username | Nom | https://t.me/...")
        ud.pop("admin_state", None)
        return True

    if state == "set_card":
        DB["card_number"] = text
        save()
        await update.message.reply_text(
            f"✅ Karta saqlandi: <code>{text}</code>", parse_mode="HTML")
        ud.pop("admin_state", None)
        return True

    if state == "addep_code":
        if text not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            ud.pop("admin_state", None)
            return True
        ud["addep_code"]  = text
        ud["admin_state"] = "addep_video"
        await update.message.reply_text(
            f"🎬 <b>{text}</b> ga video(lar)ni yuboring. Tugagach <b>NEXT</b> deb yozing.",
            parse_mode="HTML")
        return True

    if state == "addep_video" and text.upper() == "NEXT":
        await update.message.reply_text("✅ Qismlar qo'shildi!", reply_markup=admin_menu_kb())
        ud.pop("admin_state", None)
        ud.pop("addep_code", None)
        return True

    if state == "paid_code":
        if text not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            ud.pop("admin_state", None)
            return True
        ud["paid_code"]   = text
        ud["admin_state"] = "paid_ep"
        await update.message.reply_text("🎞 Nechinchi qismni pullik qilamiz? (raqam)")
        return True

    if state == "paid_ep":
        if not text.isdigit():
            await update.message.reply_text("❌ Raqam yuboring.")
            return True
        ud["paid_ep"]     = text
        ud["admin_state"] = "paid_price"
        await update.message.reply_text("💰 Narxini so'mda yuboring (masalan: 10000)")
        return True

    if state == "paid_price":
        if not text.isdigit():
            await update.message.reply_text("❌ Faqat raqam.")
            return True
        code = ud.pop("paid_code")
        ep   = ud.pop("paid_ep")
        DB["movies"][code].setdefault("prices", {})[ep] = int(text)
        save()
        await update.message.reply_text(
            f"✅ Saqlandi: <b>{code}</b> {ep}-qism — {text} so'm",
            parse_mode="HTML")
        ud.pop("admin_state", None)
        return True

    if state == "movie_episodes" and text.upper() == "NEXT":
        ud["admin_state"] = "movie_code"
        await update.message.reply_text(
            "🔢 Kino <b>kodini</b> kiriting (masalan: 1):", parse_mode="HTML")
        return True

    if state == "movie_code":
        code = text.strip()
        nm   = ud.pop("new_movie", {})
        if not nm.get("episodes"):
            await update.message.reply_text("❌ Hech qism yuklanmagan.")
            ud.pop("admin_state", None)
            return True
        DB["movies"][code] = {
            "title":          nm.get("title") or f"Kino #{code}",
            "poster_file_id": nm.get("poster_file_id"),
            "episodes":       nm["episodes"],
            "views":          {},
            "prices":         {},
        }
        save()
        await update.message.reply_text(
            f"✅ <b>Kino saqlandi!</b>\nKod: <code>{code}</code>\n"
            f"Qismlar: {len(nm['episodes'])}",
            parse_mode="HTML", reply_markup=admin_menu_kb())
        ud.pop("admin_state", None)
        return True

    if state == "movie_title":
        ud["new_movie"]["title"] = text
        ud["admin_state"]        = "movie_episodes"
        await update.message.reply_text(
            "🎬 Endi <b>video(lar)ni</b> yuboring. Tugagach <b>NEXT</b> yozing.",
            parse_mode="HTML")
        return True

    if state == "post_code":
        if text not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            ud.pop("admin_state", None)
            return True
        ud["post_code"]   = text
        ud["admin_state"] = "post_channel"
        await update.message.reply_text("📢 Kanal username (masalan: @kino_kanal):")
        return True

    if state == "post_channel":
        code    = ud.pop("post_code")
        channel = text.strip()
        m       = DB["movies"].get(code)
        if not m:
            await update.message.reply_text("❌ Kino topilmadi.")
            ud.pop("admin_state", None)
            return True
        bot_username = (await context.bot.get_me()).username
        caption = (
            f"🎬 <b>{m.get('title')}</b>\n"
            f"📺 Qismlar: <b>{len(m.get('episodes', []))}</b>\n"
            f"🔢 Kod: <b>{code}</b>\n\n"
            f"Tomosha qilish uchun tugmani bosing 👇"
        )
        try:
            kb = channel_post_kb(bot_username, code)
            if m.get("poster_file_id"):
                await context.bot.send_photo(channel, m["poster_file_id"],
                    caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await context.bot.send_message(channel, caption,
                    parse_mode="HTML", reply_markup=kb)
            await update.message.reply_text("✅ Kanalga yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        ud.pop("admin_state", None)
        return True

    return False

# ═══════════════════════ /delch ═══════════════════════════

async def delch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        i       = int(context.args[0]) - 1
        removed = DB["channels"].pop(i)
        save()
        await update.message.reply_text(f"✅ O'chirildi: {removed['title']}")
    except Exception:
        await update.message.reply_text("Format: /delch 1")

# ════════════════ BOT COMMANDS ════════════════════════════

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 Botni ishga tushirish"),
        BotCommand("help",  "🆘 Yordam"),
    ])

# ════════════════ HEALTH CHECK ════════════════════════════

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Kino Bot ishlayapti")
    def log_message(self, *a):
        return

def start_health_server():
    port = int(os.environ.get("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        logger.info(f"🌐 Health server :{port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server: {e}")

# ═══════════════════════ MAIN ═════════════════════════════

async def post_init_hook(app):
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("🧹 Webhook o'chirildi")
    except Exception as e:
        logger.warning(f"delete_webhook: {e}")
    await set_commands(app)
    save()

def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init_hook).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  handle_help))
    app.add_handler(CommandHandler("delch", delch))

    app.add_handler(CallbackQueryHandler(cb_check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_episode,   pattern="^ep\\|"))
    app.add_handler(CallbackQueryHandler(cb_payment,   pattern="^(pay_ok|pay_no)\\|"))
    app.add_handler(CallbackQueryHandler(cb_reply,     pattern="^reply\\|"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))

    logger.info("🤖 Bot ishga tushdi!")

    while True:
        try:
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False,
                stop_signals=None,
            )
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            msg = str(e)
            if "Conflict" in msg or "terminated by other getUpdates" in msg:
                logger.warning("⚠️ Boshqa instance. 30s kutamiz...")
                try:
                    import asyncio as _aio
                    _aio.run(app.bot.delete_webhook(drop_pending_updates=True))
                except Exception:
                    pass
                time.sleep(30)
                continue
            logger.error(f"❌ Xato: {e}. 10s kutamiz...")
            time.sleep(10)
            continue

    try:
        save()
    except Exception as e:
        logger.error(f"Save xato: {e}")

if __name__ == "__main__":
    main()
