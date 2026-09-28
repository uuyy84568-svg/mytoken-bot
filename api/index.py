# MYTOKEN API v5.0
import os, json, urllib.request, urllib.parse
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def preflight(path): return ("", 204)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOK = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
ADMIN_ID = str(os.environ.get("ADMIN_ID", "8063963886"))
REFERRAL_REWARD = 100
TAP_REWARD = 0.001
AD_REWARD = 0.10
MIN_WITHDRAW = 1000

def redis_cmd(*args):
    if not UPSTASH_URL or not UPSTASH_TOK: return None
    try:
        encoded = "/".join(urllib.parse.quote(str(a), safe="") for a in args)
        url = UPSTASH_URL + "/" + encoded
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + UPSTASH_TOK}, method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()).get("result")
    except Exception as e:
        print("[Redis]", e); return None

def redis_pipe(commands):
    if not UPSTASH_URL or not UPSTASH_TOK or not commands: return []
    try:
        url = UPSTASH_URL + "/pipeline"
        payload = json.dumps([list(c) for c in commands]).encode()
        req = urllib.request.Request(url, data=payload, headers={"Authorization": "Bearer " + UPSTASH_TOK, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return [x.get("result") for x in json.loads(r.read().decode())]
    except Exception as e:
        print("[Pipe]", e); return []

def ukey(uid): return "user:" + str(uid)

def get_user(uid):
    h = redis_cmd("HGETALL", ukey(uid))
    if not h: return None
    if isinstance(h, list): return {h[i]: h[i+1] for i in range(0, len(h), 2)}
    if isinstance(h, dict): return h
    return None

def save_user(uid, fields):
    cmds = [("HSET", ukey(uid), k, str(v)) for k, v in fields.items()]
    cmds.append(("SADD", "users", str(uid)))
    redis_pipe(cmds)

def update_user(uid, **fields):
    if not fields: return
    cmds = [("HSET", ukey(uid), k, str(v)) for k, v in fields.items()]
    redis_pipe(cmds)

def send_tg(chat_id, text, kb=None):
    if not BOT_TOKEN: return
    try:
        url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
        p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        if kb: p["reply_markup"] = kb
        data = json.dumps(p).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("[TG]", e)

def n(v, d=0):
    try: return float(v if v is not None else d)
    except: return float(d)

def is_admin(b): return str(b.get("admin_id", "")) == ADMIN_ID
def ok(**kw): return jsonify({"ok": True, **kw})
def err(m, c=400): return jsonify({"ok": False, "error": m}), c

@app.route("/", methods=["GET"])
def home(): return ok(name="MYTOKEN API", version="5.0.0", status="online")

@app.route("/health", methods=["GET"])
def health():
    try:
        p = redis_cmd("PING")
        return ok(redis=(p == "PONG"), uptime="ok")
    except Exception as e: return err(str(e), 500)

@app.route("/api/register", methods=["GET", "POST"])
def h_register():
    body = request.get_json(silent=True) or {} if request.method == "POST" else request.args.to_dict()
    uid = body.get("id") or body.get("user_id")
    if not uid: return err("Missing id")
    try: uid = str(int(uid))
    except: return err("Invalid id")
    ref = body.get("ref")
    fn = str(body.get("first_name", "User")).strip()[:50]
    un = str(body.get("username", "")).strip()[:50]
    if get_user(uid): return ok(exists=True, isNew=False, referral=False)
    save_user(uid, {"telegram_id": uid, "user_id": uid, "first_name": fn, "username": un, "balance": 0, "pending": 0, "refs": 0, "ref_earned": 0, "streak": 0, "checkin_day": 0, "can_checkin": 1, "wallet": "", "ads": 0, "taps": 0, "level": 1, "created_at": "now", "last_active": "now"})
    rd = False
    if ref:
        try: ref = str(int(ref))
        except: ref = None
        if ref and ref != uid and get_user(ref):
            redis_pipe([("HINCRBY", ukey(ref), "refs", 1), ("HINCRBYFLOAT", ukey(ref), "balance", REFERRAL_REWARD), ("HINCRBYFLOAT", ukey(ref), "ref_earned", REFERRAL_REWARD), ("HSET", ukey(uid), "referred_by", ref)])
            rd = True
            send_tg(int(ref), "🎉 <b>صديق جديد انضم!</b>\n💰 +100 MYT\n👥 إحالاتك +1")
    return ok(exists=True, isNew=True, referral=rd)

@app.route("/api/user", methods=["GET", "POST"])
def h_user():
    body = request.get_json(silent=True) or {} if request.method == "POST" else request.args.to_dict()
    uid = body.get("id") or body.get("user_id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return ok(exists=False)
    update_user(uid, last_active="now")
    return ok(exists=True, user_id=uid, first_name=u.get("first_name", "User"), balance=n(u.get("balance")), pending=n(u.get("pending")), refs=int(n(u.get("refs"))), checkinDay=int(n(u.get("checkin_day"))), wallet=u.get("wallet", ""), level=int(n(u.get("level"), 1)))

@app.route("/api/wallet", methods=["POST"])
def h_wallet():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); w = str(body.get("wallet", "")).strip()
    if not uid: return err("Missing id")
    if not w: return err("Missing wallet")
    update_user(str(int(uid)), wallet=w[:100])
    return ok(wallet=w)

@app.route("/api/withdraw/request", methods=["POST"])
def h_withdraw_request():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); amount = body.get("amount")
    if not uid or amount is None: return err("Missing fields")
    try:
        uid = str(int(uid)); amount = float(amount)
    except: return err("Invalid data")
    u = get_user(uid)
    if not u: return err("User not found", 404)
    bal = n(u.get("balance")); wallet = u.get("wallet", ""); fn = u.get("first_name", "User")
    if not wallet: return err("اربط محفظتك أولاً", 400)
    if amount < MIN_WITHDRAW: return err("الحد الأدنى " + str(MIN_WITHDRAW) + " MYT", 400)
    if amount > bal: return err("رصيد غير كافٍ (المتاح: " + str(round(bal, 2)) + " MYT)", 400)
    import time as _t
    req_id = uid + "_" + str(int(_t.time()))
    redis_pipe([
        ("HINCRBYFLOAT", ukey(uid), "balance", -amount),
        ("HINCRBYFLOAT", ukey(uid), "pending", amount),
        ("HSET", "withdrawal:" + req_id, "req_id", req_id),
        ("HSET", "withdrawal:" + req_id, "user_id", uid),
        ("HSET", "withdrawal:" + req_id, "first_name", fn),
        ("HSET", "withdrawal:" + req_id, "amount", str(round(amount, 2))),
        ("HSET", "withdrawal:" + req_id, "wallet", wallet),
        ("HSET", "withdrawal:" + req_id, "status", "pending"),
        ("HSET", "withdrawal:" + req_id, "created_at", str(int(_t.time()))),
        ("SADD", "withdrawals", req_id)
    ])
    txt = "🔔 <b>طلب سحب جديد</b>\n━━━━━━━━━━━━━━━━━━\n👤 " + fn + "\n🆔 <code>" + uid + "</code>\n💰 <b>" + str(round(amount, 2)) + " MYT</b>\n👛 <code>" + wallet[:10] + "..." + wallet[-6:] + "</code>"
    kb = {"inline_keyboard": [[{"text": "✅ موافقة", "callback_data": "wd_ok_" + uid + "_" + str(amount)}, {"text": "❌ رفض", "callback_data": "wd_no_" + uid + "_" + str(amount)}]]}
    send_tg(int(ADMIN_ID), txt, kb)
    return ok(message="تم إرسال الطلب", amount=amount)

@app.route("/api/admin/stats", methods=["POST"])
def h_stats():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    keys = redis_cmd("KEYS", "user:*") or []
    tb = 0.0; tr = 0
    for k in keys:
        u = redis_cmd("HGETALL", k)
        if not u: continue
        d = {u[i]: u[i+1] for i in range(0, len(u), 2)} if isinstance(u, list) else u
        tb += n(d.get("balance")); tr += int(n(d.get("refs")))
    return ok(total_users=len(keys), total_balance=round(tb, 2), total_refs=tr)

@app.route("/api/admin/users", methods=["POST"])
def h_users():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    keys = redis_cmd("KEYS", "user:*") or []
    out = []
    for k in keys[:300]:
        u = redis_cmd("HGETALL", k)
        if not u: continue
        d = {u[i]: u[i+1] for i in range(0, len(u), 2)} if isinstance(u, list) else u
        out.append({"user_id": d.get("user_id", ""), "first_name": d.get("first_name", ""), "balance": round(n(d.get("balance")), 2), "refs": int(n(d.get("refs"))), "wallet": d.get("wallet", "")})
    out.sort(key=lambda x: x["balance"], reverse=True)
    return ok(users=out, total=len(out))

@app.route("/api/admin/give", methods=["POST"])
def h_give():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    t = body.get("target_id")
    if not t: return err("Missing target_id")
    try: amt = float(body.get("amount", 0))
    except: return err("Invalid amount")
    if amt == 0: return err("Amount zero")
    uid = str(int(t)); u = get_user(uid)
    if not u: return err("User not found", 404)
    cur = n(u.get("balance"))
    if amt < 0 and abs(amt) > cur: return err("رصيد غير كافٍ (المتاح: " + str(round(cur, 2)) + " MYT)", 400)
    nb = cur + amt
    if nb < 0: nb = 0
    update_user(uid, balance=nb)
    return ok(new_balance=round(nb, 4))

@app.route("/api/admin/set", methods=["POST"])
def h_set():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    t = body.get("target_id")
    if not t: return err("Missing target_id")
    uid = str(int(t))
    if not get_user(uid): return err("User not found", 404)
    try: nb = float(body.get("balance", 0))
    except: return err("Invalid balance")
    if nb < 0: nb = 0
    update_user(uid, balance=nb)
    return ok(new_balance=nb)



@app.route("/api/admin/withdrawals", methods=["POST"])
def h_admin_withdrawals():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    ids = redis_cmd("SMEMBERS", "withdrawals") or []
    out = []
    for rid in ids:
        w = redis_cmd("HGETALL", "withdrawal:" + rid)
        if not w: continue
        d = {w[i]: w[i+1] for i in range(0, len(w), 2)} if isinstance(w, list) else w
        out.append(d)
    out.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
    return ok(withdrawals=out, total=len(out))


@app.route("/api/admin/withdrawal/approve", methods=["POST"])
def h_wd_approve():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    rid = body.get("req_id")
    if not rid: return err("Missing req_id")
    w = redis_cmd("HGETALL", "withdrawal:" + rid)
    if not w: return err("Request not found", 404)
    d = {w[i]: w[i+1] for i in range(0, len(w), 2)} if isinstance(w, list) else w
    uid = d.get("user_id", "")
    amt = float(d.get("amount", 0))
    redis_pipe([
        ("HSET", "withdrawal:" + rid, "status", "approved"),
        ("HINCRBYFLOAT", ukey(uid), "pending", -amt)
    ])
    send_tg(int(uid), "✅ <b>تمت الموافقة على سحبك</b>\n💰 " + str(round(amt, 2)) + " MYT")
    return ok(message="Approved")

@app.route("/api/admin/withdrawal/reject", methods=["POST"])
def h_wd_reject():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    rid = body.get("req_id")
    if not rid: return err("Missing req_id")
    w = redis_cmd("HGETALL", "withdrawal:" + rid)
    if not w: return err("Request not found", 404)
    d = {w[i]: w[i+1] for i in range(0, len(w), 2)} if isinstance(w, list) else w
    uid = d.get("user_id", "")
    amt = float(d.get("amount", 0))
    redis_pipe([
        ("HSET", "withdrawal:" + rid, "status", "rejected"),
        ("HINCRBYFLOAT", ukey(uid), "pending", -amt),
        ("HINCRBYFLOAT", ukey(uid), "balance", amt)
    ])
    send_tg(int(uid), "❌ <b>تم رفض طلب السحب</b>\nتم إرجاع رصيدك.")
    return ok(message="Rejected")



@app.route("/api/admin/withdrawals", methods=["POST"])
def h_admin_wd():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    ids = redis_cmd("SMEMBERS", "withdrawals") or []
    out = []
    for rid in ids:
        w = redis_cmd("HGETALL", "withdrawal:" + rid)
        if not w: continue
        d = {w[i]: w[i+1] for i in range(0, len(w), 2)} if isinstance(w, list) else w
        out.append(d)
    out.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
    return ok(withdrawals=out, total=len(out))

@app.route("/api/admin/withdrawal/approve", methods=["POST"])
def h_wd_ok():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    rid = body.get("req_id")
    if not rid: return err("Missing req_id")
    w = redis_cmd("HGETALL", "withdrawal:" + rid)
    if not w: return err("Not found", 404)
    d = {w[i]: w[i+1] for i in range(0, len(w), 2)} if isinstance(w, list) else w
    u = d.get("user_id", "")
    a = float(d.get("amount", 0))
    redis_pipe([
        ("HSET", "withdrawal:" + rid, "status", "approved"),
        ("HINCRBYFLOAT", ukey(u), "pending", -a)
    ])
    send_tg(int(u), "✅ تمت الموافقة على سحبك\n💰 " + str(round(a, 2)) + " MYT")
    return ok(message="Approved")

@app.route("/api/admin/withdrawal/reject", methods=["POST"])
def h_wd_no():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    rid = body.get("req_id")
    if not rid: return err("Missing req_id")
    w = redis_cmd("HGETALL", "withdrawal:" + rid)
    if not w: return err("Not found", 404)
    d = {w[i]: w[i+1] for i in range(0, len(w), 2)} if isinstance(w, list) else w
    u = d.get("user_id", "")
    a = float(d.get("amount", 0))
    redis_pipe([
        ("HSET", "withdrawal:" + rid, "status", "rejected"),
        ("HINCRBYFLOAT", ukey(u), "pending", -a),
        ("HINCRBYFLOAT", ukey(u), "balance", a)
    ])
    send_tg(int(u), "❌ تم رفض طلب السحب. تم إرجاع رصيدك.")
    return ok(message="Rejected")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
