import threading
import time
import requests
from typing import Optional, Dict, Any

WEBHOOK_URL = "https://discord.com/api/webhooks/1547227892742750269/BYU67OPDjuRN_wLdNjbWIdxPXX8Q30fNa8V46izw51ojOjFl-FogPOLLEb0DCTPRTPA-"
SICK_CYAN = 0x00E5FF
SICK_GREEN = 0x10B981
SICK_PURPLE = 0x8B5CF6
SICK_RED = 0xEF4444
SICK_ORANGE = 0xF59E0B

def _send_embed_async(payload: Dict[str, Any]):
    def worker():
        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=8)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()

def log_user_registered(username: str, ip: str = "Unknown"):
    payload = {
        "username": "SICK ⚡ Audit Log",
        "avatar_url": "https://cdn.discordapp.com/emojis/1083756285817819176.webp",
        "embeds": [{
            "title": "👤 New Member Registered",
            "description": f"**Username:** `{username}`\n**IP Address:** `{ip}`",
            "color": SICK_CYAN,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK Gaming & Nitro Marketplace • gg/NitroHQ"}
        }]
    }
    _send_embed_async(payload)

def log_user_login(username: str, ip: str = "Unknown"):
    payload = {
        "username": "SICK ⚡ Audit Log",
        "embeds": [{
            "title": "🔐 Member Logged In",
            "description": f"**User:** `{username}`\n**IP Address:** `{ip}`",
            "color": 0x38BDF8,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK Security Stream • gg/NitroHQ"}
        }]
    }
    _send_embed_async(payload)

def log_deposit(username: str, amount_eur: float, amount_ltc: float, tx_hash: str, is_test: bool = False):
    tag = "[DEMO TEST]" if is_test else "[BLOCKCHAIN CONFIRMED]"
    payload = {
        "username": "SICK ⚡ Financial Stream",
        "embeds": [{
            "title": f"💳 Litecoin Deposit Received {tag}",
            "color": SICK_GREEN,
            "fields": [
                {"name": "User", "value": f"`{username}`", "inline": True},
                {"name": "Amount (EUR)", "value": f"**{amount_eur:.2f} €**", "inline": True},
                {"name": "Amount (LTC)", "value": f"**{amount_ltc:.6f} LTC**", "inline": True},
                {"name": "TXID / Ref", "value": f"`{tx_hash[:32]}...`", "inline": False},
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK Treasury • LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc"}
        }]
    }
    _send_embed_async(payload)

def log_boost_order(username: str, order_id: int, invite: str, boosts: int, mode: str, price_eur: float, nickname: str = "", tokens_count: int = 0):
    mode_tag = "🔑 BYOT (Own Tokens)" if mode == "byot" else "⚡ Instant Cloud"
    fields = [
        {"name": "Order ID", "value": f"**#{order_id}**", "inline": True},
        {"name": "Mode", "value": f"`{mode_tag}`", "inline": True},
        {"name": "User", "value": f"`{username}`", "inline": True},
        {"name": "Target Invite", "value": f"`{invite}`", "inline": True},
        {"name": "Boosts", "value": f"**{boosts}x Boosts**", "inline": True},
        {"name": "Price", "value": f"**{price_eur:.2f} €**", "inline": True}
    ]
    if nickname:
        fields.append({"name": "Custom Nickname", "value": f"`{nickname}`", "inline": True})
    if tokens_count:
        fields.append({"name": "Tokens Loaded", "value": f"**{tokens_count} tokens**", "inline": True})

    payload = {
        "username": "SICK ⚡ Boost Fulfillment",
        "embeds": [{
            "title": f"🚀 Boost Dispatch Active — #{order_id}",
            "color": SICK_PURPLE if mode == "byot" else SICK_CYAN,
            "fields": fields,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK Automated Fulfillment Engine • gg/NitroHQ"}
        }]
    }
    _send_embed_async(payload)

def log_autobuy_webhook(order_id: int, invite: str, boosts: int, price_eur: float):
    payload = {
        "username": "SICK ⚡ Autobuy Dispatch",
        "embeds": [{
            "title": f"🤖 SellAuth Store Sale Fulfilled — #{order_id}",
            "color": SICK_ORANGE,
            "fields": [
                {"name": "Order #", "value": f"`#{order_id}`", "inline": True},
                {"name": "Target Invite", "value": f"`{invite}`", "inline": True},
                {"name": "Boosts Amount", "value": f"**{boosts}x Boosts**", "inline": True},
                {"name": "Fee", "value": f"**{price_eur:.2f} €**", "inline": True}
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK SellAuth / Sellix Store Hook • gg/NitroHQ"}
        }]
    }
    _send_embed_async(payload)

def log_security_alert(ip: str, reason: str, details: str = ""):
    payload = {
        "username": "SICK 🛡️ Shield Firewall",
        "embeds": [{
            "title": "⚠️ Security / Rate-Limit Triggered",
            "color": SICK_RED,
            "fields": [
                {"name": "Client IP", "value": f"`{ip}`", "inline": True},
                {"name": "Reason", "value": f"**{reason}**", "inline": True},
                {"name": "Details", "value": f"`{details[:200]}`" if details else "None", "inline": False}
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK Anti-DDoS & Attack Protection Active"}
        }]
    }
    _send_embed_async(payload)

def log_platform_online(public_url: str):
    payload = {
        "username": "SICK ⚡ System Status",
        "embeds": [{
            "title": "🌐 SICK Marketplace is Now LIVE Worldwide!",
            "description": f"**Public Domain:** {public_url}\n**Discord:** https://discord.gg/NitroHQ",
            "color": SICK_CYAN,
            "fields": [
                {"name": "Public URL", "value": f"[Open Marketplace]({public_url})", "inline": True},
                {"name": "DDoS Shield", "value": "✅ Cloudflare Active", "inline": True},
                {"name": "Boost Pricing", "value": "⚡ 14x for 0.20 €", "inline": True},
                {"name": "Wallet (LTC)", "value": "`LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc`", "inline": False}
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "footer": {"text": "SICK High-Speed Cloud Engine Online"}
        }]
    }
    _send_embed_async(payload)
