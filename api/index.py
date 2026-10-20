import os, json
import time as _t
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__)

@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"] = "*"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return r

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def preflight(path): return ("", 204)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = str(os.environ.get("ADMIN_ID", "8063963886"))
MONGO_URI = os.environ.get("MONGO_URI", "")

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

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['mytoken_db']
    users_col = db['users']
    wd_col = db['withdrawals']
    vip_col = db['vip_requests']
except Exception as e:
    print("[MongoDB Error]", e)

def get_user(uid):
    u = users_col.find_one({"user_id": str(uid)})
    if u: del u['_id']
    return u

def save_user(uid, fields):
    fields["user_id"] = str(uid)
    users_col.insert_one(fields)

def upd_user(uid, **fields):
    users_col.update_one({"user_id": str(uid)}, {"$set": fields})

def n(v, d=0):
    try: return float(v if v is not None else d)
    except: return float(d)

def is_admin(b): return str(b.get("admin_id", "")) == ADMIN_ID
def ok(**kw): return jsonify({"ok": True, **kw})
def err(m, c=400): return jsonify({"ok": False, "error": m}), c

def send_tg(chat_id, text):
    if not BOT_TOKEN: return
    try:
        import urllib.request
        url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
        p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=json.dumps(p).encode(), headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except: pass

@app.route("/", methods=["GET"])
def home(): return ok(name="MYTOKEN API", version="8.0 Mongo", status="online")

@app.route("/health", methods=["GET"])
def health():
    try:
        users_col.find_one({})
        return ok(redis=True, db="mongodb")
    except: return ok(redis=False)

@app.route("/api/register", methods=["POST"])
def h_register():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    ref = body.get("ref")
    fn = str(body.get("first_name", "User")).strip()[:50]
    
    if get_user(uid): return ok(exists=True, isNew=False, referral=False)
    
    save_user(uid, {
        "first_name": fn, "balance": 0.0, "pending": 0.0, "refs": 0, "ref_earned": 0.0,
        "streak": 0, "checkin_day": 0, "wallet": "", "ads": 0, "taps": 0, "level": 1,
        "vip_level": "", "vip_expires": 0, "created_at": int(_t.time()), "last_active": "now"
    })
    
    rd = False
    if ref:
        try: ref = str(int(ref))
        except: ref = None
        if ref and ref != uid and get_user(ref):
            upd_user(ref, refs=int(n(get_user(ref).get("refs"))) + 1, balance=n(get_user(ref).get("balance")) + REFERRAL_REWARD)
            upd_user(uid, referred_by=ref)
            rd = True
            send_tg(int(ref), "🎉 <b>صديق جديد!</b>\n💰 +100 MYT\n👥 إحالاتك +1")
            
    return ok(exists=True, isNew=True, referral=rd)

@app.route("/api/user", methods=["POST"])
def h_user():
    body = request.get_json(silent=True) or {}
    uid = body.get("id")
    if not uid: return err("Missing id")
    uid = str(int(uid))
    u = get_user(uid)
    if not u: return ok(exists=False)
    upd_user(uid, last_active="now")
    return ok(exists=True, user_id=uid, first_name=u.get("first_name", "User"), balance=n(u.get("balance")), pending=n(u.get("pending")), refs=int(n(u.get("refs"))), checkinDay=int(n(u.get("checkin_day"))), wallet=u.get("wallet", ""), level=int(n(u.get("level"), 1)), vip_level=u.get("vip_level", ""), vip_expires=int(n(u.get("vip_expires"))))

@app.route("/api/wallet", methods=["POST"])
def h_wallet():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); w = str(body.get("wallet", "")).strip()
    if not uid or not w: return err("Missing fields")
    upd_user(str(int(uid)), wallet=w[:100])
    return ok(wallet=w)

@app.route("/api/withdraw/request", methods=["POST"])
def h_wd_req():
    body = request.get_json(silent=True) or {}
    uid = body.get("id"); amt = body.get("amount")
    if not uid or amt is None: return err("Missing fields")
    uid = str(int(uid)); amt = float(amt)
    u = get_user(uid)
    if not u: return err("User not found", 404)
    bal = n(u.get("balance")); wal = u.get("wallet", "")
    if not wal: return err("اربط محفظتك أولاً", 400)
    if amt < MIN_WITHDRAW: return err("الحد الأدنى 1,000 MYT", 400)
    if amt > bal: return err("رصيد غير كافٍ", 400)
    
    rid = "wd_" + uid + "_" + str(int(_t.time()))
    wd_col.insert_one({"req_id": rid, "user_id": uid, "first_name": u.get("first_name"), "amount": str(round(amt, 2)), "wallet": wal, "status": "pending", "created_at": int(_t.time())})
    upd_user(uid, balance=bal - amt, pending=n(u.get("pending")) + amt)
    send_tg(int(ADMIN_ID), f"طلب سحب جديد\nالاسم: {u.get('first_name')}\nID: {uid}\nالمبلغ: {amt} MYT")
    return ok(message="Request sent", amount=amt)

@app.route("/api/admin/stats", methods=["POST"])
def h_stats():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    total_users = users_col.count_documents({})
    total_bal = 0.0
    for u in users_col.find({}, {"balance": 1}): total_bal += n(u.get("balance"))
    return ok(total_users=total_users, total_balance=round(total_bal, 2))

@app.route("/api/admin/users", methods=["POST"])
def h_users():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    users = []
    for u in users_col.find({}).sort("balance", -1).limit(300):
        users.append({"user_id": u.get("user_id", ""), "first_name": u.get("first_name", ""), "balance": round(n(u.get("balance")), 2), "refs": int(n(u.get("refs"))), "wallet": u.get("wallet", "")})
    return ok(users=users, total=len(users))

@app.route("/api/admin/give", methods=["POST"])
def h_give():
    body = request.get_json(silent=True) or {}
    if not is_admin(body): return err("Unauthorized", 403)
    uid = str(int(body.get("target_id", 0)))
    amt = float(body.get("amount", 0))
    u = get_user(uid)
    if not u: return err("User not found", 404)
    cur = n(u.get("balance"))
    if amt < 0 and abs(amt) > cur: return err("رصيد غير كافٍ", 400)
    nb = max(0, cur + amt)
    upd_user(uid, balance=nb)
    return ok(new_balance=round(nb, 4))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
