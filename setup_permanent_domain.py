# -*- coding: utf-8 -*-
import json
import os
import sys
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
NGROK_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ngrok.exe")

def setup():
    print("=" * 68)
    print("  🌐 SICK MARKETPLACE — PERMANENTE FESTE DOMAIN EINRICHTEN")
    print("  Damit bleibt deine Shop-Adresse für immer exakt gleich!")
    print("=" * 68)
    print()
    print("  1. Kostenlose permanente Domain über ngrok (Empfohlen - 100% kostenlos)")
    print("     -> 1 feste Domain gratis auf https://dashboard.ngrok.com")
    print("  2. Cloudflare Named Tunnel Token (Für eigene Domains)")
    print("  3. Zurücksetzen auf automatischen Cloudflare-Tunnel")
    print()

    choice = input("Wähle eine Option (1, 2 oder 3): ").strip()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "tunnel" not in cfg:
        cfg["tunnel"] = {
            "provider": "auto",
            "ngrok_authtoken": "",
            "ngrok_domain": "",
            "cloudflare_token": ""
        }

    if choice == "1":
        print()
        print("--- ngrok Kostenlose Permanente Domain ---")
        print("Falls du noch kein ngrok-Konto hast:")
        print("1. Gehe auf https://dashboard.ngrok.com/signup (kostenlos mit Google anmelden)")
        print("2. Unter 'Cloud Edge' -> 'Domains' siehst du deine kostenlose statische Domain")
        print("   (z.B. dein-name.ngrok-free.app)")
        print("3. Unter 'Your Authtoken' findest du dein Token.")
        print()

        domain = input("Gib deine feste ngrok Domain ein (z.B. dein-name.ngrok-free.app): ").strip()
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
        
        token = input("Gib dein ngrok Authtoken ein: ").strip()

        if domain:
            cfg["tunnel"]["provider"] = "ngrok"
            cfg["tunnel"]["ngrok_domain"] = domain
            if token:
                cfg["tunnel"]["ngrok_authtoken"] = token
                # Configure ngrok binary
                if os.path.exists(NGROK_EXE):
                    try:
                        subprocess.run([NGROK_EXE, "config", "add-authtoken", token], check=True)
                        print("[+] ngrok Authtoken erfolgreich im System hinterlegt!")
                    except Exception as e:
                        print(f"[!] Warnung beim Speichern des Tokens: {e}")

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)

            print()
            print("=" * 68)
            print("  🎉 ERFOLG! DEINE FESTE DOMAIN WURDE GESPEICHERT:")
            print(f"  🌐 https://{domain}")
            print("  Ab sofort bleibt diese URL für immer exakt gleich, egal wie oft")
            print("  du den Server neustartest oder Wartungsarbeiten machst!")
            print("=" * 68)

    elif choice == "2":
        print()
        token = input("Gib deinen Cloudflare Tunnel Token ein: ").strip()
        if token:
            cfg["tunnel"]["provider"] = "cloudflare_named"
            cfg["tunnel"]["cloudflare_token"] = token
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            print("[+] Cloudflare Tunnel Token gespeichert!")

    elif choice == "3":
        cfg["tunnel"]["provider"] = "auto"
        cfg["tunnel"]["ngrok_domain"] = ""
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print("[+] Zurückgesetzt auf automatischen Schnell-Tunnel.")

if __name__ == "__main__":
    setup()
