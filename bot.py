# -*- coding: utf-8 -*-
"""
DramlarUz Kino Bot
------------------
- "Barcha kinolar" -> top 10 kino surati ALBOM (media group) bilan yuboriladi
  (tepadan pastga scroll qilib koʻrasiz, har birida nom/kod/koʻrishlar/qismlar)
- Albom tagida "📂 Qolgan kinolar" tugmasi -> keyingi 10 ta kino
- "Kino kodini" yuborsangiz -> oʻsha kino haqida toʻliq ma'lumot + video

O'rnatish:
    pip install aiogram==3.13.1
    python bot.py
"""

import asyncio
import logging
import sqlite3
from contextlib import closing

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
)

# =========================================================
#  SOZLAMALAR
# =========================================================
BOT_TOKEN = "BU_YERGA_BOT_TOKENINI_QOYING"   # @BotFather dan oling
ADMINS = [123456789]                          # o'zingizni Telegram ID'ingiz
KANAL_LINK = "https://t.me/kino_kodlari"     # "Kino kodlari kanali" tugmasi
PAGE_SIZE = 10                                # bir sahifada nechta kino
DB_PATH = "kinolar.db"

logging.basicConfig(level=logging.INFO)

# =========================================================
#  BAZA
# =========================================================
def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with closing(db()) as con, con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS kinolar (
                kod         INTEGER PRIMARY KEY,
                nom         TEXT NOT NULL,
                qism        INTEGER DEFAULT 1,
                korilgan    INTEGER DEFAULT 0,
                photo_id    TEXT,        -- katta surat (file_id)
                video_id    TEXT,        -- video file_id (ixtiyoriy)
                tavsif      TEXT
            )
        """)
        # Demo ma'lumotlar (faqat bo'sh bo'lsa)
        cur = con.execute("SELECT COUNT(*) FROM kinolar")
        if cur.fetchone()[0] == 0:
            demo = [
                (8889, "Xotinboz Qotilning Alamli Qismati", 5, 8889, None, None, "Drama / Triller"),
                (441,  "Drama yangi",                       80, 441,  None, None, "Uzun seriya"),
            ]
            con.executemany(
                "INSERT INTO kinolar(kod,nom,qism,korilgan,photo_id,video_id,tavsif) VALUES (?,?,?,?,?,?,?)",
                demo,
            )

def kinolar_page(offset: int, limit: int = PAGE_SIZE):
    with closing(db()) as con:
        cur = con.execute(
            "SELECT kod,nom,qism,korilgan,photo_id,tavsif "
            "FROM kinolar ORDER BY korilgan DESC, kod DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return cur.fetchall()

def kinolar_count() -> int:
    with closing(db()) as con:
        return con.execute("SELECT COUNT(*) FROM kinolar").fetchone()[0]

def kino_by_kod(kod: int):
    with closing(db()) as con:
        cur = con.execute(
            "SELECT kod,nom,qism,korilgan,photo_id,video_id,tavsif FROM kinolar WHERE kod=?",
            (kod,),
        )
        return cur.fetchone()

def korishni_oshir(kod: int):
    with closing(db()) as con, con:
        con.execute("UPDATE kinolar SET korilgan = korilgan + 1 WHERE kod=?", (kod,))

# =========================================================
#  KEYBOARDLAR
# =========================================================
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆘 Yordam"), KeyboardButton(text="📁 Ilovani o'rnatish")],
            [KeyboardButton(text="🎬 Barcha kinolar")],
            [KeyboardButton(text="🔒 Boshqarish")],
        ],
        resize_keyboard=True,
    )

def page_keyboard(offset: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️ Oldingi", callback_data=f"page:{max(0, offset - PAGE_SIZE)}"
        ))
    if offset + PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(
            text="📂 Qolgan kinolar", callback_data=f"page:{offset + PAGE_SIZE}"
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📣 Kino kodlari kanali", url=KANAL_LINK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# =========================================================
#  HANDLERLAR
# =========================================================
dp = Dispatcher()

@dp.message(CommandStart())
async def start(msg: Message):
    await msg.answer(
        "🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
        "Kino <b>kodini</b> yuboring — video <b>darhol</b> keladi! ⚡️",
        reply_markup=main_menu(),
    )

@dp.message(F.text == "🆘 Yordam")
async def yordam(msg: Message):
    await msg.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "• Kino kodini yuboring — video keladi\n"
        "• «🎬 Barcha kinolar» — top 10 kino + qolganlari\n"
        "• Yangi kodlar uchun: " + KANAL_LINK
    )

@dp.message(F.text == "📁 Ilovani o'rnatish")
async def ilova(msg: Message):
    await msg.answer("📁 Ilovani o'rnatish havolasi: " + KANAL_LINK)

@dp.message(F.text == "🔒 Boshqarish")
async def boshqarish(msg: Message):
    if msg.from_user.id not in ADMINS:
        return await msg.answer("⛔️ Faqat admin uchun.")
    await msg.answer(
        "🔒 <b>Admin panel</b>\n\n"
        "Kino qo'shish:\n"
        "<code>/add KOD|Nom|qism|tavsif</code>\n"
        "Keyin kino suratini reply qilib yuboring: <code>/setphoto KOD</code>\n"
        "Videoni reply qilib yuboring: <code>/setvideo KOD</code>"
    )

# ---------- BARCHA KINOLAR (top 10 ALBUM) ----------
async def send_page(msg_or_cb, offset: int):
    rows = kinolar_page(offset)
    total = kinolar_count()
    if not rows:
        text = "🎬 Hozircha kinolar yo'q."
        if isinstance(msg_or_cb, CallbackQuery):
            await msg_or_cb.message.answer(text)
        else:
            await msg_or_cb.answer(text)
        return

    chat_id = (msg_or_cb.message.chat.id
               if isinstance(msg_or_cb, CallbackQuery)
               else msg_or_cb.chat.id)
    bot: Bot = msg_or_cb.bot

    # Media album (1..10 ta surat). Surati yo'qlar oddiy matn ko'rinishida yuboriladi.
    media, no_photo = [], []
    for i, (kod, nom, qism, korilgan, photo_id, tavsif) in enumerate(rows, start=1):
        caption = (
            f"<b>{offset + i}. 🎬 {nom}</b>\n"
            f"📌 Kod: <code>{kod}</code>\n"
            f"👁 Ko'rilgan: <b>{korilgan}</b>\n"
            f"🎞 Qismlar: <b>{qism}</b>"
        )
        if photo_id:
            media.append(InputMediaPhoto(media=photo_id, caption=caption))
        else:
            no_photo.append(caption)

    if media:
        await bot.send_media_group(chat_id=chat_id, media=media)

    # Album ostidagi yagona xabar — sarlavha + tugmalar
    header = (
        f"🎬 <b>Kinolar</b> ({offset + 1}–{offset + len(rows)} / {total})\n"
        "Tepaga scroll qilib barcha 10 tasini ko'ring 👆"
    )
    if no_photo:
        header += "\n\n" + "\n\n".join(no_photo)

    await bot.send_message(
        chat_id=chat_id,
        text=header,
        reply_markup=page_keyboard(offset, total),
    )

@dp.message(F.text == "🎬 Barcha kinolar")
async def barcha_kinolar(msg: Message):
    await send_page(msg, 0)

@dp.callback_query(F.data.startswith("page:"))
async def page_cb(cb: CallbackQuery):
    offset = int(cb.data.split(":")[1])
    await cb.answer()
    await send_page(cb, offset)

# ---------- KOD bo'yicha kino ----------
@dp.message(F.text.regexp(r"^\d+$"))
async def by_kod(msg: Message):
    kod = int(msg.text)
    row = kino_by_kod(kod)
    if not row:
        return await msg.answer("❌ Bunday kodli kino topilmadi.")
    kod, nom, qism, korilgan, photo_id, video_id, tavsif = row
    korishni_oshir(kod)
    caption = (
        f"🎬 <b>{nom}</b>\n"
        f"📌 Kod: <code>{kod}</code>\n"
        f"👁 Ko'rilgan: <b>{korilgan + 1}</b>\n"
        f"🎞 Qismlar: <b>{qism}</b>\n"
        f"📝 {tavsif or ''}"
    )
    if video_id:
        await msg.answer_video(video_id, caption=caption)
    elif photo_id:
        await msg.answer_photo(photo_id, caption=caption)
    else:
        await msg.answer(caption)

# ---------- ADMIN ----------
@dp.message(Command("add"))
async def add_kino(msg: Message):
    if msg.from_user.id not in ADMINS:
        return
    try:
        payload = msg.text.split(" ", 1)[1]
        kod_s, nom, qism_s, tavsif = payload.split("|", 3)
        with closing(db()) as con, con:
            con.execute(
                "INSERT OR REPLACE INTO kinolar(kod,nom,qism,korilgan,tavsif) "
                "VALUES (?,?,?,COALESCE((SELECT korilgan FROM kinolar WHERE kod=?),0),?)",
                (int(kod_s), nom.strip(), int(qism_s), int(kod_s), tavsif.strip()),
            )
        await msg.answer(f"✅ Qo'shildi: {nom} (kod {kod_s})")
    except Exception as e:
        await msg.answer(f"❌ Format: /add KOD|Nom|qism|tavsif\n{e}")

@dp.message(Command("setphoto"))
async def setphoto(msg: Message):
    if msg.from_user.id not in ADMINS or not msg.reply_to_message or not msg.reply_to_message.photo:
        return await msg.answer("Suratga reply qilib: /setphoto KOD")
    try:
        kod = int(msg.text.split()[1])
        photo_id = msg.reply_to_message.photo[-1].file_id
        with closing(db()) as con, con:
            con.execute("UPDATE kinolar SET photo_id=? WHERE kod=?", (photo_id, kod))
        await msg.answer(f"✅ Surat saqlandi (kod {kod})")
    except Exception as e:
        await msg.answer(f"❌ {e}")

@dp.message(Command("setvideo"))
async def setvideo(msg: Message):
    if msg.from_user.id not in ADMINS or not msg.reply_to_message or not msg.reply_to_message.video:
        return await msg.answer("Videoga reply qilib: /setvideo KOD")
    try:
        kod = int(msg.text.split()[1])
        video_id = msg.reply_to_message.video.file_id
        with closing(db()) as con, con:
            con.execute("UPDATE kinolar SET video_id=? WHERE kod=?", (video_id, kod))
        await msg.answer(f"✅ Video saqlandi (kod {kod})")
    except Exception as e:
        await msg.answer(f"❌ {e}")

# =========================================================
#  ISHGA TUSHIRISH
# =========================================================
async def main():
    init_db()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
