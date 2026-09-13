# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import shutil
import urllib.request
import urllib.parse
import subprocess
import threading
import webbrowser

# Force UTF-8 encoding across Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

import webhook_logger

def start_backend():
    print("[*] Starting 12b00 Web Platform on http://127.0.0.1:5890 ...", flush=True)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.join(BASE_DIR, "server.py")],
        cwd=BASE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    def stream_server_logs():
        for line in proc.stdout:
            if "running on" in line or "Error" in line:
                print(f"[Server] {line.strip()}", flush=True)
    threading.Thread(target=stream_server_logs, daemon=True).start()
    return proc

def create_vanity_url(target_url):
    candidates = [
        "nitrohq",
        "sicknitro",
        "sickhq",
        "sickboost",
        "nitro-hq",
        "sick-market",
        f"sick-{int(time.time()) % 10000}"
    ]
    # 1. Try da.gd with custom branded slugs
    for cand in candidates:
        try:
            data = urllib.parse.urlencode({"url": target_url, "shorturl": cand}).encode("utf-8")
            req = urllib.request.Request("https://da.gd/s", data=data, headers={
                "User-Agent": "curl/7.68.0",
                "Content-Type": "application/x-www-form-urlencoded"
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                res = resp.read().decode("utf-8").strip()
                if res.startswith("http"):
                    return res
        except Exception:
            continue

    # 2. Try da.gd automatic short URL
    try:
        req = urllib.request.Request(f"https://da.gd/s?url={urllib.parse.quote(target_url)}", headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = resp.read().decode("utf-8").strip()
            if res.startswith("http"):
                return res
    except Exception:
        pass

    # 3. Fallback: TinyURL
    try:
        req_url = "https://tinyurl.com/api-create.php?" + urllib.parse.urlencode({"url": target_url})
        with urllib.request.urlopen(req_url, timeout=5) as resp:
            res = resp.read().decode("utf-8").strip()
            if res.startswith("http"):
                return res
    except Exception:
        pass

    return None

def load_launcher_config():
    cfg_file = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(cfg_file):
        try:
            import json
            with open(cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def start_tunnel(cfg):
    t_cfg = cfg.get("tunnel", {})
    provider = t_cfg.get("provider", "auto")
    ngrok_domain = t_cfg.get("ngrok_domain", "").strip()
    ngrok_token = t_cfg.get("ngrok_authtoken", "").strip()
    cf_token = t_cfg.get("cloudflare_token", "").strip()

    ngrok_exe = os.path.join(BASE_DIR, "ngrok.exe")
    cloudflared_exe = os.path.join(BASE_DIR, "cloudflared.exe")
    if not os.path.exists(cloudflared_exe):
        cloudflared_exe = shutil.which("cloudflared") or "cloudflared.exe"

    # 1. Check if user configured a permanent ngrok static domain
    if (provider == "ngrok" or ngrok_domain) and os.path.exists(ngrok_exe):
        clean_domain = ngrok_domain.replace("https://", "").replace("http://", "").rstrip("/")
        print(f"[*] Starting permanent ngrok tunnel on https://{clean_domain} ...", flush=True)
        if ngrok_token:
            try:
                subprocess.run([ngrok_exe, "config", "add-authtoken", ngrok_token], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        cmd = [ngrok_exe, "http", "5890", "--url", f"https://{clean_domain}"]
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc, f"https://{clean_domain}", "ngrok"

    # 2. Check if user configured a Cloudflare Named Tunnel token
    if cf_token and os.path.exists(cloudflared_exe):
        print("[*] Starting Cloudflare Named Tunnel with custom token...", flush=True)
        cmd = [cloudflared_exe, "tunnel", "run", "--token", cf_token]
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc, "https://[Deine-Eigene-Domain]", "cloudflare_named"

    # 3. Quick Cloudflare Tunnel fallback
    print("[*] Starting Cloudflare Global Enterprise Quick Tunnel...", flush=True)
    proc = subprocess.Popen(
        [cloudflared_exe, "tunnel", "--url", "http://localhost:5890", "--http-host-header", "localhost"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    live_url = capture_cloudflare_url(proc)
    return proc, live_url or "http://localhost:5890", "cloudflare_quick"

def capture_cloudflare_url(proc):
    live_domain = None
    domain_event = threading.Event()

    def reader():
        nonlocal live_domain
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                l = line.strip()
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", l)
                if m and not live_domain:
                    live_domain = m.group(0)
                    domain_event.set()
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    domain_event.wait(timeout=15)
    return live_domain

def main():
    print("=" * 68, flush=True)
    print("  ⚡ 12b00 GAMING & NITRO MARKETPLACE — PERMANENT CLOUD ENGINE", flush=True)
    print("  Official Discord: https://discord.gg/ZEXX", flush=True)
    print("  DDoS Protection  |  Cloudflare Enterprise / ngrok  |  24/7 Watchdog", flush=True)
    print("=" * 68, flush=True)
    print()

    cfg = load_launcher_config()

    # 1. Start Backend Server
    server_proc = start_backend()
    time.sleep(2)

    # 2. Start Tunnel (Permanent static domain or Cloudflare)
    tunnel_proc, live_domain, tunnel_type = start_tunnel(cfg)

    print()
    print("=" * 68, flush=True)
    print("  🎉 12b00 MARKETPLACE IST ONLINE & WELTWEIT ERREICHBAR!", flush=True)
    print(f"  🌐 Offizielle Live-URL : {live_domain}", flush=True)
    if tunnel_type == "ngrok":
        print("  💎 Status              : PERMANENTE FESTE DOMAIN (Ändert sich NIE!)", flush=True)
    else:
        print("  💡 TIPP: Für eine dauerhaft feste Wunsch-Domain (z.B. dein-shop.ngrok-free.app):", flush=True)
        print("     Führe einfach 'setup_permanent_domain.bat' aus!", flush=True)
    print("  🛠️  Wartungsmodus       : Doppelklick auf 'toggle_maintenance.bat' zum Umschalten", flush=True)
    print("  💬 Official Discord    : https://discord.gg/ZEXX", flush=True)
    print("  ⚡ Auto-Watchdog       : Aktiv (Überwacht Server & Tunnel rund um die Uhr)", flush=True)
    print("=" * 68, flush=True)
    print()

    # 3. Notify Discord Webhook
    print("[*] Sending live alert to Discord Webhook...", flush=True)
    try:
        webhook_logger.log_platform_online(live_domain)
        print("[+] Discord Webhook successfully notified with rich embed!", flush=True)
    except Exception as ex:
        print(f"[-] Discord Webhook note: {ex}", flush=True)

    # 4. Open in Default Browser
    if live_domain.startswith("https://"):
        print(f"[*] Opening {live_domain} in your browser...", flush=True)
        try:
            webbrowser.open(live_domain)
        except Exception:
            pass

    # 5. Continuous 24/7 Watchdog Loop
    print("[*] 24/7 Watchdog actively guarding server & tunnel...", flush=True)
    try:
        while True:
            time.sleep(20)
            # Check backend
            if server_proc.poll() is not None:
                print("[!] Backend crashed or closed. Restarting immediately...", flush=True)
                server_proc = start_backend()

            # Check tunnel
            if tunnel_proc.poll() is not None:
                print("[!] Tunnel disconnected. Reconnecting immediately...", flush=True)
                cfg = load_launcher_config()
                tunnel_proc, new_domain, tunnel_type = start_tunnel(cfg)
                if new_domain and new_domain != live_domain:
                    live_domain = new_domain
                    webhook_logger.log_platform_online(live_domain)
                    print(f"[+] Reconnected! Live URL: {live_domain}", flush=True)

            # Health ping
            if live_domain.startswith("https://") and "trycloudflare.com" in live_domain:
                try:
                    req = urllib.request.Request(live_domain, headers={"User-Agent": "SICK-Watchdog/1.0"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        if resp.status == 200:
                            pass
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\n[*] Shutting down SICK Platform cleanly...", flush=True)
    finally:
        try:
            server_proc.terminate()
        except Exception:
            pass
        try:
            tunnel_proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
