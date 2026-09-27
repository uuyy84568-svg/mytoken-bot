# MYTOKEN v6 - ATF-style profile
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
states = {}
sound_settings = {}

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

def usd(m):
    try:
        return '{:.2f}'.format(float(m or 0) * RATE)
    except:
        return '0.00'

def mk_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('MYTOKEN افتح', web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton('حسابي', callback_data='account'), InlineKeyboardButton('دعوة صديق', callback_data='invite')],
        [InlineKeyboardButton('القناة', url=CHANNEL_URL)],
    ])

def mk_join():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('انضم للقناة', url=CHANNEL_URL)],
        [InlineKeyboardButton('تحقق من الاشتراك', callback_data='check_sub')],
    ])

def mk_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='account')]])

def mk_back_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='back')]])

def mk_account():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('ربط المحفظة', callback_data='acc_wallet'), InlineKeyboardButton('VIP', callback_data='acc_vip')],
        [InlineKeyboardButton('سحب', callback_data='acc_withdraw'), InlineKeyboardButton('السجل', callback_data='acc_history')],
        [InlineKeyboardButton('الإحصائيات', callback_data='acc_stats'), InlineKeyboardButton('الأصوات', callback_data='acc_sound')],
        [InlineKeyboardButton('رجوع', callback_data='back')],
    ])

async def check_sub(ctx, uid):
    try:
        m = await ctx.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        return m.status in ('member', 'administrator', 'creator')
    except Exception as e:
        logger.warning(str(e))
        return True

def render_account(ud, uid, name):
    bal = float(ud.get('balance', 0) or 0)
    pend = float(ud.get('pending', 0) or 0)
    refs = ud.get('refs', 0)
    wal = ud.get('wallet', '')
    ck = ud.get('checkinDay', 0)
    lv = ud.get('level', 1)
    wal_short = wal[:10] + '...' + wal[-6:] if wal else 'غير مربوط'
    verified = 'Verified' if wal else 'Unverified'
    sound = 'On' if sound_settings.get(uid, True) else 'Off'
    txt = ('👤 حسابي' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
           '🆔 User ID: ' + str(uid) + NL +
           '👋 الاسم: ' + name + NL + NL +
           '✅ Account: ' + verified + NL +
           '🔊 Sound: ' + sound + NL +
           '⚡ Level: Lv' + str(lv) + NL + NL +
           '💎 VIP: غير مفعل' + NL + NL +
           '💰 Assets: ' + fnum(bal) + ' MYT' + NL +
           '💵 بالدولار: $' + usd(bal) + NL + NL +
           '💳 Holding Wallet' + NL +
           '   ' + wal_short + NL + NL +
           '🏦 Pool Wallet' + NL +
           '   ' + fnum(bal) + ' MYT ($$' + usd(bal) + ')' + NL +
           '   ⏳ معلق: ' + fnum(pend) + ' MYT' + NL + NL +
           '📊 الحد الأدنى للسحب: ' + str(MIN_WITHDRAW) + ' MYT ($$' + usd(MIN_WITHDRAW) + ')' + NL + NL +
           '👥 الإحالات: ' + str(refs) + ' | 📅 ' + str(ck) + '/7' + NL + NL +
           '👇 اختر الإجراء:')
    return txt

async def cmd_start(update, ctx):
    u = update.effective_user
    fn = u.first_name or 'User'
    states.pop(u.id, None)
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
            nt = '🎉 صديق جديد!' + NL + '💰 +100 MYT' + NL + '👥 إحالاتك +1'
            await ctx.bot.send_message(chat_id=int(ref), text=nt, parse_mode='HTML')
        except Exception as e:
            logger.warning(str(e))
    t = ('👋 أهلاً ' + fn + '!' + NL + '⛏️ MYTOKEN' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
         '🎁 دعوة صديق = +100 MYT' + NL +
         '💼 اضغط حسابي لإدارة محفظتك' + NL + NL +
         '👇 ابدأ:')
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cmd_stats(update, ctx):
    u = update.effective_user
    d = api_post('/api/user', {'id': u.id})
    if not d or not d.get('exists'):
        await update.message.reply_text('اضغط /start')
        return
    bal = float(d.get('balance', 0) or 0)
    t = ('📊 رصيدك: ' + fnum(bal) + ' MYT ($' + usd(bal) + ')')
    await update.message.reply_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())

async def cb(update, ctx):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = q.from_user
    uid = u.id
    name = u.first_name or 'User'
    try:
        if d == 'check_sub':
            if await check_sub(ctx, uid):
                await q.edit_message_text('✅ تم التحقق! اضغط /start')
            else:
                await q.answer('لم تشترك!', show_alert=True)
            return

        if d == 'account':
            ud = api_post('/api/user', {'id': uid})
            if not ud or not ud.get('exists'):
                await q.edit_message_text('اضغط /start أولاً', reply_markup=mk_back_main())
                return
            txt = render_account(ud, uid, name)
            try:
                await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=mk_account())
            except Exception:
                await q.edit_message_reply_markup(reply_markup=mk_account())
                await q.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=mk_account())
            return

        if d == 'back':
            states.pop(uid, None)
            t = ('👋 أهلاً ' + name + '!' + NL + '⛏️ MYTOKEN' + NL + NL + '👇 اختر:')
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_main())
            return

        if d == 'invite':
            bi = await ctx.bot.get_me()
            rl = 'https://t.me/' + bi.username + '?start=ref_' + str(uid)
            t = '🎁 رابطك:' + NL + NL + '<code>' + rl + '</code>' + NL + NL + '💰 +100 MYT لكل صديق'
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='back')]])
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)
            return

        if d == 'acc_wallet':
            states[uid] = 'await_wallet'
            t = '💼 ربط محفظة TON' + NL + NL + 'أرسل عنوان محفظتك الآن:' + NL + 'مثال: UQ...'
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_back())
            return

        if d == 'acc_vip':
            t = ('💎 VIP' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
                 'VIP يمنحك:' + NL +
                 '• مضاعف 2x للتعدين' + NL +
                 '• مضاعف 2x للإعلانات' + NL +
                 '• مكافآت يومية أعلى' + NL + NL +
                 '💵 السعر: 1 TON' + NL + NL +
                 '⏳ قريباً')
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='account')]])
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            return

        if d == 'acc_withdraw':
            ud = api_post('/api/user', {'id': uid})
            bal = float((ud or {}).get('balance', 0) or 0)
            wal = (ud or {}).get('wallet', '')
            if not wal:
                t = '❌ اربط محفظتك أولاً!'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton('ربط المحفظة', callback_data='acc_wallet')], [InlineKeyboardButton('رجوع', callback_data='account')]])
                await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
                return
            if bal < MIN_WITHDRAW:
                need = MIN_WITHDRAW - bal
                t = '❌ رصيدك غير كافٍ' + NL + NL + '💰 رصيدك: ' + fnum(bal) + ' MYT' + NL + '📊 تحتاج: ' + fnum(need) + ' MYT'
                kb = InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='account')]])
                await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
                return
            states[uid] = 'await_withdraw'
            t = ('📤 السحب' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
                 '💰 رصيدك: ' + fnum(bal) + ' MYT ($' + usd(bal) + ')' + NL +
                 '📊 الحد الأدنى: ' + str(MIN_WITHDRAW) + ' MYT' + NL + NL +
                 'أرسل الكمية المراد سحبها:')
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=mk_back())
            return

        if d == 'acc_history':
            t = '📜 السجل' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL + 'لا توجد سحوبات بعد.'
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='account')]])
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            return

        if d == 'acc_stats':
            ud = api_post('/api/user', {'id': uid})
            if not ud:
                return
            t = ('📊 الإحصائيات' + NL + '━━━━━━━━━━━━━━━━━━' + NL + NL +
                 '👥 الإحالات: ' + str(ud.get('refs', 0)) + NL +
                 '📅 التسجيل: ' + str(ud.get('checkinDay', 0)) + '/7' + NL +
                 '⚡ المستوى: Lv' + str(ud.get('level', 1)) + NL +
                 '💰 الرصيد: ' + fnum(ud.get('balance', 0)) + ' MYT' + NL +
                 '⏳ المعلق: ' + fnum(ud.get('pending', 0)) + ' MYT')
            kb = InlineKeyboardMarkup([[InlineKeyboardButton('رجوع', callback_data='account')]])
            await q.edit_message_text(t, parse_mode=ParseMode.HTML, reply_markup=kb)
            return

        if d == 'acc_sound':
            cur = sound_settings.get(uid, True)
            sound_settings[uid] = not cur
            status = 'On' if not cur else 'Off'
            await q.answer('الصوت: ' + status)
            ud = api_post('/api/user', {'id': uid})
            txt = render_account(ud or {}, uid, name)
            await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=mk_account())
            return

        if d.startswith('wd_ok_'):
            parts = d.replace('wd_ok_', '').split('_')
            tu = parts[0]
            am = parts[1]
            await q.edit_message_text('✅ موافقة: ' + am + ' MYT لـ ' + tu)
            try:
                await ctx.bot.send_message(chat_id=int(tu), text='✅ تمت الموافقة على سحب ' + am + ' MYT' + NL + 'ستُرسل لمحفظتك قريباً', parse_mode='HTML')
            except Exception as e:
                logger.warning(str(e))
            return

        if d.startswith('wd_no_'):
            parts = d.replace('wd_no_', '').split('_')
            tu = parts[0]
            am = parts[1]
            api_post('/api/admin/give', {'admin_id': ADMIN_ID, 'target_id': tu, 'amount': float(am)})
            await q.edit_message_text('❌ رفض وإرجاع ' + am + ' MYT')
            try:
                await ctx.bot.send_message(chat_id=int(tu), text='❌ تم رفض السحب. أُرجع رصيدك.', parse_mode='HTML')
            except Exception as e:
                logger.warning(str(e))
            return

    except Exception as e:
        logger.warning(str(e))

def mk_admin(uid, am):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton('موافقة', callback_data='wd_ok_' + uid + '_' + am),
         InlineKeyboardButton('رفض', callback_data='wd_no_' + uid + '_' + am)],
    ])

async def msg(update, ctx):
    u = update.effective_user
    st = states.get(u.id)
    if not st:
        return
    txt = (update.message.text or '').strip()
    if st == 'await_wallet':
        if len(txt) < 40 or len(txt) > 90:
            await update.message.reply_text('❌ عنوان غير صالح', reply_markup=mk_back())
            return
        r = api_post('/api/wallet', {'id': u.id, 'wallet': txt})
        states.pop(u.id, None)
        if r and r.get('ok'):
            await update.message.reply_text('✅ تم ربط محفظتك!' + NL + NL + txt[:10] + '...' + txt[-6:], reply_markup=mk_main())
        else:
            await update.message.reply_text('❌ فشل', reply_markup=mk_main())
    elif st == 'await_withdraw':
        try:
            am = float(txt)
        except:
            await update.message.reply_text('❌ رقم غير صالح', reply_markup=mk_back())
            return
        ud = api_post('/api/user', {'id': u.id})
        bal = float((ud or {}).get('balance', 0) or 0)
        if am < MIN_WITHDRAW:
            await update.message.reply_text('❌ الحد الأدنى ' + str(MIN_WITHDRAW), reply_markup=mk_back())
            return
        if am > bal:
            await update.message.reply_text('❌ رصيدك ' + fnum(bal) + ' فقط', reply_markup=mk_back())
            return
        r = api_post('/api/admin/give', {'admin_id': ADMIN_ID, 'target_id': str(u.id), 'amount': -am})
        states.pop(u.id, None)
        if r and r.get('ok'):
            await update.message.reply_text('✅ طلب سحب ' + fnum(am) + ' MYT ($' + usd(am) + ')' + NL + '⏳ قيد المراجعة', reply_markup=mk_main())
            wal = (ud or {}).get('wallet', '')
            at = ('🔔 طلب سحب جديد' + NL + '━━━━━━━━━━━━━━━━━━' + NL +
                  '👤 ' + (u.first_name or 'User') + NL +
                  '🆔 ' + str(u.id) + NL +
                  '💰 ' + fnum(am) + ' MYT ($' + usd(am) + ')' + NL +
                  '👛 ' + wal[:10] + '...' + wal[-6:])
            try:
                await ctx.bot.send_message(chat_id=int(ADMIN_ID), text=at, parse_mode='HTML', reply_markup=mk_admin(str(u.id), fnum(am)))
            except Exception as e:
                logger.warning(str(e))
        else:
            await update.message.reply_text('❌ فشل', reply_markup=mk_main())

async def err(update, ctx): logger.error(str(ctx.error))

async def main():
    Thread(target=run_health, daemon=True).start()
    if not BOT_TOKEN:
        logger.error('No token')
        return
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('balance', cmd_stats))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.add_error_handler(err)
    await app.initialize()
    try:
        await app.bot.set_my_commands([BotCommand('start', 'البداية'), BotCommand('stats', 'رصيدك')])
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
