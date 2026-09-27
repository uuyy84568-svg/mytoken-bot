# MYTOKEN Bot v3
import asyncio, logging, os, json, urllib.request
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

NL = chr(10)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
WEBAPP_URL = os.environ.get('WEBAPP_URL', 'https://mytoken-app-2026.netlify.app')
API_BASE = os.environ.get('API_BASE', 'https://mytoken-api.vercel.app')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@MyTokenMiningPro2')
CHANNEL_URL = os.environ.get('CHANNEL_URL', 'https://t.me/MyTokenMiningPro2')

logging.basicConfig(format='%(message)s', level=logging.INFO)
logger = logging.getLogger('MYTOKEN')

class HH(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, *a): pass

def run_health():
    try:
        HTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8080))), HH).serve_forever()
    except Exception as e:
        logger.warning(str(e))

def api_post(path, body):
    try:
        url = API_BASE.rstrip('/') + path
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.warning(str(e))
        return None

def mk_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('MYTOKEN افتح', web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton('دعوة صديق', callback_data='invite'), InlineKeyboardButton('رصيدي', callback_data='balance')],
        [InlineKeyboardButton('القناة', url=CHANNEL_URL)],
    ])

def mk_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('انضم للقناة', url=CHANNEL_URL)],
        [InlineKeyboardButton('تحقق من الاشتراك', callback_data='check_sub')],
    ])

async def check_sub(ctx, uid):
    try:
        m = await ctx.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        return m.status in ('member', 'administrator', 'creator')
    except Exception as e:
        logger.warning(str(e))
        return True

async def cmd_start(update, ctx):
    u = update.effective_user
    fn = u.first_name or 'User'
    if not await check_sub(ctx, u.id):
        t = '🔒 الاشتراك مطلوب' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL + 'اشترك في قناتنا:' + NL + CHANNEL_ID
        await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_join())
        return
    ref = None
    if ctx.args:
        a = ctx.args[0].strip()
        if a.startswith('ref_'):
            ref = a.replace('ref_', '').strip()
    p = {'id': u.id, 'first_name': fn}
    if ref:
        p['ref'] = ref
    res = api_post('/api/register', p)
    if res and res.get('isNew') and res.get('referral') and ref:
        try:
            nt = '🎉 صديق جديد انضم!' + NL + '💰 +100 MYT' + NL + '👥 إحالاتك +1'
            await ctx.bot.send_message(chat_id=int(ref), text=nt, parse_mode='HTML')
        except Exception as e:
            logger.warning(str(e))
    t = '👋 أهلاً ' + fn + '!' + NL + '⛏️ MYTOKEN' + NL + NL + '🎁 دعوة صديق = +100 MYT' + NL + NL + '👇 ابدأ:'
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cmd_stats(update, ctx):
    u = update.effective_user
    d = api_post('/api/user', {'id': u.id})
    if not d or not d.get('exists'):
        await update.message.reply_text('اضغط /start')
        return
    t = '📊 رصيدك: ' + str(d.get('balance', 0)) + ' MYT' + NL + '👥 الإحالات: ' + str(d.get('refs', 0))
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cmd_help(update, ctx):
    t = '❓ الأوامر:' + NL + '/start' + NL + '/stats' + NL + '/balance' + NL + '/help'
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cb_handler(update, ctx):
    q = update.callback_query
    await q.answer()
    try:
        if q.data == 'check_sub':
            if await check_sub(ctx, q.from_user.id):
                await q.edit_message_text('✅ تم التحقق! اضغط /start')
            else:
                await q.answer('لم تشترك!', show_alert=True)
        elif q.data == 'invite':
            bi = await ctx.bot.get_me()
            rl = 'https://t.me/' + bi.username + '?start=ref_' + str(q.from_user.id)
            await q.edit_message_text('🎁 رابطك:' + NL + rl, reply_markup=mk_main())
        elif q.data == 'balance':
            d = api_post('/api/user', {'id': q.from_user.id})
            await q.edit_message_text('💰 رصيدك: ' + str((d or {}).get('balance', 0)) + ' MYT', reply_markup=mk_main())
    except Exception as e:
        logger.warning(str(e))

async def err_h(update, ctx): logger.error(str(ctx.error))

async def main():
    Thread(target=run_health, daemon=True).start()
    if not BOT_TOKEN:
        logger.error('No token')
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('balance', cmd_stats))
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_error_handler(err_h)
    await app.initialize()
    try:
        await app.bot.set_my_commands([BotCommand('start', 'البداية'), BotCommand('stats', 'إحصائياتك'), BotCommand('balance', 'رصيدك'), BotCommand('help', 'المساعدة')])
        await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text='MYTOKEN افتح', web_app=WebAppInfo(url=WEBAPP_URL)))
    except Exception as e:
        logger.warning(str(e))
    await app.start()
    logger.info('RUNNING')
    await app.updater.start_polling(allowed_updates=['message', 'callback_query'], drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(str(e))
