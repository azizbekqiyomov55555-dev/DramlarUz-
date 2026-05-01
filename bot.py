# -*- coding: utf-8 -*-
"""
Kino Bot - Bot API 9.4 rangli tugmalar + Premium Emoji
python-telegram-bot v22+ | api_kwargs usuli
"""
import logging, asyncio, json, time
from datetime import datetime
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

BOT_TOKEN       = "8622992113:AAHif8dJz3eq_Zm8PTafxpSiNsEqE5VmoMc"
ADMIN_ID        = 8537782289
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PE = {
    "film":    "5374062524014462236",
    "help":    "5379748062124056162",
    "install": "5361540739737993513",
    "home":    "5368324170671202286",
    "add":     "5373141891321699086",
    "money":   "5361540739737993513",
    "stats":   "5373141891321699086",
    "post":    "5373141891321699086",
    "lock":    "5361540739737993513",
    "card":    "5373141891321699086",
    "phone":   "5373141891321699086",
    "play":    "5373141891321699086",
    "share":   "5373141891321699086",
    "check":   "5373141891321699086",
    "reply":   "5373141891321699086",
    "watch":   "5373141891321699086",
    "emoji":   "5373141891321699086",
    "back":    "5373141891321699086",
    "close":   "5373141891321699086",
    "reset":   "5361540739737993513",
    "price":   "5361540739737993513",
}

PE_LABELS = {
    "film":"🎬 Kino","help":"🆘 Yordam","install":"📥 O'rnatish",
    "home":"🏠 Bosh menyu","add":"➕ Qo'shish","money":"💰 Pul",
    "stats":"📊 Statistika","post":"📢 Post","lock":"🔒 Qulf",
    "card":"💳 Karta","phone":"📲 Telefon","play":"▶️ O'ynatish",
    "share":"📤 Ulashish","check":"✅ Tasdiqlash","reply":"✉️ Javob",
    "watch":"🎬 Tomosha","emoji":"🎭 Emoji","back":"⬅️ Orqaga",
    "close":"✅ Yopish","reset":"🔄 Tiklash","price":"💰 Narx",
}

DEFAULT_DB = {
    "users":{},"movies":{},"channels":[],"card_number":"",
    "pending_payments":{},"settings":{"install_file_id":None,"install_video_id":None},
    "stats":{"total_views":0},"emoji_ids":{},
}

def db_load():
    for attempt in range(3):
        try:
            r = requests.get(f"{JSONBIN_URL}/latest",
                headers={"X-Master-Key": JSONBIN_API_KEY}, timeout=20)
            if r.status_code == 200:
                data = r.json().get("record", {})
                for k, dv in DEFAULT_DB.items():
                    if k not in data: data[k] = json.loads(json.dumps(dv))
                    elif isinstance(dv,dict) and not isinstance(data[k],dict): data[k]=json.loads(json.dumps(dv))
                    elif isinstance(dv,list) and not isinstance(data[k],list): data[k]=json.loads(json.dumps(dv))
                logger.info(f"Yuklandi: {len(data.get('users',{}))} user, {len(data.get('movies',{}))} kino")
                return data
        except Exception as e:
            logger.error(f"DB load #{attempt+1}: {e}")
    return json.loads(json.dumps(DEFAULT_DB))

def db_save(data):
    for attempt in range(3):
        try:
            r = requests.put(JSONBIN_URL,
                headers={"X-Master-Key":JSONBIN_API_KEY,"Content-Type":"application/json","X-Bin-Versioning":"false"},
                data=json.dumps(data, ensure_ascii=False), timeout=20)
            if r.status_code == 200: return True
        except Exception as e:
            logger.error(f"DB save #{attempt+1}: {e}")
    return False

DB = db_load()

def save():
    ok = db_save(DB)
    if not ok: logger.error("Saqlash muvaffaqiyatsiz!")
    return ok

def pe(key):
    return DB.get("emoji_ids",{}).get(key) or DEFAULT_PE.get(key,"")

# ══════════════════════════════════════════════════════════
# TUGMA YARATISH — dict formatida (api_kwargs uchun)
# ══════════════════════════════════════════════════════════

def ibtn(text, data=None, url=None, style=None, ekey=None):
    """Inline keyboard button dict"""
    b = {"text": text}
    if data: b["callback_data"] = data
    if url:  b["url"] = url
    if style: b["style"] = style
    if ekey:
        eid = pe(ekey)
        if eid: b["icon_custom_emoji_id"] = eid
    return b

def rbtn(text, style=None, ekey=None):
    """Reply keyboard button dict"""
    b = {"text": text}
    if style: b["style"] = style
    if ekey:
        eid = pe(ekey)
        if eid: b["icon_custom_emoji_id"] = eid
    return b

def ikb(rows):
    """Inline keyboard markup"""
    return {"inline_keyboard": rows}

def rkb(rows, resize=True):
    """Reply keyboard markup"""
    return {"keyboard": rows, "resize_keyboard": resize}

# ══════════════════════════════════════════════════════════
# KLAVIATURALAR
# ══════════════════════════════════════════════════════════

def main_menu_kb():
    return rkb([[
        rbtn("🆘 Yordam",            style="primary", ekey="help"),
        rbtn("📥 Ilovani o'rnatish", style="success", ekey="install"),
    ]])

def admin_menu_kb():
    return rkb([
        [rbtn("🎬 Kino joylash",        style="success", ekey="film"),
         rbtn("➕ Qism qo'shish",        style="primary", ekey="add")],
        [rbtn("💰 Qismni pullik qilish", style="danger",  ekey="money"),
         rbtn("📊 Statistika",           style="primary", ekey="stats")],
        [rbtn("📢 Kanalga post",         style="primary", ekey="post"),
         rbtn("🔒 Majburiy kanal",       style="danger",  ekey="lock")],
        [rbtn("💳 Karta raqami",         style="success", ekey="card"),
         rbtn("📲 Ilova fayl/video",     style="primary", ekey="phone")],
        [rbtn("🎭 Emoji sozlamalari",    style="primary", ekey="emoji")],
        [rbtn("🏠 Asosiy menyu",         style="success", ekey="home")],
    ])

def subscription_kb(channels):
    rows = [[ibtn(f"📢 {c['title']}", url=c["url"], style="primary", ekey="post")] for c in channels]
    rows.append([ibtn("✅ Tekshirish", data="check_sub", style="success", ekey="check")])
    return ikb(rows)

def movie_episodes_kb(movie, code, user_id):
    eps=movie.get("episodes",[]); prices=movie.get("prices",{})
    paid=DB["users"].get(str(user_id),{}).get("paid_episodes",{})
    rows=[]
    for i in range(len(eps)):
        ek=str(i+1); price=prices.get(ek)
        locked = price and not paid.get(f"{code}_{ek}")
        if locked:
            rows.append([ibtn(f"🔒 {ek}-qism  💰 {price} so'm", data=f"ep|{code}|{ek}", style="danger",   ekey="lock")])
        else:
            rows.append([ibtn(f"▶️ {ek}-qism",                  data=f"ep|{code}|{ek}", style="success", ekey="play")])
    return ikb(rows)

def payment_admin_kb(pid):
    return ikb([[
        ibtn("✅ Tasdiqlash",   data=f"pay_ok|{pid}", style="success", ekey="check"),
        ibtn("❌ Bekor qilish", data=f"pay_no|{pid}", style="danger",  ekey="lock"),
    ]])

def share_kb(url):
    return ikb([[ibtn("📤 Do'stlarga ulashish", url=url, style="primary", ekey="share")]])

def channel_post_kb(bot_username, code):
    return ikb([[ibtn("🎬 Tomosha qilish",
        url=f"https://t.me/{bot_username}?start=code_{code}", style="success", ekey="watch")]])

def reply_admin_kb(uid):
    return ikb([[ibtn("✉️ Javob berish", data=f"reply|{uid}", style="primary", ekey="reply")]])

def stats_kb():
    return ikb([[ibtn("🔄 Yangilash", data="refresh_stats", style="primary", ekey="stats")]])

def movie_added_kb(code):
    return ikb([[
        ibtn("📹 Qism qo'shish",  data=f"quick_add_ep|{code}", style="success", ekey="add"),
        ibtn("💰 Narx belgilash", data=f"quick_price|{code}",  style="primary", ekey="price"),
    ]])

def payment_sent_kb():
    return ikb([[ibtn("⏳ Tasdiqlanishini kuting", data="waiting_confirm", style="primary", ekey="check")]])

def help_kb():
    return ikb([[ibtn("🏠 Bosh menyu", data="go_home", style="success", ekey="home")]])

def emoji_list_kb():
    rows=[]; keys=list(PE_LABELS.keys())
    for i in range(0,len(keys),2):
        row=[]
        for key in keys[i:i+2]:
            cur=DB.get("emoji_ids",{}).get(key) or DEFAULT_PE.get(key,"")
            short=f"…{cur[-6:]}" if cur else "yo'q"
            row.append(ibtn(f"{PE_LABELS.get(key,key)} [{short}]",
                            data=f"emoji_edit|{key}", style="primary", ekey="emoji"))
        rows.append(row)
    rows.append([ibtn("🔄 Hammasini tiklash", data="emoji_reset_all", style="danger",  ekey="reset")])
    rows.append([ibtn("✅ Yopish",            data="emoji_close",     style="success", ekey="close")])
    return ikb(rows)

def emoji_single_kb(key):
    cur=DB.get("emoji_ids",{}).get(key) or DEFAULT_PE.get(key,"")
    default=DEFAULT_PE.get(key,"")
    kb=ikb([
        [ibtn("🔄 Defaultga qaytarish", data=f"emoji_reset|{key}", style="danger",  ekey="reset")],
        [ibtn("⬅️ Orqaga",              data="emoji_back",          style="success", ekey="back")],
    ])
    return kb, cur, default

# ══════════════════════════════════════════════════════════
# XABAR YUBORISH YORDAMCHILARI
# ══════════════════════════════════════════════════════════

async def sm(bot, chat_id, text, markup=None, pm="HTML"):
    kw={"chat_id":chat_id,"text":text,"parse_mode":pm}
    if markup: kw["reply_markup"]=markup
    return await bot.send_message(**kw)

async def sp(bot, chat_id, photo, caption, markup=None, pm="HTML"):
    kw={"chat_id":chat_id,"photo":photo,"caption":caption,"parse_mode":pm}
    if markup: kw["reply_markup"]=markup
    return await bot.send_photo(**kw)

async def sv(bot, chat_id, video, caption, markup=None, pm="HTML"):
    kw={"chat_id":chat_id,"video":video,"caption":caption,"parse_mode":pm}
    if markup: kw["reply_markup"]=markup
    return await bot.send_video(**kw)

# ══════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ══════════════════════════════════════════════════════════

async def check_subscription(user_id, bot):
    not_subbed=[]
    for ch in DB.get("channels",[]):
        try:
            member=await bot.get_chat_member(ch["username"],user_id)
            if member.status in ("left","kicked"): not_subbed.append(ch)
        except Exception as e:
            logger.warning(f"Sub check {ch}: {e}"); not_subbed.append(ch)
    return not_subbed

def register_user(user):
    uid=str(user.id)
    if uid not in DB["users"]:
        DB["users"][uid]={"name":user.full_name,"username":user.username or "",
            "joined":datetime.now().isoformat(),"paid_episodes":{},"watched":{}}
        save()

async def send_movie_menu(src, context, code):
    movie=DB["movies"].get(code)
    chat_id=src.effective_user.id if hasattr(src,"effective_user") else src.from_user.id
    user_id=chat_id
    if not movie:
        await sm(context.bot,chat_id,"❓ Bunday kodli kino topilmadi."); return
    eps=movie.get("episodes",[])
    if not eps:
        await sm(context.bot,chat_id,"⏳ Bu kinoga hali qism yuklanmagan."); return
    markup=movie_episodes_kb(movie,code,user_id)
    caption=(f"🎬 <b>{movie.get('title','Kino')}</b>\n"
             f"📺 Qismlar soni: <b>{len(eps)}</b>\n\nQaysi qismni ko'rmoqchisiz? 👇")
    poster=movie.get("poster_file_id")
    try:
        if poster: await sp(context.bot,chat_id,poster,caption,markup)
        else:      await sm(context.bot,chat_id,caption,markup)
    except Exception as e: logger.error(f"send_movie_menu: {e}")

# ══════════════════════════════════════════════════════════
# HANDLERLAR
# ══════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; register_user(user); args=context.args
    if args and args[0].startswith("code_"):
        code=args[0].replace("code_","")
        ns=await check_subscription(user.id,context.bot)
        if ns:
            await sm(context.bot,user.id,"🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",subscription_kb(ns))
            context.user_data["pending_code"]=code; return
        await send_movie_menu(update,context,code); return
    ns=await check_subscription(user.id,context.bot)
    if ns:
        await sm(context.bot,user.id,"🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",subscription_kb(ns)); return
    hello=(f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
           f"🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
           f"🔢 Kino <b>raqamini</b> yuboring — video darhol chiqadi.\n\n"
           f"👇 Quyidagi tugmalardan foydalaning:")
    await sm(context.bot,user.id,hello,main_menu_kb())
    if user.id==ADMIN_ID:
        await sm(context.bot,user.id,"👑 <b>Admin panel</b>",admin_menu_kb())

async def cb_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; data=q.data; await q.answer()
    if data=="emoji_back":
        await q.edit_message_text(
            "🎭 <b>Emoji sozlamalari</b>\n\nO'zgartirmoqchi bo'lgan emoji tugmasini tanlang.\n<i>Qavs ichida — joriy ID ning oxirgi 6 raqami</i>",
            parse_mode="HTML",reply_markup=emoji_list_kb()); return
    if data=="emoji_close":
        await q.edit_message_text("✅ Emoji sozlamalari yopildi."); return
    if data=="emoji_reset_all":
        DB["emoji_ids"]={};save()
        await q.edit_message_text("🔄 <b>Barcha emoji IDlar tiklandi!</b>",parse_mode="HTML",reply_markup=emoji_list_kb()); return
    if data.startswith("emoji_reset|"):
        key=data.split("|")[1]; DB["emoji_ids"].pop(key,None); save()
        kb,cur,default=emoji_single_kb(key)
        await q.edit_message_text(f"🔄 <b>{PE_LABELS.get(key,key)}</b> tiklandi!\n\n📌 Default ID:\n<code>{default}</code>",
            parse_mode="HTML",reply_markup=kb); return
    if data.startswith("emoji_edit|"):
        key=data.split("|")[1]; kb,cur,default=emoji_single_kb(key)
        context.user_data["editing_emoji_key"]=key
        await q.edit_message_text(
            f"✏️ <b>{PE_LABELS.get(key,key)}</b>\n\n"
            f"📌 Joriy ID:\n<code>{cur}</code>\n\n"
            f"📎 Default ID:\n<code>{default}</code>\n\n"
            f"🔽 Yangi premium emoji IDni yuboring\n<i>(@getidsbot orqali topish mumkin)</i>",
            parse_mode="HTML",reply_markup=kb); return

async def cb_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    ns=await check_subscription(q.from_user.id,context.bot)
    if ns: await q.answer("❌ Hali obuna bo'lmagansiz!",show_alert=True); return
    await q.edit_message_text("✅ Barcha kanallarga obuna bo'ldingiz!")
    pending=context.user_data.pop("pending_code",None)
    if pending: await send_movie_menu(q,context,pending)
    else:
        await sm(context.bot,q.from_user.id,
            f"👋 Xush kelibsiz, <b>{q.from_user.full_name}</b>!\n🔢 Kino raqamini yuboring.",
            main_menu_kb())

async def cb_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    parts=q.data.split("|")
    if len(parts)!=3: await q.answer("❌ Xato",show_alert=True); return
    _,code,ep=parts; movie=DB["movies"].get(code)
    if not movie: await q.answer("❌ Kino topilmadi",show_alert=True); return
    user_id=str(q.from_user.id)
    price=movie.get("prices",{}).get(ep)
    paid=DB["users"].get(user_id,{}).get("paid_episodes",{})
    if price and not paid.get(f"{code}_{ep}"):
        card=DB.get("card_number") or "Admin karta raqamini o'rnatmagan"
        txt=(f"💰 <b>Bu qism pullik</b>\n\n🎬 Kino: <b>{movie.get('title')}</b>\n"
             f"🎞 Qism: <b>{ep}</b>\n💵 Narxi: <b>{price} so'm</b>\n\n"
             f"💳 Karta raqami:\n<code>{card}</code>\n\nTo'lov qiling va chek rasmini yuboring 📸")
        context.user_data["awaiting_check"]={"code":code,"ep":ep,"price":price}
        await sm(context.bot,q.from_user.id,txt,payment_sent_kb()); return
    idx=int(ep)-1; eps=movie.get("episodes",[])
    if idx<0 or idx>=len(eps): await q.answer("❌ Qism topilmadi",show_alert=True); return
    movie.setdefault("views",{}); movie["views"][ep]=movie["views"].get(ep,0)+1
    DB["users"].setdefault(user_id,{}).setdefault("watched",{})[f"{code}_{ep}"]=True
    DB["stats"]["total_views"]=DB["stats"].get("total_views",0)+1; save()
    bot_me=await context.bot.get_me()
    share_url=f"https://t.me/share/url?url=https://t.me/{bot_me.username}?start=code_{code}"
    caption=(f"🎬 <b>{movie.get('title')}</b>\n🎞 Qism: <b>{ep}</b>\n👁 Ko'rishlar: <b>{movie['views'][ep]}</b>")
    await sv(context.bot,q.from_user.id,eps[idx],caption,share_kb(share_url))

async def cb_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    action,pid=q.data.split("|"); pay=DB["pending_payments"].get(pid)
    if not pay: await q.edit_message_caption("⚠️ To'lov topilmadi."); return
    if action=="pay_no":
        pay["status"]="rejected"; save()
        await q.edit_message_caption((q.message.caption or "")+"\n\n❌ <b>Bekor qilindi</b>",parse_mode="HTML")
        await sm(context.bot,pay["user_id"],"❌ <b>To'lovingiz rad etildi.</b>\nQayta urinib ko'ring yoki 🆘 Yordam orqali murojaat qiling."); return
    pay["status"]="approved"; uid=str(pay["user_id"])
    DB["users"].setdefault(uid,{}).setdefault("paid_episodes",{})[f"{pay['code']}_{pay['ep']}"]=True
    try:
        next_ep=str(int(pay["ep"])+1); DB["users"][uid]["paid_episodes"][f"{pay['code']}_{next_ep}"]=True
    except Exception: pass
    save()
    await q.edit_message_caption((q.message.caption or "")+"\n\n✅ <b>Tasdiqlandi</b>",parse_mode="HTML")
    await sm(context.bot,pay["user_id"],"✅ <b>Admin to'lovingizni tasdiqladi!</b>\n⏳ 1 daqiqa kuting, video avtomatik yuboriladi...")
    async def send_later():
        await asyncio.sleep(60)
        movie=DB["movies"].get(pay["code"])
        if not movie: return
        idx=int(pay["ep"])-1; eps=movie.get("episodes",[])
        if 0<=idx<len(eps):
            movie.setdefault("views",{}); movie["views"][pay["ep"]]=movie["views"].get(pay["ep"],0)+1
            DB["users"][uid].setdefault("watched",{})[f"{pay['code']}_{pay['ep']}"]=True
            DB["stats"]["total_views"]=DB["stats"].get("total_views",0)+1; save()
            await sv(context.bot,pay["user_id"],eps[idx],f"🎬 <b>{movie.get('title')}</b>\n🎞 Qism: {pay['ep']}")
    context.application.create_task(send_later())

async def cb_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    _,uid=q.data.split("|"); context.user_data["reply_to"]=int(uid)
    await q.message.reply_text(f"✍️ <code>{uid}</code> ga xabar yozing.",parse_mode="HTML")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=update.callback_query.data
    if data=="check_sub": await cb_check_sub(update,context)
    elif data.startswith("ep|"): await cb_episode(update,context)
    elif data.startswith("pay_ok|") or data.startswith("pay_no|"): await cb_payment(update,context)
    elif data.startswith("reply|"): await cb_reply(update,context)
    elif data=="refresh_stats":
        if update.callback_query.from_user.id==ADMIN_ID:
            q=update.callback_query; await q.answer("📊 Yangilandi!")
            u=len(DB.get("users",{})); m=len(DB.get("movies",{})); v=DB.get("stats",{}).get("total_views",0)
            await q.edit_message_text(f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: <b>{u}</b>\n🎬 Kinolar: <b>{m}</b>\n👁 Jami ko'rishlar: <b>{v}</b>",
                parse_mode="HTML",reply_markup=stats_kb())
    elif data=="go_home":
        q=update.callback_query; await q.answer()
        await q.edit_message_reply_markup(reply_markup=None)
        await sm(context.bot,q.from_user.id,"🏠 Bosh menyu",main_menu_kb())
    elif data=="waiting_confirm":
        await update.callback_query.answer("⏳ Admin ko'rib chiqmoqda, sabrli bo'ling!",show_alert=True)
    elif data.startswith("emoji_"):
        if update.callback_query.from_user.id==ADMIN_ID: await cb_emoji(update,context)
        else: await update.callback_query.answer("🚫 Ruxsat yo'q",show_alert=True)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; uid=user.id; text=(update.message.text or "").strip()
    ADMIN_BTNS=("🎬 Kino joylash","➕ Qism qo'shish","💰 Qismni pullik qilish",
                "📊 Statistika","📢 Kanalga post","🔒 Majburiy kanal",
                "💳 Karta raqami","📲 Ilova fayl/video","🏠 Asosiy menyu","🎭 Emoji sozlamalari")
    if uid==ADMIN_ID and text in ADMIN_BTNS:
        if text=="🎭 Emoji sozlamalari":
            await sm(context.bot,uid,
                "🎭 <b>Emoji sozlamalari</b>\n\nO'zgartirmoqchi bo'lgan emoji tugmasini tanlang.\n<i>Qavs ichida — joriy ID ning oxirgi 6 raqami</i>",
                emoji_list_kb()); return
        await admin_buttons(update,context,text); return
    if text=="🆘 Yordam":
        await sm(context.bot,uid,"✍️ Savol yoki muammoingizni <b>matn, rasm yoki video</b> ko'rinishida yuboring.\nAdmin tez orada javob beradi.",help_kb())
        context.user_data["awaiting_help"]=True; return
    if text=="📥 Ilovani o'rnatish":
        s=DB.get("settings",{}); f_id=s.get("install_file_id"); v_id=s.get("install_video_id")
        if not f_id and not v_id: await sm(context.bot,uid,"⏳ Admin hali ilova fayl/video joylamagan."); return
        if v_id: await sv(context.bot,uid,v_id,"📲 <b>Ilovani o'rnatish videosi</b>")
        if f_id: await context.bot.send_document(uid,f_id,caption="📦 <b>Ilova fayli</b>",parse_mode="HTML")
        return
    if uid==ADMIN_ID and context.user_data.get("editing_emoji_key"):
        key=context.user_data.pop("editing_emoji_key"); new_id=text.strip()
        if not new_id.isdigit() or len(new_id)<10:
            await sm(context.bot,uid,"❌ Noto'g'ri ID. Faqat raqamlar, kamida 10 ta.\n<i>Masalan: 5368324170671202286</i>")
            context.user_data["editing_emoji_key"]=key; return
        DB.setdefault("emoji_ids",{})[key]=new_id; save()
        await sm(context.bot,uid,f"✅ <b>{PE_LABELS.get(key,key)}</b> emoji IDsi yangilandi!\n\n🆕 Yangi ID:\n<code>{new_id}</code>\n\n<i>Endi barcha yangi tugmalarda shu emoji ko'rinadi.</i>",emoji_list_kb()); return
    if uid==ADMIN_ID and await admin_state_handler(update,context,text): return
    if context.user_data.pop("awaiting_help",False):
        cap=(f"🆘 <b>Yordam so'rovi</b>\n👤 {user.full_name} (@{user.username or '-'})\n🆔 <code>{uid}</code>\n\n")
        await sm(context.bot,ADMIN_ID,cap+text,reply_admin_kb(uid))
        await sm(context.bot,uid,"✅ Xabaringiz adminga yuborildi!"); return
    if uid==ADMIN_ID and "reply_to" in context.user_data:
        target=context.user_data.pop("reply_to")
        try:
            await sm(context.bot,target,f"✉️ <b>Admin javobi:</b>\n{text}")
            await sm(context.bot,uid,"✅ Yuborildi!")
        except Exception as e: await sm(context.bot,uid,f"❌ Xato: {e}")
        return
    if context.user_data.get("awaiting_check"):
        await sm(context.bot,uid,"📸 Iltimos chek <b>rasmini</b> yuboring."); return
    code=text.upper().strip()
    if code in DB["movies"]:
        ns=await check_subscription(uid,context.bot)
        if ns:
            await sm(context.bot,uid,"🔒 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",subscription_kb(ns))
            context.user_data["pending_code"]=code; return
        await send_movie_menu(update,context,code)
    else:
        await sm(context.bot,uid,"❓ Kino raqami topilmadi.\n🔢 To'g'ri raqamni yuboring.")

async def admin_buttons(update, context, text):
    uid=update.effective_user.id
    if text=="🏠 Asosiy menyu": await sm(context.bot,uid,"🏠 Asosiy menyu",main_menu_kb()); return
    if text=="📊 Statistika":
        u=len(DB.get("users",{})); m=len(DB.get("movies",{})); v=DB.get("stats",{}).get("total_views",0)
        await sm(context.bot,uid,f"📊 <b>Statistika</b>\n\n👥 Foydalanuvchilar: <b>{u}</b>\n🎬 Kinolar: <b>{m}</b>\n👁 Jami ko'rishlar: <b>{v}</b>",stats_kb()); return
    if text=="💳 Karta raqami":
        context.user_data["admin_state"]="set_card"; cur=DB.get("card_number") or "Kiritilmagan"
        await sm(context.bot,uid,f"💳 Joriy karta: <code>{cur}</code>\n\nYangi karta raqamini yuboring:"); return
    if text=="🎬 Kino joylash":
        context.user_data["admin_state"]="add_movie_code"
        await sm(context.bot,uid,"🎬 Kino kodini kiriting (masalan: AVATAR yoki 001):"); return
    if text=="➕ Qism qo'shish":
        context.user_data["admin_state"]="add_ep_code"
        await sm(context.bot,uid,"🎬 Qism qo'shmoqchi bo'lgan kino kodini kiriting:"); return
    if text=="💰 Qismni pullik qilish":
        context.user_data["admin_state"]="set_price_code"
        await sm(context.bot,uid,"🎬 Kino kodini kiriting:"); return
    if text=="📲 Ilova fayl/video":
        context.user_data["admin_state"]="set_install"
        await sm(context.bot,uid,"📲 Ilova fayl yoki video yuboring:"); return
    if text=="🔒 Majburiy kanal":
        context.user_data["admin_state"]="add_channel"
        await sm(context.bot,uid,"📢 Kanal username va nomi yuboring:\n<code>@username | Kanal nomi | https://t.me/username</code>"); return
    if text=="📢 Kanalga post":
        context.user_data["admin_state"]="post_channel_code"
        await sm(context.bot,uid,"🎬 Post qilmoqchi bo'lgan kino kodini kiriting:"); return

async def admin_state_handler(update, context, text):
    state=context.user_data.get("admin_state"); uid=update.effective_user.id
    if not state: return False
    if state=="set_card":
        DB["card_number"]=text; save(); context.user_data.pop("admin_state")
        await sm(context.bot,uid,f"✅ Karta saqlandi: <code>{text}</code>"); return True
    if state=="add_movie_code":
        context.user_data["new_movie_code"]=text.upper(); context.user_data["admin_state"]="add_movie_title"
        await sm(context.bot,uid,"📝 Kino nomini kiriting:"); return True
    if state=="add_movie_title":
        code=context.user_data.get("new_movie_code")
        DB["movies"][code]={"title":text,"episodes":[],"prices":{}}; save()
        context.user_data.pop("admin_state"); context.user_data.pop("new_movie_code",None)
        await sm(context.bot,uid,f"✅ <b>{text}</b> kinosi qo'shildi!\nKod: <code>{code}</code>",movie_added_kb(code)); return True
    if state=="add_ep_code":
        code=text.upper()
        if code not in DB["movies"]: await sm(context.bot,uid,"❌ Bunday kod yo'q."); context.user_data.pop("admin_state"); return True
        context.user_data["ep_movie_code"]=code; context.user_data["admin_state"]="add_ep_video"
        await sm(context.bot,uid,f"📹 <b>{code}</b> uchun video yuboring:"); return True
    if state=="set_price_code":
        code=text.upper()
        if code not in DB["movies"]: await sm(context.bot,uid,"❌ Bunday kod yo'q."); context.user_data.pop("admin_state"); return True
        context.user_data["price_movie_code"]=code; context.user_data["admin_state"]="set_price_ep"
        await sm(context.bot,uid,"🎞 Qism raqamini kiriting:"); return True
    if state=="set_price_ep":
        context.user_data["price_ep"]=text; context.user_data["admin_state"]="set_price_amount"
        await sm(context.bot,uid,"💰 Narxini kiriting (so'mda):"); return True
    if state=="set_price_amount":
        code=context.user_data.get("price_movie_code"); ep=context.user_data.get("price_ep")
        DB["movies"][code].setdefault("prices",{})[ep]=text; save(); context.user_data.pop("admin_state")
        await sm(context.bot,uid,f"✅ {code} — {ep}-qism narxi: {text} so'm"); return True
    if state=="add_channel":
        try:
            parts=[p.strip() for p in text.split("|")]; uname,title,url=parts[0],parts[1],parts[2]
            DB["channels"].append({"username":uname,"title":title,"url":url}); save()
            await sm(context.bot,uid,f"✅ Kanal qo'shildi: {title}")
        except Exception: await sm(context.bot,uid,"❌ Format xato. Qayta urinib ko'ring.")
        context.user_data.pop("admin_state"); return True
    if state=="post_channel_code":
        code=text.upper()
        if code not in DB["movies"]: await sm(context.bot,uid,"❌ Bunday kod yo'q."); context.user_data.pop("admin_state"); return True
        context.user_data["post_code"]=code; context.user_data["admin_state"]="post_channel_target"
        await sm(context.bot,uid,"📢 Kanal username ni kiriting (masalan @mychannel):"); return True
    if state=="post_channel_target":
        channel=text; code=context.user_data.get("post_code"); movie=DB["movies"].get(code,{})
        bot_me=await context.bot.get_me(); markup=channel_post_kb(bot_me.username,code)
        caption=(f"🎬 <b>{movie.get('title',code)}</b>\n\n📺 Qismlar soni: <b>{len(movie.get('episodes',[]))}</b>\n\n👇 Tomosha qilish uchun tugmani bosing!")
        poster=movie.get("poster_file_id")
        try:
            if poster: await sp(context.bot,channel,poster,caption,markup)
            else:      await sm(context.bot,channel,caption,markup)
            await sm(context.bot,uid,"✅ Post yuborildi!")
        except Exception as e: await sm(context.bot,uid,f"❌ Xato: {e}")
        context.user_data.pop("admin_state"); return True
    if state=="set_install": return False
    return False

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user; uid=user.id; msg=update.message
    state=context.user_data.get("admin_state")
    if uid==ADMIN_ID and state=="add_ep_video":
        code=context.user_data.get("ep_movie_code")
        if msg.video:
            DB["movies"][code]["episodes"].append(msg.video.file_id); save()
            ep_num=len(DB["movies"][code]["episodes"]); context.user_data.pop("admin_state")
            await sm(context.bot,uid,f"✅ {ep_num}-qism saqlandi!")
        return
    if uid==ADMIN_ID and state=="set_install":
        if msg.video:
            DB["settings"]["install_video_id"]=msg.video.file_id; save()
            context.user_data.pop("admin_state"); await sm(context.bot,uid,"✅ O'rnatish videosi saqlandi!")
        elif msg.document:
            DB["settings"]["install_file_id"]=msg.document.file_id; save()
            context.user_data.pop("admin_state"); await sm(context.bot,uid,"✅ O'rnatish fayli saqlandi!")
        return
    if context.user_data.get("awaiting_check") and msg.photo:
        pay_info=context.user_data.pop("awaiting_check")
        pid=f"{uid}_{pay_info['code']}_{pay_info['ep']}_{int(time.time())}"
        DB["pending_payments"][pid]={"user_id":uid,"code":pay_info["code"],"ep":pay_info["ep"],"price":pay_info["price"],"status":"pending"}
        save()
        cap=(f"💳 <b>To'lov cheki</b>\n👤 {user.full_name} (@{user.username or '-'})\n"
             f"🆔 <code>{uid}</code>\n🎬 Kino: <b>{pay_info['code']}</b>\n"
             f"🎞 Qism: <b>{pay_info['ep']}</b>\n💰 Narx: <b>{pay_info['price']} so'm</b>")
        await sp(context.bot,ADMIN_ID,msg.photo[-1].file_id,cap,payment_admin_kb(pid))
        await sm(context.bot,uid,"✅ Chek adminga yuborildi! Tasdiqlanishini kuting."); return
    if context.user_data.pop("awaiting_help",False):
        cap=(f"🆘 <b>Yordam so'rovi</b>\n👤 {user.full_name} (@{user.username or '-'})\n🆔 <code>{uid}</code>\n\n")
        if msg.photo: await sp(context.bot,ADMIN_ID,msg.photo[-1].file_id,cap,reply_admin_kb(uid))
        elif msg.video: await sv(context.bot,ADMIN_ID,msg.video.file_id,cap,reply_admin_kb(uid))
        await sm(context.bot,uid,"✅ Xabaringiz adminga yuborildi!"); return
    if uid==ADMIN_ID and "reply_to" in context.user_data:
        target=context.user_data.pop("reply_to")
        try:
            if msg.photo: await sp(context.bot,target,msg.photo[-1].file_id,"✉️ <b>Admin javobi</b>")
            elif msg.video: await sv(context.bot,target,msg.video.file_id,"✉️ <b>Admin javobi</b>")
            await sm(context.bot,uid,"✅ Yuborildi!")
        except Exception as e: await sm(context.bot,uid,f"❌ Xato: {e}")

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.add_handler(MessageHandler(filters.PHOTO|filters.VIDEO|filters.Document.ALL,media_handler))
    logger.info("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    main()
