import json, os, urllib.request, urllib.parse, datetime, random

BOT_TOKEN = "8063963886:AAFC70T-QidXV9M2U8k2hj1tpc_jlHaGMI0"
WEBAPP_URL = "https://teal-tartufo-5a611a.netlify.app"
REDIS_URL = os.environ.get('UPSTASH_REDIS_REST_URL', '')
REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json; charset=utf-8'
}

def json_resp(data, status=200):
    return {'statusCode': status, 'headers': CORS, 'body': json.dumps(data, ensure_ascii=False)}

def redis_cmd(*args):
    if not REDIS_URL or not REDIS_TOKEN:
        return None
    try:
        url = REDIS_URL.rstrip('/') + '/' + '/'.join(urllib.parse.quote(str(a), safe='') for a in args)
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + REDIS_TOKEN})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode()).get('result')
    except Exception as e:
        print('Redis error: ' + str(e))
        return None

def get_user(uid):
    data = redis_cmd('hgetall', 'user:' + str(uid))
    if not data:
        return None
    result = {}
    for i in range(0, len(data), 2):
        result[data[i]] = data[i+1]
    return result

def save_user(uid, data):
    for k, v in data.items():
        redis_cmd('hset', 'user:' + str(uid), k, str(v))

def create_user(uid, name='User', username='', referred_by=''):
    if get_user(uid):
        return False
    save_user(uid, {
        'user_id': uid, 'first_name': name, 'username': username,
        'balance': 0, 'energy': 100, 'max_energy': 100,
        'level': 1, 'xp': 0, 'taps': 0, 'referrals': 0,
        'ref_earned': 0, 'checkin_day': 0, 'last_checkin': '',
        'ads_today': 0, 'last_ad_date': '',
        'daily_taps': 0, 'last_reset': '',
        'referred_by': referred_by, 'wallet': '',
        'created_at': datetime.date.today().isoformat()
    })
    return True

def get_today():
    return datetime.date.today().isoformat()

def reset_daily(uid, u):
    today = get_today()
    if u.get('last_reset') != today:
        u['energy'] = u.get('max_energy', '100')
        u['daily_taps'] = '0'
        u['ads_today'] = '0'
        u['last_reset'] = today
        save_user(uid, u)
    return u

def process_referral(new_uid, ref_id):
    if not ref_id or str(ref_id) == str(new_uid):
        return False
    ref_user = get_user(ref_id)
    if not ref_user:
        return False
    new_user = get_user(new_uid)
    if new_user and new_user.get('referred_by'):
        return False
    ref_balance = float(ref_user.get('balance', 0)) + 100.0
    ref_count = int(ref_user.get('referrals', 0)) + 1
    ref_earned = float(ref_user.get('ref_earned', 0)) + 100.0
    ref_user['balance'] = ref_balance
    ref_user['referrals'] = ref_count
    ref_user['ref_earned'] = ref_earned
    save_user(ref_id, ref_user)
    if new_user:
        new_user['referred_by'] = str(ref_id)
        save_user(new_uid, new_user)
    return True

def send_tg(chat_id, text, keyboard=None):
    url = 'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = json.dumps(keyboard)
    data = urllib.parse.urlencode(payload).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print('TG error: ' + str(e))
        return None

def api_referral(data):
    uid = data.get('user_id')
    ref_id = data.get('referrer_id')
    name = data.get('name', 'User')
    username = data.get('username', '')
    if not uid:
        return json_resp({'ok': False, 'error': 'no user_id'})
    create_user(uid, name, username, str(ref_id) if ref_id else '')
    if ref_id:
        success = process_referral(uid, ref_id)
        return json_resp({'ok': True, 'referral_processed': success})
    return json_resp({'ok': True, 'referral_processed': False})

def api_user(data):
    uid = data.get('user_id')
    if not uid:
        return json_resp({'ok': False, 'error': 'no user_id'})
    u = get_user(uid)
    if not u:
        return json_resp({'ok': False, 'error': 'not found'})
    u = reset_daily(uid, u)
    return json_resp({
        'ok': True,
        'balance': float(u.get('balance', 0)),
        'energy': int(u.get('energy', 100)),
        'max_energy': int(u.get('max_energy', 100)),
        'level': int(u.get('level', 1)),
        'xp': int(u.get('xp', 0)),
        'taps': int(u.get('taps', 0)),
        'refs': int(u.get('referrals', 0)),
        'ref_earned': float(u.get('ref_earned', 0)),
        'checkinDay': int(u.get('checkin_day', 0)),
        'dailyTaps': int(u.get('daily_taps', 0)),
        'username': u.get('username', ''),
        'first_name': u.get('first_name', 'User'),
        'wallet': u.get('wallet', '')
    })

def api_tap(data):
    uid = data.get('user_id')
    taps = int(data.get('taps', 0))
    if not uid or taps <= 0:
        return json_resp({'ok': False})
    u = get_user(uid)
    if not u:
        return json_resp({'ok': False})
    energy = int(u.get('energy', 100))
    bal = float(u.get('balance', 0))
    total = int(u.get('taps', 0))
    daily = int(u.get('daily_taps', 0))
    if energy < taps:
        taps = energy
    if daily + taps > 100:
        taps = max(0, 100 - daily)
    new_bal = bal + taps * 0.001
    new_energy = energy - taps
    u['energy'] = new_energy
    u['balance'] = new_bal
    u['taps'] = total + taps
    u['daily_taps'] = daily + taps
    save_user(uid, u)
    return json_resp({'ok': True, 'balance': round(new_bal, 4), 'energy': new_energy, 'dailyTaps': daily + taps})

def api_ad(data):
    uid = data.get('user_id')
    if not uid:
        return json_resp({'ok': False})
    u = get_user(uid)
    if not u:
        return json_resp({'ok': False})
    today = get_today()
    ads = int(u.get('ads_today', 0)) if u.get('last_ad_date') == today else 0
    if ads >= 20:
        return json_resp({'ok': False, 'error': 'limit'})
    new_bal = float(u.get('balance', 0)) + 0.10
    u['balance'] = new_bal
    u['ads_today'] = ads + 1
    u['last_ad_date'] = today
    save_user(uid, u)
    return json_resp({'ok': True, 'reward': 0.10, 'balance': round(new_bal, 4)})

def api_checkin(data):
    uid = data.get('user_id')
    if not uid:
        return json_resp({'ok': False})
    u = get_user(uid)
    if not u:
        return json_resp({'ok': False})
    today = get_today()
    if u.get('last_checkin') == today:
        return json_resp({'ok': False, 'error': 'already'})
    day = int(u.get('checkin_day', 0))
    rewards = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0]
    new_day = day + 1 if day < 7 else 1
    reward = rewards[new_day - 1]
    new_bal = float(u.get('balance', 0)) + reward
    u['checkin_day'] = new_day
    u['last_checkin'] = today
    u['balance'] = new_bal
    save_user(uid, u)
    return json_resp({'ok': True, 'reward': reward, 'day': new_day, 'balance': round(new_bal, 4)})

def api_wallet_save(data):
    uid = data.get('user_id')
    wallet = data.get('wallet', '').strip()
    if not uid:
        return json_resp({'ok': False})
    u = get_user(uid)
    if not u:
        return json_resp({'ok': False})
    u['wallet'] = wallet
    save_user(uid, u)
    return json_resp({'ok': True, 'wallet': wallet})

def api_webhook(data):
    try:
        if 'message' not in data:
            return json_resp({'ok': True})
        m = data['message']
        cid = m['chat']['id']
        txt = m.get('text', '')
        f = m['from']
        uid = f['id']
        name = f.get('first_name', 'User')
        uname = f.get('username', '')
        ref_id = ''
        if txt.startswith('/start'):
            parts = txt.split(' ')
            if len(parts) > 1 and parts[1].startswith('ref_'):
                ref_id = parts[1].replace('ref_', '').strip()
        create_user(uid, name, uname, ref_id)
        if ref_id:
            success = process_referral(uid, ref_id)
            if success:
                try:
                    send_tg(int(ref_id), '🎉 صديقك ' + name + ' انضم عبر رابطك!\n💰 ربحت 100 MYT!')
                except Exception as e:
                    print('Notify error: ' + str(e))
        if txt.startswith('/start'):
            kb = {'inline_keyboard': [
                [{'text': '⛏️ ابدأ التعدين', 'web_app': {'url': WEBAPP_URL}}],
                [{'text': '👥 المجموعة', 'url': 'https://t.me/your_group'}]
            ]}
            msg = 'أهلاً ' + name + '!\n💰 اجمع MYT من التطبيق!'
            if ref_id:
                msg += '\n🎁 تم إضافة 100 MYT لصديقك!'
            send_tg(cid, msg, kb)
        return json_resp({'ok': True})
    except Exception as e:
        return json_resp({'ok': False, 'error': str(e)})

def handler(event, context):
    path = event.get('path', '/')
    if path == '/' or path == '':
        html = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>MYTOKEN API</title><style>body{background:#030607;color:#00ff88;font-family:Arial;text-align:center;padding:60px 20px}h1{font-size:44px;text-shadow:0 0 25px #00ff88}</style></head><body><h1>MYTOKEN API</h1><p>Server Online</p></body></html>'
        return {'statusCode': 200, 'headers': {'Content-Type': 'text/html; charset=utf-8'}, 'body': html}
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}
    try:
        data = json.loads(event.get('body', '{}') or '{}')
    except:
        data = {}
    routes = {
        '/api/webhook': api_webhook,
        '/api/user': api_user,
        '/api/tap': api_tap,
        '/api/ad': api_ad,
        '/api/checkin': api_checkin,
        '/api/referral': api_referral,
        '/api/wallet_save': api_wallet_save
    }
    fn = routes.get(path)
    if fn:
        return fn(data)
    return json_resp({'ok': False, 'error': 'not found'}, 404)
