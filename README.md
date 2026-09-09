# ⚡ SICK Gaming & Nitro Marketplace

A high-performance, fully automated Discord Server Boosting Web Platform and Marketplace.
Powered by **SICK High-Speed Cloud Dispatch**, **BYOT Token Deployer**, **Litecoin (LTC)** payments, and **Live Discord Audit Webhooks**.

- **Official Discord:** [https://discord.gg/NitroHQ](https://discord.gg/NitroHQ)
- **Litecoin Wallet:** `LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc`
- **Pricing:** 14x Discord Server Boosts = **0.20 €**

---

## ✨ Features & Capabilities

1. **🔒 Exclusive Members-Only Auth Gate:**
   - Unauthenticated visitors see a sleek, branded login & registration gate.
   - Boost workspaces, API keys, order logs, and deposits are completely protected until sign-in.

2. **🔑 BYOT (Bring Your Own Tokens) Booster:**
   - **Server Invite:** Input field for any Discord server invite link or code.
   - **Your Tokens:** Paste tokens in raw format, `email:pass:token`, or `email:pass:token:refresh`.
   - **Live Token Counter:** Real-time regex detection and token count validation.
   - **Custom Bio & Profile Customizer (🪄):**
     - Custom Nickname
     - Custom Bio (About Me)
     - Avatar & Banner image URLs
     - Quick 1-click presets: 🎮 Gamer Squad, 👑 VIP Member, 🌸 Aesthetic Anime, ⚡ SICK Booster
   - Fast background dispatch and automated balance refund if any issues arise.

3. **⚡ Instant Cloud Stock Boosts:**
   - One-click server boost orders fulfilled through our automated cloud backend.
   - Select 14x Boosts (€0.20), 7x Boosts (€0.20), or 30x Overboosts (€0.43).

4. **🤖 SellAuth / Sellix Store Autobuy Webhooks:**
   - Personal API key and webhook endpoint: `https://your-domain/api/webhook/sellauth?key=sick_...`
   - Automatically fulfills Discord boost orders when customers buy on your SellAuth, Sellix, or Shoppy store.
   - Includes one-click test simulation.

5. **💳 Litecoin (LTC) Automated Deposit System:**
   - Official Wallet: `LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc`
   - Real-time exchange rate calculation (€/LTC) and QR code generation.
   - Instant transaction hash (TXID) verification with double-spend protection.
   - Demo deposit chips for quick testing.

6. **🛡️ SICK Shield Anti-DDoS & Security:**
   - IP rate-limiting middleware prevents brute-force and DDoS attacks.
   - Security headers: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`.

7. **📢 Live Discord Audit Webhooks:**
   - Rich embed notifications sent in real time to your Discord server for:
     - New User Registrations
     - User Logins
     - Litecoin Deposits (Blockchain & Demo)
     - Server Boost Dispatches (BYOT & Cloud)
     - SellAuth Store Webhook Sales
     - Security & Rate-Limit Alerts
     - Online Tunnel Status Alerts

---

## 🚀 How to Run

### Option 1: Run Online with Global HTTPS & Cloudflare Tunnel
Double-click:
```bat
start_online_service.bat
```
- Starts the web backend on port 5890.
- Launches Cloudflare Tunnel (`cloudflared`) to assign a secure, global `https://*.trycloudflare.com` domain.
- Automatically sends a Discord webhook embed with the live URL and opens it in your browser!

### Option 2: Run Locally
Double-click:
```bat
start_web_service.bat
```
- Accessible locally at: `http://localhost:5890`

---

## 📁 Project Structure
- `server.py`: Async web server (aiohttp) with security middleware, APIs, and authentication.
- `database.py`: SQLite database for users, balances, boost orders, and deposits.
- `salta7_service.py`: Cloud boost dispatch and token parsing engine.
- `crypto_service.py`: Litecoin blockchain verification and rate converter.
- `webhook_logger.py`: Discord rich embed audit logger.
- `online_launcher.py`: Cloudflare tunnel manager with webhook integration.
- `frontend/`:
  - `index.html`: Responsive, cyberpunk/electric cyan marketplace UI with Auth Gate.
  - `style.css`: Modern liquid glass / dark mode styling.
  - `app.js`: Interactive client engine for boosts, auth, orders, and autobuy.
  - `assets/`: Official SICK 3D logo (`sick_logo.jpg`) and banner (`sick_banner.webp`).
