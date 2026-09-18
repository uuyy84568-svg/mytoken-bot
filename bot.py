# ============================================
# MYTOKEN LEGENDARY BOT — bot.py
# ============================================
# النسخة النهائية الآمنة
# التوكن يُقرأ من Environment Variables فقط
# ============================================

import asyncio
import logging
import os
import json
import urllib.request
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (
    Update,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ============================================
# ⚙️ الإعدادات — تُقرأ من Environment
# ============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# رابط الموقع (WebApp)
WEBAPP_URL = os.environ.get(
    "WEBAPP_URL",
    "https://regal-kitten-2da9af.netlify.app"
)

# رابط API
API_BASE = os.environ.get(
    "API_BASE",
    "https://mytoken-api.vercel.app"
)

# معلومات ثابتة
BOT_USERNAME = "OOOOBBBBBBOT"
SUPPORT_URL = "https://t.me/OOO0BBBBBBOT"
CHANNEL_URL = "https://t.me/OOO0BBBBBBOT"

# ============================================
# ✅ التحقق من التوكن
# ============================================
if not BOT_TOKEN:
    raise RuntimeError(
        "❌ BOT_TOKEN غير موجود في Environment Variables. "
        "أضفه في Render → Environment."
    )

# ============================================
# 📋 Logging
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("MYTOKEN_BOT")

# ============================================
# 🌐 Health Check Server (لـ Render)
# ============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = """<!DOCTYPE html>
<html><head><title>MYTOKEN BOT</title></head>
<body style="background:#080303;color:#00FF88;font-family:Arial;
display:flex;align-items:center;justify-content:center;
height:100vh;margin:0;flex-direction:column">
<h1 style="font-size:42px;text-shadow:0 0 20px #00FF88">MYTOKEN BOT</h1>
<p style="color:#a88888;font-size:16px">✅ Server is Online</p>
</body></html>"""
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"✅ Health server on port {port}")
    server.serve_forever()

# ============================================
# 🔧 دوال مساعدة
# ============================================
def api_get(endpoint: str) -> dict:
    try:
        url = f"{API_BASE}{endpoint}"
        req = urllib.request.Request(url, headers={"User-Agent": "MYTOKEN-BOT"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(f"API error [{endpoint}]: {e}")
        return {}

def fmt_number(n, d=4):
    try:
        n = float(n)
        if n >= 1e9: return f"{n/1e9:.2f}B"
        if n >= 1e6: return f"{n/1e6:.2f}M"
        if n >= 1e3: return f"{n/1e3:.2f}K"
        return f"{n:.{d}f}"
    except:
        return "0.0000"

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⛏️ ابدأ التعدين",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )],
        [
            InlineKeyboardButton("💰 حسابي", callback_data="account"),
            InlineKeyboardButton("❓ مساعدة", callback_data="help"),
        ],
        [
            InlineKeyboardButton("📢 قناة", url=CHANNEL_URL),
            InlineKeyboardButton("💬 دعم", url=SUPPORT_URL),
        ],
    ])

# ============================================
# 🎯 /start
# ============================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name or "صديقي"

    # معالجة الإحالة
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            ref_id = arg.replace("ref_", "")
            try:
                api_get(f"/api/register?id={user.id}&ref={ref_id}")
            except Exception as e:
                logger.warning(f"Ref error: {e}")

    text = (
        f"👋 أهلاً <b>{first_name}</b>!\n\n"
        f"⛏️ <b>مرحباً بك في MYTOKEN</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 اجمع <b>MYT</b> من التطبيق\n"
        f"🎁 كل صديق = <b>+100 MYT</b>\n"
        f"📺 20 إعلان يومياً\n"
        f"⚡ 100 ضغطة يومياً\n"
        f"🎯 تسجيل يومي حتى <b>+100 MYT</b>\n"
        f"👛 اسحب أرباحك بـ TON\n\n"
        f"👇 اضغط الزر للبدء:"
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
    logger.info(f"✅ /start from {user.id} ({first_name})")

# ============================================
# 💰 /stats
# ============================================
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = api_get(f"/api/user?id={user.id}")

    if not data or not data.get("exists"):
        await update.message.reply_text(
            "⚠️ لم تسجل بعد! اضغط /start للبدء.",
            parse_mode="HTML",
        )
        return

    balance = fmt_number(data.get("balance", 0))
    pending = fmt_number(data.get("pending", 0))
    refs = data.get("refs", 0)
    streak = data.get("streak", 0)
    checkin_day = data.get("checkinDay", 0)
    wallet = data.get("wallet", "")

    wallet_text = f"<code>{wallet[:8]}...{wallet[-6:]}</code>" if wallet else "❌ غير متصل"

    text = (
        f"📊 <b>إحصائياتك</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 الاسم: <b>{user.first_name}</b>\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"💰 الرصيد: <b>{balance} MYT</b>\n"
        f"⏳ معلق: <b>{pending} MYT</b>\n"
        f"👥 الإحالات: <b>{refs}</b>\n"
        f"🔥 السلسلة: <b>{streak}</b>\n"
        f"📅 أيام التسجيل: <b>{checkin_day}/7</b>\n"
        f"👛 المحفظة: {wallet_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⛏️ فتح التطبيق",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

# ============================================
# 💰 /balance
# ============================================
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_stats(update, context)

# ============================================
# ❓ /help
# ============================================
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"❓ <b>مساعدة MYTOKEN</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>⛏️ كيف أبدأ؟</b>\n"
        f"• اضغط /start\n"
        f"• اضغط 'ابدأ التعدين'\n"
        f"• انقر على العملة MYT\n\n"
        f"<b>💰 كيف أربح؟</b>\n"
        f"• كل ضغطة = 0.001 MYT\n"
        f"• كل إعلان = 0.10 MYT\n"
        f"• كل إحالة = +100 MYT\n"
        f"• التسجيل اليومي حتى +100 MYT\n\n"
        f"<b>👛 كيف أسحب؟</b>\n"
        f"• اربط محفظة TON من التطبيق\n"
        f"• اذهب لصفحة 'حسابك'\n"
        f"• اضغط 'Connect Wallet'\n\n"
        f"<b>📋 الأوامر:</b>\n"
        f"/start — البداية\n"
        f"/stats — إحصائياتك\n"
        f"/balance — رصيدك\n"
        f"/help — هذه القائمة\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💬 للدعم: @OOO0BBBBBBOT"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⛏️ افتح التطبيق",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )],
        [InlineKeyboardButton("💬 الدعم", url=SUPPORT_URL)],
    ])

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

# ============================================
# 🔘 Callback Handler
# ============================================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "account":
        user = query.from_user
        info = api_get(f"/api/user?id={user.id}")
        balance = fmt_number(info.get("balance", 0)) if info else "0.0000"
        refs = info.get("refs", 0) if info else 0

        text = (
            f"👤 <b>حسابك</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 <code>{user.id}</code>\n"
            f"💰 الرصيد: <b>{balance} MYT</b>\n"
            f"👥 الإحالات: <b>{refs}</b>\n\n"
            f"👇 افتح التطبيق للمزيد:"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "⛏️ افتح التطبيق",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif data == "help":
        text = (
            f"❓ <b>مساعدة سريعة</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"⛏️ اضغط على العملة لجمع MYT\n"
            f"📺 شاهد 20 إعلاناً يومياً\n"
            f"🎁 سجّل يومياً حتى +100 MYT\n"
            f"👥 ادعُ أصدقاءك (+100 لكل صديق)\n"
            f"👛 اربط محفظة TON للسحب\n\n"
            f"استخدم /help للتفاصيل الكاملة"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back")],
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif data == "back":
        user = query.from_user
        text = (
            f"👋 <b>{user.first_name}</b> — القائمة الرئيسية\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👇 اختر من الأزرار:"
        )
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=main_keyboard(),
        )

# ============================================
# 🛠️ ضبط Menu Button
# ============================================
async def set_menu_button(app):
    try:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="⛏️ افتح MYTOKEN",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        )
        logger.info("✅ Menu button set")
    except Exception as e:
        logger.warning(f"Menu button error: {e}")

# ============================================
# 🚀 Main
# ============================================
async def main():
    t = Thread(target=run_health_server, daemon=True)
    t.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(callback_handler))

    await app.initialize()
    await set_menu_button(app)
    await app.start()

    logger.info("✅ MYTOKEN Bot is running...")
    logger.info(f"🌐 WebApp: {WEBAPP_URL}")
    logger.info(f"🔗 API: {API_BASE}")

    await app.updater.start_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )

    await asyncio.Event().wait()

# ============================================
# ▶️ Entry Point
# ============================================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped")
    except Exception as e:
        logger.error(f"❌ Fatal: {e}")
