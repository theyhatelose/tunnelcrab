"use strict";

const $ = (id) => document.getElementById(id);

let BOOT = null;
let SECRETS = { ru: [], en: [] };
let LINKS = [];
let crabData = null;
let crabPhase = "idle";
let crabFrame = 0;
let booted = false;
let lastPhase = "";
let connectMsgIdx = 0;
let connectMsgTimer = null;
let connectStartedAt = 0;
let pendingConnected = false;
let burrowHoldTimer = null;
const MIN_BURROW_MS = 2000;
const CONNECTING_KEYS = ["connecting.0", "connecting.1", "connecting.2", "connecting.3"];

const PALETTE_MAP = {
  "--bg": "app_bg", "--hero": "hero_bg", "--card": "card_bg", "--panel": "panel_bg",
  "--border": "border", "--accent": "accent", "--accent-hover": "accent_hover",
  "--success": "success", "--warning": "warning", "--error": "error",
  "--title": "title", "--text": "text", "--muted": "muted", "--soft": "soft",
  "--pill-text": "pill_text",
};

const INDICATOR_KEYS = {
  idle: "indicator.idle", connecting: "indicator.connecting", waiting: "indicator.waiting",
  connected: "indicator.connected", error: "indicator.error", need_admin: "indicator.need_admin",
};
const ICON_SVG = {
  power: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 3v9"/><path d="M7.5 6.5a7 7 0 1 0 9 0"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2.5"/></svg>',
  cross: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M7 7l10 10M17 7L7 17"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4l9 16H3z"/><path d="M12 10v4"/><path d="M12 17.4v.01"/></svg>',
};
const CONNECT_ICONS = {
  idle: ICON_SVG.power, connecting: ICON_SVG.power, waiting: ICON_SVG.power,
  connected: ICON_SVG.stop, error: ICON_SVG.cross, need_admin: ICON_SVG.warn,
};
const HINT_KEYS = {
  idle: "hint.idle",
  connecting: "hint.connecting",
  waiting: "hint.connecting",
  connected: "hint.connected",
  error: "hint.error",
  need_admin: "",
};

function applyTheme(name) {
  const pal = (BOOT.themes || {})[name];
  if (!pal) return;
  const root = document.documentElement.style;
  for (const [cssVar, key] of Object.entries(PALETTE_MAP)) {
    if (pal[key]) root.setProperty(cssVar, pal[key]);
  }
  root.setProperty("--accent2", pal.title || pal.accent);
  root.setProperty("--pill", "color-mix(in srgb, " + (pal.pill_bg || pal.accent) + " 55%, transparent)");
  document.querySelectorAll(".theme-card").forEach((c) => c.classList.toggle("active", c.dataset.theme === name));
}

async function boot() {
  if (booted) return;
  booted = true;
  try { BOOT = await window.pywebview.api.get_bootstrap(); }
  catch (e) {
    const ru = (navigator.language || "").toLowerCase().startsWith("ru");
    $("status").textContent = (ru ? "Ошибка моста: " : "Bridge error: ") + e;
    revealUI(); return;
  }

  crabData = BOOT.crab || null;
  LANG = BOOT.selected_language || "en";
  applyBranding(BOOT.branding);
  applyStaticI18n();
  markLangSeg();
  applyTheme(BOOT.selected_theme);
  buildThemeGrid();
  setServerName();
  updateEmptyState();
  refresh();
  revealUI();
  setInterval(refresh, 1000);
  setInterval(tickCrab, 300);
  checkUpdate();
  setInterval(checkUpdate, 20000);
  try { await window.pywebview.api.debug("phase1 boot ok theme=" + BOOT.selected_theme + " profiles=" + (BOOT.profiles || []).length); } catch (e) {}
}

function applyStaticI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
}

const BRAND_MAP = {
  tagline: "hero.sub",
  subtitle: "hero.tag",
  about_description: "about.desc",
  about_made: "about.made",
  poke_hint: "about.poke",
};

function pickLang(value, lang) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value[lang] === "string") return value[lang];
  return typeof value.ru === "string" ? value.ru : "";
}

function applyBranding(branding) {
  if (!branding || typeof branding !== "object") return;
  for (const field in BRAND_MAP) {
    const val = branding[field];
    if (val == null) continue;
    const key = BRAND_MAP[field];
    ["ru", "en"].forEach((lang) => {
      if (!I18N[lang]) I18N[lang] = {};
      I18N[lang][key] = pickLang(val, lang);
    });
  }
  SECRETS = (branding.secrets && typeof branding.secrets === "object") ? branding.secrets : { ru: [], en: [] };
  LINKS = Array.isArray(branding.links) ? branding.links : [];
  applyAppName();
}

function applyAppName() {
  const name = pickLang((BOOT && BOOT.branding || {}).app_name, LANG) || "TunnelCrab";
  document.title = name;
  document.querySelectorAll("[data-brand-name]").forEach((el) => { el.textContent = name; });
}

function burrowActive() {
  return lastPhase === "connecting" || lastPhase === "waiting" || pendingConnected;
}
function setPhase(phase) {
  if (phase === "connected" && burrowActive() && Date.now() - connectStartedAt < MIN_BURROW_MS) {
    pendingConnected = true;
    if (!burrowHoldTimer) {
      burrowHoldTimer = setTimeout(() => {
        burrowHoldTimer = null;
        pendingConnected = false;
        applyPhase("connected");
      }, MIN_BURROW_MS - (Date.now() - connectStartedAt));
    }
    return;
  }
  if (pendingConnected && phase !== "connected") {
    pendingConnected = false;
    if (burrowHoldTimer) { clearTimeout(burrowHoldTimer); burrowHoldTimer = null; }
  }
  applyPhase(phase);
}
function applyPhase(phase) {
  document.body.dataset.phase = phase;
  crabPhase = (crabData && crabData[phase]) ? phase : "idle";
  $("indicator").textContent = t(INDICATOR_KEYS[phase] || INDICATOR_KEYS.idle);
  const iconEl = $("connect-icon");
  if (iconEl) iconEl.innerHTML = CONNECT_ICONS[phase] || ICON_SVG.power;
  const hintEl = $("connect-hint");
  if (hintEl) hintEl.textContent = HINT_KEYS[phase] ? t(HINT_KEYS[phase]) : "";
  const isConn = phase === "connecting" || phase === "waiting";
  const wasConn = lastPhase === "connecting" || lastPhase === "waiting";
  if (isConn && !wasConn) { connectStartedAt = Date.now(); startConnectMsgs(); }
  else if (!isConn) stopConnectMsgs();
  lastPhase = phase;
}
function startConnectMsgs() {
  if (connectMsgTimer) return;
  connectMsgIdx = 0;
  $("status").textContent = t(CONNECTING_KEYS[0]);
  connectMsgTimer = setInterval(() => {
    connectMsgIdx = (connectMsgIdx + 1) % CONNECTING_KEYS.length;
    $("status").textContent = t(CONNECTING_KEYS[connectMsgIdx]);
  }, 2200);
}
function stopConnectMsgs() {
  if (!connectMsgTimer) return;
  clearInterval(connectMsgTimer);
  connectMsgTimer = null;
}
function tickCrab() {
  if (!crabData) return;
  const frames = crabData[crabPhase] || crabData.idle;
  if (!frames || !frames.length) return;
  crabFrame = (crabFrame + 1) % frames.length;
  $("crab").src = frames[crabFrame];
}

async function refresh() {
  let s;
  try { s = await window.pywebview.api.get_status(); } catch (e) { return; }
  const newPhase = s.phase || "idle";
  const isConn = newPhase === "connecting" || newPhase === "waiting";
  if (!isConn && !pendingConnected) $("status").textContent = s.status || "";
  $("helper").textContent = s.helper || "";
  setPhase(newPhase);
  $("m-ip").textContent = s.ip || "—";
  $("m-dns").textContent = t(s.phase === "connected" ? "dns.protected" : "dns.waiting");

  if ($("menu-panel").classList.contains("open") && $("tab-checks") && !$("tab-checks").hidden) updateLog();

  if (s.phase === "connected") {
    let m;
    try { m = await window.pywebview.api.get_metrics(); } catch (e) { m = null; }
    if (m) {
      $("m-ping").textContent = m.ping_ms == null ? "—" : (m.ping_ms + " ms · " + (m.quality || ""));
      $("m-session").textContent = fmtDur(m.session_seconds || 0);
      $("traffic").textContent = "↓ " + fmtSpeed(m.download_rate) + "   ↑ " + fmtSpeed(m.upload_rate)
        + "   ·   " + t("traffic.session") + " ↓ " + fmtBytes(m.downloaded_total) + " ↑ " + fmtBytes(m.uploaded_total);
    }
  } else {
    $("m-ping").textContent = "—";
    $("m-session").textContent = "—";
    $("traffic").textContent = "";
  }
}

function fmtDur(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = String(Math.floor(sec / 3600)).padStart(2, "0");
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}
function fmtSpeed(v) {
  v = v || 0; const u = ["B/s", "KB/s", "MB/s", "GB/s"]; let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? Math.round(v) : v.toFixed(1)) + " " + u[i];
}
function fmtBytes(v) {
  v = v || 0; const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? Math.round(v) : v.toFixed(1)) + " " + u[i];
}

function setServerName() {
  const p = (BOOT.profiles || []).find((x) => x.id === BOOT.selected_profile_id);
  $("server-name").textContent = p ? p.name : "—";
  const locEl = $("server-loc");
  if (locEl) locEl.innerHTML = p && p.location ? locationHtml(p.location) : "";
}

function updateEmptyState() {
  const empty = (BOOT.profiles || []).length === 0;
  document.body.classList.toggle("no-servers", empty);
  const es = $("empty-state");
  if (es) es.hidden = !empty;
}
let serverPop = null;
function closeServerPop() { if (serverPop) { serverPop.remove(); serverPop = null; } }
$("server-select").addEventListener("click", (e) => {
  if (serverPop) { closeServerPop(); return; }
  const pop = document.createElement("div");
  pop.className = "menu-pop";
  const profiles = BOOT.profiles || [];
  if (profiles.length === 0) {
    const it = document.createElement("div");
    it.className = "menu-item";
    it.innerHTML = `${escapeHtml(t("dropdown.empty_title"))}<small>${escapeHtml(t("dropdown.empty_sub"))}</small>`;
    it.addEventListener("click", () => { closeServerPop(); openNoServerModal(); });
    pop.appendChild(it);
  }
  profiles.forEach((p) => {
    const it = document.createElement("div");
    it.className = "menu-item" + (p.id === BOOT.selected_profile_id ? " active" : "");
    it.innerHTML = `${escapeHtml(p.name)}<small>${escapeHtml(p.server || "")}</small>`;
    it.addEventListener("click", async () => {
      closeServerPop();
      if (p.id === BOOT.selected_profile_id) return;
      BOOT.selected_profile_id = p.id;
      setServerName();
      try { await window.pywebview.api.select_profile(p.id); } catch (e) {}
    });
    pop.appendChild(it);
  });
  document.body.appendChild(pop);
  const r = $("server-select").getBoundingClientRect();
  pop.style.left = r.left + "px";
  pop.style.top = (r.bottom + 6) + "px";
  pop.style.width = r.width + "px";
  serverPop = pop;
});
document.addEventListener("click", (e) => {
  if (serverPop && !serverPop.contains(e.target) && e.target !== $("server-select") && !$("server-select").contains(e.target)) closeServerPop();
});

function escapeHtml(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

const FLAG_SVGS = {
  FI: '<svg viewBox="0 0 18 12"><rect width="18" height="12" fill="#fff"/><rect x="5" width="3" height="12" fill="#003580"/><rect y="4.5" width="18" height="3" fill="#003580"/></svg>',
  DE: '<svg viewBox="0 0 18 12"><rect width="18" height="4" fill="#000"/><rect y="4" width="18" height="4" fill="#D00"/><rect y="8" width="18" height="4" fill="#FFCE00"/></svg>',
  NL: '<svg viewBox="0 0 18 12"><rect width="18" height="4" fill="#AE1C28"/><rect y="4" width="18" height="4" fill="#fff"/><rect y="8" width="18" height="4" fill="#21468B"/></svg>',
  RU: '<svg viewBox="0 0 18 12"><rect width="18" height="4" fill="#fff"/><rect y="4" width="18" height="4" fill="#0039A6"/><rect y="8" width="18" height="4" fill="#D52B1E"/></svg>',
  SE: '<svg viewBox="0 0 18 12"><rect width="18" height="12" fill="#006AA7"/><rect x="5" width="3" height="12" fill="#FECC00"/><rect y="4.5" width="18" height="3" fill="#FECC00"/></svg>',
  FR: '<svg viewBox="0 0 18 12"><rect width="6" height="12" fill="#0055A4"/><rect x="6" width="6" height="12" fill="#fff"/><rect x="12" width="6" height="12" fill="#EF4135"/></svg>',
  US: '<svg viewBox="0 0 18 12"><rect width="18" height="12" fill="#fff"/><rect width="18" height="2" fill="#B22234"/><rect y="4" width="18" height="2" fill="#B22234"/><rect y="8" width="18" height="2" fill="#B22234"/><rect width="8" height="6" fill="#3C3B6E"/></svg>',
  GB: '<svg viewBox="0 0 18 12"><rect width="18" height="12" fill="#012169"/><path d="M0,0 18,12 M18,0 0,12" stroke="#fff" stroke-width="2.4"/><path d="M0,0 18,12 M18,0 0,12" stroke="#C8102E" stroke-width="1.2"/><rect x="7" width="4" height="12" fill="#fff"/><rect y="4" width="18" height="4" fill="#fff"/><rect x="7.8" width="2.4" height="12" fill="#C8102E"/><rect y="4.8" width="18" height="2.4" fill="#C8102E"/></svg>',
};
function flagCode(text) {
  const arr = Array.from(text || "");
  const ri = [];
  for (const ch of arr) {
    const cp = ch.codePointAt(0);
    if (cp >= 0x1F1E6 && cp <= 0x1F1FF) ri.push(String.fromCharCode(65 + cp - 0x1F1E6));
    else break;
  }
  return ri.length === 2 ? ri.join("") : "";
}
function stripFlag(text) {
  const arr = Array.from(text || "");
  let i = 0;
  while (i < arr.length) {
    const cp = arr[i].codePointAt(0);
    if (cp >= 0x1F1E6 && cp <= 0x1F1FF) i++;
    else break;
  }
  return arr.slice(i).join("").trim();
}
function flagHtml(text) {
  const code = flagCode(text);
  if (!code) return "";
  const svg = FLAG_SVGS[code];
  return svg ? `<span class="flag">${svg}</span>` : `<span class="flag-badge">${escapeHtml(code)}</span>`;
}
function locationHtml(text) {
  if (!text) return "";
  const flag = flagHtml(text);
  const label = escapeHtml(stripFlag(text));
  return (flag ? flag + " " : "") + label;
}

function buildThemeGrid() {
  const grid = $("theme-grid");
  grid.innerHTML = "";
  (BOOT.theme_names || []).forEach((name) => {
    const pal = BOOT.themes[name] || {};
    const card = document.createElement("div");
    card.className = "theme-card" + (name === BOOT.selected_theme ? " active" : "");
    card.dataset.theme = name;
    card.innerHTML = `<span class="swatch" style="background:linear-gradient(135deg, ${pal.title || "#f79"}, ${pal.accent || "#e45"})"></span>${escapeHtml(name)}`;
    card.addEventListener("click", async () => {
      BOOT.selected_theme = name;
      applyTheme(name);
      try { await window.pywebview.api.set_theme(name); } catch (e) {}
    });
    grid.appendChild(card);
  });
}
function openSheet(open) {
  $("theme-sheet").classList.toggle("open", open);
  $("sheet-backdrop").classList.toggle("open", open);
}
$("theme-btn").addEventListener("click", () => openSheet(true));
$("sheet-backdrop").addEventListener("click", () => openSheet(false));

function markLangSeg() {
  $("seg-lang").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === LANG));
}
async function setLanguage(lang) {
  LANG = lang;
  if (BOOT) BOOT.selected_language = lang;
  try { await window.pywebview.api.set_language(lang); } catch (e) {}
  applyStaticI18n();
  applyAppName();
  markLangSeg();
  setServerName();
  refresh();
  if ($("menu-panel").classList.contains("open")) {
    const active = document.querySelector(".tab.active");
    if (active) switchTab(active.dataset.tab);
  }
}
$("seg-lang").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => setLanguage(b.dataset.v)));

let _toggleBusy = false;
let _toggleLast = 0;
$("toggle").addEventListener("click", async () => {
  const now = Date.now();
  if (_toggleBusy || now - _toggleLast < 700) return;
  _toggleLast = now;
  _toggleBusy = true;
  let res;
  try { res = await window.pywebview.api.toggle(); }
  catch (e) { _toggleBusy = false; return; }
  _toggleBusy = false;
  if (res && res.ok === false && res.error === "no_profile") openNoServerModal();
});
$("min").addEventListener("click", () => window.pywebview.api.minimize());
function fadeOutThen(fn) {
  document.body.classList.add("fading");
  setTimeout(fn, 180);
}
$("close").addEventListener("click", async () => {
  let res;
  try { res = await window.pywebview.api.request_close(); } catch (e) { return; }
  const action = res && res.action;
  if (action === "ask") openCloseModal();
  else if (action === "tray") fadeOutThen(() => window.pywebview.api.hide_to_tray());
  else if (action === "quit") fadeOutThen(() => window.pywebview.api.quit_app());
});

function openCloseModal() {
  $("close-remember").checked = false;
  $("modal-backdrop").classList.add("open");
  $("close-modal").classList.add("open");
}
function closeCloseModal() {
  $("modal-backdrop").classList.remove("open");
  $("close-modal").classList.remove("open");
}
async function rememberCloseChoice(action) {
  if (!$("close-remember").checked) return;
  try { await window.pywebview.api.set_setting("close_action", action); } catch (e) {}
  if (BOOT && BOOT.settings) BOOT.settings.close_action = action;
}
$("modal-backdrop").addEventListener("click", () => { closeCloseModal(); closeNoServerModal(); });
$("close-tray").addEventListener("click", async () => {
  await rememberCloseChoice("tray");
  closeCloseModal();
  fadeOutThen(() => window.pywebview.api.hide_to_tray());
});
$("close-quit").addEventListener("click", async () => {
  await rememberCloseChoice("quit");
  fadeOutThen(() => window.pywebview.api.quit_app());
});

function openNoServerModal() {
  $("modal-backdrop").classList.add("open");
  $("no-server-modal").classList.add("open");
}
function closeNoServerModal() {
  $("modal-backdrop").classList.remove("open");
  $("no-server-modal").classList.remove("open");
}
$("ns-cancel").addEventListener("click", closeNoServerModal);
$("ns-manual").addEventListener("click", () => {
  closeNoServerModal();
  openMenu("servers");
  setTimeout(() => { const el = $("add-link"); if (el) el.focus(); }, 60);
});
$("ns-subscription").addEventListener("click", () => {
  closeNoServerModal();
  openMenu("servers");
  setTimeout(() => { const el = $("sub-url"); if (el) el.focus(); }, 60);
});
$("ns-clipboard").addEventListener("click", async () => {
  let text = "";
  try { text = ((await window.pywebview.api.read_clipboard()) || "").trim(); }
  catch (e) { toast(t("toast.clip_failed")); closeNoServerModal(); openMenu("servers"); return; }
  try {
    if (/^vless:\/\//i.test(text)) {
      closeNoServerModal();
      const res = await window.pywebview.api.add_profile_by_link(text, "");
      if (applyProfilesResult(res)) toast(t("toast.server_added"));
    } else if (/^https?:\/\//i.test(text)) {
      closeNoServerModal();
      toast(t("toast.loading_sub"));
      const res = await window.pywebview.api.add_subscription("", text);
      if (applyProfilesResult(res)) toast(t("toast.sub_added"));
    } else {
      toast(t("toast.clip_empty"));
    }
  } catch (e) {
    toast(t("toast.add_failed"));
  }
});

let updateDismissed = false;
async function checkUpdate() {
  if (updateDismissed) return;
  let info;
  try { info = await window.pywebview.api.get_update_info(); } catch (e) { return; }
  const banner = $("update-banner");
  if (info && info.available) {
    $("update-text").textContent = t("update.available_v", { version: info.version || "" });
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }
}
$("update-dismiss").addEventListener("click", () => { updateDismissed = true; $("update-banner").hidden = true; });
$("update-btn").addEventListener("click", async () => {
  $("update-btn").disabled = true;
  toast(t("update.downloading"));
  let res;
  try { res = await window.pywebview.api.install_update(); } catch (e) { res = null; }
  if (res && res.ok) toast(t("update.launching"));
  else { toast((res && res.error) || t("update.failed")); $("update-btn").disabled = false; }
});

let toastTimer = null;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
}

const TAB_TITLE_KEYS = { servers: "tab.servers", checks: "tab.checks", settings: "tab.settings", about: "about.title_tab" };

function openMenu(tab) {
  $("menu-panel").classList.add("open");
  switchTab(tab || "servers");
}
function closeMenu() { $("menu-panel").classList.remove("open"); }

function switchTab(tab) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll(".tabview").forEach((v) => (v.hidden = v.dataset.tab !== tab));
  $("menu-title").textContent = t(TAB_TITLE_KEYS[tab] || "menu.title");
  if (tab === "servers") renderServers();
  else if (tab === "checks") renderChecks();
  else if (tab === "settings") renderSettings();
  else if (tab === "about") renderAbout();
}

document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
$("open-menu").addEventListener("click", () => openMenu("servers"));
$("menu-back").addEventListener("click", closeMenu);
$("quick-check").addEventListener("click", () => { openMenu("checks"); runSiteCheck(); });

function applyProfilesResult(res) {
  if (!res || !res.ok) { if (res && res.error) toast(res.error); return false; }
  if (res.profiles) BOOT.profiles = res.profiles;
  if (res.subscriptions) BOOT.subscriptions = res.subscriptions;
  if ("selected_profile_id" in res) BOOT.selected_profile_id = res.selected_profile_id || "";
  setServerName();
  updateEmptyState();
  renderServers();
  return true;
}

function renderServers() {
  const root = $("tab-servers");
  root.innerHTML = "";

  const add = document.createElement("div");
  add.innerHTML = `
    <div class="section-h">${t("servers.add_title")}</div>
    <input class="field" id="add-link" placeholder="${t("servers.add_link_ph")}" />
    <div style="display:flex; gap:8px; margin-top:8px;">
      <button class="btn" id="add-link-btn" style="flex:1">${t("servers.add_link_btn")}</button>
      <button class="btn sec" id="import-json" style="flex:0 0 auto">${t("servers.import_json")}</button>
    </div>`;
  root.appendChild(add);

  const subBox = document.createElement("div");
  subBox.style.marginTop = "14px";
  subBox.innerHTML = `
    <div class="section-h">${t("servers.subs_title")}</div>
    <div class="hint">${t("servers.subs_hint")}</div>
    <input class="field" id="sub-name" placeholder="${t("servers.sub_name_ph")}" style="margin-top:8px" />
    <input class="field" id="sub-url" placeholder="${t("servers.sub_url_ph")}" style="margin-top:8px" />
    <button class="btn" id="add-sub-btn" style="width:100%; margin-top:8px">${t("servers.add_sub_btn")}</button>
    <div id="sub-list" style="display:flex; flex-direction:column; gap:8px; margin-top:10px"></div>`;
  root.appendChild(subBox);

  const subList = subBox.querySelector("#sub-list");
  (BOOT.subscriptions || []).forEach((s) => subList.appendChild(subCard(s)));

  const listHead = document.createElement("div");
  listHead.className = "section-h";
  listHead.style.marginTop = "14px";
  listHead.textContent = t("servers.list_title");
  root.appendChild(listHead);

  const list = document.createElement("div");
  list.className = "tabview";
  list.style.marginTop = "8px";
  (BOOT.profiles || []).forEach((p) => list.appendChild(serverCard(p)));
  root.appendChild(list);

  $("add-link-btn").addEventListener("click", async () => {
    const link = $("add-link").value.trim();
    if (!link) return;
    if (/^https?:\/\//i.test(link)) {
      toast(t("toast.loading_sub"));
      const res = await window.pywebview.api.add_subscription("", link);
      if (applyProfilesResult(res)) toast(t("toast.sub_added"));
    } else {
      const res = await window.pywebview.api.add_profile_by_link(link, "");
      if (applyProfilesResult(res)) toast(t("toast.server_added"));
    }
  });
  $("import-json").addEventListener("click", async () => {
    const res = await window.pywebview.api.import_profile_file();
    if (res && res.cancelled) return;
    if (applyProfilesResult(res)) toast(t("toast.profile_imported"));
  });
  $("add-sub-btn").addEventListener("click", async () => {
    const url = $("sub-url").value.trim();
    if (!url) { toast(t("toast.paste_sub")); return; }
    const name = $("sub-name").value.trim();
    $("add-sub-btn").disabled = true;
    toast(t("toast.loading_sub"));
    try {
      const res = await window.pywebview.api.add_subscription(name, url);
      if (applyProfilesResult(res)) toast(t("toast.sub_added"));
      else $("add-sub-btn").disabled = false;
    } catch (e) {
      toast(t("toast.add_failed"));
      $("add-sub-btn").disabled = false;
    }
  });
}

function subCard(s) {
  const card = document.createElement("div");
  card.className = "sub-card";
  card.innerHTML = `
    <div class="sub-name">${escapeHtml(s.name)}</div>
    <div class="sub-url">${escapeHtml(s.url)}</div>
    <div class="sub-actions"></div>`;
  const acts = card.querySelector(".sub-actions");
  const mk = (label, cls, fn) => { const b = document.createElement("button"); b.className = "mini" + (cls ? " " + cls : ""); b.textContent = label; b.addEventListener("click", fn); acts.appendChild(b); };
  mk(t("sub.refresh"), "", async () => { const r = await window.pywebview.api.refresh_subscription(s.id); if (applyProfilesResult(r)) toast(t("toast.sub_refreshed")); });
  mk(t("sub.delete"), "danger", async () => { const r = await window.pywebview.api.delete_subscription(s.id); if (applyProfilesResult(r)) toast(t("toast.sub_deleted")); });
  return card;
}

function serverCard(p) {
  const active = p.id === BOOT.selected_profile_id;
  const card = document.createElement("div");
  card.className = "srv" + (active ? " active" : "");
  card.innerHTML = `
    <div class="srv-h">
      <div style="flex:1">
        <div class="srv-name">${escapeHtml(p.name)}${p.subscription_id ? `<span class="srv-sub-tag">${t("srv.tag_sub")}</span>` : ""}</div>
        ${p.location ? `<div class="srv-loc">${locationHtml(p.location)}</div>` : ""}
        <div class="srv-srv">${escapeHtml(p.server || "")}</div>
      </div>
      ${active ? `<span class="srv-badge">${t("srv.badge_selected")}</span>` : ""}
    </div>
    <div class="srv-actions"></div>`;
  const acts = card.querySelector(".srv-actions");
  const mk = (label, cls, fn) => { const b = document.createElement("button"); b.className = "mini" + (cls ? " " + cls : ""); b.textContent = label; b.addEventListener("click", fn); acts.appendChild(b); };
  if (!active) mk(t("srv.select"), "", async () => { await window.pywebview.api.select_profile(p.id); BOOT.selected_profile_id = p.id; setServerName(); renderServers(); toast(t("toast.selected_name", { name: p.name })); });
  mk(t("srv.rename"), "", () => inlineRename(card, p));
  mk(t("srv.location"), "", () => inlineLocation(card, p));
  mk(t("srv.duplicate"), "", async () => { applyProfilesResult(await window.pywebview.api.duplicate_profile(p.id)) && toast(t("toast.copy_made")); });
  mk(t("srv.refresh"), "", async () => { const r = await window.pywebview.api.refresh_profile(p.id); applyProfilesResult(r) ? toast(t("toast.config_refreshed")) : 0; });
  mk(t("srv.delete"), "danger", async () => { const r = await window.pywebview.api.delete_profile(p.id); applyProfilesResult(r) && toast(t("toast.profile_deleted")); });
  return card;
}

function inlineRename(card, p) {
  const head = card.querySelector(".srv-name");
  const input = document.createElement("input");
  input.className = "field"; input.value = p.name;
  head.replaceWith(input);
  input.focus();
  const save = async () => {
    const name = input.value.trim();
    if (!name || name === p.name) { renderServers(); return; }
    applyProfilesResult(await window.pywebview.api.rename_profile(p.id, name)) && toast(t("toast.name_saved"));
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); if (e.key === "Escape") renderServers(); });
  input.addEventListener("blur", save);
}

function inlineLocation(card, p) {
  const existing = card.querySelector(".srv-loc");
  const nameDiv = card.querySelector(".srv-name");
  const input = document.createElement("input");
  input.className = "field";
  input.value = p.location || "";
  input.placeholder = t("location.ph");
  input.style.cssText = "font-size:12px; margin-top:4px; margin-bottom:2px;";
  if (existing) existing.replaceWith(input);
  else nameDiv.insertAdjacentElement("afterend", input);
  input.focus();
  const save = async () => {
    const loc = input.value.trim();
    if (loc === (p.location || "")) { renderServers(); return; }
    const r = await window.pywebview.api.set_profile_location(p.id, loc);
    if (applyProfilesResult(r)) { p.location = loc; setServerName(); }
    else renderServers();
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); if (e.key === "Escape") renderServers(); });
  input.addEventListener("blur", save);
}

function renderChecks() {
  const root = $("tab-checks");
  root.innerHTML = `
    <button class="btn" id="run-check">${t("checks.run")}</button>
    <div class="tabview" id="site-results" style="margin-top:4px"></div>
    <div class="section-h">${t("checks.diary")}</div>
    <div class="logbox" id="logbox"></div>
    <div class="section-h">${t("checks.help")}</div>
    <button class="btn sec" id="copy-diag">${t("checks.copy_diag")}</button>
    <div class="hint">${t("checks.help_hint")}</div>`;
  $("run-check").addEventListener("click", runSiteCheck);
  $("copy-diag").addEventListener("click", async () => {
    const text = await window.pywebview.api.diagnostics_text();
    try { await navigator.clipboard.writeText(text); toast(t("toast.diag_copied")); }
    catch (e) { toast(t("toast.copy_failed")); }
  });
  lastLogLen = -1;
  updateLog();
}

let lastLogLen = -1;
async function updateLog() {
  const box = $("logbox");
  if (!box) return;
  let events;
  try { events = await window.pywebview.api.get_events(); } catch (e) { return; }
  if (!events) return;
  if (events.length === lastLogLen) return;
  lastLogLen = events.length;
  box.innerHTML = events.map((e) => `<div class="logline"><span class="logt">${escapeHtml(e.t)}</span> ${escapeHtml(e.msg)}</div>`).join("");
  box.scrollTop = box.scrollHeight;
}
async function runSiteCheck() {
  const box = $("site-results");
  if (box) box.innerHTML = `<div class="hint">${t("checks.checking")}</div>`;
  let res;
  try { res = await window.pywebview.api.check_sites(BOOT.sites); } catch (e) { return; }
  if (!box) return;
  box.innerHTML = "";
  (res || []).forEach((r) => {
    const row = document.createElement("div");
    row.className = "site-row";
    row.innerHTML = `<span class="nm">${escapeHtml(r.name)}</span><span class="st ${r.ok ? "ok" : "bad"}">${escapeHtml(r.detail)}</span>`;
    box.appendChild(row);
  });
}

function renderSettings() {
  const root = $("tab-settings");
  const s = BOOT.settings || {};
  const rows = [
    ["launch_on_startup", t("set.launch_on_startup"), ""],
    ["auto_connect_on_launch", t("set.auto_connect_on_launch"), ""],
    ["connect_when_internet", t("set.connect_when_internet"), ""],
    ["auto_reconnect", t("set.auto_reconnect"), ""],
    ["quiet_mode", t("set.quiet_mode"), ""],
    ["auto_update", t("set.auto_update"), ""],
    ["auto_refresh_subscriptions", t("set.auto_refresh_subscriptions"), ""],
  ];
  root.innerHTML = `<div class="section-h">${t("settings.behavior")}</div>`;
  rows.forEach(([key, label, hint]) => {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `<div class="lbl">${label}${hint ? "<small>" + hint + "</small>" : ""}</div><div class="switch ${s[key] ? "on" : ""}"></div>`;
    const sw = row.querySelector(".switch");
    sw.addEventListener("click", async () => {
      const next = !sw.classList.contains("on");
      const res = await window.pywebview.api.set_setting(key, next);
      if (res && res.ok) { sw.classList.toggle("on", next); BOOT.settings[key] = next; }
      else if (res && res.error) toast(res.error);
    });
    root.appendChild(row);
  });

  const behave = document.createElement("div");
  behave.innerHTML = `
    <div style="font-size:12px;font-weight:800;color:var(--soft);margin:14px 2px 4px">${t("settings.on_close")}</div>
    <div class="seg" id="seg-close"><button data-v="ask">${t("close.ask")}</button><button data-v="tray">${t("close.to_tray")}</button><button data-v="quit">${t("close.exit")}</button></div>
    <div style="font-size:12px;font-weight:800;color:var(--soft);margin:14px 2px 4px">${t("settings.routing")}</div>
    <div class="seg" id="seg-routing"><button data-v="global">${t("routing.global")}</button><button data-v="bypass_ru">${t("routing.bypass_ru")}</button></div>
    <div class="hint" style="margin-top:6px">${t("settings.routing_hint")}</div>`;
  root.appendChild(behave);

  const adv = document.createElement("div");
  adv.innerHTML = `
    <div class="section-h" style="margin-top:14px">${t("settings.advanced")}</div>
    <div class="hint">${t("settings.advanced_hint")}</div>
    <div style="font-size:12px;font-weight:800;color:var(--soft);margin:10px 2px 4px">${t("settings.core")}</div>
    <div class="seg" id="seg-core"><button data-v="sing-box">sing-box</button><button data-v="xray">xray-core</button></div>
    <div style="font-size:12px;font-weight:800;color:var(--soft);margin:12px 2px 4px">${t("settings.mode")}</div>
    <div class="seg" id="seg-mode"><button data-v="tun">${t("mode.tun")}</button><button data-v="proxy">${t("mode.proxy")}</button></div>
    <div class="hint" id="mode-hint" style="margin-top:6px"></div>`;
  root.appendChild(adv);

  const markSeg = (id, val) => $(id).querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === val));
  const updateModeHint = (mode) => {
    const el = $("mode-hint");
    if (!el) return;
    el.textContent = t(mode === "proxy" ? "modehint.proxy" : "modehint.tun");
  };
  markSeg("seg-core", BOOT.selected_core);
  markSeg("seg-mode", BOOT.connection_mode);
  updateModeHint(BOOT.connection_mode);
  markSeg("seg-close", (BOOT.settings || {}).close_action || "ask");
  markSeg("seg-routing", BOOT.routing_mode || "global");
  $("seg-core").querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => { const r = await window.pywebview.api.set_core(b.dataset.v); BOOT.selected_core = r.core; markSeg("seg-core", r.core); }));
  $("seg-mode").querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => { const r = await window.pywebview.api.set_mode(b.dataset.v); BOOT.connection_mode = r.mode; markSeg("seg-mode", r.mode); updateModeHint(r.mode); }));
  $("seg-close").querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => { const r = await window.pywebview.api.set_setting("close_action", b.dataset.v); if (r && r.ok) { BOOT.settings.close_action = b.dataset.v; markSeg("seg-close", b.dataset.v); } else if (r && r.error) toast(r.error); }));
  $("seg-routing").querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => { const r = await window.pywebview.api.set_routing(b.dataset.v); BOOT.routing_mode = r.routing; markSeg("seg-routing", r.routing); toast(t(r.routing === "bypass_ru" ? "toast.routing_bypass" : "toast.routing_global")); }));
}

let aboutTimer = null, aboutClicks = 0, aboutEaster = false, aboutFrame = 0;
function renderAbout() {
  aboutEaster = false; aboutClicks = 0; aboutFrame = 0;
  const root = $("tab-about");
  root.textContent = "";

  const card = document.createElement("div");
  card.className = "card status-card";
  card.style.cssText = "gap:10px; position:relative; overflow:hidden";

  const img = document.createElement("img");
  img.id = "about-crab";
  img.className = "crab";
  img.style.cssText = "width:100px;height:100px;cursor:pointer";
  img.alt = "";
  img.title = "psst…";
  card.appendChild(img);

  const name = document.createElement("div");
  name.style.cssText = "font-size:16px;font-weight:800";
  name.textContent = pickLang((BOOT.branding || {}).app_name, LANG) || "TunnelCrab";
  card.appendChild(name);

  const desc = document.createElement("div");
  desc.className = "hint";
  desc.style.textAlign = "center";
  desc.appendChild(document.createTextNode(t("about.desc")));
  desc.appendChild(document.createElement("br"));
  desc.appendChild(document.createTextNode(t("about.made")));
  card.appendChild(desc);

  const story = document.createElement("div");
  story.className = "hint";
  story.style.cssText = "text-align:center; opacity:.85; max-width:300px; white-space:pre-line; line-height:1.5";
  story.textContent = t("about.story");
  card.appendChild(story);

  const ver = document.createElement("div");
  ver.className = "srv-srv";
  ver.textContent = t("about.version", { v: BOOT.version || "" });
  card.appendChild(ver);

  const secret = document.createElement("div");
  secret.id = "secret";
  card.appendChild(secret);

  const secretLines = (SECRETS && Array.isArray(SECRETS[LANG])) ? SECRETS[LANG] : [];
  const hasSecrets = secretLines.length > 0;

  const hint = document.createElement("div");
  hint.className = "hint";
  hint.id = "about-hint";
  hint.style.cssText = "opacity:.55; margin-top:4px";
  if (hasSecrets) hint.textContent = t("about.poke");
  card.appendChild(hint);

  const links = buildLinksBlock();
  if (links) card.appendChild(links);

  const linkRow = document.createElement("div");
  linkRow.className = "about-links";
  linkRow.style.cssText = "display:flex; flex-wrap:wrap; justify-content:center; gap:8px; margin-top:6px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const makeLinkButton = (viewBox, pathD, labelKey, url) => {
    const btn = document.createElement("button");
    btn.className = "mini";
    btn.style.cssText = "display:inline-flex; align-items:center; gap:6px";
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", viewBox);
    svg.setAttribute("width", "14");
    svg.setAttribute("height", "14");
    svg.setAttribute("fill", "currentColor");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", pathD);
    svg.appendChild(path);
    const label = document.createElement("span");
    label.textContent = t(labelKey);
    btn.appendChild(svg);
    btn.appendChild(label);
    btn.addEventListener("click", () => { try { window.pywebview.api.open_url(url); } catch (e) {} });
    return btn;
  };
  linkRow.appendChild(makeLinkButton(
    "0 0 16 16",
    "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z",
    "about.github",
    "https://github.com/theyhatelose/tunnelcrab"
  ));
  linkRow.appendChild(makeLinkButton(
    "0 0 24 24",
    "M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z",
    "about.telegram",
    "https://t.me/feellikelose"
  ));
  card.appendChild(linkRow);

  const footer = document.createElement("div");
  footer.className = "hint";
  footer.style.cssText = "opacity:.6; font-size:12px; margin-top:8px";
  footer.textContent = t("about.footer");
  card.appendChild(footer);

  root.appendChild(card);

  const animate = () => {
    if (!crabData) return;
    const set = (aboutEaster ? crabData.easter : crabData.idle) || crabData.idle || [];
    if (!set.length) return;
    aboutFrame = (aboutFrame + 1) % set.length;
    img.src = set[aboutFrame];
  };
  if (aboutTimer) clearInterval(aboutTimer);
  aboutTimer = setInterval(animate, 280);
  animate();

  if (hasSecrets) {
    img.addEventListener("click", () => {
      aboutClicks++;
      if (aboutClicks >= 5 && !aboutEaster) {
        aboutEaster = true; aboutFrame = 0;
        secret.textContent = "";
        const msg = document.createElement("div");
        msg.className = "secret-msg";
        secretLines.forEach((line, i) => {
          if (i) msg.appendChild(document.createElement("br"));
          msg.appendChild(document.createTextNode(line));
        });
        secret.appendChild(msg);
        hint.textContent = "";
        burstHearts(card);
      }
    });
  }
}

function buildLinksBlock() {
  const valid = (LINKS || []).filter((l) =>
    l && typeof l.label === "string" && typeof l.url === "string" && /^https?:\/\//i.test(l.url)
  );
  if (!valid.length) return null;
  const wrap = document.createElement("div");
  wrap.className = "about-links";
  wrap.style.cssText = "display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:6px";
  valid.forEach((l) => {
    const b = document.createElement("button");
    b.className = "mini";
    b.textContent = l.label;
    b.addEventListener("click", () => { try { window.pywebview.api.open_url(l.url); } catch (e) {} });
    wrap.appendChild(b);
  });
  return wrap;
}

function burstHearts(host) {
  if (!host) return;
  for (let i = 0; i < 14; i++) {
    const heart = document.createElement("div");
    heart.className = "heart";
    heart.textContent = ["💗", "💖", "💕", "🦀"][i % 4];
    heart.style.left = (10 + Math.random() * 80) + "%";
    heart.style.animationDelay = (Math.random() * 0.5) + "s";
    heart.style.fontSize = (14 + Math.random() * 16) + "px";
    host.appendChild(heart);
    setTimeout(() => heart.remove(), 2600);
  }
}

function revealUI() {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.body.classList.remove("booting");
  }));
}

window.addEventListener("pywebviewready", boot);
if (window.pywebview && window.pywebview.api) boot();
setTimeout(revealUI, 2500);
