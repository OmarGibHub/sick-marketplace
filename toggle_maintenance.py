import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def toggle_maintenance():
    if not os.path.exists(CONFIG_PATH):
        print(f"[!] Fehler: {CONFIG_PATH} nicht gefunden.")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if "maintenance" not in cfg:
        cfg["maintenance"] = {
            "enabled": False,
            "admin_secret": "sick_admin_pass",
            "message": "Wir führen aktuell geplante Upgrades am SICK Marketplace durch.",
            "discord_url": "https://discord.gg/NitroHQ"
        }

    current_state = cfg["maintenance"].get("enabled", False)
    new_state = not current_state
    cfg["maintenance"]["enabled"] = new_state

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    if new_state:
        print("  🛠️  WARTUNGSMODUS: AKTIVIERT!")
        print("  Besucher sehen ab sofort die animierte Wartungsseite.")
        print(f"  Admin-Bypass: Öffne die Seite mit ?bypass={cfg['maintenance'].get('admin_secret', 'sick_admin_pass')}")
    else:
        print("  ✅  WARTUNGSMODUS: DEAKTIVIERT!")
        print("  Der Marketplace ist für alle Besucher wieder vollständig online.")
    print("=" * 60)

if __name__ == "__main__":
    toggle_maintenance()
