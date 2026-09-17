from flask import Flask, request, jsonify
import json, os, urllib.request, urllib.parse, datetime, random

app = Flask(__name__)

# ============================================
# الإعدادات
# ============================================
BOT_TOKEN = "8063963886:AAFC70T-QidXV9M2U8k2hj1tpc_jlHaGMI0"
WEBAPP_URL = "https://tranquil-pony-287daf.netlify.app"
REDIS_URL = os.environ.get('UPSTASH_REDIS_REST_URL', '')
REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
ADMIN_ID = 8063963886

# ============================================
# CORS (مهم للاتصال من Netlify)
# ============================================
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200

# ============================================
# Redis
# ============================================
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
        'referred_by': referred_by, 'ref_processed': '',
        'wallet': '', 'clan_id': '', 'clan_role': '',
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

def gen_code(length=6):
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))

def send_tg(chat_id, text):
    url = 'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage'
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    data = urllib.parse.urlencode(payload).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print('TG error: ' + str(e))
        return None

# ============================================
# الإحالة (مصححة)
# ============================================
def process_referral(new_uid, ref_id):
    if not ref_id or str(ref_id) == str(new_uid):
        return False
    ref_user = get_user(ref_id)
    if not ref_user:
        return False
    new_user = get_user(new_uid)
    if not new_user:
        return False
    if new_user.get('ref_processed') == '1':
        return False
    existing = new_user.get('referred_by', '')
    if existing and str(existing) != str(ref_id):
        return False
    ref_balance = float(ref_user.get('balance', 0)) + 100.0
    ref_count = int(ref_user.get('referrals', 0)) + 1
    ref_earned = float(ref_user.get('ref_earned', 0)) + 100.0
    ref_user['balance'] = ref_balance
    ref_user['referrals'] = ref_count
    ref_user['ref_earned'] = ref_earned
    save_user(ref_id, ref_user)
    new_user['referred_by'] = str(ref_id)
    new_user['ref_processed'] = '1'
    save_user(new_uid, new_user)
    return True

# ============================================
# الصفحة الرئيسية
# ============================================
@app.route('/')
def home():
    return '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>MYTOKEN API</title><style>body{background:#030607;color:#00ff88;font-family:Arial;text-align:center;padding:60px 20px}h1{font-size:44px;text-shadow:0 0 25px #00ff88}</style></head><body><h1>MYTOKEN API</h1><p>Server Online</p></body></html>'

# ============================================
# APIs المستخدم
# ============================================
@app.route('/api/referral', methods=['POST'])
def api_referral():
    data = request.get_json() or {}
    uid = data.get('user_id')
    ref_id = data.get('referrer_id')
    name = data.get('name', 'User')
    username = data.get('username', '')
    if not uid:
        return jsonify({'ok': False, 'error': 'no user_id'})
    existed = bool(get_user(uid))
    if not existed:
        create_user(uid, name, username, str(ref_id) if ref_id else '')
    if ref_id:
        success = process_referral(uid, ref_id)
        return jsonify({'ok': True, 'referral_processed': success, 'new_user': not existed})
    return jsonify({'ok': True, 'referral_processed': False, 'new_user': not existed})

@app.route('/api/user', methods=['POST'])
def api_user():
    data = request.get_json() or {}
    uid = data.get('user_id')
    if not uid:
        return jsonify({'ok': False, 'error': 'no user_id'})
    u = get_user(uid)
    if not u:
        return jsonify({'ok': False, 'error': 'not found'})
    u = reset_daily(uid, u)
    return jsonify({
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
        'wallet': u.get('wallet', ''),
        'referred_by': u.get('referred_by', '')
    })

@app.route('/api/tap', methods=['POST'])
def api_tap():
    data = request.get_json() or {}
    uid = data.get('user_id')
    taps = int(data.get('taps', 0))
    if not uid or taps <= 0:
        return jsonify({'ok': False})
    u = get_user(uid)
    if not u:
        return jsonify({'ok': False})
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
    return jsonify({'ok': True, 'balance': round(new_bal, 4), 'energy': new_energy, 'dailyTaps': daily + taps})

@app.route('/api/ad', methods=['POST'])
def api_ad():
    data = request.get_json() or {}
    uid = data.get('user_id')
    if not uid:
        return jsonify({'ok': False})
    u = get_user(uid)
    if not u:
        return jsonify({'ok': False})
    today = get_today()
    ads = int(u.get('ads_today', 0)) if u.get('last_ad_date') == today else 0
    if ads >= 20:
        return jsonify({'ok': False, 'error': 'limit'})
    new_bal = float(u.get('balance', 0)) + 0.10
    u['balance'] = new_bal
    u['ads_today'] = ads + 1
    u['last_ad_date'] = today
    save_user(uid, u)
    return jsonify({'ok': True, 'reward': 0.10, 'balance': round(new_bal, 4)})

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    data = request.get_json() or {}
    uid = data.get('user_id')
    if not uid:
        return jsonify({'ok': False})
    u = get_user(uid)
    if not u:
        return jsonify({'ok': False})
    today = get_today()
    if u.get('last_checkin') == today:
        return jsonify({'ok': False, 'error': 'already'})
    day = int(u.get('checkin_day', 0))
    rewards = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0]
    new_day = day + 1 if day < 7 else 1
    reward = rewards[new_day - 1]
    new_bal = float(u.get('balance', 0)) + reward
    u['checkin_day'] = new_day
    u['last_checkin'] = today
    u['balance'] = new_bal
    save_user(uid, u)
    return jsonify({'ok': True, 'reward': reward, 'day': new_day, 'balance': round(new_bal, 4)})

@app.route('/api/wallet_save', methods=['POST'])
def api_wallet_save():
    data = request.get_json() or {}
    uid = data.get('user_id')
    wallet = data.get('wallet', '').strip()
    if not uid:
        return jsonify({'ok': False})
    u = get_user(uid)
    if not u:
        return jsonify({'ok': False})
    u['wallet'] = wallet
    save_user(uid, u)
    return jsonify({'ok': True, 'wallet': wallet})

@app.route('/api/ref_stats', methods=['POST'])
def api_ref_stats():
    data = request.get_json() or {}
    uid = data.get('user_id')
    if not uid:
        return jsonify({'ok': False})
    u = get_user(uid)
    if not u:
        return jsonify({'ok': False})
    return jsonify({
        'ok': True,
        'referrals': int(u.get('referrals', 0)),
        'ref_earned': float(u.get('ref_earned', 0)),
        'referred_by': u.get('referred_by', '')
    })

# ============================================
# APIs الأدمن
# ============================================
@app.route('/api/admin/stats', methods=['POST'])
def api_admin_stats():
    data = request.get_json() or {}
    if str(data.get('admin_id')) != str(ADMIN_ID):
        return jsonify({'ok': False, 'error': 'unauthorized'})
    keys = redis_cmd('keys', 'user:*')
    if not keys:
        return jsonify({'ok': True, 'total_users': 0, 'active_users': 0, 'total_balance': 0, 'total_refs': 0})
    total_balance = 0
    total_refs = 0
    today = get_today()
    active = 0
    for k in keys:
        u = redis_cmd('hgetall', k)
        if not u:
            continue
        d = {}
        for i in range(0, len(u), 2):
            d[u[i]] = u[i+1]
        total_balance += float(d.get('balance', 0))
        total_refs += int(d.get('referrals', 0))
        if d.get('last_reset') == today:
            active += 1
    return jsonify({
        'ok': True,
        'total_users': len(keys),
        'active_users': active,
        'total_balance': round(total_balance, 2),
        'total_refs': total_refs
    })

@app.route('/api/admin/users', methods=['POST'])
def api_admin_users():
    data = request.get_json() or {}
    if str(data.get('admin_id')) != str(ADMIN_ID):
        return jsonify({'ok': False, 'error': 'unauthorized'})
    keys = redis_cmd('keys', 'user:*')
    users = []
    if keys:
        for k in keys[:100]:
            u = redis_cmd('hgetall', k)
            if not u:
                continue
            d = {}
            for i in range(0, len(u), 2):
                d[u[i]] = u[i+1]
            users.append({
                'user_id': d.get('user_id', ''),
                'first_name': d.get('first_name', ''),
                'username': d.get('username', ''),
                'balance': round(float(d.get('balance', 0)), 2),
                'level': int(d.get('level', 1)),
                'refs': int(d.get('referrals', 0)),
                'taps': int(d.get('taps', 0))
            })
    users.sort(key=lambda x: x['balance'], reverse=True)
    return jsonify({'ok': True, 'users': users})

@app.route('/api/admin/give', methods=['POST'])
def api_admin_give():
    data = request.get_json() or {}
    if str(data.get('admin_id')) != str(ADMIN_ID):
        return jsonify({'ok': False, 'error': 'unauthorized'})
    target = data.get('target_id')
    amount = float(data.get('amount', 0))
    if not target or amount == 0:
        return jsonify({'ok': False, 'error': 'missing'})
    u = get_user(target)
    if not u:
        return jsonify({'ok': False, 'error': 'user not found'})
    new_bal = float(u.get('balance', 0)) + amount
    u['balance'] = new_bal
    save_user(target, u)
    return jsonify({'ok': True, 'new_balance': round(new_bal, 4)})

@app.route('/api/admin/broadcast', methods=['POST'])
def api_admin_broadcast():
    data = request.get_json() or {}
    if str(data.get('admin_id')) != str(ADMIN_ID):
        return jsonify({'ok': False, 'error': 'unauthorized'})
    text = data.get('text', '')
    if not text:
        return jsonify({'ok': False, 'error': 'no text'})
    keys = redis_cmd('keys', 'user:*')
    sent = 0
    if keys:
        for k in keys:
            try:
                target = k.replace('user:', '')
                send_tg(int(target), '📢 ' + text)
                sent += 1
            except:
                pass
    return jsonify({'ok': True, 'sent': sent})

# ============================================
# APIs الفرق
# ============================================
@app.route('/api/clan/ranking', methods=['POST'])
def api_clan_ranking():
    keys = redis_cmd('keys', 'clan:*')
    clans = []
    if keys:
        for k in keys:
            c = redis_cmd('hgetall', k)
            if not c:
                continue
            d = {}
            for i in range(0, len(c), 2):
                d[c[i]] = c[i+1]
            clans.append({
                'name': d.get('name', ''),
                'code': d.get('code', ''),
                'members': int(d.get('members', 0)),
                'total': int(d.get('total_score', 0))
            })
    clans.sort(key=lambda x: x['total'], reverse=True)
    return jsonify({'ok': True, 'clans': clans[:20]})

# ============================================
# Telegram Webhook
# ============================================
@app.route('/api/webhook', methods=['POST'])
def api_webhook():
    try:
        data = request.get_json() or {}
        if 'message' not in data:
            return jsonify({'ok': True})
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
                except:
                    pass
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# ============================================
# التشغيل
# ============================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
