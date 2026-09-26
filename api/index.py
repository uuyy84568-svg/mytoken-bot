import json, os, urllib.request, urllib.parse
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
ADMIN_ID = str(os.environ.get("ADMIN_ID", "8063963886"))

def redis_cmd(*args):
    if not UPSTASH_URL or not UPSTASH_TOKEN: return None
    try:
        url = UPSTASH_URL.rstrip("/") + "/" + "/".join(urllib.parse.quote(str(a), safe="") for a in args)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + UPSTASH_TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()).get("result")
    except Exception as e:
        print("[Redis]", e); return None

def redis_pipe(cmds):
    if not UPSTASH_URL or not UPSTASH_TOKEN: return []
    try:
        url = UPSTASH_URL.rstrip("/") + "/pipeline"
        data = json.dumps([list(c) for c in cmds]).encode()
        req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer " + UPSTASH_TOKEN, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return [x.get("result") for x in json.loads(r.read().decode())]
    except Exception as e:
        print("[Pipe]", e); return []

def ukey(uid): return "user:" + str(uid)

def get_user(uid):
    h = redis_cmd("HGETALL", ukey(uid))
    if not h: return None
    d = {}
    if isinstance(h, list):
        for i in range(0, len(h), 2): d[h[i]] = h[i+1]
    elif isinstance(h, dict): d = h
    return d

def save_user(uid, fields):
    cmds = [("HSET", ukey(uid), k, str(v)) for k, v in fields.items()]
    cmds.append(("SADD", "users", str(uid)))
    redis_pipe(cmds)

def send_tg(chat_id, text):
    if not BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("[TG]", e)

def n(v, d=0):
    try: return float(v or d)
    except: return d

# ============ ROUTES ============

@app.route("/")
def home():
    return jsonify({"ok": True, "name": "MYTOKEN API", "status": "online"})

@app.route("/api/register", methods=["GET", "POST"])
def h_register():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
    else:
        body = request.args.to_dict()
    uid = body.get("id") or body.get("user_id")
    if not uid: return jsonify({"ok": False, "error": "Missing id"}), 400
    uid = str(int(uid))
    ref = body.get("ref")
    first_name = body.get("first_name", "User")

    if get_user(uid):
        return jsonify({"ok": True, "exists": True, "isNew": False})

    save_user(uid, {
        "telegram_id": uid, "user_id": uid, "first_name": first_name,
        "balance": 0, "pending": 0, "refs": 0, "streak": 0,
        "checkin_day": 0, "can_checkin": 1, "wallet": "",
        "ads": 0, "taps": 0, "level": 1,
        "created_at": "now", "last_active": "now"
    })

    referral_done = False
    if ref:
        ref = str(int(ref))
        if ref != uid and get_user(ref):
            redis_pipe([
                ("HINCRBY", ukey(ref), "refs", 1),
                ("HINCRBYFLOAT", ukey(ref), "balance", 100),
                ("HSET", ukey(uid), "referred_by", ref)
            ])
            referral_done = True
            try:
                send_tg(int(ref), f"🎉 <b>صديق جديد انضم عبر رابطك!</b>\n💰 +100 MYT\n👥 إحالاتك +1")
            except: pass

    return jsonify({"ok": True, "exists": True, "isNew": True, "referral": referral_done})

@app.route("/api/user", methods=["GET", "POST"])
def h_user():
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
    else:
        body = request.args.to_dict()
    uid = body.get("id") or body.get("user_id")
    if not uid: return jsonify({"ok": False, "error": "Missing id"}), 400
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return jsonify({"ok": True, "exists": False})
    redis_cmd("HSET", ukey(uid), "last_active", "now")
    return jsonify({
        "ok": True, "exists": True,
        "balance": n(u.get("balance")), "pending": n(u.get("pending")),
        "refs": n(u.get("refs")), "streak": n(u.get("streak")),
        "checkinDay": n(u.get("checkin_day")), "canCheckin": u.get("can_checkin", "1") == "1",
        "achievements": [], "wallet": u.get("wallet", ""),
        "ads": n(u.get("ads")), "taps": n(u.get("taps")),
        "clicks": n(u.get("taps")), "level": n(u.get("level"), 1),
        "first_name": u.get("first_name", "User")
    })

@app.route("/api/tap", methods=["POST"])
def h_tap():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return jsonify({"ok": False, "error": "Missing id"}), 400
    uid = str(int(uid))
    cnt = min(int(body.get("count", 0)), 500)
    if cnt <= 0: return jsonify({"ok": False, "error": "Invalid count"}), 400
    if not get_user(uid): return jsonify({"ok": True, "exists": False})
    reward = 0.001 * cnt
    redis_pipe([
        ("HINCRBY", ukey(uid), "taps", cnt),
        ("HINCRBYFLOAT", ukey(uid), "balance", reward),
        ("HSET", ukey(uid), "last_active", "now")
    ])
    u = get_user(uid)
    return jsonify({"ok": True, "balance": n(u.get("balance")), "taps": n(u.get("taps")), "added": cnt})

@app.route("/api/ad", methods=["POST"])
def h_ad():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return jsonify({"ok": False, "error": "Missing id"}), 400
    uid = str(int(uid))
    if not get_user(uid): return jsonify({"ok": True, "exists": False})
    reward = 0.10
    redis_pipe([
        ("HINCRBY", ukey(uid), "ads", 1),
        ("HINCRBYFLOAT", ukey(uid), "balance", reward),
        ("HINCRBYFLOAT", ukey(uid), "pending", reward),
        ("HSET", ukey(uid), "last_active", "now")
    ])
    u = get_user(uid)
    return jsonify({"ok": True, "balance": n(u.get("balance")), "pending": n(u.get("pending")), "ads": n(u.get("ads"))})

@app.route("/api/checkin", methods=["POST"])
def h_checkin():
    body = request.get_json(silent=True) or {}
    uid = body.get("id") or body.get("user_id")
    if not uid: return jsonify({"ok": False, "error": "Missing id"}), 400
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return jsonify({"ok": False, "error": "not found"})
    day = int(u.get("checkin_day", 0))
    rewards = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0]
    new_day = day + 1 if day < 7 else 1
    reward = rewards[new_day - 1]
    redis_pipe([
        ("HINCRBYFLOAT", ukey(uid), "balance", reward),
        ("HSET", ukey(uid), "checkin_day", new_day),
        ("HSET", ukey(uid), "last_checkin", "now")
    ])
    return jsonify({"ok": True, "reward": reward, "day": new_day, "balance": n(u.get("balance")) + reward})

@app.route("/api/wallet", methods=["POST"])
def h_wallet():
    body = request.get_json(silent=True) or {}
    uid = body.get("id") or body.get("user_id")
    wallet = body.get("wallet", "").strip()
    if not uid: return jsonify({"ok": False, "error": "Missing id"}), 400
    redis_cmd("HSET", ukey(str(int(uid))), "wallet", wallet)
    return jsonify({"ok": True, "wallet": wallet})

@app.route("/api/admin/stats", methods=["POST"])
def h_admin_stats():
    body = request.get_json(silent=True) or {}
    if str(body.get("admin_id")) != ADMIN_ID: return jsonify({"ok": False, "error": "unauthorized"}), 403
    keys = redis_cmd("keys", "user:*") or []
    total_balance = 0; total_refs = 0
    for k in keys:
        u = redis_cmd("hgetall", k)
        if not u: continue
        d = {}
        for i in range(0, len(u), 2): d[u[i]] = u[i+1]
        total_balance += n(d.get("balance"))
        total_refs += int(n(d.get("refs")))
    return jsonify({"ok": True, "total_users": len(keys), "active_users": len(keys), "total_balance": round(total_balance, 2), "total_refs": total_refs})

@app.route("/api/admin/users", methods=["POST"])
def h_admin_users():
    body = request.get_json(silent=True) or {}
    if str(body.get("admin_id")) != ADMIN_ID: return jsonify({"ok": False, "error": "unauthorized"}), 403
    keys = redis_cmd("keys", "user:*") or []
    users = []
    for k in keys[:200]:
        u = redis_cmd("hgetall", k)
        if not u: continue
        d = {}
        for i in range(0, len(u), 2): d[u[i]] = u[i+1]
        users.append({
            "user_id": d.get("user_id", ""), "first_name": d.get("first_name", ""),
            "balance": n(d.get("balance")), "level": int(n(d.get("level"), 1)),
            "refs": int(n(d.get("refs"))), "taps": int(n(d.get("taps")))
        })
    users.sort(key=lambda x: x["balance"], reverse=True)
    return jsonify({"ok": True, "users": users})

@app.route("/api/admin/give", methods=["POST"])
def h_admin_give():
    body = request.get_json(silent=True) or {}
    if str(body.get("admin_id")) != ADMIN_ID: return jsonify({"ok": False, "error": "unauthorized"}), 403
    target = body.get("target_id"); amount = float(body.get("amount", 0))
    if not target or amount == 0: return jsonify({"ok": False, "error": "missing"})
    u = get_user(str(int(target)))
    if not u: return jsonify({"ok": False, "error": "user not found"})
    new_bal = n(u.get("balance")) + amount
    redis_cmd("HSET", ukey(str(int(target))), "balance", str(new_bal))
    return jsonify({"ok": True, "new_balance": round(new_bal, 4)})

@app.route("/api/admin/broadcast", methods=["POST"])
def h_admin_broadcast():
    body = request.get_json(silent=True) or {}
    if str(body.get("admin_id")) != ADMIN_ID: return jsonify({"ok": False, "error": "unauthorized"}), 403
    text = body.get("text", "")
    if not text: return jsonify({"ok": False, "error": "no text"})
    keys = redis_cmd("keys", "user:*") or []
    sent = 0
    for k in keys:
        try:
            send_tg(int(k.replace("user:", "")), text)
            sent += 1
        except: pass
    return jsonify({"ok": True, "sent": sent})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
