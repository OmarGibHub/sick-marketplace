// ==========================================================================
// ⚡ SICK GAMING & NITRO MARKETPLACE — FRONTEND ENGINE 4.0
// Simplified, modern tabbed workspace & automated Litecoin fulfillment
// ==========================================================================

let currentUser = null;
let currentMainTab = "boost";
let activeAuthMode = "login";
let activeGateMode = "login";
let pollingTimer = null;
let blockchainScannerTimer = null;
let activeInvoiceData = null;
let invoiceCountdownSeconds = 0;
let invoiceTimerInterval = null;

// --- DOM INITIALIZATION ---
document.addEventListener("DOMContentLoaded", async () => {
  await checkAuthStatus();
  await loadPlatformInfo();
  await loadActiveInvoice();
  updateTokenCounter();
  updateLtcPreview(0.20);
});

// --- MAIN TAB SWITCHER ---
function switchMainTab(tabName) {
  currentMainTab = tabName;
  const tabs = ["boost", "deposit", "orders"];

  tabs.forEach(t => {
    const pane = document.getElementById(`pane${capitalize(t)}`);
    const btn = document.getElementById(`tabBtn${capitalize(t)}`);
    const navLink = document.getElementById(`navLink${capitalize(t)}`);

    if (t === tabName) {
      if (pane) {
        pane.style.display = "block";
        pane.classList.add("active");
      }
      if (btn) btn.classList.add("active");
      if (navLink) navLink.classList.add("active");
    } else {
      if (pane) {
        pane.style.display = "none";
        pane.classList.remove("active");
      }
      if (btn) btn.classList.remove("active");
      if (navLink) navLink.classList.remove("active");
    }
  });

  if (tabName === "orders") {
    loadUserOrders();
  }
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function scrollToDeposit() {
  switchMainTab("deposit");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function scrollToOrders() {
  switchMainTab("orders");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// --- AUTHENTICATION STATE & WORKSPACE VISIBILITY ---

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/me");
    if (res.ok) {
      const data = await res.json();
      if (data.authenticated && data.user) {
        currentUser = data.user;
        setWorkspaceVisibility(true);
        renderNavUser();
        await loadUserOrders();
        
        startOrderPolling();
        startBlockchainAutoScanner();
        calculateByotPrice();
        return;
      }
    }
  } catch (e) {}

  currentUser = null;
  setWorkspaceVisibility(false);
  renderNavGuest();
}

function setWorkspaceVisibility(isAuthenticated) {
  const gateEl = document.getElementById("authGateContainer");
  const appEl = document.getElementById("authenticatedAppContainer");
  const navLinks = document.getElementById("mainNavLinks");

  if (isAuthenticated) {
    if (gateEl) gateEl.style.display = "none";
    if (appEl) appEl.style.display = "block";
    if (navLinks) navLinks.style.display = "flex";
  } else {
    if (gateEl) gateEl.style.display = "flex";
    if (appEl) appEl.style.display = "none";
    if (navLinks) navLinks.style.display = "none";
  }
}

function renderNavGuest() {
  const container = document.getElementById("navAuthContainer");
  if (!container) return;
  container.innerHTML = `
    <button class="btn btn-outline" onclick="openAuthModal('login')">Anmelden</button>
    <button class="btn btn-primary glow-btn" onclick="openAuthModal('register')">Registrieren</button>
  `;
}

function renderNavUser() {
  const container = document.getElementById("navAuthContainer");
  if (!currentUser) return;

  const balFormatted = currentUser.balance_eur.toFixed(2) + " €";

  // Update top workspace balance indicators
  const topBal = document.getElementById("topBalanceDisplay");
  if (topBal) topBal.textContent = balFormatted;

  const orderBal = document.getElementById("displayAvailableUserBalance");
  if (orderBal) orderBal.textContent = balFormatted;

  if (container) {
    container.innerHTML = `
      <div class="user-pill">
        <button class="user-profile-btn" onclick="openProfileModal()" title="Profil & Einstellungen">
          <span>👤 ${escapeHtml(currentUser.username)}</span>
          <span style="font-size:0.75rem;color:var(--text-dim);">⚙️</span>
        </button>
        <span class="user-balance-badge" id="navBalanceDisplay">${balFormatted}</span>
        <button class="btn btn-sm btn-secondary" onclick="scrollToDeposit()" title="Guthaben aufladen">+ Aufladen</button>
        <button class="btn btn-sm btn-outline" onclick="handleLogout()" title="Abmelden">Logout</button>
      </div>
    `;
  }
}

// --- AUTH GATE TABS & SUBMISSION ---

function switchGateTab(mode) {
  activeGateMode = mode;
  const tabLogin = document.getElementById("gateTabLoginBtn");
  const tabRegister = document.getElementById("gateTabRegisterBtn");
  const submitBtn = document.getElementById("gateAuthSubmitBtn");
  const errorEl = document.getElementById("gateAuthErrorMsg");

  if (errorEl) errorEl.style.display = "none";

  if (mode === "login") {
    if (tabLogin) tabLogin.classList.add("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (submitBtn) submitBtn.textContent = "Jetzt Einloggen & Boosten";
  } else {
    if (tabRegister) tabRegister.classList.add("active");
    if (tabLogin) tabLogin.classList.remove("active");
    if (submitBtn) submitBtn.textContent = "Konto erstellen & Starten";
  }
}

async function handleGateAuthSubmit(event) {
  event.preventDefault();
  const usernameInput = document.getElementById("gateAuthUsernameInput");
  const passwordInput = document.getElementById("gateAuthPasswordInput");
  const errorEl = document.getElementById("gateAuthErrorMsg");
  const submitBtn = document.getElementById("gateAuthSubmitBtn");

  const username = usernameInput ? usernameInput.value.trim() : "";
  const password = passwordInput ? passwordInput.value.trim() : "";

  if (!username || !password) return;

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Authentifiziere...";
  }
  if (errorEl) errorEl.style.display = "none";

  try {
    const endpoint = activeGateMode === "register" ? "/api/auth/register" : "/api/auth/login";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      currentUser = data.user;
      setWorkspaceVisibility(true);
      renderNavUser();
      calculateByotPrice();
      showToast(activeGateMode === "register" ? "Konto erfolgreich erstellt! Willkommen bei SICK." : `Willkommen zurück, ${currentUser.username}!`, "success");
      await loadUserOrders();
      
      startOrderPolling();
      startBlockchainAutoScanner();
    } else {
      if (errorEl) {
        errorEl.textContent = data.message || "Anmeldung fehlgeschlagen.";
        errorEl.style.display = "block";
      }
    }
  } catch (err) {
    if (errorEl) {
      errorEl.textContent = "Verbindungsfehler. Bitte erneut versuchen.";
      errorEl.style.display = "block";
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = activeGateMode === "register" ? "Konto erstellen & Starten" : "Jetzt Einloggen & Boosten";
    }
  }
}

// --- HEADER QUICK AUTH MODAL ---

function openAuthModal(mode = "login") {
  activeAuthMode = mode;
  switchAuthTab(mode);
  const overlay = document.getElementById("authModalOverlay");
  if (overlay) overlay.classList.add("active");
  const err = document.getElementById("authErrorMsg");
  if (err) err.style.display = "none";
  const userIn = document.getElementById("authUsernameInput");
  if (userIn) userIn.focus();
}

function closeAuthModal(e) {
  if (e && e.target !== e.currentTarget) return;
  const overlay = document.getElementById("authModalOverlay");
  if (overlay) overlay.classList.remove("active");
}

function switchAuthTab(mode) {
  activeAuthMode = mode;
  const tabLogin = document.getElementById("tabLoginBtn");
  const tabRegister = document.getElementById("tabRegisterBtn");
  const submitBtn = document.getElementById("authSubmitBtn");

  if (mode === "login") {
    if (tabLogin) tabLogin.classList.add("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (submitBtn) submitBtn.textContent = "Anmelden";
  } else {
    if (tabRegister) tabRegister.classList.add("active");
    if (tabLogin) tabLogin.classList.remove("active");
    if (submitBtn) submitBtn.textContent = "Konto registrieren";
  }
  const err = document.getElementById("authErrorMsg");
  if (err) err.style.display = "none";
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const username = document.getElementById("authUsernameInput").value.trim();
  const password = document.getElementById("authPasswordInput").value.trim();
  const errorEl = document.getElementById("authErrorMsg");
  const submitBtn = document.getElementById("authSubmitBtn");

  if (!username || !password) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Wird verarbeitet...";
  errorEl.style.display = "none";

  try {
    const endpoint = activeAuthMode === "register" ? "/api/auth/register" : "/api/auth/login";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      currentUser = data.user;
      setWorkspaceVisibility(true);
      renderNavUser();
      calculateByotPrice();
      closeAuthModal();
      showToast(activeAuthMode === "register" ? "Konto erfolgreich erstellt! Willkommen bei SICK." : `Willkommen zurück, ${currentUser.username}!`, "success");
      await loadUserOrders();
      
      startOrderPolling();
      startBlockchainAutoScanner();
    } else {
      errorEl.textContent = data.message || "Anmeldung fehlgeschlagen.";
      errorEl.style.display = "block";
    }
  } catch (err) {
    errorEl.textContent = "Serververbindungsfehler.";
    errorEl.style.display = "block";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = activeAuthMode === "register" ? "Konto registrieren" : "Anmelden";
  }
}

async function handleLogout() {
  try {
    await fetch("/api/auth/logout", { method: "POST" });
  } catch (e) {}
  currentUser = null;
  setWorkspaceVisibility(false);
  renderNavGuest();
  showToast("Erfolgreich abgemeldet.", "success");
  if (pollingTimer) clearInterval(pollingTimer);
  stopBlockchainAutoScanner();
  const tbody = document.getElementById("ordersTableBody");
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="8" class="table-empty-msg">Bitte logge dich ein, um deine Bestellungen zu sehen.</td></tr>`;
  }
  closeProfileModal();
}

// --- USER PROFILE & ACCOUNT SETTINGS ---

function openProfileModal() {
  if (!currentUser) {
    openAuthModal("login");
    return;
  }
  const nameEl = document.getElementById("profileModalUsername");
  const balEl = document.getElementById("profileModalBalance");
  const keyInput = document.getElementById("profileApiKeyInput");
  const overlay = document.getElementById("profileModalOverlay");

  if (nameEl) nameEl.textContent = currentUser.username;
  if (balEl) balEl.textContent = `Guthaben: ${currentUser.balance_eur.toFixed(2)} €`;
  if (keyInput) keyInput.value = currentUser.api_key || "";
  if (overlay) overlay.classList.add("active");
}

function closeProfileModal(e) {
  if (e && e.target !== e.currentTarget) return;
  const overlay = document.getElementById("profileModalOverlay");
  if (overlay) overlay.classList.remove("active");
}

function copyProfileApiKey() {
  const input = document.getElementById("profileApiKeyInput");
  if (!input || !input.value) return;
  navigator.clipboard.writeText(input.value).then(() => {
    showToast("SICK API Key in die Zwischenablage kopiert!", "success");
  }).catch(() => {
    showToast("API Key: " + input.value, "success");
  });
}

async function handleRegenerateKey() {
  if (!currentUser) return;
  if (!confirm("Möchtest du wirklich einen neuen SICK API-Key generieren?")) {
    return;
  }
  try {
    const res = await fetch("/api/user/regenerate-key", { method: "POST" });
    const data = await res.json();
    if (res.ok && data.success) {
      currentUser.api_key = data.api_key;
      const keyInput = document.getElementById("profileApiKeyInput");
      if (keyInput) keyInput.value = data.api_key;
      showToast("Neuer SICK API Key erfolgreich generiert!", "success");
    } else {
      showToast(data.message || "Fehler beim Generieren des Keys.", "error");
    }
  } catch (e) {
    showToast("Serverfehler beim Generieren des Keys.", "error");
  }
}

async function handleChangePassword(event) {
  event.preventDefault();
  const currentPass = document.getElementById("currentPassInput").value.trim();
  const newPass = document.getElementById("newPassInput").value.trim();
  const btn = document.getElementById("btnSubmitPassChange");

  if (!currentPass || !newPass) return;
  if (newPass.length < 4) {
    showToast("Das neue Passwort muss mindestens 4 Zeichen lang sein.", "error");
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Wird aktualisiert...";
  }

  try {
    const res = await fetch("/api/user/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPass, new_password: newPass })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast("Passwort erfolgreich geändert!", "success");
      document.getElementById("currentPassInput").value = "";
      document.getElementById("newPassInput").value = "";
      closeProfileModal();
    } else {
      showToast(data.message || "Fehler beim Ändern des Passworts.", "error");
    }
  } catch (e) {
    showToast("Serverfehler beim Ändern des Passworts.", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Passwort aktualisieren";
    }
  }
}

// --- PLATFORM INFO & RATES ---

async function loadPlatformInfo() {
  try {
    const res = await fetch("/api/payment/info?amount=0.20");
    if (res.ok) {
      const data = await res.json();
      if (data.wallet_address) {
        const addrField = document.getElementById("invoiceFieldAddress");
        if (addrField && !addrField.textContent.trim()) {
          addrField.textContent = data.wallet_address;
        }
      }
    }
  } catch (e) {}
}

// --- BYOT TOKEN PARSER & COUNTER ---

function parseTokensFromText(text) {
  if (!text) return [];
  const lines = text.trim().split(/\r?\n/);
  const valid = [];
  const seen = new Set();

  for (let line of lines) {
    line = line.trim().replace(/^['"`]+|['"`]+$/g, '');
    if (!line || line.startsWith("#")) continue;

    let token = null;
    if (line.includes(":")) {
      const parts = line.split(":");
      for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i].trim();
        if (p.length >= 50 && !p.includes("@") && !p.includes("/")) {
          token = p;
          break;
        }
      }
      if (!token && parts[parts.length - 1].trim().length >= 24) {
        token = parts[parts.length - 1].trim();
      }
    } else {
      const match = line.match(/([A-Za-z0-9_\-]{24,28}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,38})/);
      if (match) {
        token = match[1];
      } else if (line.length >= 50) {
        token = line;
      }
    }

    if (token && !seen.has(token)) {
      valid.push(token);
      seen.add(token);
    }
  }
  return valid;
}

function updateTokenCounter() {
  const textarea = document.getElementById("byotTokensTextarea");
  const counterBadge = document.getElementById("byotTokenCounter");
  if (!textarea || !counterBadge) return;

  const count = parseTokensFromText(textarea.value).length;
  if (count > 0) {
    counterBadge.textContent = `${count} Token${count > 1 ? 's' : ''} erkannt`;
    counterBadge.classList.add("has-tokens");
  } else {
    counterBadge.textContent = `0 Tokens erkannt`;
    counterBadge.classList.remove("has-tokens");
  }
  calculateByotPrice();
}

// --- DYNAMIC BYOT PRICING & SMART BUTTON ---
// Every 14 boosts = 0.20 € (0.20 € per pack)
function calculateByotPrice() {
  const input = document.getElementById("byotBoostsCountInput");
  const textarea = document.getElementById("byotTokensTextarea");
  const btn = document.getElementById("btnStartByotBoost");
  const btnText = document.getElementById("byotStartBtnText");
  const costDisplay = document.getElementById("displayTotalOrderCost");
  const balDisplay = document.getElementById("displayAvailableUserBalance");

  let val = parseInt(input ? input.value : 14);
  if (isNaN(val) || val <= 0) {
    const count = textarea ? parseTokensFromText(textarea.value).length : 0;
    val = Math.max(14, count * 2);
  }

  const packs = Math.max(1, Math.ceil(val / 14.0));
  const price = parseFloat((packs * 0.20).toFixed(2));
  const priceStr = price.toFixed(2).replace(".", ",") + " €";

  if (costDisplay) costDisplay.textContent = priceStr;

  const userBal = currentUser ? currentUser.balance_eur : 0;
  if (balDisplay) {
    balDisplay.textContent = userBal.toFixed(2).replace(".", ",") + " €";
  }

  if (btnText && btn) {
    if (currentUser && userBal < price) {
      btnText.textContent = `Guthaben aufladen (${priceStr} benötigt)`;
      btn.classList.add("needs-deposit");
    } else {
      btnText.textContent = `Jetzt Server Boosten (${priceStr})`;
      btn.classList.remove("needs-deposit");
    }
  }

  return price;
}

function stepBoosts(delta) {
  const input = document.getElementById("byotBoostsCountInput");
  if (!input) return;
  let val = parseInt(input.value) || 0;
  val = Math.max(0, Math.min(200, val + delta));
  input.value = val;

  document.querySelectorAll(".boost-preset-btn").forEach(b => {
    b.classList.toggle("active", parseInt(b.getAttribute("data-num")) === val);
  });

  calculateByotPrice();
}

function setBoostsPreset(num) {
  const input = document.getElementById("byotBoostsCountInput");
  if (input) {
    input.value = num;
  }
  document.querySelectorAll(".boost-preset-btn").forEach(b => {
    b.classList.toggle("active", parseInt(b.getAttribute("data-num")) === num);
  });
  calculateByotPrice();
}

// --- PROFILE ACCORDION & PRESETS ---

function toggleProfileDrawer() {
  const drawer = document.getElementById("profileDrawerCard");
  const btn = document.getElementById("btnToggleProfileDrawer");
  if (!drawer) return;

  if (drawer.style.display === "none") {
    drawer.style.display = "block";
    if (btn) btn.classList.add("active");
  } else {
    drawer.style.display = "none";
    if (btn) btn.classList.remove("active");
  }
}

function applyProfilePreset(presetKey) {
  const nickInput = document.getElementById("byotNickInput");
  const bioTextarea = document.getElementById("byotBioTextarea");
  const avatarInput = document.getElementById("byotAvatarInput");
  const bannerInput = document.getElementById("byotBannerInput");

  if (presetKey === "gamer") {
    nickInput.value = "🎮 Pro Gamer";
    bioTextarea.value = "Level 100 Boss 🕹️ Ready for scrims | Playing Discord | GG WP!";
    showToast("Preset 'Gamer Squad' angewendet!", "success");
  } else if (presetKey === "vip") {
    nickInput.value = "👑 Server VIP";
    bioTextarea.value = "✨ Certified SICK Booster • Elite Member • Boosting this server to Level 3!";
    showToast("Preset 'VIP Member' angewendet!", "success");
  } else if (presetKey === "anime") {
    nickInput.value = "🌸 Senpai";
    bioTextarea.value = "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧ Just an otaku boosting awesome servers! 🍜";
    showToast("Preset 'Aesthetic Anime' angewendet!", "success");
  } else if (presetKey === "sick") {
    nickInput.value = "⚡ SICK Booster";
    bioTextarea.value = "🚀 Supercharged with SICK Marketplace • discord.gg/NitroHQ!";
    showToast("Preset 'SICK Booster' angewendet!", "success");
  } else if (presetKey === "clear") {
    nickInput.value = "";
    bioTextarea.value = "";
    avatarInput.value = "";
    bannerInput.value = "";
    showToast("Custom Profil zurückgesetzt.", "success");
  }
}

// --- BYOT BOOST ORDER PLACEMENT ---

async function handlePlaceByotOrder() {
  if (!currentUser) {
    openAuthModal("login");
    showToast("Bitte logge dich zuerst ein.", "error");
    return;
  }

  const price = calculateByotPrice();
  if (currentUser.balance_eur < price) {
    showToast(`Dein Guthaben (${currentUser.balance_eur.toFixed(2)} €) reicht nicht aus. Lade kurz ${price.toFixed(2)} € auf!`, "error");
    scrollToDeposit();
    return;
  }

  const inviteInput = document.getElementById("byotInviteInput");
  const invite = inviteInput ? inviteInput.value.trim() : "";
  const rawTokens = document.getElementById("byotTokensTextarea")?.value.trim() || "";
  const boostsNeeded = parseInt(document.getElementById("byotBoostsCountInput")?.value) || 0;
  const nickname = document.getElementById("byotNickInput")?.value.trim() || "";
  const bio = document.getElementById("byotBioTextarea")?.value.trim() || "";
  const avatar = document.getElementById("byotAvatarInput")?.value.trim() || "";
  const banner = document.getElementById("byotBannerInput")?.value.trim() || "";
  const btn = document.getElementById("btnStartByotBoost");

  if (!invite) {
    showToast("Bitte gib den Discord Server-Invite ein!", "error");
    if (inviteInput) inviteInput.focus();
    return;
  }

  const tokensList = parseTokensFromText(rawTokens);
  if (tokensList.length === 0) {
    showToast("Bitte füge deine Tokens in das Feld ein!", "error");
    document.getElementById("byotTokensTextarea")?.focus();
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" class="spin-icon"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>
    <span>Starte Boosts über die SICK Cloud Engine...</span>
  `;

  try {
    const res = await fetch("/api/boost/byot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        invite,
        tokens: tokensList,
        boosts_needed: boostsNeeded,
        nickname,
        bio,
        avatar,
        banner,
        duration: "1m"
      })
    });

    const data = await res.json();

    if (res.ok && data.success) {
      showToast(`🎉 Bestellung #${data.order_id} gestartet! ${data.tokens_count} Tokens eingesetzt.`, "success");
      currentUser.balance_eur = data.new_balance;
      renderNavUser();
      calculateByotPrice();
      if (inviteInput) inviteInput.value = "";
      const tokensArea = document.getElementById("byotTokensTextarea");
      if (tokensArea) tokensArea.value = "";
      updateTokenCounter();
      await loadUserOrders();
      scrollToOrders();
    } else if (data.insufficient_balance) {
      showToast(`Guthaben reicht nicht aus (${data.current_balance.toFixed(2)} €). Bitte lade kurz per Litecoin auf!`, "error");
      scrollToDeposit();
    } else {
      showToast(data.message || "Fehler beim Starten der Bestellung.", "error");
      if (data.refunded) {
        currentUser.balance_eur = data.new_balance;
        renderNavUser();
        calculateByotPrice();
      }
    }
  } catch (err) {
    showToast("Serverfehler beim Starten des Boosts.", "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
      <span id="byotStartBtnText">Jetzt Server Boosten (0,20 €)</span>
    `;
    calculateByotPrice();
  }
}

// --- LITECOIN (LTC) DEPOSITS & INVOICE WORKFLOW ---

async function loadActiveInvoice() {
  try {
    const res = await fetch("/api/payment/invoice");
    if (res.ok) {
      const data = await res.json();
      if (data.success && data.invoice) {
        populateInvoiceFields(data.invoice);
        const notice = document.getElementById("activeInvoiceNotice");
        const noticeAmt = document.getElementById("activeNoticeAmount");
        if (notice && noticeAmt && data.invoice.status !== "completed") {
          noticeAmt.textContent = `${data.invoice.amount_eur.toFixed(2)} €`;
          notice.style.display = "flex";
        }
      }
    }
  } catch (e) {}
}

function showAmountStep() {
  const stepAmount = document.getElementById("depositAmountStep");
  const stepInvoice = document.getElementById("invoiceActiveContainer");
  const title = document.getElementById("depositHeaderTitle");
  const sub = document.getElementById("depositHeaderSubtitle");

  if (stepInvoice) stepInvoice.style.display = "none";
  if (stepAmount) stepAmount.style.display = "flex";

  if (title) title.textContent = "Guthaben aufladen";
  if (sub) sub.textContent = "Zahle sicher mit Litecoin (LTC) • 100% automatische Gutschrift";
}

function showInvoiceStep() {
  const stepAmount = document.getElementById("depositAmountStep");
  const stepInvoice = document.getElementById("invoiceActiveContainer");
  const title = document.getElementById("depositHeaderTitle");
  const sub = document.getElementById("depositHeaderSubtitle");

  if (stepAmount) stepAmount.style.display = "none";
  if (stepInvoice) stepInvoice.style.display = "flex";

  if (title) title.textContent = "Litecoin (LTC) Checkout";
  if (sub) sub.textContent = "Sende den exakten LTC-Betrag zur automatischen Gutschrift";
}

function setDepositAmount(amount, el) {
  document.querySelectorAll("#amountChipsContainer .amount-chip").forEach(c => c.classList.remove("active"));
  if (el) el.classList.add("active");
  const input = document.getElementById("customAmountInput");
  if (input) input.value = amount.toFixed(2);
  updateLtcPreview(amount);
}

function onCustomAmountInput(val) {
  const amt = parseFloat(val) || 0;
  document.querySelectorAll("#amountChipsContainer .amount-chip").forEach(c => {
    const chipAmt = parseFloat(c.getAttribute("data-amt"));
    c.classList.toggle("active", Math.abs(chipAmt - amt) < 0.01);
  });
  updateLtcPreview(amt);
}

function updateLtcPreview(eurAmount) {
  const preview = document.getElementById("previewLtcAmount");
  if (!preview) return;
  // Estimate: ~46.5 EUR per LTC => 1 EUR ≈ 0.021496 LTC
  const ltc = Math.max(0, eurAmount * 0.021496);
  preview.textContent = `${ltc.toFixed(5)} LTC`;
}

async function proceedToInvoice() {
  const input = document.getElementById("customAmountInput");
  let amt = parseFloat(input ? input.value : 0.20) || 0.20;
  if (amt < 0.20) amt = 0.20;
  if (input) input.value = amt.toFixed(2);

  if (!currentUser) {
    showToast("Bitte logge dich zuerst ein.", "info");
    openAuthModal("login");
    return;
  }

  const btn = document.getElementById("btnProceedToInvoice");
  const btnText = document.getElementById("btnProceedText");
  if (btn) btn.disabled = true;
  if (btnText) btnText.textContent = "Generiere Blockchain-Rechnung...";

  try {
    const res = await fetch("/api/payment/invoice/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount_eur: amt })
    });
    const data = await res.json();
    if (res.ok && data.success && data.invoice) {
      renderInvoice(data.invoice);
      showToast(`⚡ Litecoin Rechnung für ${amt.toFixed(2)} € erstellt!`, "success");
    } else {
      showToast(data.message || "Fehler beim Erstellen der Rechnung.", "error");
    }
  } catch (e) {
    showToast("Verbindungsfehler beim Erstellen der Rechnung.", "error");
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = "Litecoin-Zahlung starten";
  }
}

function populateInvoiceFields(inv) {
  activeInvoiceData = inv;

  const qrImg = document.getElementById("invoiceQrImage");
  const receiveVal = document.getElementById("invoiceReceiveVal");
  const fieldLtc = document.getElementById("invoiceFieldLtc");
  const fieldAddress = document.getElementById("invoiceFieldAddress");
  const fieldPaymentId = document.getElementById("invoiceFieldPaymentId");
  const statusBadge = document.getElementById("invoiceStatusBadge");
  const statusText = document.getElementById("invoiceStatusText");

  if (qrImg && inv.qr_url) qrImg.src = inv.qr_url;
  if (receiveVal) receiveVal.textContent = `${inv.amount_eur.toFixed(2).replace(".", ",")} EUR`;
  if (fieldLtc) fieldLtc.textContent = inv.amount_ltc_str || `${inv.amount_ltc_raw.toFixed(8)} LTC`;
  if (fieldAddress) fieldAddress.textContent = inv.wallet_address;
  if (fieldPaymentId) fieldPaymentId.textContent = inv.payment_id;

  if (inv.status === "completed") {
    if (statusBadge) {
      statusBadge.className = "invoice-badge-pill status-completed";
      statusBadge.innerHTML = `<span>✅</span><span>Zahlung bestätigt &amp; gutgeschrieben!</span>`;
    }
  } else {
    if (statusBadge) {
      statusBadge.className = "invoice-badge-pill status-waiting";
      statusBadge.innerHTML = `<span class="invoice-status-dot"></span><span id="invoiceStatusText">Warte auf Zahlung im Litecoin-Netzwerk...</span>`;
    }
  }

  startInvoiceCountdown(inv.expires_in_seconds || 28700);
}

function renderInvoice(inv) {
  populateInvoiceFields(inv);
  showInvoiceStep();
}

function startInvoiceCountdown(totalSeconds) {
  if (invoiceTimerInterval) clearInterval(invoiceTimerInterval);
  invoiceCountdownSeconds = Math.max(0, totalSeconds);

  function updateDisplay() {
    const el = document.getElementById("invoiceCountdownText");
    if (!el) return;
    if (invoiceCountdownSeconds <= 0) {
      el.textContent = "Abgelaufen";
      return;
    }
    const hours = Math.floor(invoiceCountdownSeconds / 3600);
    const minutes = Math.floor((invoiceCountdownSeconds % 3600) / 60);
    el.textContent = `${hours}h ${minutes < 10 ? '0' : ''}${minutes}m`;
  }

  updateDisplay();
  invoiceTimerInterval = setInterval(() => {
    invoiceCountdownSeconds--;
    if (invoiceCountdownSeconds <= 0) {
      clearInterval(invoiceTimerInterval);
      updateDisplay();
    } else {
      updateDisplay();
    }
  }, 1000);
}

function copyInvoiceValue(type, btnEl) {
  if (!activeInvoiceData) return;
  let text = "";
  let label = "In die Zwischenablage kopiert!";

  if (type === "ltc") {
    text = (activeInvoiceData.amount_ltc_raw || 0.00268142).toFixed(8);
    label = `LTC Betrag (${text}) kopiert!`;
  } else if (type === "address") {
    text = activeInvoiceData.wallet_address || "LM9NsXJGYdCzK6nPWPS4tHXZTKKUknERRc";
    label = "Litecoin-Adresse kopiert!";
  } else if (type === "payment_id") {
    text = activeInvoiceData.payment_id || "5784378544";
    label = `Tracking ID (${text}) kopiert!`;
  }

  navigator.clipboard.writeText(text).then(() => {
    showToast(label, "success");
    if (btnEl) {
      btnEl.classList.add("copied");
      const textSpan = btnEl.querySelector(".copy-text");
      if (textSpan) textSpan.textContent = "✓ Kopiert";
      setTimeout(() => {
        btnEl.classList.remove("copied");
        if (textSpan) textSpan.textContent = "Kopieren";
      }, 1500);
    }
  }).catch(() => {
    showToast(text, "success");
  });
}

async function handleRefreshInvoiceStatus() {
  const btn = document.getElementById("btnInvoiceRefresh");
  const btnText = document.getElementById("btnInvoiceRefreshText");
  if (btn) btn.classList.add("scanning");
  if (btnText) btnText.textContent = "Scanne Litecoin Blockchain...";

  try {
    const res = await fetch("/api/payment/invoice/check", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      if (data.current_balance !== undefined && currentUser) {
        currentUser.balance_eur = data.current_balance;
        renderNavUser();
        calculateByotPrice();
      }
      if (data.detected && data.new_balance !== undefined) {
        currentUser.balance_eur = data.new_balance;
        renderNavUser();
        calculateByotPrice();
        const statusBadge = document.getElementById("invoiceStatusBadge");
        if (statusBadge) {
          statusBadge.className = "invoice-badge-pill status-completed";
          statusBadge.innerHTML = `<span>✅</span><span>Zahlung bestätigt! (+${data.amount_eur.toFixed(2)} €)</span>`;
        }
        showToast(`🎉 Zahlung verifiziert! +${data.amount_eur.toFixed(2)} € deinem Guthaben gutgeschrieben!`, "success");
        await loadUserOrders();
      } else if (data.current_balance !== undefined && data.current_balance > 0) {
        const statusBadge = document.getElementById("invoiceStatusBadge");
        if (statusBadge) {
          statusBadge.className = "invoice-badge-pill status-completed";
          statusBadge.innerHTML = `<span>✅</span><span>Guthaben aktiv: ${data.current_balance.toFixed(2)} €</span>`;
        }
        showToast(`✅ Dein Guthaben (${data.current_balance.toFixed(2)} €) ist auf deinem Account bereit!`, "success");
      } else {
        showToast("Scanne Blockchain... Noch keine neue ungebuchte Zahlung gefunden.", "info");
      }
    }
  } catch (e) {
    showToast("Verbindungsfehler beim Prüfen der Blockchain.", "error");
  } finally {
    setTimeout(() => {
      if (btn) btn.classList.remove("scanning");
      if (btnText) btnText.textContent = "Status prüfen (Auto-Erkennung aktiv)";
    }, 600);
  }
}

// --- AUTOMATIC BLOCKCHAIN SCANNER ---

function startBlockchainAutoScanner() {
  if (blockchainScannerTimer) clearInterval(blockchainScannerTimer);

  // Poll blockchain scanner every 6 seconds
  blockchainScannerTimer = setInterval(async () => {
    if (!currentUser) return;
    try {
      const res = await fetch("/api/payment/auto-detect", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.detected && data.new_balance !== undefined) {
          currentUser.balance_eur = data.new_balance;
          renderNavUser();
          calculateByotPrice();

          const statusBadge = document.getElementById("invoiceStatusBadge");
          if (statusBadge) {
            statusBadge.className = "invoice-badge-pill status-completed";
            statusBadge.innerHTML = `<span>✅</span><span>Zahlung erhalten! (+${data.amount_eur.toFixed(2)} €)</span>`;
          }

          showToast(`🎉 Litecoin-Zahlung erkannt! +${data.amount_eur.toFixed(2)} € automatisch gutgeschrieben!`, "success");
          await loadUserOrders();
        }
      }
    } catch (e) {}
  }, 6000);
}

function stopBlockchainAutoScanner() {
  if (blockchainScannerTimer) {
    clearInterval(blockchainScannerTimer);
    blockchainScannerTimer = null;
  }
}

// --- ORDER HISTORY & LIVE STATUS ---

async function loadUserOrders() {
  if (!currentUser) return;
  const tbody = document.getElementById("ordersTableBody");
  if (!tbody) return;

  try {
    const res = await fetch("/api/boost/orders");
    if (res.ok) {
      const data = await res.json();
      const orders = data.orders || [];

      if (orders.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="table-empty-msg">Noch keine Bestellungen aufgegeben. Gib oben einen Server-Invite ein!</td></tr>`;
        return;
      }

      tbody.innerHTML = orders.map(o => {
        let statusBadge = "";
        const s = (o.status || "pending").toLowerCase();
        if (s === "completed") {
          statusBadge = `<span class="badge-status badge-completed">✅ Fertig (${o.boosts}/${o.boosts})</span>`;
        } else if (s === "in_progress" || s === "running") {
          statusBadge = `<span class="badge-status badge-in-progress">🚀 Läuft</span>`;
        } else if (s === "failed") {
          statusBadge = `<span class="badge-status badge-failed" title="${escapeHtml(o.error_msg || '')}">❌ Fehlgeschlagen</span>`;
        } else {
          statusBadge = `<span class="badge-status badge-pending">⏳ Wartend</span>`;
        }

        let modeBadge = `<span class="badge-status" style="background:rgba(157,78,221,0.15);color:#d8b4fe;border:1px solid rgba(157,78,221,0.3);">⚡ Stock</span>`;
        const m = (o.mode || "stock").toLowerCase();
        if (m === "byot") {
          modeBadge = `<span class="badge-status" style="background:rgba(59,130,246,0.15);color:#93c5fd;border:1px solid rgba(59,130,246,0.3);">🔑 BYOT</span>`;
        }

        const taskId = o.task_id;
        const jobStr = taskId ? `<code>#${escapeHtml(taskId)}</code>` : `<span style="color:var(--text-dim);">-</span>`;
        const boostsInfo = m === "byot" && o.tokens_count 
          ? `<strong>${o.boosts}x Boosts</strong> <span style="font-size:0.75rem;color:var(--text-dim);">(${o.tokens_count} Tokens)</span>`
          : `<strong>${o.boosts}x Boosts</strong>`;
        const dateStr = o.created_at ? new Date(o.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "-";

        return `
          <tr>
            <td><strong>#${o.id}</strong></td>
            <td>${modeBadge}</td>
            <td><code>${escapeHtml(o.invite)}</code></td>
            <td>${boostsInfo}</td>
            <td>${o.price_eur.toFixed(2)} €</td>
            <td>${statusBadge}</td>
            <td>${jobStr}</td>
            <td style="color:var(--text-dim);">${dateStr}</td>
          </tr>
        `;
      }).join("");
    }
  } catch (e) {}
}

function startOrderPolling() {
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(() => {
    if (currentUser) {
      loadUserOrders();
    }
  }, 8000);
}

// --- TOAST NOTIFICATIONS & ESCAPING ---

function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "slideIn 0.3s ease reverse forwards";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  return String(str || "").replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}
