# -*- coding: utf-8 -*-
"""
🎬 Kino Bot — To'liq versiya
Fly.io uchun moslashtirilgan. Ma'lumotlar JSONBin da saqlanadi.
"""

import logging
import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# ===================== 🔧 SOZLAMALAR =====================
BOT_TOKEN = "8655776547:AAEUwAvt_XTEC_5kHy2tsdZZ7Pyo8tkSQv4"
ADMIN_ID = 8537782289

JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID = "69cc43a2856a682189e936f0"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# ===================== 📋 LOGGING =====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===================== 💾 MA'LUMOTLAR BAZASI (JSONBin) =====================
DEFAULT_DB = {
    "users": {},          # user_id -> {name, joined, paid_episodes: {code_ep: true}, watched: {code_ep: true}}
    "movies": {},         # code -> {title, poster_file_id, episodes: [file_id, ...], views: {ep: count}, prices: {ep: price}}
    "channels": [],       # majburiy kanallar [{username, title, url}]
    "card_number": "",    # to'lov karta raqami
    "pending_payments": {},  # payment_id -> {user_id, code, ep, check_file_id, status}
    "settings": {"install_file_id": None, "install_video_id": None},
    "stats": {"total_views": 0},
}

def db_load():
    """JSONBin dan to'liq botni yuklash (3 marta urinish bilan)."""
    for attempt in range(3):
        try:
            r = requests.get(
                f"{JSONBIN_URL}/latest",
                headers={"X-Master-Key": JSONBIN_API_KEY},
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json().get("record", {})
                # Har bir bo'lim bor-yo'qligini ta'minlash
                for k, v in DEFAULT_DB.items():
                    if k not in data:
                        data[k] = v if not isinstance(v, (dict, list)) else (
                            {} if isinstance(v, dict) else []
                        )
                logger.info(f"✅ JSONBin dan yuklandi: {len(data.get('users',{}))} user, {len(data.get('movies',{}))} kino")
                return data
            logger.warning(f"JSONBin GET {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.error(f"DB load attempt {attempt+1} xato: {e}")
    logger.warning("⚠️ JSONBin yuklanmadi, DEFAULT bilan boshlanadi")
    return json.loads(json.dumps(DEFAULT_DB))  # chuqur nusxa

def db_save(data):
    """Butun ma'lumotlarni JSONBin ga saqlash (3 marta urinish)."""
    for attempt in range(3):
        try:
            r = requests.put(
                JSONBIN_URL,
                headers={
                    "X-Master-Key": JSONBIN_API_KEY,
                    "Content-Type": "application/json",
                    "X-Bin-Versioning": "false",
                },
                data=json.dumps(data, ensure_ascii=False),
                timeout=20,
            )
            if r.status_code == 200:
                return True
            logger.warning(f"JSONBin PUT {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.error(f"DB save attempt {attempt+1} xato: {e}")
    return False

DB = db_load()

_save_lock = asyncio.Lock() if False else None  # placeholder

def save():
    """Har qanday o'zgarishdan keyin chaqiring — butun bot JSONBin ga yoziladi."""
    ok = db_save(DB)
    if ok:
        logger.info(f"💾 Saqlandi (users={len(DB.get('users',{}))}, movies={len(DB.get('movies',{}))})")
    else:
        logger.error("❌ Saqlash muvaffaqiyatsiz!")
    return ok

# ===================== 🎨 TUGMALAR & MENYULAR =====================
def main_menu_kb():
    kb = [
        [KeyboardButton("🆘 Yordam"), KeyboardButton("📥 Ilovani o'rnatish")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def admin_menu_kb():
    kb = [
        [KeyboardButton("🎬 Kino joylash"), KeyboardButton("➕ Qism qo'shish")],
        [KeyboardButton("💰 Qismni pullik qilish"), KeyboardButton("📊 Statistika")],
        [KeyboardButton("📢 Kanalga post"), KeyboardButton("🔒 Majburiy kanal")],
        [KeyboardButton("💳 Karta raqami"), KeyboardButton("📲 Ilova fayl/video")],
        [KeyboardButton("🏠 Asosiy menyu")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ===================== ✅ MAJBURIY OBUNA =====================
async def check_subscription(user_id: int, bot) -> list:
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi."""
    not_subbed = []
    for ch in DB.get("channels", []):
        try:
            member = await bot.get_chat_member(ch["username"], user_id)
            if member.status in ("left", "kicked"):
                not_subbed.append(ch)
        except Exception as e:
            logger.warning(f"Subscription check failed for {ch}: {e}")
            not_subbed.append(ch)
    return not_subbed

def subscription_kb(channels):
    kb = [[InlineKeyboardButton(f"📢 {c['title']}", url=c["url"])] for c in channels]
    kb.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(kb)

# ===================== 👤 FOYDALANUVCHI =====================
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

# ===================== 🎬 KINO CHIQARISH =====================
async def send_movie_menu(update_or_query, context, code):
    movie = DB["movies"].get(code)
    if not movie:
        if hasattr(update_or_query, "message"):
            await update_or_query.message.reply_text("❌ Bunday kodli kino topilmadi.")
        else:
            await update_or_query.edit_message_text("❌ Bunday kodli kino topilmadi.")
        return

    user_id = str(
        update_or_query.from_user.id
        if hasattr(update_or_query, "from_user")
        else update_or_query.effective_user.id
    )
    eps = movie.get("episodes", [])
    prices = movie.get("prices", {})
    paid = DB["users"].get(user_id, {}).get("paid_episodes", {})

    if not eps:
        txt = "⏳ Bu kinoga hali qism yuklanmagan."
        if hasattr(update_or_query, "message"):
            await update_or_query.message.reply_text(txt)
        else:
            await update_or_query.edit_message_text(txt)
        return

    kb = []
    for i in range(len(eps)):
        ep_key = str(i + 1)
        price = prices.get(ep_key)
        if price and not paid.get(f"{code}_{ep_key}"):
            label = f"🔒 {ep_key}-qism • 💰 {price} so'm"
        else:
            label = f"▶️ {ep_key}-qism"
        kb.append([InlineKeyboardButton(label, callback_data=f"ep|{code}|{ep_key}")])

    caption = (
        f"🎬 <b>{movie.get('title', 'Kino')}</b>\n"
        f"📺 Qismlar soni: <b>{len(eps)}</b>\n\n"
        f"Qaysi qismni ko'rmoqchisiz? 👇"
    )
    markup = InlineKeyboardMarkup(kb)

    poster = movie.get("poster_file_id")
    target = update_or_query.message if hasattr(update_or_query, "message") else update_or_query.message
    try:
        if poster:
            await context.bot.send_photo(
                chat_id=update_or_query.from_user.id if hasattr(update_or_query, "from_user") else update_or_query.effective_user.id,
                photo=poster,
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
        else:
            await context.bot.send_message(
                chat_id=update_or_query.from_user.id if hasattr(update_or_query, "from_user") else update_or_query.effective_user.id,
                text=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    except Exception as e:
        logger.error(f"send_movie_menu err: {e}")

# ===================== 🚀 /start =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)

    # Deep-link argument (kanaldagi tugmadan kelgan bo'lsa: /start code_X)
    args = context.args
    if args:
        arg = args[0]
        if arg.startswith("code_"):
            code = arg.replace("code_", "")
            not_subbed = await check_subscription(user.id, context.bot)
            if not_subbed:
                await update.message.reply_text(
                    "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                    reply_markup=subscription_kb(not_subbed),
                )
                context.user_data["pending_code"] = code
                return
            await send_movie_menu(update, context, code)
            return

    not_subbed = await check_subscription(user.id, context.bot)
    if not_subbed:
        await update.message.reply_text(
            "🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_kb(not_subbed),
        )
        return

    hello = (
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        f"🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
        f"📥 Kino <b>kodini</b> yuboring va kino siz uchun chiqariladi.\n\n"
        f"🧡 Quyidagi tugmalardan foydalaning:"
    )
    await update.message.reply_text(hello, parse_mode="HTML", reply_markup=main_menu_kb())

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            "👑 <b>Admin panel</b>",
            parse_mode="HTML",
            reply_markup=admin_menu_kb(),
        )

# ===================== 🔔 OBUNA TEKSHIRISH =====================
async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    not_subbed = await check_subscription(q.from_user.id, context.bot)
    if not_subbed:
        await q.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)
        return
    await q.edit_message_text("✅ Barcha kanallarga obuna bo'ldingiz! Endi botdan bemalol foydalaning.")
    pending = context.user_data.pop("pending_code", None)
    if pending:
        await send_movie_menu(q, context, pending)
    else:
        await context.bot.send_message(
            q.from_user.id,
            f"👋 Xush kelibsiz, <b>{q.from_user.full_name}</b>!\n📥 Kino kodini yuboring.",
            parse_mode="HTML",
            reply_markup=main_menu_kb(),
        )

# ===================== ▶️ QISMNI KO'RSATISH =====================
async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, code, ep = q.data.split("|")
    movie = DB["movies"].get(code)
    if not movie:
        await q.answer("❌ Kino topilmadi", show_alert=True)
        return

    user_id = str(q.from_user.id)
    prices = movie.get("prices", {})
    paid = DB["users"].get(user_id, {}).get("paid_episodes", {})
    price = prices.get(ep)

    if price and not paid.get(f"{code}_{ep}"):
        # Pullik qism — to'lov jarayoni
        card = DB.get("card_number") or "Karta raqami admin tomonidan o'rnatilmagan"
        txt = (
            f"💰 <b>Bu qism pullik</b>\n\n"
            f"🎬 Kino: <b>{movie.get('title')}</b>\n"
            f"🎞 Qism: <b>{ep}</b>\n"
            f"💵 Narxi: <b>{price} so'm</b>\n\n"
            f"💳 Karta raqami:\n<code>{card}</code>\n\n"
            f"To'lov qiling va chekni rasmini yuboring 📸"
        )
        context.user_data["awaiting_check"] = {"code": code, "ep": ep, "price": price}
        await q.message.reply_text(txt, parse_mode="HTML")
        return

    # Bepul ko'rish
    idx = int(ep) - 1
    eps = movie.get("episodes", [])
    if idx < 0 or idx >= len(eps):
        await q.answer("❌ Qism topilmadi", show_alert=True)
        return

    # View count
    movie.setdefault("views", {})
    movie["views"][ep] = movie["views"].get(ep, 0) + 1
    DB["users"][user_id].setdefault("watched", {})[f"{code}_{ep}"] = True
    DB["stats"]["total_views"] = DB["stats"].get("total_views", 0) + 1
    save()

    share_url = f"https://t.me/share/url?url=https://t.me/{(await context.bot.get_me()).username}?start=code_{code}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Do'stlarga ulashish", url=share_url)],
    ])
    caption = (
        f"🎬 <b>{movie.get('title')}</b>\n"
        f"🎞 Qism: <b>{ep}</b>\n"
        f"👁 Ko'rishlar: <b>{movie['views'][ep]}</b>"
    )
    await context.bot.send_video(
        chat_id=q.from_user.id,
        video=eps[idx],
        caption=caption,
        parse_mode="HTML",
        reply_markup=kb,
    )

# ===================== 🆘 YORDAM =====================
async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✍️ Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\n"
        "Admin tez orada javob beradi.",
        parse_mode="HTML",
    )
    context.user_data["awaiting_help"] = True

# ===================== 📥 ILOVA O'RNATISH =====================
async def handle_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = DB.get("settings", {})
    f_id = s.get("install_file_id")
    v_id = s.get("install_video_id")
    if not f_id and not v_id:
        await update.message.reply_text("⏳ Admin hali ilova fayl/video joylamagan.")
        return
    if v_id:
        await update.message.reply_video(v_id, caption="📲 <b>Ilovani o'rnatish videosi</b>", parse_mode="HTML")
    if f_id:
        await update.message.reply_document(f_id, caption="📦 <b>Ilova fayli</b>", parse_mode="HTML")

# ===================== 📩 MATN/RASM/VIDEO HANDLER =====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = update.message.text or ""

    # Admin menyu
    if uid == ADMIN_ID and text in (
        "🎬 Kino joylash", "➕ Qism qo'shish", "💰 Qismni pullik qilish",
        "📊 Statistika", "📢 Kanalga post", "🔒 Majburiy kanal",
        "💳 Karta raqami", "📲 Ilova fayl/video", "🏠 Asosiy menyu"
    ):
        await admin_buttons(update, context, text)
        return

    # Foydalanuvchi tugmalari
    if text == "🆘 Yordam":
        await handle_help(update, context)
        return
    if text == "📥 Ilovani o'rnatish":
        await handle_install(update, context)
        return

    # Admin state-based inputs
    if uid == ADMIN_ID and await admin_state_handler(update, context, text):
        return

    # Yordam xabari
    if context.user_data.pop("awaiting_help", False):
        caption = (
            f"🆘 <b>Yordam so'rovi</b>\n"
            f"👤 {user.full_name} (@{user.username or '-'})\n"
            f"🆔 <code>{uid}</code>\n\n"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✉️ Javob berish", callback_data=f"reply|{uid}")]])
        if update.message.text:
            await context.bot.send_message(ADMIN_ID, caption + update.message.text, parse_mode="HTML", reply_markup=kb)
        elif update.message.photo:
            await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=caption + (update.message.caption or ""), parse_mode="HTML", reply_markup=kb)
        elif update.message.video:
            await context.bot.send_video(ADMIN_ID, update.message.video.file_id, caption=caption + (update.message.caption or ""), parse_mode="HTML", reply_markup=kb)
        await update.message.reply_text("✅ Xabaringiz adminga yuborildi!")
        return

    # Admin javob berish
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        target = context.user_data.pop("reply_to")
        try:
            if update.message.text:
                await context.bot.send_message(target, f"✉️ <b>Admin javobi:</b>\n{update.message.text}", parse_mode="HTML")
            elif update.message.photo:
                await context.bot.send_photo(target, update.message.photo[-1].file_id, caption=update.message.caption or "")
            elif update.message.video:
                await context.bot.send_video(target, update.message.video.file_id, caption=update.message.caption or "")
            await update.message.reply_text("✅ Yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        return

    # Chek rasmi kutilyapti
    if context.user_data.get("awaiting_check"):
        if not update.message.photo:
            await update.message.reply_text("📸 Iltimos chek <b>rasmini</b> yuboring.", parse_mode="HTML")
            return
        info = context.user_data.pop("awaiting_check")
        pid = f"{uid}_{datetime.now().timestamp()}"
        DB["pending_payments"][pid] = {
            "user_id": uid, "code": info["code"], "ep": info["ep"],
            "price": info["price"], "status": "pending",
        }
        save()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok|{pid}"),
             InlineKeyboardButton("❌ Bekor qilish", callback_data=f"pay_no|{pid}")],
        ])
        cap = (
            f"💳 <b>Yangi to'lov cheki</b>\n"
            f"👤 {user.full_name} (@{user.username or '-'})\n"
            f"🆔 <code>{uid}</code>\n"
            f"🎬 Kino kodi: <b>{info['code']}</b>\n"
            f"🎞 Qism: <b>{info['ep']}</b>\n"
            f"💰 Narx: <b>{info['price']} so'm</b>"
        )
        await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=cap, parse_mode="HTML", reply_markup=kb)
        await update.message.reply_text(
            "✅ Chekingiz qabul qilindi!\n⏳ Admin 5 daqiqadan 2 soatgacha tekshiradi.\nTasdiqlangach video avtomatik yuboriladi."
        )
        return

    # Kino kodi sifatida qarash
    if text.strip().isdigit() or text.strip():
        code = text.strip()
        if code in DB["movies"]:
            await send_movie_menu(update, context, code)
            return

    await update.message.reply_text("❓ Bunday kod topilmadi. Boshqa kod yuboring yoki tugmalardan foydalaning.")

# ===================== 💳 TO'LOV TASDIQLASH =====================
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
        await q.edit_message_caption(q.message.caption + "\n\n❌ <b>Bekor qilindi</b>", parse_mode="HTML")
        await context.bot.send_message(
            pay["user_id"],
            "❌ <b>To'lovingiz rad etildi.</b>\nQayta urinib ko'ring yoki 🆘 Yordam orqali savolingizni yozing.",
            parse_mode="HTML",
        )
        return

    # Tasdiqlash
    pay["status"] = "approved"
    uid = str(pay["user_id"])
    DB["users"].setdefault(uid, {}).setdefault("paid_episodes", {})[f"{pay['code']}_{pay['ep']}"] = True
    # Keyingi qismni ham bepul qilamiz (foydalanuvchi talabi)
    try:
        next_ep = str(int(pay["ep"]) + 1)
        DB["users"][uid]["paid_episodes"][f"{pay['code']}_{next_ep}"] = True
    except Exception:
        pass
    save()

    await q.edit_message_caption(q.message.caption + "\n\n✅ <b>Tasdiqlandi</b>", parse_mode="HTML")
    await context.bot.send_message(
        pay["user_id"],
        "✅ <b>Admin to'lovingizni tasdiqladi!</b>\n⏳ 1 daqiqa kuting, video avtomatik yuboriladi...",
        parse_mode="HTML",
    )

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
            save()
            await context.bot.send_video(
                pay["user_id"],
                eps[idx],
                caption=f"🎬 <b>{movie.get('title')}</b>\n🎞 Qism: {pay['ep']}",
                parse_mode="HTML",
            )

    context.application.create_task(send_later())

# ===================== ✉️ YORDAMGA JAVOB =====================
async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, uid = q.data.split("|")
    context.user_data["reply_to"] = int(uid)
    await q.message.reply_text(f"✍️ <code>{uid}</code> ga yuboriladigan xabarni yozing (matn/rasm/video).", parse_mode="HTML")

# ===================== 👑 ADMIN TUGMALARI =====================
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    ud = context.user_data
    ud.pop("admin_state", None)

    if text == "🏠 Asosiy menyu":
        await update.message.reply_text("🏠 Asosiy menyu", reply_markup=main_menu_kb())
        return

    if text == "🎬 Kino joylash":
        ud["admin_state"] = "movie_poster"
        ud["new_movie"] = {"episodes": []}
        await update.message.reply_text("🖼 Avval kino uchun <b>rasm (poster)</b> yuboring.", parse_mode="HTML")
        return

    if text == "➕ Qism qo'shish":
        ud["admin_state"] = "addep_code"
        await update.message.reply_text("🔢 Mavjud kino <b>kodini</b> yuboring:", parse_mode="HTML")
        return

    if text == "💰 Qismni pullik qilish":
        ud["admin_state"] = "paid_code"
        await update.message.reply_text("🔢 Kino <b>kodini</b> yuboring:", parse_mode="HTML")
        return

    if text == "📊 Statistika":
        total_users = len(DB["users"])
        total_movies = len(DB["movies"])
        total_views = DB.get("stats", {}).get("total_views", 0)
        lines = [f"📊 <b>Statistika</b>\n",
                 f"👥 Foydalanuvchilar: <b>{total_users}</b>",
                 f"🎬 Kinolar: <b>{total_movies}</b>",
                 f"👁 Umumiy ko'rishlar: <b>{total_views}</b>\n",
                 f"<b>Kinolar bo'yicha:</b>"]
        for code, m in DB["movies"].items():
            views = m.get("views", {})
            total = sum(views.values())
            lines.append(f"• <code>{code}</code> — {m.get('title','?')} ({len(m.get('episodes',[]))} qism, 👁 {total})")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if text == "📢 Kanalga post":
        ud["admin_state"] = "post_code"
        await update.message.reply_text("🔢 Kanalga yuboriladigan kino <b>kodini</b> yuboring:", parse_mode="HTML")
        return

    if text == "🔒 Majburiy kanal":
        lines = ["🔒 <b>Majburiy kanallar</b>\n"]
        for i, c in enumerate(DB.get("channels", []), 1):
            lines.append(f"{i}. {c['title']} — {c['username']}")
        lines.append("\nYangi qo'shish uchun: <code>@username | Kanal nomi | https://t.me/...</code>")
        lines.append("O'chirish: <code>/delch raqam</code>")
        ud["admin_state"] = "add_channel"
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if text == "💳 Karta raqami":
        ud["admin_state"] = "set_card"
        await update.message.reply_text(
            f"💳 Hozirgi: <code>{DB.get('card_number') or 'yoq'}</code>\nYangi karta raqamini yuboring:",
            parse_mode="HTML",
        )
        return

    if text == "📲 Ilova fayl/video":
        ud["admin_state"] = "install_file"
        await update.message.reply_text("📦 Ilova <b>faylini</b> (document) yuboring:", parse_mode="HTML")
        return

# ===================== 👑 ADMIN STATE HANDLER =====================
async def admin_state_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, text):
    ud = context.user_data
    state = ud.get("admin_state")
    if not state:
        return False

    # Kanal qo'shish
    if state == "add_channel":
        try:
            parts = [p.strip() for p in text.split("|")]
            username, title, url = parts[0], parts[1], parts[2]
            DB.setdefault("channels", []).append({"username": username, "title": title, "url": url})
            save()
            await update.message.reply_text(f"✅ Qo'shildi: {title}")
        except Exception:
            await update.message.reply_text("❌ Format: @username | Nom | https://t.me/...")
        ud.pop("admin_state", None)
        return True

    # Karta raqami
    if state == "set_card":
        DB["card_number"] = text
        save()
        await update.message.reply_text(f"✅ Karta saqlandi: <code>{text}</code>", parse_mode="HTML")
        ud.pop("admin_state", None)
        return True

    # Qism qo'shish — kod
    if state == "addep_code":
        if text not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            ud.pop("admin_state", None)
            return True
        ud["addep_code"] = text
        ud["admin_state"] = "addep_video"
        await update.message.reply_text(f"🎬 <b>{text}</b> ga qo'shiladigan video(lar)ni yuboring. Tugagach <b>NEXT</b> deb yozing.", parse_mode="HTML")
        return True

    if state == "addep_video" and text.upper() == "NEXT":
        await update.message.reply_text("✅ Qismlar qo'shildi!", reply_markup=admin_menu_kb())
        ud.pop("admin_state", None)
        ud.pop("addep_code", None)
        return True

    # Pullik qilish — kod
    if state == "paid_code":
        if text not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            ud.pop("admin_state", None)
            return True
        ud["paid_code"] = text
        ud["admin_state"] = "paid_ep"
        await update.message.reply_text("🎞 Nechinchi qismni pullik qilamiz? (raqam)")
        return True

    if state == "paid_ep":
        if not text.isdigit():
            await update.message.reply_text("❌ Raqam yuboring.")
            return True
        ud["paid_ep"] = text
        ud["admin_state"] = "paid_price"
        await update.message.reply_text("💰 Narxini so'mda yuboring (masalan: 10000)")
        return True

    if state == "paid_price":
        if not text.isdigit():
            await update.message.reply_text("❌ Faqat raqam.")
            return True
        code = ud.pop("paid_code")
        ep = ud.pop("paid_ep")
        DB["movies"][code].setdefault("prices", {})[ep] = int(text)
        save()
        await update.message.reply_text(f"✅ Saqlandi: <b>{code}</b> {ep}-qism — {text} so'm", parse_mode="HTML")
        ud.pop("admin_state", None)
        return True

    # Kino joylash — NEXT
    if state == "movie_episodes" and text.upper() == "NEXT":
        ud["admin_state"] = "movie_code"
        await update.message.reply_text("🔢 Kino <b>kodini</b> kiriting (masalan: 1):", parse_mode="HTML")
        return True

    # Kino joylash — kod
    if state == "movie_code":
        code = text.strip()
        nm = ud.pop("new_movie", {})
        if not nm.get("episodes"):
            await update.message.reply_text("❌ Hech qism yuklanmagan.")
            ud.pop("admin_state", None)
            return True
        DB["movies"][code] = {
            "title": nm.get("title") or f"Kino #{code}",
            "poster_file_id": nm.get("poster_file_id"),
            "episodes": nm["episodes"],
            "views": {},
            "prices": {},
        }
        save()
        await update.message.reply_text(
            f"✅ <b>Kino saqlandi!</b>\nKod: <code>{code}</code>\nQismlar: {len(nm['episodes'])}",
            parse_mode="HTML", reply_markup=admin_menu_kb(),
        )
        ud.pop("admin_state", None)
        return True

    # Kino nomi
    if state == "movie_title":
        ud["new_movie"]["title"] = text
        ud["admin_state"] = "movie_episodes"
        await update.message.reply_text("🎬 Endi <b>video(lar)ni</b> yuboring. Tugagach <b>NEXT</b> yozing.", parse_mode="HTML")
        return True

    # Post — kod
    if state == "post_code":
        if text not in DB["movies"]:
            await update.message.reply_text("❌ Bunday kod yo'q.")
            ud.pop("admin_state", None)
            return True
        ud["post_code"] = text
        ud["admin_state"] = "post_channel"
        await update.message.reply_text("📢 Kanal username (masalan: @kino_kanal):")
        return True

    if state == "post_channel":
        code = ud.pop("post_code")
        channel = text.strip()
        m = DB["movies"][code]
        bot_username = (await context.bot.get_me()).username
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Tomosha qilish", url=f"https://t.me/{bot_username}?start=code_{code}")]
        ])
        caption = (
            f"🎬 <b>{m.get('title')}</b>\n"
            f"📺 Qismlar: <b>{len(m.get('episodes',[]))}</b>\n"
            f"🔢 Kod: <b>{code}</b>\n\n"
            f"Tomosha qilish uchun tugmani bosing 👇"
        )
        try:
            if m.get("poster_file_id"):
                await context.bot.send_photo(channel, m["poster_file_id"], caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await context.bot.send_message(channel, caption, parse_mode="HTML", reply_markup=kb)
            await update.message.reply_text("✅ Kanalga yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
        ud.pop("admin_state", None)
        return True

    return False

# ===================== 🖼 RASM/VIDEO/FAYL (ADMIN) =====================
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ud = context.user_data
    state = ud.get("admin_state")

    # Yordam so'rovi (foydalanuvchi)
    if context.user_data.get("awaiting_help"):
        await text_handler(update, context)
        return

    # Admin javob berish
    if uid == ADMIN_ID and "reply_to" in context.user_data:
        await text_handler(update, context)
        return

    # Chek rasmi
    if context.user_data.get("awaiting_check") and update.message.photo:
        await text_handler(update, context)
        return

    if uid != ADMIN_ID:
        return

    # Ilova fayl/video
    if state == "install_file":
        if update.message.document:
            DB["settings"]["install_file_id"] = update.message.document.file_id
            save()
            ud["admin_state"] = "install_video"
            await update.message.reply_text("✅ Fayl saqlandi. Endi <b>videoni</b> yuboring:", parse_mode="HTML")
        else:
            await update.message.reply_text("📦 Document turidagi fayl yuboring.")
        return

    if state == "install_video":
        if update.message.video:
            DB["settings"]["install_video_id"] = update.message.video.file_id
            save()
            await update.message.reply_text("✅ Ilova fayl va video saqlandi!", reply_markup=admin_menu_kb())
            ud.pop("admin_state", None)
        else:
            await update.message.reply_text("🎥 Video yuboring.")
        return

    # Kino joylash — poster
    if state == "movie_poster":
        if not update.message.photo:
            await update.message.reply_text("🖼 Rasm yuboring.")
            return
        ud["new_movie"]["poster_file_id"] = update.message.photo[-1].file_id
        ud["admin_state"] = "movie_title"
        await update.message.reply_text("✍️ Kino <b>nomini</b> yuboring:", parse_mode="HTML")
        return

    # Kino qismlari
    if state == "movie_episodes" and update.message.video:
        ud["new_movie"]["episodes"].append(update.message.video.file_id)
        await update.message.reply_text(f"✅ Qism qo'shildi ({len(ud['new_movie']['episodes'])} ta). Yana yuboring yoki <b>NEXT</b> yozing.", parse_mode="HTML")
        return

    # Qism qo'shish — video
    if state == "addep_video" and update.message.video:
        code = ud.get("addep_code")
        if code and code in DB["movies"]:
            DB["movies"][code]["episodes"].append(update.message.video.file_id)
            save()
            await update.message.reply_text(f"✅ Qism qo'shildi ({len(DB['movies'][code]['episodes'])}-qism). Yana yuboring yoki <b>NEXT</b>.", parse_mode="HTML")
        return

# ===================== /delch =====================
async def delch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        i = int(context.args[0]) - 1
        removed = DB["channels"].pop(i)
        save()
        await update.message.reply_text(f"✅ O'chirildi: {removed['title']}")
    except Exception:
        await update.message.reply_text("Format: /delch 1")

# ===================== 🎛 BOT COMMANDS (MENU) =====================
async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "🚀 Botni ishga tushirish"),
        BotCommand("help", "🆘 Yordam"),
    ])

# ===================== 🌐 HEALTH CHECK SERVER (Fly.io 8080) =====================
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Kino Bot ishlayapti")

    def log_message(self, format, *args):
        return  # logni o'chiramiz

def start_health_server():
    port = int(os.environ.get("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        logger.info(f"🌐 Health server 0.0.0.0:{port} da ishga tushdi")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health server xato: {e}")

# ===================== 🏁 MAIN =====================
async def post_init_hook(app):
    # Webhook bo'lsa o'chiramiz va eski yangilanishlarni tozalaymiz —
    # bu Conflict (terminated by other getUpdates request) xatosini oldini oladi
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("🧹 Webhook o'chirildi va eski updates tashlandi")
    except Exception as e:
        logger.warning(f"delete_webhook xato (e'tiborsiz): {e}")
    await set_commands(app)
    save()  # boshlang'ich strukturani JSONBin ga yozish

def main():
    # Fly.io health check uchun fon HTTP serverni ishga tushiramiz
    threading.Thread(target=start_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init_hook).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("delch", delch))

    app.add_handler(CallbackQueryHandler(cb_check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_episode, pattern="^ep\\|"))
    app.add_handler(CallbackQueryHandler(cb_payment, pattern="^(pay_ok|pay_no)\\|"))
    app.add_handler(CallbackQueryHandler(cb_reply, pattern="^reply\\|"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, media_handler))

    logger.info("🤖 Bot ishga tushdi! Barcha ma'lumotlar JSONBin ga saqlanadi.")

    # Conflict-resilient loop: agar boshqa instance polling qilsa, kutamiz va qayta urinamiz.
    # Bu yerda crash qilmaymiz — Fly machineni qayta tug'masin.
    import time
    backoff = 5
    while True:
        try:
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                close_loop=False,
                stop_signals=None,
            )
            logger.info("Polling normal tugadi, chiqamiz.")
            break
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt — chiqamiz.")
            break
        except Exception as e:
            msg = str(e)
            if "Conflict" in msg or "terminated by other getUpdates" in msg:
                logger.warning(f"⚠️ Conflict (boshqa instance polling qilyapti). {backoff}s kutamiz va qayta urinamiz...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                # Webhook tozalashga yana urinamiz
                try:
                    import asyncio as _aio
                    _aio.run(app.bot.delete_webhook(drop_pending_updates=True))
                except Exception:
                    pass
                continue
            logger.error(f"❌ Polling xato: {e}. 10s dan keyin qayta urinamiz...")
            time.sleep(10)
            continue

    logger.info("💾 To'xtatishdan oldin oxirgi saqlash...")
    try:
        save()
    except Exception as e:
        logger.error(f"Save xato: {e}")

if __name__ == "__main__":
    main()

