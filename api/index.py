# =====================================================================
#  MYTOKEN API v7.0 - Clean Rebuild
# =====================================================================
import os, json, urllib.request, urllib.parse
import time as _t
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CORS ---
@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return r

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def preflight(path): return ("", 204)

# --- Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
UPSTASH_TOK = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
ADMIN_ID = str(os.environ.get("ADMIN_ID", "8063963886"))
REFERRAL_REWARD = 100
TAP_REWARD = 0.001
AD_REWARD = 0.10
MIN_WITHDRAW = 1000

VIP_PLANS = {
    "bronze":  {"name": "Bronze",  "price": 0.5, "days": 7,    "mult": 2,  "icon": "B"},
    "silver":  {"name": "Silver",  "price": 1.0, "days": 30,   "mult": 3,  "icon": "S"},
    "gold":    {"name": "Gold",    "price": 2.0, "days": 90,   "mult": 5,  "icon": "G"},
    "diamond": {"name": "Diamond", "price": 5.0, "days": 3650, "mult": 10, "icon": "D"},
}

# --- Redis via pipeline (يعمل 100%) ---
def rpipe(commands):
    if not UPSTASH_URL or not UPSTASH_TOK or not commands:
        return []
    try:
        url = UPSTASH_URL + "/pipeline"
        payload = json.dumps([list(c) for c in commands]).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": "Bearer " + UPSTASH_TOK,
            "Content-Type": "application/json"
        }, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return [x.get("result") for x in json.loads(r.read().decode())]
    except Exception as e:
        print("[pipe]", e)
        return []

def rcmd(*args):
    r = rpipe([list(args)])
    return r[0] if r else None

# --- Helpers ---
def ukey(uid): return "user:" + str(uid)

def get_user(uid):
    h = rcmd("HGETALL", ukey(uid))
    if not h: return None
    if isinstance(h, list):
        return {h[i]: h[i+1] for i in range(0, len(h), 2)}
    if isinstance(h, dict):
        return h
    return None

def save_user(uid, fields):
    cmds = [("HSET", ukey(uid), k, str(v)) for k, v in fields.items()]
    cmds.append(("SADD", "users", str(uid)))
    rpipe(cmds)

def upd_user(uid, **fields):
    if not fields: return
    rpipe([("HSET", ukey(uid), k, str(v)) for k, v in fields.items()])

def n(v, d=0):
    try: return float(v if v is not None else d)
    except: return float(d)

def is_admin(b): return str(b.get("admin_id", "")) == ADMIN_ID
def ok(**kw): return jsonify({"ok": True, **kw})
def err(m, c=400): return jsonify({"ok": False, "error": m}), c
def today(): return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def send_tg(chat_id, text, kb=None):
    if not BOT_TOKEN: return
    try:
        url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
        p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if kb: p["reply_markup"] = kb
        req = urllib.request.Request(url, data=json.dumps(p).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("[tg]", e)

# --- Health ---
@app.route("/", methods=["GET"])
def home(): return ok(name="MYTOKEN API", version="7.0", status="online")

@app.route("/health", methods=["GET"])
def health(): return ok(redis=(rcmd("PING") == "PONG"))

@app.route("/api/debug", methods=["GET", "POST"])
def debug():
    users = rcmd("KEYS", "user:*") or []
    return ok(
        url=UPSTASH_URL[:35] if UPSTASH_URL else "MISSING",
        token=UPSTASH_TOK[:12] if UPSTASH_TOK else "MISSING",
        ping=rcmd("PING"),
        users_count=len(users)
    )

# --- User ---
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
    save_user(uid, {
        "user_id": uid, "first_name": fn, "username": un,
        "balance": 0, "pending": 0, "refs": 0, "ref_earned": 0,
        "streak": 0, "checkin_day": 0, "can_checkin": 1,
        "wallet": "", "ads": 0, "taps": 0, "level": 1,
        "vip_level": "", "vip_expires": 0,
        "created_at": str(int(_t.time())), "last_active": "now"
    })
    rd = False
    if ref:
        try: ref = str(int(ref))
        except: ref = None
        if ref and ref != uid and get_user(ref):
            rpipe([
                ("HINCRBY", ukey(ref), "refs", 1),
                ("HINCRBYFLOAT", ukey(ref), "balance", REFERRAL_REWARD),
                ("HINCRBYFLOAT", ukey(ref), "ref_earned", REFERRAL_REWARD),
                ("HSET", ukey(uid), "referred_by", ref)
            ])
            rd = True
            send_tg(int(ref), "🎉 <b>صديق جديد!</b>\n💰 +100 MYT\n👥 إحالاتك +1")
    return ok(exists=True, isNew=True, referral=rd)

@app.route("/api/user", methods=["GET", "POST"])
def h_user():
    body = request.get_json(silent=True) or {} if request.method == "POST" else request.args.to_dict()
    uid = body.get("id") or body.get("user_id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return ok(exists=False)
    upd_user(uid, last_active="now")
    return ok(
        exists=True, user_id=uid,
        first_name=u.get("first_name", "User"),
        balance=n(u.get("balance")),
        pending=n(u.get("pending")),
        refs=int(n(u.get("refs"))),
        checkinDay=int(n(u.get("checkin_day"))),
        wallet=u.get("wallet", ""),
        level=int(n(u.get("level"), 1)),
        vip_level=u.get("vip_level", ""),
        vip_expires=int(n(u.get("vip_expires")))
    )

@app.route("/api/wallet", methods=["POST"])
def h_wallet():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); w = str(body.get("wallet", "")).strip()
    if not uid: return err("Missing id")
    if not w: return err("Missing wallet")
    upd_user(str(int(uid)), wallet=w[:100])
    return ok(wallet=w)

# --- Mining ---
@app.route("/api/tap", methods=["POST"])
def h_tap():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    cnt = min(int(body.get("count", 0)), 500)
    if cnt <= 0: return err("Invalid count")
    u = get_user(uid)
    if not u: return ok(exists=False)
    reward = TAP_REWARD * cnt
    rpipe([("HINCRBY", ukey(uid), "taps", cnt),
           ("HINCRBYFLOAT", ukey(uid), "balance", reward)])
    u = get_user(uid)
    return ok(balance=n(u.get("balance")), taps=int(n(u.get("taps"))))

@app.route("/api/ad", methods=["POST"])
def h_ad():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return ok(exists=False)
    rpipe([("HINCRBY", ukey(uid), "ads", 1),
           ("HINCRBYFLOAT", ukey(uid), "balance", AD_REWARD),
           ("HINCRBYFLOAT", ukey(uid), "pending", AD_REWARD)])
    u = get_user(uid)
    return ok(balance=n(u.get("balance")), pending=n(u.get("pending")), ads=int(n(u.get("ads"))))

@app.route("/api/checkin", methods=["POST"])
def h_checkin():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return ok(exists=False)
    t = today()
    if u.get("last_checkin") == t: return err("Already checked in")
    day = int(n(u.get("checkin_day")))
    new_day = day + 1 if day < 7 else 1
    rewards = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 100.0]
    reward = rewards[new_day - 1]
    rpipe([("HINCRBYFLOAT", ukey(uid), "balance", reward),
           ("HSET", ukey(uid), "checkin_day", new_day),
           ("HSET", ukey(uid), "last_checkin", t)])
    u = get_user(uid)
    return ok(reward=reward, day=new_day, balance=n(u.get("balance")))

# --- Withdrawals ---
@app.route("/api/withdraw/request", methods=["POST"])
def h_wd_req():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); amt = body.get("amount")
    if not uid or amt is None: return err("Missing fields")
    try: uid = str(int(uid)); amt = float(amt)
    except: return err("Invalid data")
    u = get_user(uid)
    if not u: return err("User not found", 404)
    bal = n(u.get("balance")); wal = u.get("wallet", "")
    if not wal: return err("اربط محفظتك أولاً", 400)
    if amt < MIN_WITHDRAW: return err("الحد الأدنى 1,000 MYT", 400)
    if amt > bal: return err("رصيد غير كافٍ (" + str(round(bal, 2)) + " MYT)", 400)
    rid = "wd_" + uid + "_" + str(int(_t.time()))
    save_user("wd_" + rid, {
        "req_id": rid, "user_id": uid,
        "first_name": u.get("first_name", "User"),
        "amount": str(round(amt, 2)), "wallet": wal,
        "status": "pending", "created_at": str(int(_t.time()))
    })
    rpipe([("HINCRBYFLOAT", ukey(uid), "balance", -amt),
           ("HINCRBYFLOAT", ukey(uid), "pending", amt)])
    txt = ("طلب سحب جديد\n━━━━━━━━━━━━━━━━━━\n"
           "الاسم: " + u.get("first_name", "User") + "\n"
           "ID: " + uid + "\n"
           "المبلغ: " + str(round(amt, 2)) + " MYT")
    kb = {"inline_keyboard": [[
        {"text": "✅ موافقة", "callback_data": "wd_ok_" + rid},
        {"text": "❌ رفض", "callback_data": "wd_no_" + rid}
    ]]}
    send_tg(int(ADMIN_ID), txt, kb)
    return ok(message="Request sent", amount=amt, req_id=rid)

@app.route("/api/admin/withdrawals", methods=["POST"])
def h_wd_list():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    keys = rcmd("KEYS", "user:wd_wd_*") or []
    out = []
    for k in keys:
        u = get_user(k.replace("user:", ""))
        if u: out.append(u)
    out.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
    return ok(withdrawals=out, total=len(out))

# --- VIP ---
@app.route("/api/vip/plans", methods=["GET"])
def h_vip_plans(): return ok(plans=VIP_PLANS)

@app.route("/api/vip/my", methods=["POST"])
def h_vip_my():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return err("Missing id")
    u = get_user(str(int(uid)))
    if not u: return ok(exists=False)
    lvl = u.get("vip_level", ""); exp = int(n(u.get("vip_expires")))
    now = int(_t.time()); active = bool(lvl) and exp > now
    return ok(exists=True, vip_level=lvl if active else "",
              vip_expires=exp if active else 0, active=active)

@app.route("/api/vip/purchase", methods=["POST"])
def h_vip_req():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); plan = body.get("plan")
    if not uid or not plan: return err("Missing fields")
    if plan not in VIP_PLANS: return err("Invalid plan")
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return err("User not found", 404)
    rid = "vip_" + uid + "_" + str(int(_t.time()))
    p = VIP_PLANS[plan]
    save_user("vip_" + rid, {
        "req_id": rid, "user_id": uid,
        "first_name": u.get("first_name", "User"),
        "plan": plan, "plan_name": p["name"],
        "price": str(p["price"]),
        "status": "pending", "created_at": str(int(_t.time()))
    })
    txt = ("طلب VIP جديد\n━━━━━━━━━━━━━━━━━━\n"
           "الاسم: " + u.get("first_name", "User") + "\n"
           "ID: " + uid + "\n"
           "المستوى: " + p["name"] + "\n"
           "السعر: " + str(p["price"]) + " TON")
    kb = {"inline_keyboard": [[
        {"text": "✅ تفعيل", "callback_data": "vip_ok_" + rid},
        {"text": "❌ رفض", "callback_data": "vip_no_" + rid}
    ]]}
    send_tg(int(ADMIN_ID), txt, kb)
    return ok(req_id=rid, message="Request sent")

@app.route("/api/admin/vip/requests", methods=["POST"])
def h_vip_list():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    keys = rcmd("KEYS", "user:vip_vip_*") or []
    out = []
    for k in keys:
        u = get_user(k.replace("user:", ""))
        if u: out.append(u)
    out.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)
    return ok(requests=out, total=len(out))

@app.route("/api/admin/vip/activate", methods=["POST"])
def h_vip_ok():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    rid = body.get("req_id")
    if not rid: return err("Missing req_id")
    r = get_user("vip_" + rid)
    if not r: return err("Not found", 404)
    uid = r.get("user_id", ""); plan = r.get("plan", "")
    if plan not in VIP_PLANS: return err("Invalid plan")
    p = VIP_PLANS[plan]
    exp = int(_t.time()) + p["days"] * 86400
    upd_user(uid, vip_level=plan, vip_expires=exp)
    upd_user("vip_" + rid, status="approved")
    exp_s = _t.strftime("%Y-%m-%d", _t.gmtime(exp))
    send_tg(int(uid), "✅ VIP مفعّل!\nالمستوى: " + p["name"] + "\nالمضاعف: x" + str(p["mult"]) + "\nينتهي: " + exp_s)
    return ok(message="Activated")

@app.route("/api/admin/vip/reject", methods=["POST"])
def h_vip_no():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    rid = body.get("req_id")
    if not rid: return err("Missing req_id")
    r = get_user("vip_" + rid)
    if not r: return err("Not found", 404)
    uid = r.get("user_id", "")
    upd_user("vip_" + rid, status="rejected")
    send_tg(int(uid), "❌ تم رفض طلب VIP")
    return ok(message="Rejected")

# --- Admin ---
@app.route("/api/admin/stats", methods=["POST"])
def h_stats():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    keys = rcmd("KEYS", "user:*") or []
    real_users = [k for k in keys if not k.startswith("user:wd_") and not k.startswith("user:vip_") and not k.startswith("user:vipreq_")]
    tb = 0.0; tr = 0
    for k in real_users:
        u = get_user(k.replace("user:", ""))
        if u:
            tb += n(u.get("balance")); tr += int(n(u.get("refs")))
    return ok(total_users=len(real_users), total_balance=round(tb, 2), total_refs=tr)

@app.route("/api/admin/users", methods=["POST"])
def h_users():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    keys = rcmd("KEYS", "user:*") or []
    real_users = [k for k in keys if not k.startswith("user:wd_") and not k.startswith("user:vip_") and not k.startswith("user:vipreq_")]
    out = []
    for k in real_users[:300]:
        u = get_user(k.replace("user:", ""))
        if u:
            out.append({
                "user_id": u.get("user_id", ""),
                "first_name": u.get("first_name", ""),
                "balance": round(n(u.get("balance")), 2),
                "refs": int(n(u.get("refs"))),
                "wallet": u.get("wallet", "")
            })
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
    if amt < 0 and abs(amt) > cur:
        return err("رصيد غير كافٍ (" + str(round(cur, 2)) + " MYT)", 400)
    nb = cur + amt
    if nb < 0: nb = 0
    upd_user(uid, balance=nb)
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
    upd_user(uid, balance=nb)
    return ok(new_balance=nb)

@app.route("/api/admin/broadcast", methods=["POST"])
def h_bc():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    txt = str(body.get("text", "")).strip()
    if not txt: return err("No text")
    keys = rcmd("KEYS", "user:*") or []
    sent = 0
    for k in keys:
        if k.startswith("user:wd_") or k.startswith("user:vip_"): continue
        try:
            uid = int(k.replace("user:", ""))
            send_tg(uid, "📢 " + txt); sent += 1
        except: pass
    return ok(sent=sent)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
