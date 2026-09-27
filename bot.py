# MYTOKEN Bot v4 - with withdrawal
import asyncio, logging, os, json, urllib.request
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode

NL = chr(10)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
WEBAPP_URL = os.environ.get('WEBAPP_URL', 'https://mytoken-app-2026.netlify.app')
API_BASE = os.environ.get('API_BASE', 'https://mytoken-api.vercel.app')
ADMIN_ID = os.environ.get('ADMIN_ID', '8063963886')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@MyTokenMiningPro2')
CHANNEL_URL = os.environ.get('CHANNEL_URL', 'https://t.me/MyTokenMiningPro2')
MIN_WITHDRAW = 1000

logging.basicConfig(format='%(message)s', level=logging.INFO)
logger = logging.getLogger('MYTOKEN')
user_states = {}

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

def fnum(v):
    try:
        n = float(v or 0)
        return str(int(n)) if n == int(n) else '{:.2f}'.format(n)
    except:
        return '0'

def mk_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('MYTOKEN افتح', web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton('دعوة صديق', callback_data='invite'), InlineKeyboardButton('رصيدي', callback_data='balance')],
        [InlineKeyboardButton('ربط المحفظة', callback_data='wallet'), InlineKeyboardButton('سحب', callback_data='withdraw')],
        [InlineKeyboardButton('القناة', url=CHANNEL_URL)],
    ])

def mk_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('انضم للقناة', url=CHANNEL_URL)],
        [InlineKeyboardButton('تحقق من الاشتراك', callback_data='check_sub')],
    ])

def mk_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='back')]])

def mk_admin_withdraw(uid, amount, wallet):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('موافقة', callback_data='wd_ok_' + uid + '_' + str(amount)),
         InlineKeyboardButton('رفض', callback_data='wd_no_' + uid)],
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
    user_states.pop(u.id, None)
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
    t = '👋 أهلاً ' + fn + '!' + NL + '⛏️ MYTOKEN' + NL + NL + '🎁 دعوة صديق = +100 MYT' + NL + '👛 اربط محفظتك' + NL + '📤 اسحب أرباحك' + NL + NL + '👇 ابدأ:'
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cmd_stats(update, ctx):
    u = update.effective_user
    d = api_post('/api/user', {'id': u.id})
    if not d or not d.get('exists'):
        await update.message.reply_text('اضغط /start')
        return
    wal = d.get('wallet', '')
    wt = wal[:8] + '...' + wal[-6:] if wal else 'غير مربوط'
    t = ('📊 رصيدك: ' + fnum(d.get('balance', 0)) + ' MYT' + NL +
         '👥 الإحالات: ' + str(d.get('refs', 0)) + NL +
         '👛 المحفظة: ' + wt)
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cb_handler(update, ctx):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = q.from_user
    try:
        if d == 'check_sub':
            if await check_sub(ctx, u.id):
                await q.edit_message_text('✅ تم التحقق! اضغط /start')
            else:
                await q.answer('لم تشترك!', show_alert=True)
        elif d == 'invite':
            bi = await ctx.bot.get_me()
            rl = 'https://t.me/' + bi.username + '?start=ref_' + str(u.id)
            await q.edit_message_text('🎁 رابطك:' + NL + rl, reply_markup=mk_main())
        elif d == 'balance':
            ud = api_post('/api/user', {'id': u.id})
            await q.edit_message_text('💰 رصيدك: ' + fnum((ud or {}).get('balance', 0)) + ' MYT', reply_markup=mk_main())
        elif d == 'wallet':
            user_states[u.id] = 'await_wallet'
            await q.edit_message_text('📝 أرسل عنوان محفظتك TON:' + NL + NL + 'مثال: UQ...', reply_markup=mk_back())
        elif d == 'withdraw':
            ud = api_post('/api/user', {'id': u.id})
            if not ud or not ud.get('exists'):
                await q.edit_message_text('اضغط /start أولاً', reply_markup=mk_main())
                return
            wal = ud.get('wallet', '')
            bal = float(ud.get('balance', 0) or 0)
            if not wal:
                await q.edit_message_text('❌ اربط محفظتك أولاً!', reply_markup=mk_main())
                return
            if bal < MIN_WITHDRAW:
                await q.edit_message_text('❌ الحد الأدنى للسحب ' + str(MIN_WITHDRAW) + ' MYT' + NL + 'رصيدك: ' + fnum(bal), reply_markup=mk_main())
                return
            user_states[u.id] = 'await_amount'
            await q.edit_message_text('📤 أدخل الكمية المراد سحبها:' + NL + 'الحد الأدنى: ' + str(MIN_WITHDRAW) + NL + 'رصيدك: ' + fnum(bal) + ' MYT', reply_markup=mk_back())
        elif d == 'back':
            user_states.pop(u.id, None)
            await q.edit_message_text('القائمة الرئيسية:', reply_markup=mk_main())
        elif d.startswith('wd_ok_'):
            parts = d.replace('wd_ok_', '').split('_')
            uid = parts[0]
            amt = parts[1]
            await q.edit_message_text('✅ تمت الموافقة على سحب ' + amt + ' MYT من ' + uid)
            try:
                await ctx.bot.send_message(chat_id=int(uid), text='✅ تمت الموافقة على طلبك!' + NL + '💰 ' + amt + ' MYT ستُرسل إلى محفظتك قريباً.', parse_mode='HTML')
            except Exception as e:
                logger.warning(str(e))
        elif d.startswith('wd_no_'):
            uid = d.replace('wd_no_', '')
            api_post('/api/admin/give', {'admin_id': ADMIN_ID, 'target_id': uid, 'amount': 0})
            await q.edit_message_text('❌ تم رفض الطلب، وأُرجع الرصيد لـ ' + uid)
            try:
                await ctx.bot.send_message(chat_id=int(uid), text='❌ تم رفض طلب السحب. أعد المحاولة لاحقاً.', parse_mode='HTML')
            except Exception as e:
                logger.warning(str(e))
    except Exception as e:
        logger.warning(str(e))

async def msg_handler(update, ctx):
    u = update.effective_user
    st = user_states.get(u.id)
    if not st:
        return
    txt = (update.message.text or '').strip()
    if st == 'await_wallet':
        if len(txt) < 40 or len(txt) > 80:
            await update.message.reply_text('❌ عنوان غير صالح! أرسل عنوان TON صحيح', reply_markup=mk_back())
            return
        r = api_post('/api/wallet', {'id': u.id, 'wallet': txt})
        user_states.pop(u.id, None)
        if r and r.get('ok'):
            await update.message.reply_text('✅ تم ربط محفظتك!' + NL + NL + txt[:10] + '...' + txt[-6:], reply_markup=mk_main())
        else:
            await update.message.reply_text('❌ فشل الربط', reply_markup=mk_main())
    elif st == 'await_amount':
        try:
            amt = float(txt)
        except:
            await update.message.reply_text('❌ رقم غير صالح', reply_markup=mk_back())
            return
        ud = api_post('/api/user', {'id': u.id})
        bal = float((ud or {}).get('balance', 0) or 0)
        if amt < MIN_WITHDRAW:
            await update.message.reply_text('❌ الحد الأدنى ' + str(MIN_WITHDRAW), reply_markup=mk_back())
            return
        if amt > bal:
            await update.message.reply_text('❌ رصيدك ' + fnum(bal), reply_markup=mk_back())
            return
        r = api_post('/api/admin/give', {'admin_id': ADMIN_ID, 'target_id': str(u.id), 'amount': -amt})
        user_states.pop(u.id, None)
        if r and r.get('ok'):
            await update.message.reply_text('✅ تم إنشاء طلب سحب ' + fnum(amt) + ' MYT' + NL + 'قيد المراجعة', reply_markup=mk_main())
            wal = (ud or {}).get('wallet', '')
            atxt = ('🔔 طلب سحب جديد' + NL +
                    '👤 ' + (u.first_name or 'User') + NL +
                    '🆔 ' + str(u.id) + NL +
                    '💰 ' + fnum(amt) + ' MYT' + NL +
                    '👛 ' + wal[:10] + '...' + wal[-6:])
            try:
                await ctx.bot.send_message(chat_id=int(ADMIN_ID), text=atxt, parse_mode='HTML', reply_markup=mk_admin_withdraw(str(u.id), fnum(amt), wal))
            except Exception as e:
                logger.warning(str(e))
        else:
            await update.message.reply_text('❌ فشل', reply_markup=mk_main())

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
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    app.add_error_handler(err_h)
    await app.initialize()
    try:
        await app.bot.set_my_commands([BotCommand('start', 'البداية'), BotCommand('stats', 'إحصائياتك'), BotCommand('balance', 'رصيدك')])
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
