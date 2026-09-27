# MYTOKEN Bot v5 - professional withdrawal
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
RATE = 0.001

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

def to_usd(myt):
    try:
        return '{:.2f}'.format(float(myt or 0) * RATE)
    except:
        return '0.00'

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

def mk_admin_wd(uid, amount):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('موافقة', callback_data='wd_ok_' + uid + '_' + amount),
         InlineKeyboardButton('رفض', callback_data='wd_no_' + uid + '_' + amount)],
    ])

async def check_sub(ctx, uid):
    try:
        m = await ctx.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        return m.status in ('member', 'administrator', 'creator')
    except Exception as e:
        logger.warning(str(e))
        return True

async def show_wallet(q, uid):
    d = api_post('/api/user', {'id': uid})
    wal = (d or {}).get('wallet', '')
    if wal:
        wt = wal[:10] + '...' + wal[-6:]
        t = ('💼 محفظتك مربوطة' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
             '👛 ' + wt + NL + NL +
             'لتغييرها اضغط تحديث')
    else:
        t = ('💼 ربط المحفظة' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
             'لم تربط محفظتك بعد.' + NL + NL +
             'اضغط ربط لإدخال عنوان محفظة TON')
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton('ربط/تحديث المحفظة', callback_data='wallet_set')],
        [InlineKeyboardButton('رجوع', callback_data='back')],
    ])
    await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)

async def show_withdraw(q, uid):
    d = api_post('/api/user', {'id': uid})
    if not d or not d.get('exists'):
        await q.edit_message_text('اضغط /start أولاً', reply_markup=mk_main())
        return
    wal = d.get('wallet', '')
    bal = float(d.get('balance', 0) or 0)
    pend = float(d.get('pending', 0) or 0)
    bal_usd = to_usd(bal)
    min_usd = to_usd(MIN_WITHDRAW)
    if bal >= MIN_WITHDRAW:
        status = '✅ يمكنك السحب'
        can = True
    else:
        need = MIN_WITHDRAW - bal
        status = '❌ تحتاج ' + fnum(need) + ' MYT للسحب'
        can = False
    wt = wal[:10] + '...' + wal[-6:] if wal else 'غير مربوط'
    t = ('📤 سحب الأرباح' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
         '💰 رصيدك: ' + fnum(bal) + ' MYT' + NL +
         '💵 بالدولار: $' + bal_usd + NL +
         '⏳ معلق: ' + fnum(pend) + ' MYT' + NL + NL +
         '📊 الحد الأدنى: ' + fnum(MIN_WITHDRAW) + ' MYT ($' + min_usd + ')' + NL +
         '👛 المحفظة: ' + wt + NL + NL +
         status)
    rows = []
    if can and wal:
        rows.append([InlineKeyboardButton('إرسال طلب سحب', callback_data='wd_send')])
    if not wal:
        rows.append([InlineKeyboardButton('ربط المحفظة', callback_data='wallet')])
    if can and not wal:
        pass
    rows.append([InlineKeyboardButton('رجوع', callback_data='back')])
    kb = InlineKeyboardMarkup(rows)
    await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)

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
    d = api_post('/api/user', {'id': u.id})
    bal = float((d or {}).get('balance', 0) or 0)
    bal_usd = to_usd(bal)
    t = ('👋 أهلاً ' + fn + '!' + NL + '⛏️ MYTOKEN' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
         '💰 رصيدك: ' + fnum(bal) + ' MYT ($' + bal_usd + ')' + NL + NL +
         '🎁 دعوة صديق = +100 MYT' + NL +
         '👛 اربط محفظتك' + NL +
         '📤 اسحب أرباحك' + NL + NL +
         '👇 ابدأ:')
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cmd_stats(update, ctx):
    u = update.effective_user
    d = api_post('/api/user', {'id': u.id})
    if not d or not d.get('exists'):
        await update.message.reply_text('اضغط /start')
        return
    bal = float(d.get('balance', 0) or 0)
    wal = d.get('wallet', '')
    wt = wal[:10] + '...' + wal[-6:] if wal else 'غير مربوط'
    t = ('📊 حسابك' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
         '💰 ' + fnum(bal) + ' MYT ($' + to_usd(bal) + ')' + NL +
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
            b = float((ud or {}).get('balance', 0) or 0)
            await q.edit_message_text('💰 ' + fnum(b) + ' MYT ($' + to_usd(b) + ')', reply_markup=mk_main())
        elif d == 'wallet':
            await show_wallet(q, u.id)
        elif d == 'wallet_set':
            user_states[u.id] = 'await_wallet'
            await q.edit_message_text('📝 أرسل عنوان محفظتك TON:' + NL + NL + 'مثال: UQ...', reply_markup=mk_back())
        elif d == 'withdraw':
            await show_withdraw(q, u.id)
        elif d == 'wd_send':
            user_states[u.id] = 'await_amount'
            ud = api_post('/api/user', {'id': u.id})
            b = float((ud or {}).get('balance', 0) or 0)
            await q.edit_message_text('📤 أدخل الكمية:' + NL + NL + '💰 رصيدك: ' + fnum(b) + ' MYT' + NL + '📊 الحد الأدنى: ' + str(MIN_WITHDRAW), reply_markup=mk_back())
        elif d == 'back':
            user_states.pop(u.id, None)
            await q.edit_message_text('القائمة:', reply_markup=mk_main())
        elif d.startswith('wd_ok_'):
            parts = d.replace('wd_ok_', '').split('_')
            uid = parts[0]
            amt = parts[1]
            await q.edit_message_text('✅ تمت الموافقة: ' + amt + ' MYT لـ ' + uid)
            try:
                await ctx.bot.send_message(chat_id=int(uid), text='✅ تمت الموافقة على سحب ' + amt + ' MYT' + NL + 'ستُرسل لمحفظتك قريباً', parse_mode='HTML')
            except Exception as e:
                logger.warning(str(e))
        elif d.startswith('wd_no_'):
            parts = d.replace('wd_no_', '').split('_')
            uid = parts[0]
            amt = parts[1]
            api_post('/api/admin/give', {'admin_id': ADMIN_ID, 'target_id': uid, 'amount': float(amt)})
            await q.edit_message_text('❌ تم الرفض وإرجاع ' + amt + ' MYT')
            try:
                await ctx.bot.send_message(chat_id=int(uid), text='❌ تم رفض طلب السحب. أُرجع رصيدك.', parse_mode='HTML')
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
            await update.message.reply_text('❌ عنوان غير صالح', reply_markup=mk_back())
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
            await update.message.reply_text('❌ الحد الأدنى ' + str(MIN_WITHDRAW) + ' MYT', reply_markup=mk_back())
            return
        if amt > bal:
            await update.message.reply_text('❌ رصيدك ' + fnum(bal) + ' MYT فقط', reply_markup=mk_back())
            return
        r = api_post('/api/admin/give', {'admin_id': ADMIN_ID, 'target_id': str(u.id), 'amount': -amt})
        user_states.pop(u.id, None)
        if r and r.get('ok'):
            await update.message.reply_text('✅ تم إنشاء طلب سحب ' + fnum(amt) + ' MYT ($' + to_usd(amt) + ')' + NL + '⏳ قيد المراجعة', reply_markup=mk_main())
            wal = (ud or {}).get('wallet', '')
            atxt = ('🔔 طلب سحب جديد' + NL + '━━━━━━━━━━━━━━━━━━' + NL +
                    '👤 ' + (u.first_name or 'User') + NL +
                    '🆔 ' + str(u.id) + NL +
                    '💰 ' + fnum(amt) + ' MYT ($' + to_usd(amt) + ')' + NL +
                    '👛 ' + wal[:10] + '...' + wal[-6:])
            try:
                await ctx.bot.send_message(chat_id=int(ADMIN_ID), text=atxt, parse_mode='HTML', reply_markup=mk_admin_wd(str(u.id), fnum(amt)))
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
        await app.bot.set_my_commands([BotCommand('start', 'البداية'), BotCommand('stats', 'حسابك'), BotCommand('balance', 'رصيدك')])
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
