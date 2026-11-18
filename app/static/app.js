const $ = (s, el = document) => el.querySelector(s);
const api = async (url, opts = {}) => {
  // X-Lang : le serveur renvoie ses messages d'erreur dans la langue de l'interface
  const r = await fetch(url, { ...opts, headers: { ...(opts.headers || {}), "X-Lang": LANG } });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const JSON_HEADERS = { "Content-Type": "application/json" };
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const SWATCH = { black: "#111", gray: "#888", white: "#f5f5f5", red: "#d22", orange: "#f80", yellow: "#fd0",
  beige: "#dcc69c", brown: "#7a4a21", green: "#2a2", cyan: "#0cc", blue: "#25d", purple: "#829", pink: "#f6a" };
const EV_TITLES = { weapon: "ev_weapon", face: "ev_face", person: "ev_person", zone: "ev_zone" };
const REC_MODES = ["off", "alerts", "people", "continuous"];
const fmtTime = ts => new Date(ts * 1000).toLocaleString(LOCALES[LANG]);
const swatch = c => c ? `<span class="swatch" style="background:${SWATCH[c] || "#555"}"></span>${esc(tv(c))}` : "—";
const garment = (type, color) => (type ? `<b>${esc(tv(type))}</b> ` : "") + swatch(color);

let cameras = [];
let lastEventId = null;
let engineStatus = {};
let savedSettings = {};

// --- onglets -------------------------------------------------------------
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  history.replaceState(null, "", "#" + b.dataset.tab);  // onglet dans l'adresse : #events, #settings...
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.id === "tab-" + b.dataset.tab));
  if (b.dataset.tab === "events") loadEvents();
  if (b.dataset.tab === "faces") loadFaces();
  if (b.dataset.tab === "settings") loadSettings();
  if (b.dataset.tab === "recordings") loadRecordingsTab();
});

// --- langue ------------------------------------------------------------------
$("#lang").value = LANG;
$("#lang").onchange = e => {
  LANG = e.target.value;
  try { localStorage.setItem("vs-lang", LANG); } catch { /* stockage indisponible */ }
  renderAll();
};

// Réaffiche tout ce qui contient du texte (après un changement de langue)
function renderAll() {
  applyStatic();
  renderEngine();
  renderFilters();
  cameras.forEach(updateCard);
  refreshCameras();
  const active = document.querySelector("nav button.active")?.dataset.tab;
  if (active === "events") loadEvents();
  if (active === "faces") loadFaces();
  if (active === "settings") loadSettings();
  if (active === "recordings") loadRecordingsTab();
}

// --- statut moteur ---------------------------------------------------------
async function loadStatus() {
  const s = await api("/api/status");
  if (s.reloading) { waitReload(); return; }
  engineStatus = s;
  if (!s.privacy_ack) showPrivacy();
  renderEngine();
  renderFilters();
}

function renderEngine() {
  const s = engineStatus;
  if (!s.device) return;
  const parts = [t("engine_device", { d: s.device })];
  parts.push(s.faces_available ? t("faces_ok") : t("faces_missing"));
  parts.push(s.weapon_model ? t("weapons_model", { c: s.weapon_classes.map(tv).join(", ") }) : t("weapons_coco"));
  $("#engine").textContent = $("#engine").title = parts.join(" · ");
  $("#faces-off").classList.toggle("hidden", s.face_recognition !== false);
}

// Listes de filtres du journal : reconstruites (valeur = clé neutre, texte = traduction)
function renderFilters() {
  const s = engineStatus;
  const fill = (sel, first, values) => {
    const cur = sel.value;
    sel.innerHTML = `<option value="">${esc(first)}</option>` +
      values.map(v => `<option value="${esc(v)}">${esc(tv(v))}</option>`).join("");
    sel.value = cur;
  };
  fill($("#f-upper-color"), t("f_upper_color"), s.colors || []);
  fill($("#f-lower-color"), t("f_lower_color"), s.colors || []);
  fill($("#f-upper-type"), t("f_upper_type"), s.clothing_upper || []);
  fill($("#f-lower-type"), t("f_lower_type"), s.clothing_lower || []);
  const noTypes = !(s.clothing_upper || []).length;
  document.querySelectorAll("#f-upper-type, #f-lower-type").forEach(x => x.classList.toggle("hidden", noTypes));
  fillCameraFilter();
}

function fillCameraFilter() {
  const sel = $("#ev-cam"), cur = sel.value;
  sel.innerHTML = `<option value="">${esc(t("f_all_cams"))}</option>` +
    cameras.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  sel.value = cur;
}

// --- direct ------------------------------------------------------------------
function camCard(c) {
  const el = document.createElement("div");
  el.className = "cam";
  el.id = "cam-" + c.id;
  el.innerHTML = `
    <div class="feed"><img src="/api/cameras/${c.id}/stream" alt="${esc(c.name)}"><span class="feed-tag">LIVE</span></div>
    <div class="bar">
      <span class="dot"></span><b>${esc(c.name)}</b><span class="st muted"></span>
      <div class="opts">
        <button data-k="colors" data-i18n="btn_clothes" data-i18n-title="btn_clothes_title"></button>
        <button data-k="faces" data-i18n="btn_faces" data-i18n-title="btn_faces_title"></button>
        <button data-k="weapons" data-i18n="btn_weapons" data-i18n-title="btn_weapons_title"></button>
        <button data-areas data-i18n="btn_areas" data-i18n-title="btn_areas_title"></button>
        <button data-rec data-i18n-title="rec_btn_title"></button>
        <button data-del data-i18n-title="delete">🗑</button>
      </div>
    </div>
    <div class="counts"></div>`;
  applyStatic(el);
  $("img", el).onclick = () => openFull(`/api/cameras/${c.id}/stream`);
  el.querySelectorAll("[data-k]").forEach(b => b.onclick = async () => {
    const cam = cameras.find(x => x.id === c.id);
    const upd = await api(`/api/cameras/${c.id}`, { method: "PATCH", headers: JSON_HEADERS,
      body: JSON.stringify({ [b.dataset.k]: !cam[b.dataset.k] }) });
    Object.assign(cam, upd); updateCard(cam);
  });
  $("[data-areas]", el).onclick = () => openAreas(cameras.find(x => x.id === c.id));
  // Mode d'enregistrement : un clic passe au suivant (off → alertes → personnes → continu)
  $("[data-rec]", el).onclick = async () => {
    const cam = cameras.find(x => x.id === c.id);
    const cur = cam.record || "alerts";
    const next = REC_MODES[(REC_MODES.indexOf(cur) + 1) % REC_MODES.length];
    Object.assign(cam, await api(`/api/cameras/${c.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ record: next }) }));
    updateCard(cam);
  };
  $("[data-del]", el).onclick = async () => {
    if (!confirm(t("confirm_delete_cam", { name: c.name }))) return;
    await api(`/api/cameras/${c.id}`, { method: "DELETE" });
    el.remove(); refreshCameras();
  };
  return el;
}

const statusClass = c => c.status === "online" ? "on" : c.status === "offline" ? "off" : "";

function updateCard(c) {
  const el = document.getElementById("cam-" + c.id);
  if (!el) return;
  $(".dot", el).className = "dot " + statusClass(c);
  $(".st", el).textContent = `${t("st_" + c.status)} · ${t("fps", { n: c.fps })}`;
  el.querySelectorAll("[data-k]").forEach(b => b.classList.toggle("on", !!c[b.dataset.k]));
  $("[data-areas]", el).classList.toggle("on", !!(c.areas || []).length);
  const mode = c.record || "alerts";
  const recBtn = $("[data-rec]", el);
  recBtn.textContent = t("rec_mode_" + mode);
  recBtn.classList.toggle("on", mode !== "off");
  const tag = $(".feed-tag", el);
  tag.textContent = c.recording ? "REC" : "LIVE";
  tag.classList.toggle("rec", !!c.recording);
  $(".counts", el).innerHTML = typeof areaChips === "function" ? areaChips(c) : "";
  applyStatic(el);
}

// --- colonne des caméras : choix de celles affichées (mémorisé dans ce navigateur) --------
// Une caméra masquée n'est plus diffusée ici, mais reste analysée : ses alertes arrivent toujours.
let hiddenCams = new Set();
try { hiddenCams = new Set(JSON.parse(localStorage.getItem("vs-hidden-cams") || "[]")); } catch { /* stockage indisponible */ }
const alertCams = new Set();
const isShown = c => !hiddenCams.has(c.id);

function saveHidden() {
  try { localStorage.setItem("vs-hidden-cams", JSON.stringify([...hiddenCams])); } catch { /* stockage indisponible */ }
}

function setHidden(ids) {
  hiddenCams = new Set(ids);
  saveHidden();
  syncGrid();
  renderCamList();
}

function syncGrid() {
  const grid = $("#grid");
  const shown = cameras.filter(isShown);
  const ids = new Set(shown.map(c => c.id));
  grid.querySelectorAll(".cam").forEach(el => {
    if (!ids.has(el.id.slice(4))) { $("img", el).src = ""; el.remove(); }  // coupe le flux vidéo
  });
  shown.forEach((c, i) => {
    if (document.getElementById("cam-" + c.id)) return;
    // insérée à sa place dans l'ordre des caméras
    const next = shown.slice(i + 1).map(x => document.getElementById("cam-" + x.id)).find(Boolean);
    grid.insertBefore(camCard(c), next || null);
  });
  shown.forEach(updateCard);
  $("#no-cam").classList.toggle("hidden", cameras.length > 0);
  $("#no-selected").classList.toggle("hidden", !(cameras.length && !shown.length));
}

function renderCamList() {
  $("#cam-items").innerHTML = cameras.map(c => `
    <li data-id="${c.id}" class="${alertCams.has(c.id) ? "alert" : ""}">
      <input type="checkbox" ${isShown(c) ? "checked" : ""} aria-label="${esc(c.name)}">
      <span class="dot ${statusClass(c)}" title="${esc(t("st_" + c.status))}"></span>
      <button type="button" class="cam-name" title="${esc(t("cams_solo_title"))}">${esc(c.name)}</button>
      <span class="muted small">${esc(t("fps", { n: c.fps }))}</span>
    </li>`).join("");
  $("#cams-count").textContent = t("cams_count", { n: cameras.filter(isShown).length, total: cameras.length });
}

$("#cam-items").addEventListener("change", e => {
  const id = e.target.closest("li")?.dataset.id;
  if (!id) return;
  const ids = new Set(hiddenCams);
  e.target.checked ? ids.delete(id) : ids.add(id);
  setHidden(ids);
});
$("#cam-items").addEventListener("click", e => {
  const id = e.target.closest(".cam-name") && e.target.closest("li").dataset.id;
  if (id) setHidden(cameras.map(c => c.id).filter(x => x !== id));  // n'affiche que celle-ci
});
$("#cams-all").onclick = () => setHidden([]);
$("#cams-none").onclick = () => setHidden(cameras.map(c => c.id));

async function refreshCameras() {
  cameras = await api("/api/cameras");
  syncGrid();
  renderCamList();
  fillCameraFilter();
}

$("#grid-size").onchange = e => $("#grid").className = "grid cols-" + e.target.value;
$("#btn-add").onclick = () => $("#dlg-add").showModal();
$("#cam-form").addEventListener("submit", async e => {
  if (e.submitter?.value !== "ok") return;
  const f = new FormData(e.target);
  const body = { name: f.get("name"), source: f.get("source"), colors: f.has("colors"),
    faces: f.has("faces"), weapons: f.has("weapons"), max_fps: Number(f.get("max_fps")) || null,
    record: f.get("record") || "alerts" };
  try { await api("/api/cameras", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) }); }
  catch (err) { alert(err.message); }
  e.target.reset();
  refreshCameras();
});

function openFull(src) { $("#full-img").src = src; $("#dlg-full").showModal(); }
$("#full-close").onclick = () => { $("#dlg-full").close(); };
$("#dlg-full").addEventListener("close", () => { $("#full-img").src = ""; });

// --- alertes en direct -----------------------------------------------------------
let audioCtx;
function beep() {
  try {
    audioCtx ??= new AudioContext();
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.frequency.value = 880; o.type = "square"; g.gain.value = 0.08;
    o.connect(g).connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime + 0.35);
  } catch { /* son bloqué par le navigateur */ }
}

function toast(ev) {
  const el = document.createElement("div");
  el.className = "toast " + ev.type;
  const title = ev.type === "weapon" ? t("toast_weapon", { label: tlabel(ev.label) })
    : ev.type === "zone" ? t("toast_zone", { name: ev.label, n: ev.value }) : "👤 " + tv(ev.label);
  el.innerHTML = `<b>${esc(title)}</b><br>${esc(ev.camera_name)} · ${fmtTime(ev.ts)}`;
  el.onclick = () => ev.snapshot && openFull("/snapshots/" + ev.snapshot);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), ev.type === "weapon" ? 15000 : 6000);
}

async function pollAlerts() {
  try {
    if (lastEventId === null) {
      const last = await api("/api/events?limit=1");
      lastEventId = last[0]?.id ?? 0;
    } else {
      const evs = (await api(`/api/events?after_id=${lastEventId}&limit=50`)).reverse();
      for (const ev of evs) {
        lastEventId = Math.max(lastEventId, ev.id);
        if (ev.type === "weapon" || ev.type === "face" || ev.type === "zone") toast(ev);
        if (ev.type === "weapon") {
          beep();
          const card = document.getElementById("cam-" + ev.camera_id);
          card?.classList.add("alert");
          alertCams.add(ev.camera_id);  // signalée aussi dans la colonne, même si masquée
          renderCamList();
          setTimeout(() => { card?.classList.remove("alert"); alertCams.delete(ev.camera_id); renderCamList(); }, 8000);
        }
      }
      if (evs.length && $("#tab-events").classList.contains("active")) loadEvents();
    }
  } catch { /* serveur indisponible : on réessaie */ }
}

// --- journal ----------------------------------------------------------------------
async function loadEvents() {
  const params = new URLSearchParams([...new FormData($("#ev-filter"))].filter(([, v]) => v));
  const evs = await api("/api/events?" + params);
  $("#events").innerHTML = evs.length ? evs.map(ev => {
    let title = t(EV_TITLES[ev.type]);
    if (ev.type === "weapon") title += " : " + tlabel(ev.label);
    else if (ev.type === "face") title += " : " + tv(ev.label);
    else if (ev.type === "zone") title += ` : ${ev.label} (${t("people_n", { n: ev.value })})`;
    else if (ev.track_id != null) title += " #" + ev.track_id;
    const conf = ev.confidence != null ? " · " + t("confidence", { n: (ev.confidence * 100).toFixed(0) }) : "";
    return `
    <div class="ev ${ev.type}">
      ${ev.snapshot ? `<img src="/snapshots/${ev.snapshot}" loading="lazy" data-full="/snapshots/${ev.snapshot}">` : ""}
      <div class="meta">
        <span class="title">${esc(title)}</span>
        <span class="muted">${esc(ev.camera_name)} · ${fmtTime(ev.ts)}${conf}</span>
        ${ev.type === "person" ? `<span>${t("top")} : ${garment(ev.upper_type, ev.upper)} &nbsp; ${t("bottom")} : ${garment(ev.lower_type, ev.lower)}</span>` : ""}
      </div>
      <button type="button" class="ev-video" data-cam="${esc(ev.camera_id)}" data-ts="${ev.ts}">${esc(t("rec_watch"))}</button>
    </div>`;
  }).join("") : `<p class="empty">${esc(t("no_events"))}</p>`;
  $("#events").querySelectorAll("img[data-full]").forEach(i => i.onclick = () => openFull(i.dataset.full));
  $("#events").querySelectorAll(".ev-video").forEach(b => b.onclick = () => openRecordingAt(b.dataset.cam, +b.dataset.ts));
}
$("#ev-filter").addEventListener("submit", e => { e.preventDefault(); loadEvents(); });
$("#ev-clear").onclick = async () => {
  if (!confirm(t("confirm_clear"))) return;
  await api("/api/events", { method: "DELETE" }); loadEvents();
};

// --- visages -----------------------------------------------------------------------
async function loadFaces() {
  const faces = await api("/api/faces");
  $("#faces").innerHTML = faces.length ? faces.map(f => `
    <div class="face">
      <header><b>${esc(f.name)}</b><button class="danger" data-name="${esc(f.name)}">${esc(t("delete"))}</button></header>
      <div class="pics">${f.photos.map(p => `<img src="/faces/${encodeURIComponent(f.name)}/${encodeURIComponent(p)}">`).join("")}</div>
      <span class="muted small">${esc(t("photos", { n: f.count }))}</span>
    </div>`).join("") : `<p class="empty">${esc(t("no_faces"))}</p>`;
  $("#faces").querySelectorAll("[data-name]").forEach(b => b.onclick = async () => {
    if (!confirm(t("confirm_delete_face", { name: b.dataset.name }))) return;
    await api("/api/faces/" + encodeURIComponent(b.dataset.name), { method: "DELETE" }); loadFaces();
  });
}
$("#face-form").addEventListener("submit", async e => {
  e.preventDefault();
  const msg = $("#face-msg");
  msg.textContent = t("analysing");
  try {
    const r = await api("/api/faces", { method: "POST", body: new FormData(e.target) });
    msg.textContent = t("enrolled", { name: r.name });
    e.target.photo.value = "";
    loadFaces();
  } catch (err) { msg.textContent = "✗ " + err.message; }
});

// --- paramètres ------------------------------------------------------------------
const pct = v => `${Math.round(v * 100)} %`;
// label / help : clés de traduction (ou fonctions pour les textes avec valeurs)
const SETTINGS_UI = () => [
  { title: "sec_compute", fields: [
    { key: "device", type: "select", label: "s_device",
      options: () => [["auto", t("s_device_auto")],
        ["cuda:0", engineStatus.gpu_available ? t("s_device_gpu", { name: engineStatus.gpu_name }) : t("s_device_nogpu")],
        ["cpu", t("s_device_cpu")]],
      help: () => t("s_device_help", { cur: engineStatus.device === "cpu" ? "CPU" : "GPU" }) },
    { key: "max_fps", type: "number", min: 1, max: 30, label: "s_max_fps", help: "s_max_fps_help" },
  ]},
  { title: "sec_privacy", cls: "privacy", fields: [
    { key: "face_recognition", type: "toggle", label: "s_face_rec", help: "s_face_rec_help", confirmOn: "s_face_rec_confirm" },
    { key: "blur_unknown_faces", type: "toggle", label: "s_blur", help: "s_blur_help" },
    { key: "log_unknown_faces", type: "toggle", label: "s_log_unknown" },
    { key: "retention_days", type: "number", min: 0, max: 3650, label: "s_retention", help: "s_retention_help",
      warn: v => (v === 0 || v > 30) ? t("s_retention_warn") : "" },
    { type: "action", label: "s_privacy_reread", action: () => showPrivacy(),
      help: () => savedSettings.privacy_ack
        ? t("s_privacy_acked", { date: new Date(savedSettings.privacy_ack).toLocaleString(LOCALES[LANG]) })
        : t("s_privacy_not") },
  ]},
  { title: "sec_recording", fields: [
    { key: "recording_pre_s", type: "number", min: 0, max: 60, label: "s_rec_pre", help: "s_rec_pre_help" },
    { key: "recording_post_s", type: "number", min: 5, max: 600, label: "s_rec_post" },
    { key: "recording_fps", type: "number", min: 2, max: 25, label: "s_rec_fps", help: "s_rec_fps_help" },
    { key: "recording_width", type: "select", num: true, label: "s_rec_width",
      options: () => [["960", "960 px"], ["1280", "1280 px (HD)"], ["1920", "1920 px (Full HD)"]] },
    { key: "recording_max_gb", type: "number", min: 0, max: 100000, label: "s_rec_max", help: "s_rec_max_help" },
    { key: "recording_overlay", type: "toggle", label: "s_rec_overlay" },
  ]},
  { title: "sec_detection", fields: [
    { key: "person_conf", type: "range", min: 0.1, max: 0.95, step: 0.05, fmt: pct, label: "s_person_conf" },
    { key: "weapon_conf", type: "range", min: 0.1, max: 0.95, step: 0.05, fmt: pct, label: "s_weapon_conf", help: "s_weapon_conf_help" },
    { key: "weapon_types", type: "toggle", label: "s_weapon_types", help: "s_weapon_types_help" },
    { key: "weapon_verify", type: "toggle", label: "s_weapon_verify", help: "s_weapon_verify_help" },
    { key: "weapon_verify_threshold", type: "range", min: 0.3, max: 0.95, step: 0.05, fmt: pct, label: "s_verify_th", help: "s_verify_th_help" },
    { key: "coco_weapon_conf", type: "range", min: 0.1, max: 0.95, step: 0.05, fmt: pct, label: "s_coco_conf" },
    { key: "face_match_threshold", type: "range", min: 0.2, max: 0.9, step: 0.01, fmt: v => v.toFixed(2),
      label: "s_face_th", help: "s_face_th_help" },
    { key: "weapon_cooldown_s", type: "number", min: 1, max: 3600, label: "s_weapon_cd" },
    { key: "face_cooldown_s", type: "number", min: 1, max: 3600, label: "s_face_cd" },
  ]},
  { title: "sec_display", fields: [
    { key: "clothing", type: "toggle", label: "s_clothing", help: "s_clothing_help" },
    { key: "clothing_min_conf", type: "range", min: 0.1, max: 0.9, step: 0.05, fmt: pct, label: "s_clothing_conf", help: "s_clothing_conf_help" },
    { key: "draw_style", type: "select", label: "s_draw", help: "s_draw_help",
      options: () => [["box", t("s_draw_box")], ["contour", t("s_draw_contour")]] },
    { key: "face_shape", type: "select", label: "s_face_shape",
      options: () => [["oval", t("s_shape_oval")], ["box", t("s_shape_box")]] },
    { key: "overlay_lang", type: "select", label: "s_overlay_lang", help: "s_overlay_lang_help",
      options: () => [["fr", "Français"], ["nl", "Nederlands"], ["en", "English"]] },
  ]},
];

const text = v => typeof v === "function" ? v() : (v ? t(v) : "");

function fieldHTML(f) {
  const help = text(f.help);
  const helpHTML = help ? `<span class="help">${esc(help)}</span>` : "";
  const label = esc(text(f.label));
  if (f.type === "action")
    return `<div class="field"><button type="button" data-action="${f.label}">${label}</button>${helpHTML}</div>`;
  if (f.type === "toggle")
    return `<label class="field toggle"><input type="checkbox" data-key="${f.key}"><span><b>${label}</b><br>${helpHTML}</span></label>`;
  let input;
  if (f.type === "select")
    input = `<select data-key="${f.key}"${f.num ? " data-num" : ""}>${f.options().map(([v, o]) => `<option value="${v}">${esc(o)}</option>`).join("")}</select>`;
  else if (f.type === "range")
    input = `<input type="range" data-key="${f.key}" min="${f.min}" max="${f.max}" step="${f.step}">`;
  else
    input = `<input type="number" data-key="${f.key}" min="${f.min}" max="${f.max}" step="1">`;
  return `<label class="field"><span>${label}${f.type === "range" ? `<span class="val" data-val="${f.key}"></span>` : ""}</span>
    ${input}${helpHTML}<span class="warn" data-warn="${f.key}"></span></label>`;
}

const allFields = () => SETTINGS_UI().flatMap(s => s.fields);

function readField(el) {
  if (el.type === "checkbox") return el.checked;
  if (el.type === "range" || el.type === "number" || el.dataset.num !== undefined) return Number(el.value);
  return el.value;
}

function refreshFieldHints(form) {
  for (const f of allFields()) {
    if (!f.key) continue;
    const v = readField(form.querySelector(`[data-key="${f.key}"]`));
    const out = form.querySelector(`[data-val="${f.key}"]`);
    if (out) out.textContent = f.fmt ? f.fmt(v) : v;
    const w = form.querySelector(`[data-warn="${f.key}"]`);
    if (w) w.textContent = f.warn ? f.warn(v) : "";
  }
}

async function loadSettings() {
  try { engineStatus = { ...engineStatus, ...(await api("/api/status")) }; } catch { /* serveur occupé */ }
  const { values } = await api("/api/settings");
  savedSettings = values;
  const form = $("#settings-form");
  form.innerHTML = SETTINGS_UI().map(s =>
    `<fieldset class="${s.cls || ""}"><legend>${esc(t(s.title))}</legend>${s.fields.map(fieldHTML).join("")}</fieldset>`).join("");
  for (const f of allFields()) {
    if (!f.key) continue;
    const el = form.querySelector(`[data-key="${f.key}"]`);
    if (el.type === "checkbox") el.checked = !!values[f.key];
    else el.value = String(values[f.key]);
    el.addEventListener("input", () => refreshFieldHints(form));
    if (f.confirmOn) el.addEventListener("change", () => {
      if (el.checked && !confirm(t(f.confirmOn))) el.checked = false;
    });
  }
  form.querySelectorAll("[data-action]").forEach(b =>
    b.onclick = () => allFields().find(f => f.label === b.dataset.action).action());
  refreshFieldHints(form);
  $("#settings-msg").textContent = "";
}

$("#settings-save").onclick = async () => {
  const form = $("#settings-form"), changes = {};
  for (const f of allFields()) {
    if (!f.key) continue;
    const v = readField(form.querySelector(`[data-key="${f.key}"]`));
    if (v !== savedSettings[f.key]) changes[f.key] = v;
  }
  const msg = $("#settings-msg");
  if (!Object.keys(changes).length) { msg.textContent = t("no_change"); return; }
  try {
    const r = await api("/api/settings", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(changes) });
    Object.assign(savedSettings, changes);
    msg.textContent = t("saved");
    if (r.reloading) waitReload();
    else loadStatus();
  } catch (err) { msg.textContent = "✗ " + err.message; }
};

// Rechargement des modèles : on attend la fin puis on recharge la page (flux vidéo compris)
async function waitReload() {
  $("#reload-overlay").classList.remove("hidden");
  await new Promise(r => setTimeout(r, 1500));
  for (;;) {
    try { if (!(await api("/api/status")).reloading) break; } catch { /* serveur occupé */ }
    await new Promise(r => setTimeout(r, 1000));
  }
  location.reload();
}

// --- avertissement RGPD -----------------------------------------------------------
function showPrivacy() {
  const dlg = $("#dlg-privacy");
  if (dlg.open) return;
  const acked = !!(savedSettings.privacy_ack || engineStatus.privacy_ack);
  $("#privacy-check").checked = acked;
  $("#privacy-ok").disabled = !acked;
  dlg.showModal();
}
$("#privacy-check").onchange = e => { $("#privacy-ok").disabled = !e.target.checked; };
// Échap ne ferme pas l'avertissement tant qu'il n'a pas été validé
$("#dlg-privacy").addEventListener("cancel", e => { if (!engineStatus.privacy_ack) e.preventDefault(); });
$("#privacy-form").addEventListener("submit", async () => {
  if (engineStatus.privacy_ack) return;
  const ack = new Date().toISOString();
  await api("/api/settings", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ privacy_ack: ack }) });
  engineStatus.privacy_ack = savedSettings.privacy_ack = ack;
  if ($("#tab-settings").classList.contains("active")) loadSettings();
});

// --- démarrage ---------------------------------------------------------------------
(async () => {
  applyStatic();
  try { VALUE_NAMES = await api("/api/i18n"); } catch { /* noms bruts en attendant */ }
  await loadStatus().catch(() => {});
  await refreshCameras().catch(() => {});  // la liste des caméras sert aussi à l'onglet ouvert ci-dessous
  // Ouvre directement l'onglet demandé dans l'adresse (ex. http://localhost:8000/#events)
  document.querySelector(`nav button[data-tab="${location.hash.slice(1)}"]`)?.click();
})();
// Horloge du bandeau (format de la langue choisie)
const tickClock = () => {
  const now = new Date();
  $("#hud-clock").textContent = now.toLocaleDateString(LOCALES[LANG]) + "  " + now.toLocaleTimeString(LOCALES[LANG]);
};
tickClock();
setInterval(tickClock, 1000);
setInterval(refreshCameras, 3000);
setInterval(pollAlerts, 1500);
