import asyncio
import logging
import os
import urllib.request
import json
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8063963886:AAFC70T-QidXV9M2U8k2hj1tpc_jlHaGMI0"
WEBAPP_URL = "https://silver-taffy-3217e8.netlify.app"
API_BASE = "https://mytoken-api.vercel.app"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'MYTOKEN Bot is alive')
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print('Health server running on port ' + str(port))
    server.serve_forever()

def api_call(endpoint, data):
    try:
        url = API_BASE + endpoint
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body,
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print('API error [' + endpoint + ']: ' + str(e))
        return None

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛏️ ابدأ التعدين", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📊 حسابي", callback_data="stats"),
         InlineKeyboardButton("👥 المجموعة", url="https://t.me/your_group")]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text or ''
    ref_id = ''
    parts = text.split(' ')
    if len(parts) > 1 and parts[1].startswith('ref_'):
        ref_id = parts[1].replace('ref_', '').strip()

    result = api_call('/api/referral', {
        'user_id': user.id,
        'name': user.first_name or 'User',
        'username': user.username or '',
        'referrer_id': ref_id
    })

    if ref_id and result and result.get('referral_processed'):
        try:
            notify = '🎉 صديقك ' + (user.first_name or 'User') + ' انضم عبر رابطك!\n💰 ربحت 100 MYT!'
            await context.bot.send_message(chat_id=int(ref_id), text=notify)
        except Exception as e:
            print('Notify error: ' + str(e))

    msg = '👋 أهلاً ' + (user.first_name or 'User') + '!\n\n'
    msg += '💰 اجمع MYT من التطبيق!\n'
    msg += '🎁 100 MYT لكل صديق يدعوه\n'
    msg += '📅 20 إعلان يومياً\n'
    msg += '⚡ 100 ضغطة يومياً'
    if ref_id:
        msg += '\n\n🎁 تم إضافة 100 MYT لصديقك!'
    await update.message.reply_text(msg, reply_markup=main_keyboard())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = api_call('/api/user', {'user_id': user.id})
    if not data or not data.get('ok'):
        await update.message.reply_text('⚠️ لم أجد بياناتك.\nاضغط /start أولاً.')
        return
    txt = (
        '📊 *إحصائياتك*\n\n'
        '💰 الرصيد: `' + str(round(data.get('balance', 0), 4)) + '` MYT\n'
        '⚡ الطاقة: `' + str(data.get('energy', 0)) + '/' + str(data.get('max_energy', 100)) + '`\n'
        '⭐ المستوى: `' + str(data.get('level', 1)) + '`\n'
        '🎯 النقرات: `' + str(data.get('taps', 0)) + '`\n'
        '👥 الإحالات: `' + str(data.get('refs', 0)) + '`\n'
        '💎 أرباح الإحالات: `' + str(round(data.get('ref_earned', 0), 2)) + '` MYT\n'
        '📅 أيام التسجيل: `' + str(data.get('checkinDay', 0)) + '/7`'
    )
    await update.message.reply_text(txt, parse_mode='Markdown', reply_markup=main_keyboard())

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = api_call('/api/user', {'user_id': user.id})
    if not data or not data.get('ok'):
        await update.message.reply_text('⚠️ اضغط /start أولاً.')
        return
    await update.message.reply_text(
        '💰 رصيدك: `' + str(round(data.get('balance', 0), 4)) + '` MYT',
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (
        '🤖 *أوامر البوت*\n\n'
        '/start — ابدأ اللعب\n'
        '/stats — إحصائياتك الكاملة\n'
        '/balance — رصيدك فقط\n'
        '/help — هذه القائمة\n\n'
        '💡 افتح التطبيق واضغط على العملة لجمع MYT!\n'
        '🎁 ادعُ أصدقاءك واحصل على 100 MYT لكل صديق.'
    )
    await update.message.reply_text(txt, parse_mode='Markdown', reply_markup=main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == 'stats':
        user = update.effective_user
        data = api_call('/api/user', {'user_id': user.id})
        if not data or not data.get('ok'):
            await query.message.reply_text('⚠️ اضغط /start أولاً.')
            return
        txt = (
            '📊 *إحصائياتك*\n\n'
            '💰 الرصيد: `' + str(round(data.get('balance', 0), 4)) + '` MYT\n'
            '⚡ الطاقة: `' + str(data.get('energy', 0)) + '/' + str(data.get('max_energy', 100)) + '`\n'
            '⭐ المستوى: `' + str(data.get('level', 1)) + '`\n'
            '👥 الإحالات: `' + str(data.get('refs', 0)) + '`'
        )
        await query.message.reply_text(txt, parse_mode='Markdown')

async def main() -> None:
    t = Thread(target=run_health_server, daemon=True)
    t.start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("✅ Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
