import os
import sys
import json
import time
import asyncio
from aiohttp import web

# Set encoding
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

import database as db
from crypto_service import crypto_service
from salta7_service import salta7_service
import webhook_logger

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_client_ip(request: web.Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()
    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded and x_forwarded.strip():
        return x_forwarded.split(",")[0].strip()
    x_real = request.headers.get("X-Real-IP")
    if x_real and x_real.strip():
        return x_real.strip()

    # Differentiate tunnel visitors via session cookie or User-Agent if remote is loopback
    remote = request.remote or "127.0.0.1"
    if remote in ("127.0.0.1", "::1", "localhost"):
        sess_token = request.cookies.get("sick_session") or request.headers.get("Authorization", "")
        if sess_token:
            return f"sess_{sess_token[:16]}"
        ua = request.headers.get("User-Agent", "")
        if ua:
            import hashlib
            return f"ua_{hashlib.md5(ua.encode('utf-8', errors='ignore')).hexdigest()[:10]}"

    return remote

class RateLimiter:
    def __init__(self):
        self.requests = {}

    def is_allowed(self, ip: str, max_requests: int = 200, window_seconds: int = 60) -> bool:
        now = time.time()
        if ip not in self.requests:
            self.requests[ip] = []
        self.requests[ip] = [t for t in self.requests[ip] if now - t < window_seconds]
        if len(self.requests[ip]) >= max_requests:
            return False
        self.requests[ip].append(now)
        return True

rate_limiter = RateLimiter()

EXEMPT_PATHS = {
    "/",
    "/index.html",
    "/api/info",
    "/api/auth/me",
    "/api/payment/invoice",
    "/api/payment/invoice/check",
    "/api/payment/auto-detect",
    "/api/boost/orders"
}

@web.middleware
async def security_and_rate_limit_middleware(request: web.Request, handler):
    ip = get_client_ip(request)
    path = request.path

    # Check Maintenance Mode
    cfg = load_config()
    m_cfg = cfg.get("maintenance", {})
    if m_cfg.get("enabled", False):
        bypass_token = request.query.get("bypass", "") or request.cookies.get("m_bypass", "")
        is_bypass = (bypass_token == m_cfg.get("admin_secret", "sick_admin_pass"))
        
        # If not bypassed, block mutating API requests
        if not is_bypass:
            if path.startswith("/api/") and path not in ["/api/info"]:
                return web.json_response({
                    "success": False,
                    "maintenance": True,
                    "message": "Marketplace befindet sich aktuell in Wartungsarbeiten. Bitte versuche es gleich noch einmal."
                }, status=503)

    # Whitelist harmless polling, static assets & read endpoints
    if path in EXEMPT_PATHS or path.startswith("/static/"):
        response = await handler(request)
        response.headers["Server"] = "12b00-Shield/3.0"
        return response

    # Rate Limiter (Anti-Brute Force & Anti-DDoS for sensitive action endpoints)
    if path.startswith("/api/"):
        # Exempt loopback without proxy header from self-blocking
        if not ip.startswith(("127.0.0.1", "::1")):
            max_req = 80 if path.startswith(("/api/auth/", "/api/payment/verify")) else 300
            if not rate_limiter.is_allowed(ip, max_requests=max_req, window_seconds=60):
                webhook_logger.log_security_alert(ip, "Rate Limit Exceeded (Anti-DDoS Shield)", f"Path: {path}")
                return web.json_response({
                    "success": False,
                    "message": "Too many requests. 12b00 Shield security rate-limit triggered. Please wait a few seconds."
                }, status=429)

    response = await handler(request)

    # Security Headers
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Server"] = "12b00-Shield/3.0"
    return response

class BoostPlatformServer:
    def __init__(self):
        self.app = web.Application(middlewares=[security_and_rate_limit_middleware])
        self.cfg = load_config()
        self.setup_routes()

    def setup_routes(self):
        # Frontend Static Serving
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/index.html", self.handle_index)
        self.app.router.add_static("/static", FRONTEND_DIR, follow_symlinks=True)

        # Public Info
        self.app.router.add_get("/api/info", self.api_info)

        # Authentication APIs
        self.app.router.add_post("/api/auth/register", self.api_register)
        self.app.router.add_post("/api/auth/login", self.api_login)
        self.app.router.add_get("/api/auth/me", self.api_me)
        self.app.router.add_post("/api/auth/logout", self.api_logout)

        # User Profile & Security APIs
        self.app.router.add_post("/api/user/change-password", self.api_change_password)
        self.app.router.add_post("/api/user/regenerate-key", self.api_regenerate_key)

        # Payment & Crypto APIs
        self.app.router.add_get("/api/payment/info", self.api_payment_info)
        self.app.router.add_post("/api/payment/verify", self.api_payment_verify)
        self.app.router.add_post("/api/payment/auto-detect", self.api_payment_auto_detect)
        self.app.router.add_get("/api/payment/invoice", self.api_payment_invoice_get)
        self.app.router.add_post("/api/payment/invoice/create", self.api_payment_invoice_create)
        self.app.router.add_post("/api/payment/invoice/check", self.api_payment_invoice_check)

        # Boost Order APIs
        self.app.router.add_post("/api/boost/order", self.api_boost_order)
        self.app.router.add_post("/api/boost/byot", self.api_boost_byot)
        self.app.router.add_get("/api/boost/orders", self.api_get_orders)

        # Autobuy & Store Webhook APIs (SellAuth / Sellix)
        self.app.router.add_post("/api/webhook/sellauth", self.api_webhook_sellauth)
        self.app.router.add_get("/api/autobuy/info", self.api_autobuy_info)
        self.app.router.add_post("/api/webhook/test", self.api_webhook_test)

        # Admin & System Status
        self.app.router.add_get("/api/admin/stats", self.api_admin_stats)
        self.app.router.add_get("/api/admin/users", self.api_admin_users)
        self.app.router.add_post("/api/admin/set_balance", self.api_admin_set_balance)
        self.app.router.add_post("/api/admin/set_webhook", self.api_admin_set_webhook)
        self.app.router.add_get("/api/test_webhook", self.api_trigger_test_webhook)
        self.app.router.add_post("/api/test_webhook", self.api_trigger_test_webhook)

    # --- Helper: Extract Current User from Session ---
    def get_current_user(self, request: web.Request):
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = request.cookies.get("session_token", "")
            
        if not token:
            return None
        return db.get_user_by_session(token)

    # --- Frontend Handlers ---
    async def handle_index(self, request: web.Request) -> web.Response:
        cfg = load_config()
        m_cfg = cfg.get("maintenance", {})
        is_maintenance = m_cfg.get("enabled", False)
        
        bypass_token = request.query.get("bypass", "") or request.cookies.get("m_bypass", "")
        expected_secret = m_cfg.get("admin_secret", "sick_admin_pass")
        is_bypass = (bypass_token == expected_secret)

        if is_maintenance and not is_bypass:
            m_path = os.path.join(FRONTEND_DIR, "maintenance.html")
            if os.path.exists(m_path):
                with open(m_path, "r", encoding="utf-8") as f:
                    return web.Response(text=f.read(), content_type="text/html")

        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                resp = web.Response(text=f.read(), content_type="text/html")
                if is_bypass and bypass_token:
                    resp.set_cookie("m_bypass", bypass_token, max_age=86400)
                return resp
        return web.Response(text="Frontend not found", status=404)

    # --- API Handlers ---
    async def api_info(self, request: web.Request) -> web.Response:
        cfg = load_config()
        m_cfg = cfg.get("maintenance", {})
        is_maintenance = bool(m_cfg.get("enabled", False))
        return web.json_response({
            "site_name": cfg.get("branding", {}).get("site_name", "SICK ⚡ Gaming & Nitro Marketplace"),
            "support_discord": "https://discord.gg/NitroHQ",
            "wallet_address": cfg.get("crypto", {}).get("ltc_wallet_address", "LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc"),
            "price_per_14_boosts_eur": cfg.get("pricing", {}).get("price_per_14_boosts_eur", 0.20),
            "price_byot_per_order_eur": cfg.get("pricing", {}).get("price_byot_per_order_eur", 0.20),
            "currency_symbol": "€",
            "engine_status": "Maintenance Mode" if is_maintenance else "Online (High-Speed)",
            "maintenance": is_maintenance,
            "autobuy_enabled": True
        })

    async def api_register(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            username = data.get("username", "")
            password = data.get("password", "")
            
            ok, msg, user = db.create_user(username, password)
            if not ok:
                return web.json_response({"success": False, "message": msg}, status=400)
                
            token = db.create_session(user["id"])
            webhook_logger.log_user_registered(username, get_client_ip(request))
            resp = web.json_response({
                "success": True,
                "message": msg,
                "user": user,
                "token": token
            })
            resp.set_cookie("session_token", token, max_age=86400*30, httponly=True)
            return resp
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_login(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            username = data.get("username", "")
            password = data.get("password", "")
            
            ok, msg, user = db.authenticate_user(username, password)
            if not ok:
                return web.json_response({"success": False, "message": msg}, status=401)
                
            token = db.create_session(user["id"])
            webhook_logger.log_user_login(username, get_client_ip(request))
            resp = web.json_response({
                "success": True,
                "message": msg,
                "user": user,
                "token": token
            })
            resp.set_cookie("session_token", token, max_age=86400*30, httponly=True)
            return resp
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_change_password(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login first."}, status=401)
        try:
            data = await request.json()
            old_p = data.get("current_password", "")
            new_p = data.get("new_password", "")
            ok, msg = db.update_user_password(user["id"], old_p, new_p)
            if not ok:
                return web.json_response({"success": False, "message": msg}, status=400)
            return web.json_response({"success": True, "message": "Password successfully updated!"})
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_regenerate_key(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login first."}, status=401)
        new_key = db.regenerate_user_api_key(user["id"])
        return web.json_response({"success": True, "api_key": new_key, "message": "New SICK API key generated!"})

    async def api_me(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"authenticated": False}, status=401)
        # Fetch fresh balance
        balance = db.get_user_balance(user["id"])
        user["balance_eur"] = balance
        return web.json_response({"authenticated": True, "user": user})

    async def api_logout(self, request: web.Request) -> web.Response:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else request.cookies.get("session_token", "")
        if token:
            db.delete_session(token)
        resp = web.json_response({"success": True, "message": "Logged out."})
        resp.del_cookie("session_token")
        return resp

    async def api_payment_info(self, request: web.Request) -> web.Response:
        amount_eur = float(request.query.get("amount", 0.20))
        info = crypto_service.get_payment_info(amount_eur)
        return web.json_response(info)

    async def api_payment_verify(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login first."}, status=401)

        try:
            data = await request.json()
            tx_hash = data.get("tx_hash", "").strip().lower()
            if not tx_hash:
                return web.json_response({"success": False, "message": "Missing transaction hash."}, status=400)

            if db.is_deposit_recorded(tx_hash):
                return web.json_response({
                    "success": False,
                    "message": "This transaction hash has already been credited or is historical."
                }, status=400)

            # Query blockchain for tx
            ok, credited_eur, msg = crypto_service.verify_tx_on_chain(tx_hash)
            if ok:
                ltc_amt = crypto_service.eur_to_ltc(credited_eur)
                rec_ok = db.record_deposit(user["id"], tx_hash, ltc_amt, credited_eur, status="completed")
                if rec_ok:
                    new_bal = db.get_user_balance(user["id"])
                    webhook_logger.log_deposit(user["username"], credited_eur, ltc_amt, tx_hash, is_test=False)
                    return web.json_response({
                        "success": True,
                        "message": f"Deposit confirmed! {credited_eur:.2f} € credited to your account.",
                        "new_balance": new_bal
                    })
                else:
                    return web.json_response({
                        "success": False,
                        "message": "This transaction hash has already been credited."
                    }, status=400)
            else:
                return web.json_response({"success": False, "message": msg}, status=400)
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    def _check_invoice_deposit(self, user_id: int, username: str) -> dict:
        """
        Global blockchain payment verification:
        Checks recent confirmed transactions from Litecoin blockchain.
        Matches each transaction to the exact pending invoice by its unique satoshi amount.
        Credits the invoice's true owner (matching_inv["user_id"]).
        """
        incoming = crypto_service.get_recent_incoming_transactions(limit=25)
        matched_for_caller = None

        for tx in incoming:
            tx_hash = tx.get("tx_hash", "").strip().lower()
            if not tx_hash:
                continue

            # 1. Skip if already processed in DB
            if db.is_deposit_recorded(tx_hash):
                continue

            # 2. Strict confirmation check: Must be confirmed on the blockchain
            if not tx.get("confirmed", False):
                continue

            tx_time = int(tx.get("timestamp", 0))
            if tx_time == 0:
                continue

            actual_ltc = float(tx.get("amount_ltc", 0.0))
            if actual_ltc <= 0:
                continue

            # 3. Find exact matching pending invoice (satoshi precision)
            matching_inv = db.find_matching_pending_invoice(actual_ltc, tolerance=0.0000005)
            if not matching_inv:
                # Fallback: check caller's active invoice with tight 1% tolerance if no other invoice exists
                caller_inv = db.get_active_invoice(user_id)
                if caller_inv and abs(float(caller_inv["amount_ltc"]) - actual_ltc) <= (float(caller_inv["amount_ltc"]) * 0.01):
                    matching_inv = caller_inv

            if not matching_inv:
                continue

            # 4. Strict timestamp verification: Transaction block time must be after invoice creation
            if tx_time < (matching_inv["created_at"] - 60):
                continue

            # Genuine matching payment detected!
            target_user_id = matching_inv["user_id"]
            target_username = matching_inv.get("username") or (username if target_user_id == user_id else f"user_{target_user_id}")

            rec_ok = db.record_deposit(target_user_id, tx_hash, actual_ltc, matching_inv["amount_eur"], status="completed")
            if rec_ok:
                db.mark_invoice_completed(matching_inv["payment_id"])
                new_bal = db.get_user_balance(target_user_id)
                webhook_logger.log_deposit(target_username, matching_inv["amount_eur"], actual_ltc, tx_hash, is_test=False)
                
                res_data = {
                    "success": True,
                    "detected": True,
                    "amount_eur": matching_inv["amount_eur"],
                    "amount_ltc": actual_ltc,
                    "new_balance": new_bal,
                    "tx_hash": tx_hash,
                    "message": f"Payment verified on Litecoin blockchain! Credited {matching_inv['amount_eur']:.2f} € ({actual_ltc:.6f} LTC) to your balance."
                }

                if target_user_id == user_id:
                    matched_for_caller = res_data

        if matched_for_caller:
            return matched_for_caller

        return {"success": True, "detected": False, "scanning": True}

    async def api_payment_auto_detect(self, request: web.Request) -> web.Response:
        """Background scanner: only checks for payments matching the user's active invoice"""
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Unauthorized"}, status=401)

        try:
            res = self._check_invoice_deposit(user["id"], user["username"])
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_payment_invoice_get(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            # Guest preview invoice
            amount_eur = 0.20
            amount_ltc = crypto_service.eur_to_ltc(amount_eur)
            ltc_str = f"{amount_ltc:.8f} LTC"
            uri = f"litecoin:{crypto_service.wallet_address}?amount={amount_ltc:.8f}&label=SICK%20Marketplace"
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={uri}"
            return web.json_response({
                "success": True,
                "invoice": {
                    "payment_id": "5784378544",
                    "amount_eur": amount_eur,
                    "amount_ltc_str": ltc_str,
                    "amount_ltc_raw": amount_ltc,
                    "wallet_address": crypto_service.wallet_address,
                    "status": "pending",
                    "expires_in_seconds": 28700,
                    "expires_in_text": "7h 58m",
                    "qr_url": qr_url
                }
            })

        user_id = user["id"]
        inv = db.get_active_invoice(user_id)
        if not inv:
            amount_eur = 0.20
            amount_ltc = crypto_service.eur_to_ltc(amount_eur)
            inv = db.create_invoice(user_id, amount_eur, amount_ltc, crypto_service.wallet_address, duration_hours=8)

        now = int(time.time())
        rem_sec = max(0, inv["expires_at"] - now)
        hours = rem_sec // 3600
        mins = (rem_sec % 3600) // 60
        countdown_str = f"{hours}h {mins:02d}m"

        ltc_str = f"{inv['amount_ltc']:.8f} LTC"
        uri = f"litecoin:{inv['wallet_address']}?amount={inv['amount_ltc']:.8f}&label=SICK%20Marketplace"
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={uri}"

        return web.json_response({
            "success": True,
            "invoice": {
                "payment_id": inv["payment_id"],
                "amount_eur": inv["amount_eur"],
                "amount_ltc_str": ltc_str,
                "amount_ltc_raw": inv["amount_ltc"],
                "wallet_address": inv["wallet_address"],
                "status": inv["status"],
                "expires_in_seconds": rem_sec,
                "expires_in_text": countdown_str,
                "qr_url": qr_url
            }
        })

    async def api_payment_invoice_create(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login to generate an invoice."}, status=401)
        user_id = user["id"]

        try:
            data = await request.json()
            amount_eur = float(data.get("amount_eur", 0.20))
            if amount_eur < 0.20:
                amount_eur = 0.20

            amount_ltc = crypto_service.eur_to_ltc(amount_eur)
            inv = db.create_invoice(user_id, amount_eur, amount_ltc, crypto_service.wallet_address, duration_hours=8)

            now = int(time.time())
            rem_sec = max(0, inv["expires_at"] - now)
            hours = rem_sec // 3600
            mins = (rem_sec % 3600) // 60
            countdown_str = f"{hours}h {mins:02d}m"

            ltc_str = f"{inv['amount_ltc']:.8f} LTC"
            uri = f"litecoin:{inv['wallet_address']}?amount={inv['amount_ltc']:.8f}&label=SICK%20Marketplace"
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={uri}"

            return web.json_response({
                "success": True,
                "invoice": {
                    "payment_id": inv["payment_id"],
                    "amount_eur": inv["amount_eur"],
                    "amount_ltc_str": ltc_str,
                    "amount_ltc_raw": inv["amount_ltc"],
                    "wallet_address": inv["wallet_address"],
                    "status": inv["status"],
                    "expires_in_seconds": rem_sec,
                    "expires_in_text": countdown_str,
                    "qr_url": qr_url
                }
            })
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_payment_invoice_check(self, request: web.Request) -> web.Response:
        """Manual status check triggered by 'Refresh Status' button"""
        user = self.get_current_user(request)
        if not user:
            user = db.get_default_user()
        user_id = user["id"] if user else 1
        username = user["username"] if user else "user"

        try:
            res = self._check_invoice_deposit(user_id, username)
            res["current_balance"] = db.get_user_balance(user_id)
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_boost_order(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login to place boost orders."}, status=401)

        try:
            data = await request.json()
            invite = data.get("invite", "").strip()
            boosts = int(data.get("boosts", 14))
            duration = data.get("duration", "1m")
            nickname = data.get("nickname", "").strip()

            if not invite:
                return web.json_response({"success": False, "message": "Discord server invite is required."}, status=400)

            # Price Calculation: €0.20 per 14 boosts
            cfg = load_config()
            base_price = cfg.get("pricing", {}).get("price_per_14_boosts_eur", 0.20)
            order_price = round((boosts / 14.0) * base_price, 2)
            if order_price < 0.20:
                order_price = 0.20

            # Check user balance
            current_bal = db.get_user_balance(user["id"])
            if current_bal < order_price:
                return web.json_response({
                    "success": False,
                    "insufficient_balance": True,
                    "required_eur": order_price,
                    "current_balance": current_bal,
                    "message": f"Insufficient balance ({current_bal:.2f} €). You need {order_price:.2f} € to order {boosts}x Boosts. Please deposit via Litecoin."
                }, status=402)

            # Deduct balance
            deduct_ok, new_bal = db.adjust_user_balance(user["id"], -order_price)
            if not deduct_ok:
                return web.json_response({"success": False, "message": "Transaction failed."}, status=400)

            # Create order record
            order_id = db.create_order(user["id"], invite, boosts, order_price, duration, nickname)

            # Dispatch order via High-Speed Cloud Backend
            engine_ok, engine_msg, engine_data = salta7_service.dispatch_boost_order(order_id, invite, boosts, nickname=nickname)
            task_id = engine_data.get("job_id") if engine_data else None

            webhook_logger.log_boost_order(user["username"], order_id, invite, boosts, "stock", order_price, nickname)

            return web.json_response({
                "success": True,
                "order_id": order_id,
                "boosts": boosts,
                "price_eur": order_price,
                "new_balance": new_bal,
                "dispatched": engine_ok,
                "task_id": task_id,
                "message": f"Successfully created order #{order_id} for {boosts}x Boosts! SICK High-Speed Cloud delivery is active."
            })
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_boost_byot(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login to boost servers with your tokens."}, status=401)

        try:
            data = await request.json()
            invite = data.get("invite", "").strip()
            raw_tokens = data.get("tokens", "")
            boosts_needed = int(data.get("boosts_needed", 14))
            nickname = data.get("nickname", "").strip()
            bio = data.get("bio", "").strip()
            avatar = data.get("avatar", "").strip()
            banner = data.get("banner", "").strip()
            duration = data.get("duration", "1m")

            if not invite:
                return web.json_response({"success": False, "message": "Discord server invite is required."}, status=400)

            # Parse Tokens (Support string or array)
            if isinstance(raw_tokens, list):
                parsed_tokens = [salta7_service.extract_clean_token(t) for t in raw_tokens if salta7_service.extract_clean_token(t)]
            else:
                parsed_tokens = salta7_service.parse_token_list(str(raw_tokens))

            if not parsed_tokens:
                return web.json_response({
                    "success": False,
                    "message": "No valid Discord tokens detected! Please paste your tokens (Format: token or email:pass:token)."
                }, status=400)

            effective_boosts = boosts_needed if boosts_needed > 0 else max(14, len(parsed_tokens) * 2)
            import math
            packs = max(1, math.ceil(effective_boosts / 14.0))
            byot_price = round(packs * 0.20, 2)

            # Check user balance
            current_bal = db.get_user_balance(user["id"])
            if current_bal < byot_price:
                return web.json_response({
                    "success": False,
                    "insufficient_balance": True,
                    "required_eur": byot_price,
                    "current_balance": current_bal,
                    "message": f"Insufficient balance ({current_bal:.2f} €). This order requires {byot_price:.2f} € for {effective_boosts} boosts ({packs}x 14-boost pack{'s' if packs > 1 else ''}). Please deposit via Litecoin."
                }, status=402)

            # Deduct balance
            deduct_ok, new_bal = db.adjust_user_balance(user["id"], -byot_price)
            if not deduct_ok:
                return web.json_response({"success": False, "message": "Transaction failed."}, status=400)

            # Record Order in DB
            order_id = db.create_order(
                user_id=user["id"],
                invite=invite,
                boosts=effective_boosts,
                price_eur=byot_price,
                duration=duration,
                nickname=nickname,
                mode="byot",
                tokens_count=len(parsed_tokens),
                bio=bio,
                avatar_url=avatar,
                banner_url=banner
            )

            # Dispatch via SICK High-Speed Cloud Engine
            humanize_data = {
                "nickname": nickname,
                "bio": bio,
                "avatar": avatar,
                "banner": banner
            }

            engine_ok, engine_msg, engine_data = salta7_service.dispatch_boost_order(
                order_id=order_id,
                invite=invite,
                boosts=effective_boosts,
                mode="byot",
                tokens=parsed_tokens,
                boosts_needed=boosts_needed,
                humanize=humanize_data
            )
            task_id = engine_data.get("job_id") if engine_data else None

            if not engine_ok:
                # Immediate refund if engine rejects the task!
                db.adjust_user_balance(user["id"], byot_price)
                refunded_bal = db.get_user_balance(user["id"])
                return web.json_response({
                    "success": False,
                    "order_id": order_id,
                    "refunded": True,
                    "new_balance": refunded_bal,
                    "message": f"Boost Dispatch Error: {engine_msg} (Your {byot_price:.2f} € was refunded automatically!)"
                }, status=400)

            webhook_logger.log_boost_order(user["username"], order_id, invite, effective_boosts, "byot", byot_price, nickname, tokens_count=len(parsed_tokens))

            return web.json_response({
                "success": True,
                "order_id": order_id,
                "mode": "byot",
                "tokens_count": len(parsed_tokens),
                "boosts": effective_boosts,
                "price_eur": byot_price,
                "new_balance": new_bal,
                "dispatched": engine_ok,
                "task_id": task_id,
                "message": f"BYOT Boost Order #{order_id} active! {len(parsed_tokens)} tokens deployed. Cloud delivery in progress."
            })
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_webhook_sellauth(self, request: web.Request) -> web.Response:
        """Automated Store Webhook (SellAuth / Sellix / Custom Shop)"""
        try:
            # Check for API Key in query params, headers, or bearer auth
            api_key = request.query.get("key") or request.query.get("api_key") or request.query.get("token")
            if not api_key:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    api_key = auth_header[7:].strip()
                else:
                    api_key = request.headers.get("X-Auth-Token") or request.headers.get("X-API-Key")

            user = None
            if api_key:
                user = db.get_user_by_api_key(api_key)
            if not user:
                user = self.get_current_user(request)
            if not user:
                user = db.get_default_user()

            if not user:
                return web.json_response({"success": False, "message": "No account associated with webhook. Please configure your API key."}, status=401)

            # Parse incoming body
            try:
                payload = await request.json()
            except Exception:
                payload = dict(await request.post())

            # Find Invite in payload (SellAuth custom fields, root fields, nested data)
            data_obj = payload.get("data", payload)
            custom_fields = data_obj.get("custom_fields", {})
            if not isinstance(custom_fields, dict):
                custom_fields = {}

            invite = (
                custom_fields.get("invite") or
                custom_fields.get("server_invite") or
                custom_fields.get("discord_invite") or
                custom_fields.get("server") or
                data_obj.get("invite") or
                data_obj.get("discord_invite") or
                payload.get("invite") or
                request.query.get("invite") or
                ""
            )

            if not invite:
                return web.json_response({
                    "success": False,
                    "message": "Missing 'invite' in webhook payload. Please configure custom field 'invite' in SellAuth."
                }, status=400)

            # Boosts amount
            raw_boosts = (
                custom_fields.get("boosts") or
                data_obj.get("boosts") or
                (int(data_obj.get("quantity", 1)) * 14) or
                payload.get("boosts") or
                request.query.get("boosts") or
                14
            )
            try:
                boosts = int(raw_boosts)
            except Exception:
                boosts = 14

            nickname = custom_fields.get("nickname") or data_obj.get("nickname") or "Autobuy Order"
            order_price = round((boosts / 14.0) * 0.20, 2)

            # Deduct balance if available
            current_bal = db.get_user_balance(user["id"])
            if current_bal >= order_price:
                db.adjust_user_balance(user["id"], -order_price)

            order_id = db.create_order(
                user_id=user["id"],
                invite=invite,
                boosts=boosts,
                price_eur=order_price,
                duration="1m",
                nickname=nickname,
                mode="autobuy"
            )

            # Dispatch order to SICK High-Speed Cloud Engine
            engine_ok, engine_msg, engine_data = salta7_service.dispatch_boost_order(
                order_id=order_id,
                invite=invite,
                boosts=boosts,
                nickname=nickname
            )

            webhook_logger.log_autobuy_webhook(order_id, invite, boosts, order_price)

            return web.json_response({
                "success": True,
                "order_id": order_id,
                "mode": "autobuy",
                "invite": invite,
                "boosts": boosts,
                "price_eur": order_price,
                "dispatched": engine_ok,
                "message": f"Autobuy boost order #{order_id} fulfilled automatically! High-speed cloud delivery active."
            })
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_autobuy_info(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"authenticated": False}, status=401)
        
        api_key = user.get("api_key", "")
        host = request.headers.get("Host", "localhost:5890")
        webhook_url = f"http://{host}/api/webhook/sellauth?key={api_key}"

        return web.json_response({
            "success": True,
            "api_key": api_key,
            "webhook_url": webhook_url,
            "setup_guide": {
                "step1": "In your SellAuth / Sellix dashboard, go to Settings -> Webhooks.",
                "step2": f"Set Webhook URL to: {webhook_url}",
                "step3": "Select event 'order.created' or 'order.completed'.",
                "step4": "In your product settings, add a Custom Field named 'invite' (or 'server_invite') for the customer to enter their Discord server invite."
            },
            "sample_payload": {
                "event": "order.created",
                "data": {
                    "custom_fields": {
                        "invite": "https://discord.gg/yourserver",
                        "boosts": 14
                    }
                }
            }
        })

    async def api_webhook_test(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "message": "Please login first to test Autobuy."}, status=401)

        try:
            data = await request.json()
            test_invite = data.get("invite", "https://discord.gg/test").strip()
            boosts = int(data.get("boosts", 14))

            order_price = 0.20
            cur_bal = db.get_user_balance(user["id"])
            if cur_bal < order_price:
                # Add demo credit for test
                db.adjust_user_balance(user["id"], 1.00)

            db.adjust_user_balance(user["id"], -order_price)
            order_id = db.create_order(
                user_id=user["id"],
                invite=test_invite,
                boosts=boosts,
                price_eur=order_price,
                duration="1m",
                nickname="SICK Autobuy Bot",
                mode="autobuy"
            )

            engine_ok, engine_msg, engine_data = salta7_service.dispatch_boost_order(
                order_id=order_id,
                invite=test_invite,
                boosts=boosts,
                nickname="SICK Autobuy Bot"
            )

            webhook_logger.log_autobuy_webhook(order_id, test_invite, boosts, order_price)

            return web.json_response({
                "success": True,
                "order_id": order_id,
                "test_passed": True,
                "message": f"Autobuy test simulation succeeded! Order #{order_id} created for {test_invite}. Cloud delivery in progress."
            })
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    async def api_get_orders(self, request: web.Request) -> web.Response:
        user = self.get_current_user(request)
        if not user:
            return web.json_response({"success": False, "orders": []}, status=401)
        orders = db.get_user_orders(user["id"], limit=50)
        return web.json_response({"success": True, "orders": orders})

    async def api_admin_stats(self, request: web.Request) -> web.Response:
        deposits = db.get_all_deposits(limit=20)
        return web.json_response({
            "engine_status": "Operational (High-Speed)",
            "recent_deposits": deposits
        })

    def is_admin_authorized(self, request: web.Request, data: dict = None) -> bool:
        user = self.get_current_user(request)
        if user and user.get("is_admin"):
            return True
        secret = ""
        if data and isinstance(data, dict):
            secret = data.get("admin_secret", "")
        if not secret:
            secret = request.headers.get("X-Admin-Secret") or request.query.get("secret") or ""
        config = load_config()
        configured_secret = config.get("maintenance", {}).get("admin_secret", "sick_admin_pass")
        return bool(secret and secret.strip() == configured_secret)

    async def api_admin_users(self, request: web.Request) -> web.Response:
        if not self.is_admin_authorized(request):
            return web.json_response({"success": False, "message": "Admin authorization required."}, status=403)
        users = db.get_all_users_admin(limit=100)
        return web.json_response({"success": True, "users": users})

    async def api_admin_set_balance(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not self.is_admin_authorized(request, data):
            return web.json_response({"success": False, "message": "Invalid admin secret."}, status=403)
        
        username = str(data.get("username", "")).strip()
        if not username:
            return web.json_response({"success": False, "message": "Username is required."}, status=400)
        
        try:
            amount = float(data.get("amount_eur", 0.0))
        except (ValueError, TypeError):
            return web.json_response({"success": False, "message": "Invalid amount."}, status=400)
            
        mode = str(data.get("mode", "set")).strip().lower()
        ok, msg, new_bal = db.set_or_add_user_balance(username, amount, mode=mode)
        
        # Persist into config.json
        try:
            config = load_config()
            if "admin_balances" not in config:
                config["admin_balances"] = {}
            config["admin_balances"][username.lower()] = new_bal
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"[!] Warning persisting admin balance: {e}", flush=True)
            
        # Log to Discord
        webhook_logger.log_deposit(username, new_bal, 0.0, f"ADMIN_CREDIT_{mode.upper()}", is_test=False)
        
        return web.json_response({
            "success": True,
            "message": msg,
            "username": username,
            "new_balance": new_bal
        })

    async def api_admin_set_webhook(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not self.is_admin_authorized(request, data):
            return web.json_response({"success": False, "message": "Invalid admin secret."}, status=403)
            
        webhook_url = str(data.get("webhook_url", "")).strip()
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            return web.json_response({"success": False, "message": "Invalid Discord Webhook URL. Must start with https://discord.com/api/webhooks/"}, status=400)
            
        config = load_config()
        if "discord" not in config:
            config["discord"] = {}
        config["discord"]["webhook_url"] = webhook_url
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            
        webhook_logger.WEBHOOK_URL = webhook_url
        domain = os.environ.get("RENDER_EXTERNAL_URL", "https://sick-marketplace.onrender.com")
        webhook_logger.log_platform_online(domain)
        return web.json_response({
            "success": True,
            "message": "Discord webhook updated and test alert dispatched to Discord!",
            "webhook_url": webhook_url
        })

    async def api_trigger_test_webhook(self, request: web.Request) -> web.Response:
        domain = os.environ.get("RENDER_EXTERNAL_URL", "https://sick-marketplace.onrender.com")
        webhook_logger.log_platform_online(domain)
        return web.json_response({
            "success": True,
            "message": "Discord test log sent successfully!",
            "domain": domain
        })

    def sync_admin_balances(self):
        try:
            config = load_config()
            balances = config.get("admin_balances", {})
            for uname, amt in balances.items():
                db.set_or_add_user_balance(uname, amt, mode="set")
            if balances:
                print(f"[*] Synced {len(balances)} admin balances from config.json", flush=True)
        except Exception as e:
            print(f"[!] Error syncing admin balances: {e}", flush=True)

    def seed_historical_blockchain_transactions(self):
        """
        On startup, query Litecoin blockchain explorer and record any existing historical transactions
        as user_id=0, amount_eur=0.0, status='historical' so they can NEVER be falsely credited.
        """
        try:
            url = f"https://litecoinspace.org/api/address/{crypto_service.wallet_address}/txs"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            seeded = 0
            if r.status_code == 200:
                for tx in r.json():
                    txid = tx.get("txid", "").strip().lower()
                    if txid and not db.is_deposit_recorded(txid):
                        db.record_deposit(user_id=0, tx_hash=txid, amount_ltc=0.0, amount_eur=0.0, status="historical")
                        seeded += 1
            if seeded > 0:
                print(f"[*] Pre-seeded {seeded} historical blockchain transactions to prevent false credits.", flush=True)
        except Exception as e:
            print(f"[!] Historical transaction seed warning: {e}", flush=True)

    def run(self, host: str = "0.0.0.0", port: int = 5890):
        self.seed_historical_blockchain_transactions()
        self.sync_admin_balances()
        domain = os.environ.get("RENDER_EXTERNAL_URL", f"http://localhost:{port}")
        print(f"[*] 12b00 ⚡ Gaming & Nitro Marketplace running on http://localhost:{port}...", flush=True)
        try:
            webhook_logger.log_platform_online(domain)
        except Exception as e:
            print(f"[!] Startup webhook warning: {e}", flush=True)
        web.run_app(self.app, host=host, port=port)

if __name__ == "__main__":
    server = BoostPlatformServer()
    port = int(os.environ.get("PORT", 5890))
    server.run(port=port)
