from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os
import json
import time
import urllib.request
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app) # للسماح للواجهة بالاتصال

# --- الإعدادات الأساسية ---
MONGO_URI = os.environ.get("MONGO_URI")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = "8063963886"

# --- الاتصال بقاعدة البيانات ---
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.get_database("mytoken_db")
    users_col = db.get_collection("users")
    wd_col = db.get_collection("withdrawals")
    vip_col = db.get_collection("vip_requests")
except Exception as e:
    print(f"DB Error: {e}")

# --- دوال مساعدة ---
def is_admin(body):
    return str(body.get("admin_id", "")) == ADMIN_ID

def send_tg(chat_id, text):
    if not BOT_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=json.dumps(p).encode(), headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"TG Send Error: {e}")

def n(val, default=0.0):
    try: return float(val if val is not None else default)
    except: return float(default)

# --- المسارات (Endpoints) ---

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "success", "db": "mongodb"}), 200

@app.route('/api/user/register', methods=['POST'])
def register():
    try:
        data = request.json
        user_id = str(data.get("id"))
        ref = data.get("ref")
        first_name = data.get("first_name", "User")

        user = users_col.find_one({"telegram_id": user_id})
        if user:
            return jsonify({"exists": True, "isNew": False}), 200

        # إنشاء مستخدم جديد
        new_user = {
            "telegram_id": user_id,
            "first_name": first_name,
            "balance": 0.0,
            "refs": 0,
            "wallet": "",
            "is_verified": False,
            "vip_level": 0,
            "vip_expires": 0,
            "ads_watched": 0,
            "last_checkin": 0,
            "created_at": int(time.time())
        }
        users_col.insert_one(new_user)

        # معالجة الإحالة
        if ref and str(ref) != user_id:
            ref_user = users_col.find_one({"telegram_id": str(ref)})
            if ref_user:
                users_col.update_one(
                    {"telegram_id": str(ref)},
                    {"$inc": {"balance": 100, "refs": 1}} # مكافأة 100 عملة للمحيل
                )
                users_col.update_one({"telegram_id": user_id}, {"$set": {"referred_by": str(ref)}})
                send_tg(ref, f"🎉 انضم صديق جديد عبر رابطك!\n+100 MYT")

        return jsonify({"exists": True, "isNew": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user', methods=['POST'])
def get_user():
    try:
        data = request.json
        user_id = str(data.get("id"))
        user = users_col.find_one({"telegram_id": user_id})
        if user:
            user['_id'] = str(user['_id'])
            return jsonify({"exists": True, "user": user}), 200
        return jsonify({"exists": False}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/update', methods=['POST'])
def update_user():
    try:
        data = request.json
        user_id = str(data.get("telegram_id"))
        if "telegram_id" in data: del data["telegram_id"]
        users_col.update_one({"telegram_id": user_id}, {"$set": data})
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/withdraw/request', methods=['POST'])
def withdraw_request():
    try:
        data = request.json
        user_id = str(data.get("id"))
        amount = float(data.get("amount", 0))

        user = users_col.find_one({"telegram_id": user_id})
        if not user: return jsonify({"error": "User not found"}), 404
        
        balance = n(user.get("balance"))
        wallet = user.get("wallet", "")

        if not wallet: return jsonify({"error": "اربط محفظتك أولاً"}), 400
        if amount < 1000: return jsonify({"error": "الحد الأدنى 1000 MYT"}), 400
        if amount > balance: return jsonify({"error": "رصيد غير كافٍ"}), 400

        # العمولات
        platform_fee = round(amount * 0.02, 2)
        network_fee = 50.0
        net_amount = amount - platform_fee - network_fee

        if net_amount <= 0: return jsonify({"error": "المبلغ لا يغطي الرسوم"}), 400

        req_id = f"wd_{user_id}_{int(time.time())}"
        
        # حفظ الطلب
        wd_col.insert_one({
            "req_id": req_id,
            "user_id": user_id,
            "first_name": user.get("first_name"),
            "requested": amount,
            "net_amount": net_amount,
            "wallet": wallet,
            "status": "pending",
            "created_at": int(time.time())
        })

        # خصم الرصيد وتحويله للمعلق
        users_col.update_one({"telegram_id": user_id}, {"$inc": {"balance": -amount}})

        # إشعار الأدمن
        send_tg(ADMIN_ID, f"💸 طلب سحب جديد\n👤 {user.get('first_name')}\n💰 {amount} MYT\n🪙 الصافي: {net_amount} MYT")
        
        return jsonify({"ok": True, "message": "Request sent", "net_amount": net_amount}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vip/purchase', methods=['POST'])
def vip_purchase():
    try:
        data = request.json
        user_id = str(data.get("id"))
        plan = data.get("plan") # bronze, silver, gold
        
        prices = {"bronze": 5000, "silver": 20000, "gold": 50000}
        if plan not in prices: return jsonify({"error": "Invalid plan"}), 400

        user = users_col.find_one({"telegram_id": user_id})
        if n(user.get("balance")) < prices[plan]:
            return jsonify({"error": "رصيدك غير كافٍ لشراء VIP"}), 400

        # خصم الرصيد وتفعيل VIP
        users_col.update_one({"telegram_id": user_id}, {
            "$inc": {"balance": -prices[plan]},
            "$set": {"vip_level": plan, "vip_expires": int(time.time()) + (30 * 86400)}
        })
        
        send_tg(ADMIN_ID, f"👑 شراء VIP جديد\n👤 {user.get('first_name')}\nالمستوى: {plan}")
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/task/claim_ad', methods=['POST'])
def claim_ad():
    try:
        data = request.json
        user_id = str(data.get("id"))
        
        user = users_col.find_one({"telegram_id": user_id})
        if not user: return jsonify({"error": "User not found"}), 404

        # إضافة 0.10 عملة لكل إعلان
        users_col.update_one({"telegram_id": user_id}, {
            "$inc": {"balance": 0.10, "ads_watched": 1}
        })
        return jsonify({"ok": True, "reward": 0.10}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- مسارات الأدمن (Admin Endpoints) ---

@app.route('/api/admin/stats', methods=['POST'])
def stats():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    
    total_users = users_col.count_documents({})
    total_bal = 0
    for u in users_col.find({}, {"balance": 1}): total_bal += n(u.get("balance"))
    
    return jsonify({
        "ok": True, 
        "total_users": total_users, 
        "total_balance": total_bal, 
        "pending_withdrawals": wd_col.count_documents({"status": "pending"}),
        "verified_users": users_col.count_documents({"is_verified": True})
    }), 200

@app.route('/api/admin/withdrawals', methods=['POST'])
def wd_list():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    out = list(wd_col.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1))
    return jsonify({"ok": True, "withdrawals": out}), 200

@app.route('/api/admin/withdraw/approve', methods=['POST'])
def wd_approve():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    req_id = body.get("req_id")
    wd = wd_col.find_one({"req_id": req_id})
    if wd:
        wd_col.update_one({"req_id": req_id}, {"$set": {"status": "approved"}})
        send_tg(wd["user_id"], f"✅ تمت الموافقة على طلب السحب الخاص بك!\nالصافي: {wd['net_amount']} MYT")
    return jsonify({"ok": True}), 200

@app.route('/api/admin/withdraw/reject', methods=['POST'])
def wd_reject():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    req_id = body.get("req_id")
    wd = wd_col.find_one({"req_id": req_id})
    if wd:
        wd_col.update_one({"req_id": req_id}, {"$set": {"status": "rejected"}})
        # إرجاع الرصيد للمستخدم
        users_col.update_one({"telegram_id": wd["user_id"]}, {"$inc": {"balance": n(wd["requested"])}})
        send_tg(wd["user_id"], f"❌ تم رفض طلب السحب وإرجاع الرصيد لحسابك.")
    return jsonify({"ok": True}), 200

@app.route('/api/admin/users', methods=['POST'])
def users_list():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    users = []
    for u in users_col.find({}).sort("balance", -1).limit(100):
        users.append({
            "user_id": u.get("telegram_id", ""),
            "first_name": u.get("first_name", "مستخدم"),
            "balance": n(u.get("balance")),
            "refs": int(n(u.get("refs"))),
            "wallet": u.get("wallet", ""),
            "is_verified": u.get("is_verified", False),
            "vip": u.get("vip_level", "None")
        })
    return jsonify({"ok": True, "users": users}), 200

@app.route('/api/admin/give_balance', methods=['POST'])
def give_balance():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    user_id = str(body.get("user_id"))
    amount = float(body.get("amount", 0))
    
    users_col.update_one({"telegram_id": user_id}, {"$inc": {"balance": amount}})
    send_tg(user_id, f"💰 <b>تم تعديل رصيدك من الإدارة!</b>\nالتعديل: {amount} MYT")
    return jsonify({"ok": True}), 200

@app.route('/api/admin/broadcast', methods=['POST'])
def broadcast():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    message = body.get("message")
    if not message: return jsonify({"error": "Message is empty"}), 400
    
    all_users = users_col.find({}, {"telegram_id": 1})
    count = 0
    for u in all_users:
        send_tg(u["telegram_id"], message)
        count += 1
        time.sleep(0.05) # لتجنب حظر البوت من تيليجرام
        
    return jsonify({"ok": True, "sent_to": count}), 200

# --- معالج Vercel ---
def handler(event, context):
    return app(event, context)
