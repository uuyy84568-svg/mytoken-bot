from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import os
import time

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get("MONGO_URI")
ADMIN_ID = "8063963886"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client.get_database("mytoken_db")
    users_col = db.get_collection("users")
    wd_col = db.get_collection("withdrawals")
except Exception as e:
    print(f"DB Error: {e}")

def is_admin(body):
    return str(body.get("admin_id", "")) == ADMIN_ID

def n(val, default=0.0):
    try: return float(val if val is not None else default)
    except: return float(default)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "success", "db": "mongodb"}), 200

@app.route('/api/user', methods=['POST'])
def get_user():
    try:
        data = request.json
        user_id = str(data.get("id"))
        user = users_col.find_one({"telegram_id": user_id})
        if user:
            user['_id'] = str(user['_id'])
            return jsonify({"exists": True, "balance": user.get('balance', 0), "user": user}), 200
        return jsonify({"exists": False, "balance": 0}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/update', methods=['POST'])
def update_user():
    try:
        data = request.json
        user_id = str(data.get("telegram_id"))
        if "telegram_id" in data: del data["telegram_id"]
        users_col.update_one({"telegram_id": user_id}, {"$set": data}, upsert=True)
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
        if amount < 1000: return jsonify({"error": "الحد الأدنى 1000 MYT"}), 400
        if amount > balance: return jsonify({"error": "رصيد غير كافٍ"}), 400

        platform_fee = round(amount * 0.02, 2)
        network_fee = 50.0
        net_amount = amount - platform_fee - network_fee

        if net_amount <= 0: return jsonify({"error": "المبلغ لا يغطي الرسوم"}), 400

        req_id = f"wd_{user_id}_{int(time.time())}"
        wd_col.insert_one({
            "req_id": req_id, "user_id": user_id, "first_name": user.get("first_name"),
            "requested": amount, "net_amount": net_amount, "wallet": user.get("wallet", ""),
            "status": "pending", "created_at": int(time.time())
        })
        users_col.update_one({"telegram_id": user_id}, {"$inc": {"balance": -amount}})
        return jsonify({"ok": True, "message": "Request sent", "net_amount": net_amount}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/stats', methods=['POST'])
def stats():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    
    total_users = users_col.count_documents({})
    total_bal = 0
    for u in users_col.find({}, {"balance": 1}): total_bal += n(u.get("balance"))
    
    return jsonify({
        "ok": True, "total_users": total_users, "total_balance": total_bal, 
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
    wd_col.update_one({"req_id": body.get("req_id")}, {"$set": {"status": "approved"}})
    return jsonify({"ok": True}), 200

@app.route('/api/admin/withdraw/reject', methods=['POST'])
def wd_reject():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    req_id = body.get("req_id")
    wd = wd_col.find_one({"req_id": req_id})
    if wd:
        wd_col.update_one({"req_id": req_id}, {"$set": {"status": "rejected"}})
        users_col.update_one({"telegram_id": wd["user_id"]}, {"$inc": {"balance": n(wd["requested"])}})
    return jsonify({"ok": True}), 200

@app.route('/api/admin/users', methods=['POST'])
def users_list():
    body = request.json
    if not is_admin(body): return jsonify({"error": "Unauthorized"}), 403
    users = []
    for u in users_col.find({}).sort("balance", -1).limit(100):
        users.append({
            "user_id": u.get("telegram_id", ""), "first_name": u.get("first_name", "مستخدم"),
            "balance": n(u.get("balance")), "refs": int(n(u.get("refs"))),
            "wallet": u.get("wallet", ""), "is_verified": u.get("is_verified", False)
        })
    return jsonify({"ok": True, "users": users}), 200

def handler(event, context):
    return app(event, context)
