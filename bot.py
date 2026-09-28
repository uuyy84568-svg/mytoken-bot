# MYTOKEN BOT v4.0
import asyncio, logging, os, json, time
import urllib.request, urllib.parse
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (Update, WebAppInfo, InlineKeyboardButton,
    InlineKeyboardMarkup, MenuButtonWebApp, BotCommand)
from telegram.ext import (ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, MessageHandler, ContextTypes, filters)
from telegram.constants import ParseMode
from telegram.error import TelegramError

BOT_TOKEN   = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL  = os.environ.get("WEBAPP_URL", "https://mytoken-app-2026.netlify.app")
API_BASE    = os.environ.get("API_BASE", "https://mytoken-api.vercel.app")
ADMIN_ID    = os.environ.get("ADMIN_ID", "8063963886")
CHANNEL_ID  = os.environ.get("CHANNEL_ID", "@MyTokenMiningPro2")
CHANNEL_URL = os.environ.get("CHANNEL_URL", "https://t.me/MyTokenMiningPro2")
MIN_WITHDRAW = 1000
RATE = 0.001
RATE_LIMIT = 1.5
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("MYTOKEN")
user_states = {}
sound_settings = {}
last_cmd = {}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception: pass
    def log_message(self, *a): pass

def run_health_server():
    try:
        port = int(os.environ.get("PORT", 8080))
        HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except Exception as e:
        logger.warning("Health: " + str(e))

def api_post(path, body, timeout=15):
    try:
        url = API_BASE.rstrip("/") + path
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning("API " + path + ": " + str(e))
        return None

def fmt(n):
    try:
        n = float(n or 0)
        return str(int(n)) if n == int(n) else "{:.2f}".format(n)
    except Exception: return "0"

def to_usd(myt):
    try: return "{:.2f}".format(float(myt or 0) * RATE)
    except Exception: return "0.00"

def is_rate_limited(uid):
    now = time.time()
    if now - last_cmd.get(uid, 0) < RATE_LIMIT: return True
    last_cmd[uid] = now
    return False

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("MYTOKEN افتح", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("حسابي", callback_data="account"),
         InlineKeyboardButton("دعوة صديق", callback_data="invite")],
        [InlineKeyboardButton("القناة", url=CHANNEL_URL)],
    ])

def kb_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("انضم للقناة", url=CHANNEL_URL)],
        [InlineKeyboardButton("تحقق من الاشتراك", callback_data="check_sub")],
    ])

def kb_account():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ربط المحفظة", callback_data="acc_wallet"),
         InlineKeyboardButton("VIP", callback_data="acc_vip")],
        [InlineKeyboardButton("سحب", callback_data="acc_withdraw"),
         InlineKeyboardButton("السجل", callback_data="acc_history")],
        [InlineKeyboardButton("الإحصائيات", callback_data="acc_stats"),
         InlineKeyboardButton("الصوت", callback_data="acc_sound")],
        [InlineKeyboardButton("رجوع", callback_data="back")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="account")]])

def kb_back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="back")]])

def kb_admin_withdraw(uid, amount):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("موافقة", callback_data="wd_ok_" + uid + "_" + amount),
        InlineKeyboardButton("رفض", callback_data="wd_no_" + uid + "_" + amount),
    ]])

async def check_subscription(ctx, user_id):
    try:
        m = await ctx.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return m.status in ("member", "administrator", "creator")
    except TelegramError as e:
        logger.warning("Sub: " + str(e))
        return True

async def send_join_message(message):
    text = ("الاشتراك مطلوب\n━━━━━━━━━━━━━━━━━━\n\n"
        "اشترك في قناتنا:\n\n" + CHANNEL_ID + "\n\nاضغط الانضمام ثم تحقق.")
    await message.reply_text(text, parse_mode=ParseMode.HTML,
        reply_markup=kb_join(), disable_web_page_preview=True)

def render_account(ud, user):
    bal = float(ud.get("balance", 0) or 0)
    pend = float(ud.get("pending", 0) or 0)
    refs = ud.get("refs", 0)
    wallet = ud.get("wallet", "") or ""
    checkin = ud.get("checkinDay", 0)
    level = ud.get("level", 1)
    sound = "On" if sound_settings.get(user.id, True) else "Off"
    verified = "Verified" if wallet else "Unverified"
    wshort = wallet[:10] + "..." + wallet[-6:] if wallet else "غير مربوط"
    return ("حسابي\n━━━━━━━━━━━━━━━━━━\n\n"
        "User ID: " + str(user.id) + "\n"
        "الاسم: " + (user.first_name or "User") + "\n\n"
        "Account: " + verified + "\n"
        "Sound: " + sound + "\n"
        "Level: Lv" + str(level) + "\n\n"
        "VIP: غير مفعل\n\n"
        "Assets: " + fmt(bal) + " MYT\n"
        "بالدولار: $" + to_usd(bal) + "\n\n"
        "Holding Wallet\n   " + wshort + "\n\n"
        "Pool Wallet\n   " + fmt(bal) + " MYT ($" + to_usd(bal) + ")\n"
        "   معلق: " + fmt(pend) + " MYT\n\n"
        "الحد الأدنى: " + str(MIN_WITHDRAW) + " MYT\n\n"
        "الإحالات: " + str(refs) + " | التسجيل: " + str(checkin) + "/7\n\n"
        "اختر الإجراء:")

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    fn = user.first_name or "صديقي"
    user_states.pop(user.id, None)
    if is_rate_limited(user.id): return
    if not await check_subscription(ctx, user.id):
        await send_join_message(update.message); return
    ref_id = None
    if ctx.args and len(ctx.args) > 0:
        a = ctx.args[0].strip()
        if a.startswith("ref_"): ref_id = a.replace("ref_", "").strip()
    payload = {"id": user.id, "first_name": fn}
    if ref_id: payload["ref"] = ref_id
    result = api_post("/api/register", payload)
    logger.info("Register " + str(user.id) + ": " + str(result))
    if result and result.get("isNew") and result.get("referral") and ref_id:
        try:
            await ctx.bot.send_message(chat_id=int(ref_id),
                text="صديق جديد!\n+100 MYT\nإحالاتك +1",
                parse_mode=ParseMode.HTML)
        except Exception as e: logger.warning(str(e))
    text = ("أهلاً " + fn + "!\nمرحباً بك في MYTOKEN\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "دعوة صديق = +100 MYT\nالإعلانات\nالتعدين\nالتسجيل اليومي\n\nابدأ:")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
        reply_markup=kb_main(), disable_web_page_preview=True)

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_rate_limited(user.id): return
    data = api_post("/api/user", {"id": user.id})
    if not data or not data.get("exists"):
        await update.message.reply_text("اضغط /start"); return
    bal = float(data.get("balance", 0) or 0)
    await update.message.reply_text(
        "رصيدك: " + fmt(bal) + " MYT ($" + to_usd(bal) + ")",
        parse_mode=ParseMode.HTML, reply_markup=kb_main())

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = ("المساعدة\n━━━━━━━━━━━━━━━━━━\n\n"
        "/start - البداية\n/stats - رصيدك\n/help - المساعدة\n\n"
        "القناة: " + CHANNEL_ID)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
        reply_markup=kb_main())

async def cb_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = q.from_user
    uid = user.id
    name = user.first_name or "User"
    try:
        if data == "check_sub":
            if await check_subscription(ctx, uid):
                await q.edit_message_text("تم التحقق! اضغط /start")
            else:
                await q.answer("لم تشترك!", show_alert=True)
            return
        if data == "account":
            ud = api_post("/api/user", {"id": uid})
            if not ud or not ud.get("exists"):
                await q.edit_message_text("اضغط /start", reply_markup=kb_back_main()); return
            text = render_account(ud, user)
            try:
                await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_account())
            except TelegramError:
                await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb_account())
            return
        if data == "back":
            user_states.pop(uid, None)
            await q.edit_message_text("أهلاً " + name + "!\n\nاختر:",
                parse_mode=ParseMode.HTML, reply_markup=kb_main())
            return
        if data == "invite":
            bi = await ctx.bot.get_me()
            rl = "https://t.me/" + bi.username + "?start=ref_" + str(uid)
            text = ("رابط الإحالة\n━━━━━━━━━━━━━━━━━━\n\n<code>" + rl +
                "</code>\n\n+100 MYT لكل صديق")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="back")]])
            await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                reply_markup=kb, disable_web_page_preview=True)
            return
        if data == "acc_wallet":
            user_states[uid] = "await_wallet"
            await q.edit_message_text("ربط محفظة TON\n\nأرسل عنوان محفظتك:",
                parse_mode=ParseMode.HTML, reply_markup=kb_back())
            return
        if data == "acc_vip":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="account")]])
            await q.edit_message_text("VIP\n\nمضاعف 2x\nمكافآت أعلى\n\nالسعر: 1 TON\n\nقريباً...",
                parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if data == "acc_withdraw":
            ud = api_post("/api/user", {"id": uid})
            if not ud or not ud.get("exists"):
                await q.answer("اضغط /start", show_alert=True); return
            bal = float(ud.get("balance", 0) or 0)
            wallet = ud.get("wallet", "") or ""
            if not wallet:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("ربط المحفظة", callback_data="acc_wallet")],
                    [InlineKeyboardButton("رجوع", callback_data="account")]])
                await q.edit_message_text("اربط محفظتك أولاً!", parse_mode=ParseMode.HTML, reply_markup=kb); return
            if bal < MIN_WITHDRAW:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="account")]])
                await q.edit_message_text("رصيدك غير كافٍ\n\n" + fmt(bal) + " MYT",
                    parse_mode=ParseMode.HTML, reply_markup=kb); return
            user_states[uid] = "await_withdraw"
            await q.edit_message_text(
                "السحب\n\nرصيدك: " + fmt(bal) + " MYT\nالحد الأدنى: " + str(MIN_WITHDRAW) + "\n\nأرسل الكمية:",
                parse_mode=ParseMode.HTML, reply_markup=kb_back())
            return
        if data == "acc_history":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="account")]])
            await q.edit_message_text("سجل السحوبات\n\nلا توجد سحوبات بعد.",
                parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if data == "acc_stats":
            ud = api_post("/api/user", {"id": uid})
            if not ud: return
            text = ("الإحصائيات\n\n"
                "الإحالات: " + str(ud.get("refs", 0)) + "\n"
                "التسجيل: " + str(ud.get("checkinDay", 0)) + "/7\n"
                "المستوى: Lv" + str(ud.get("level", 1)) + "\n"
                "الرصيد: " + fmt(ud.get("balance", 0)) + " MYT")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="account")]])
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if data == "acc_sound":
            cur = sound_settings.get(uid, True)
            sound_settings[uid] = not cur
            await q.answer("الصوت: " + ("مفعّل" if not cur else "متوقف"))
            ud = api_post("/api/user", {"id": uid})
            if ud:
                await q.edit_message_text(render_account(ud, user),
                    parse_mode=ParseMode.HTML, reply_markup=kb_account())
            return
        if data.startswith("wd_ok_"):
            p = data.replace("wd_ok_", "").split("_")
            await q.edit_message_text("تمت الموافقة: " + p[1] + " MYT")
            try:
                await ctx.bot.send_message(chat_id=int(p[0]),
                    text="تمت الموافقة على سحبك\n" + p[1] + " MYT", parse_mode=ParseMode.HTML)
            except Exception as e: logger.warning(str(e))
            return
        if data.startswith("wd_no_"):
            p = data.replace("wd_no_", "").split("_")
            api_post("/api/admin/give", {"admin_id": ADMIN_ID, "target_id": p[0], "amount": float(p[1])})
            await q.edit_message_text("تم الرفض وإرجاع " + p[1] + " MYT")
            try:
                await ctx.bot.send_message(chat_id=int(p[0]),
                    text="تم رفض السحب. تم إرجاع رصيدك.", parse_mode=ParseMode.HTML)
            except Exception as e: logger.warning(str(e))
            return
    except TelegramError as e:
        logger.warning("CB: " + str(e))

async def msg_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state = user_states.get(user.id)
    if not state: return
    text = (update.message.text or "").strip()
    if state == "await_wallet":
        if len(text) < 40 or len(text) > 90:
            await update.message.reply_text("عنوان غير صالح (40-90 حرفاً).", reply_markup=kb_back()); return
        result = api_post("/api/wallet", {"id": user.id, "wallet": text})
        user_states.pop(user.id, None)
        if result and result.get("ok"):
            await update.message.reply_text("تم ربط محفظتك!\n\n<code>" + text[:10] + "..." + text[-6:] + "</code>",
                parse_mode=ParseMode.HTML, reply_markup=kb_main())
        else:
            await update.message.reply_text("فشل الحفظ.", reply_markup=kb_main())
        return
    if state == "await_withdraw":
        try: amount = float(text)
        except ValueError:
            await update.message.reply_text("رقم غير صالح.", reply_markup=kb_back()); return
        ud = api_post("/api/user", {"id": user.id})
        bal = float((ud or {}).get("balance", 0) or 0)
        wallet = (ud or {}).get("wallet", "") or ""
        if amount < MIN_WITHDRAW:
            await update.message.reply_text("الحد الأدنى " + str(MIN_WITHDRAW), reply_markup=kb_back()); return
        if amount > bal:
            await update.message.reply_text("رصيدك " + fmt(bal) + " فقط", reply_markup=kb_back()); return
        result = api_post("/api/admin/give", {"admin_id": ADMIN_ID, "target_id": str(user.id), "amount": -amount})
        user_states.pop(user.id, None)
        if result and result.get("ok"):
            await update.message.reply_text("تم إنشاء طلب سحب\n\n" + fmt(amount) + " MYT\nقيد المراجعة",
                parse_mode=ParseMode.HTML, reply_markup=kb_main())
            try:
                atext = ("طلب سحب جديد\n━━━━━━━━━━━━━━━━━━\n"
                    "الاسم: " + (user.first_name or "User") + "\n"
                    "ID: <code>" + str(user.id) + "</code>\n"
                    "المبلغ: " + fmt(amount) + " MYT\n"
                    "المحفظة: <code>" + wallet[:10] + "..." + wallet[-6:] + "</code>")
                await ctx.bot.send_message(chat_id=int(ADMIN_ID), text=atext,
                    parse_mode=ParseMode.HTML, reply_markup=kb_admin_withdraw(str(user.id), fmt(amount)))
            except Exception as e: logger.warning(str(e))
        else:
            await update.message.reply_text("فشل الطلب.", reply_markup=kb_main())
        return

async def error_handler(update, ctx):
    logger.error("Error: " + str(ctx.error))

async def set_bot_commands(app):
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "البداية"),
            BotCommand("stats", "رصيدك"),
            BotCommand("help", "المساعدة"),
        ])
    except TelegramError as e: logger.warning(str(e))

async def set_menu_button(app):
    try:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="MYTOKEN افتح", web_app=WebAppInfo(url=WEBAPP_URL)))
    except TelegramError as e: logger.warning(str(e))

async def main():
    Thread(target=run_health_server, daemon=True).start()
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing!"); return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("balance", cmd_stats))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    app.add_error_handler(error_handler)
    await app.initialize()
    await set_bot_commands(app)
    await set_menu_button(app)
    await app.start()
    logger.info("MYTOKEN Bot RUNNING")
    await app.updater.start_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Stopped")
    except Exception as e: logger.error("Fatal: " + str(e))
