import asyncio
import logging
import os
import urllib.request
import json
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8063963886:AAFC70T-QidXV9M2U8k2hj1tpc_jlHaGMI0"
WEBAPP_URL = "https://teal-tartufo-5a611a.netlify.app"
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
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print('API error: ' + str(e))
        return None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text or ''
    ref_id = ''
    parts = text.split(' ')
    if len(parts) > 1 and parts[1].startswith('ref_'):
        ref_id = parts[1].replace('ref_', '').strip()
    api_call('/api/referral', {
        'user_id': user.id,
        'name': user.first_name or 'User',
        'username': user.username or '',
        'referrer_id': ref_id
    })
    keyboard = [
        [InlineKeyboardButton("⛏️ ابدأ التعدين", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("👥 المجموعة", url="https://t.me/your_group")]
    ]
    msg = 'أهلاً ' + (user.first_name or 'User') + '!\n💰 اجمع MYT من التطبيق!'
    if ref_id:
        msg += '\n🎁 تم إضافة 100 MYT لصديقك!'
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def main() -> None:
    t = Thread(target=run_health_server, daemon=True)
    t.start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    print("Bot is running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
