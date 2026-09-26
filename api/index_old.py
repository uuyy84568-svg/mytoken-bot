# MYTOKEN API v2 - Python + Upstash Redis
import json, os, datetime, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8063963886"))
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://regal-kitten-2da9af.netlify.app")

def redis_cmd(*args):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        url = UPSTASH_URL.rstrip("/") + "/" + "/".join(urllib.parse.quote(str(a), safe="") for a in args)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + UPSTASH_TOKEN})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()).get("result")
    except Exception as e:
        print("[Redis]", e)
        return None

def redis_pipe(commands):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return []
    try:
        url = UPSTASH_URL.rstrip("/") + "/pipeline"
        data = json.dumps([list(c) for c in commands]).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": "Bearer " + UPSTASH_TOKEN,
            "Content-Type": "application/json"
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return [x.get("result") for x in json.loads(r.read().decode())]
    except Exception as e:
        print("[Pipe]", e)
        return []

def ukey(uid): return "user:" + str(uid)

def get_user(uid):
    h = redis_cmd("HGETALL", ukey(uid))
    if not h: return None
    d = {}
    if isinstance(h, list):
        for i in range(0, len(h), 2):
            d[h[i]] = h[i+1]
    elif isinstance(h, dict):
        d = h
    return d

def save_user(uid, fields):
    cmds = [("HSET", ukey(uid), k, str(v)) for k, v in fields.items()]
    cmds.append(("SADD", "users", str(uid)))
    redis_pipe(cmds)

def n(v, d=0):
    try:
        x = float(v)
        return int(x) if x.is_integer() else x
    except:
        return d

class handler(BaseHTTPRequestHandler):
    def _send(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0: return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except:
            return {}

    def do_OPTIONS(self): self._send({})

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        body = {k: v[0] for k, v in qs.items()}
        self._route(path, body)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        self._route(path, self._body())

    def _route(self, path, body):
        try:
            if path.endswith("/"): path = path[:-1]
            routes = {
                "/api/user": self.h_user,
                "/api/register": self.h_register,
                "/api/tap": self.h_tap,
                "/api/ad": self.h_ad,
                "/api/claim": self.h_claim,
                "/api/checkin": self.h_checkin,
                "/api/wallet": self.h_wallet,
                "/api/ref_stats": self.h_ref_stats,
                "/api/admin/stats": self.h_a_stats,
                "/api/admin/users": self.h_a_users,
                "/api/admin/give": self.h_a_give,
                "/api/admin/broadcast": self.h_a_broadcast,
                "/api/clan/ranking": self.h_clans
            }
            if path in routes:
                return routes[path](body)
            if path in ("", "/"):
                return self._send({"ok": True, "name": "MYTOKEN API", "status": "online"})
            return self._send({"ok": False, "error": "Not found"}, 404)
        except Exception as e:
            print("[ERR]", e)
            return self._send({"ok": False, "error": str(e)}, 500)

    # === USER HANDLERS ===
    def h_user(self, body):
        uid = body.get("id") or body.get("user_id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        u = get_user(uid)
        if not u: return self._send({"ok": True, "exists": False})
        redis_cmd("HSET", ukey(uid), "last_active", "now")
        return self._send({
            "ok": True, "exists": True,
            "balance": n(u.get("balance", 0)),
            "pending": n(u.get("pending", 0)),
            "refs": n(u.get("refs", 0)),
            "streak": n(u.get("streak", 0)),
            "checkinDay": n(u.get("checkin_day", 0)),
            "canCheckin": u.get("can_checkin", "1") == "1",
            "achievements": [],
            "wallet": u.get("wallet", ""),
            "ads": n(u.get("ads", 0)),
            "taps": n(u.get("taps", 0)),
            "clicks": n(u.get("taps", 0)),
            "level": n(u.get("level", 1)),
            "first_name": u.get("first_name", "User")
        })

    def h_register(self, body):
        uid = body.get("id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        ref = body.get("ref")
        first_name = body.get("first_name", "User")
        if get_user(uid):
            return self._send({"ok": True, "exists": True, "isNew": False})
        save_user(uid, {
            "telegram_id": uid, "first_name": first_name,
            "balance": 0, "pending": 0, "refs": 0, "streak": 0,
            "checkin_day": 0, "can_checkin": 1, "wallet": "",
            "ads": 0, "taps": 0, "level": 1,
            "created_at": "now", "last_active": "now"
        })
        if ref:
            ref = str(int(ref))
            if ref != uid and get_user(ref):
                redis_pipe([
                    ("HINCRBY", ukey(ref), "refs", 1),
                    ("HINCRBYFLOAT", ukey(ref), "balance", 100),
                    ("HSET", ukey(uid), "referred_by", ref)
                ])
        return self._send({"ok": True, "exists": True, "isNew": True})

    def h_tap(self, body):
        uid = body.get("id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        cnt = min(int(body.get("count", 0)), 500)
        if cnt <= 0: return self._send({"ok": False, "error": "Invalid count"}, 400)
        if not get_user(uid): return self._send({"ok": True, "exists": False})
        reward = 0.001 * cnt
        redis_pipe([
            ("HINCRBY", ukey(uid), "taps", cnt),
            ("HINCRBYFLOAT", ukey(uid), "balance", reward),
            ("HSET", ukey(uid), "last_active", "now")
        ])
        u = get_user(uid)
        return self._send({"ok": True, "balance": n(u.get("balance", 0)), "taps": n(u.get("taps", 0)), "added": cnt})

    def h_ad(self, body):
        uid = body.get("id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        if not get_user(uid): return self._send({"ok": True, "exists": False})
        reward = 0.10
        redis_pipe([
            ("HINCRBY", ukey(uid), "ads", 1),
            ("HINCRBYFLOAT", ukey(uid), "balance", reward),
            ("HINCRBYFLOAT", ukey(uid), "pending", reward),
            ("HSET", ukey(uid), "last_active", "now")
        ])
        u = get_user(uid)
        return self._send({"ok": True, "balance": n(u.get("balance", 0)), "pending": n(u.get("pending", 0)), "ads": n(u.get("ads", 0))})

    def h_claim(self, body):
        uid = body.get("id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        u = get_user(uid)
        if not u: return self._send({"ok": True, "exists": False})
        pending = n(u.get("pending", 0))
        if pending <= 0:
            return self._send({"ok": True, "balance": n(u.get("balance", 0)), "pending": 0})
        redis_pipe([
            ("HINCRBYFLOAT", ukey(uid), "balance", pending),
            ("HSET", ukey(uid), "pending", 0)
        ])
        u = get_user(uid)
        return self._send({"ok": True, "balance": n(u.get("balance", 0)), "pending": 0})

    def h_checkin(self, body):
        uid = body.get("id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        u = get_user(uid)
        if not u: return self._send({"ok": True, "exists": False})
        today = datetime.date.today().isoformat()
        if u.get("last_checkin", "") == today:
            return self._send({"ok": False, "error": "already"})
        REWARDS = [0.20, 0.50, 1, 2, 5, 10, 100]
        day = n(u.get("checkin_day", 0))
        if day >= 7: day = 0
        day += 1
        reward = REWARDS[day - 1]
        streak = n(u.get("streak", 0)) + 1
        redis_pipe([
            ("HINCRBYFLOAT", ukey(uid), "balance", reward),
            ("HSET", ukey(uid), "checkin_day", day),
            ("HSET", ukey(uid), "last_checkin", today),
            ("HSET", ukey(uid), "can_checkin", 0),
            ("HSET", ukey(uid), "streak", streak)
        ])
        u = get_user(uid)
        return self._send({"ok": True, "day": day, "reward": reward, "balance": n(u.get("balance", 0)), "streak": streak})

    def h_wallet(self, body):
        uid = body.get("id")
        wallet = body.get("wallet", "")
        if not uid or not wallet:
            return self._send({"ok": False, "error": "Missing data"}, 400)
        uid = str(int(uid))
        if not get_user(uid): return self._send({"ok": True, "exists": False})
        redis_cmd("HSET", ukey(uid), "wallet", wallet)
        return self._send({"ok": True, "wallet": wallet})

    def h_ref_stats(self, body):
        uid = body.get("user_id") or body.get("id")
        if not uid: return self._send({"ok": False, "error": "Missing id"}, 400)
        uid = str(int(uid))
        u = get_user(uid)
        return self._send({"ok": True, "referrals": n((u or {}).get("refs", 0)), "refs": n((u or {}).get("refs", 0))})

    # === ADMIN HANDLERS ===
    def _admin(self, body):
        try:
            return int(body.get("admin_id", 0)) == ADMIN_ID
        except:
            return False

    def h_a_stats(self, body):
        if not self._admin(body):
            return self._send({"ok": False, "error": "Forbidden"}, 403)
        uids = redis_cmd("SMEMBERS", "users") or []
        if not isinstance(uids, list): uids = []
        tot_bal = tot_refs = tot_ads = tot_chk = tot_taps = tot_wal = 0
        for uid in uids[:500]:
            u = get_user(uid)
            if not u: continue
            tot_bal += n(u.get("balance", 0))
            tot_refs += n(u.get("refs", 0))
            tot_ads += n(u.get("ads", 0))
            tot_chk += n(u.get("checkin_day", 0))
            tot_taps += n(u.get("taps", 0))
            if u.get("wallet"): tot_wal += 1
        return self._send({
            "ok": True,
            "total_users": len(uids),
            "active_users": len(uids),
            "total_balance": round(tot_bal, 2),
            "total_refs": tot_refs,
            "total_ads": tot_ads,
            "total_checkins": tot_chk,
            "total_taps": tot_taps,
            "total_wallets": tot_wal
        })

    def h_a_users(self, body):
        if not self._admin(body):
            return self._send({"ok": False, "error": "Forbidden"}, 403)
        uids = redis_cmd("SMEMBERS", "users") or []
        if not isinstance(uids, list): uids = []
        result = []
        for uid in uids[:200]:
            u = get_user(uid)
            if not u: continue
            result.append({
                "user_id": int(uid),
                "first_name": u.get("first_name", "User"),
                "balance": round(n(u.get("balance", 0)), 4),
                "level": n(u.get("level", 1)),
                "refs": n(u.get("refs", 0)),
                "ads": n(u.get("ads", 0)),
                "checkin": n(u.get("checkin_day", 0)),
                "taps": n(u.get("taps", 0)),
                "wallet": u.get("wallet", "")
            })
        result.sort(key=lambda x: x["balance"], reverse=True)
        return self._send({"ok": True, "users": result, "count": len(result)})

    def h_a_give(self, body):
        if not self._admin(body):
            return self._send({"ok": False, "error": "Forbidden"}, 403)
        target = body.get("target_id")
        try:
            amount = float(body.get("amount", 0))
        except:
            amount = 0
        if not target or amount <= 0:
            return self._send({"ok": False, "error": "Invalid data"}, 400)
        target = str(int(target))
        if not get_user(target):
            return self._send({"ok": False, "error": "User not found"}, 404)
        redis_cmd("HINCRBYFLOAT", ukey(target), "balance", amount)
        u = get_user(target)
        return self._send({"ok": True, "new_balance": n(u.get("balance", 0))})

    def h_a_broadcast(self, body):
        if not self._admin(body):
            return self._send({"ok": False, "error": "Forbidden"}, 403)
        text = body.get("text", "").strip()
        if not text:
            return self._send({"ok": False, "error": "Missing text"}, 400)
        if not BOT_TOKEN:
            return self._send({"ok": False, "error": "BOT_TOKEN not set"}, 500)
        uids = redis_cmd("SMEMBERS", "users") or []
        if not isinstance(uids, list): uids = []
        sent = 0
        failed = 0
        for uid in uids:
            try:
                data = json.dumps({"chat_id": int(uid), "text": text, "parse_mode": "HTML"}).encode()
                req = urllib.request.Request(
                    "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                    data=data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    if json.loads(r.read().decode()).get("ok"):
                        sent += 1
                    else:
                        failed += 1
            except:
                failed += 1
        return self._send({"ok": True, "sent": sent, "failed": failed})

    def h_clans(self, body):
        return self._send({"ok": True, "clans": []})
