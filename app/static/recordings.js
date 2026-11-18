// Onglet « Enregistrements » : ligne de temps sur 24 h, lecture, extrait à exporter.
const REC = { cam: null, dayStart: 0, segments: [], events: [], seg: null, markIn: null, markOut: null };
const recVideo = $("#rec-video");
const DAY = 86400;

const startOfDay = d => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x.getTime() / 1000; };
const fmtClock = ts => new Date(ts * 1000).toLocaleTimeString(LOCALES[LANG]);
const fmtDur = s => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
  return (h ? `${h} h ` : "") + (h || m ? `${m} min ` : "") + `${r} s`; };
const fmtBytes = b => { const [g, m, k] = LANG === "fr" ? ["Go", "Mo", "Ko"] : ["GB", "MB", "KB"];
  return b >= 1e9 ? (b / 1e9).toFixed(1) + " " + g : b >= 1e6 ? (b / 1e6).toFixed(0) + " " + m : (b / 1e3).toFixed(0) + " " + k; };
const isoDay = ts => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

async function loadRecordingsTab() {
  const sel = $("#rec-cam");
  const cur = REC.cam || sel.value || cameras[0]?.id || "";
  sel.innerHTML = cameras.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  sel.value = cur;
  REC.cam = sel.value;
  if (!REC.dayStart) REC.dayStart = startOfDay(Date.now());
  $("#rec-day").value = isoDay(REC.dayStart);
  await loadRecDay();
}

async function loadRecDay() {
  if (!REC.cam) { renderRecDay(); return; }
  const [segs, evs, usage] = await Promise.all([
    api(`/api/recordings?camera_id=${REC.cam}&start=${REC.dayStart}&end=${REC.dayStart + DAY}`),
    api(`/api/events?camera_id=${REC.cam}&since=${REC.dayStart}&limit=1000`),
    api("/api/recordings/usage"),
  ]);
  REC.segments = segs;
  REC.events = evs.filter(e => e.ts < REC.dayStart + DAY && e.type !== "person");
  const max = usage.max_gb ? fmtBytes(usage.max_gb * 1e9) : t("rec_unlimited");
  $("#rec-usage").textContent = t("rec_usage", { n: usage.count, used: fmtBytes(usage.bytes), max });
  renderRecDay();
}

function renderRecDay() {
  const pct = ts => Math.min(100, Math.max(0, (ts - REC.dayStart) / DAY * 100));
  $("#rec-timeline .tl-hours").innerHTML = Array.from({ length: 25 }, (_, h) =>
    `<span style="left:${h / 24 * 100}%">${h % 3 === 0 ? String(h).padStart(2, "0") : ""}</span>`).join("");
  $("#rec-timeline .tl-track").innerHTML =
    REC.segments.map(s => `<div class="tl-seg ${s.kind}${s.open ? " live" : ""}" style="left:${pct(s.start)}%;width:${Math.max(.15, pct(s.end) - pct(s.start))}%"
      title="${esc(fmtClock(s.start))} – ${esc(fmtClock(s.end))}"></div>`).join("") +
    REC.events.map(e => `<div class="tl-ev ${e.type}" style="left:${pct(e.ts)}%" title="${esc(fmtClock(e.ts) + " · " + t(EV_TITLES[e.type]) + " : " + (e.type === "weapon" ? tlabel(e.label) : tv(e.label)))}"></div>`).join("");
  $("#rec-empty").classList.toggle("hidden", REC.segments.length > 0);
  $("#rec-list").innerHTML = REC.segments.slice().reverse().map(s => `
    <li data-id="${s.id}" class="${REC.seg?.id === s.id ? "active" : ""}">
      <button type="button" class="rec-play">▶ ${esc(fmtClock(s.start))} – ${esc(fmtClock(s.end))}</button>
      <span class="muted small">${esc(t(s.kind === "continuous" ? "rec_kind_continuous" : "rec_kind_event"))} · ${esc(fmtDur(s.end - s.start))} · ${esc(fmtBytes(s.size))}${s.open ? " · " + esc(t("rec_live")) : ""}</span>
      ${s.open ? "" : `<button type="button" class="rec-del danger" title="${esc(t("delete"))}">✕</button>`}
    </li>`).join("");
  renderRecHead();
  renderRecRange();
}

function renderRecHead() {
  const head = $("#rec-timeline .tl-head");
  if (!REC.seg) { head.classList.add("hidden"); return; }
  const ts = REC.seg.start + (recVideo.currentTime || 0);
  head.classList.toggle("hidden", ts < REC.dayStart || ts > REC.dayStart + DAY);
  head.style.left = `${(ts - REC.dayStart) / DAY * 100}%`;
  $("#rec-clock").textContent = new Date(ts * 1000).toLocaleString(LOCALES[LANG]);
}

function renderRecRange() {
  const { markIn: a, markOut: b } = REC;
  $("#rec-range").textContent = a && b && b > a
    ? t("rec_range", { a: fmtClock(a), b: fmtClock(b), d: fmtDur(b - a) })
    : a ? t("rec_range", { a: fmtClock(a), b: "…", d: "" }) : t("rec_range_hint");
  $("#rec-export").disabled = !(a && b && b > a);
}

function playSegment(seg, offset = 0) {
  REC.seg = seg;
  recVideo.src = `/api/recordings/${seg.id}/video?v=${seg.open ? Date.now() : seg.id}`;
  recVideo.onloadedmetadata = () => {
    recVideo.currentTime = Math.max(0, Math.min(offset, (recVideo.duration || offset) - 0.5));
    recVideo.play().catch(() => {});
  };
  renderRecDay();
}

async function playAt(ts) {
  try {
    const r = await api(`/api/recordings/locate?camera_id=${REC.cam}&ts=${ts}`);
    playSegment(r, r.offset);
  } catch (err) { $("#rec-range").textContent = "✗ " + err.message; }
}

// Ouverture depuis le journal : bonne caméra, bon jour, quelques secondes avant l'alerte
async function openRecordingAt(camId, ts) {
  REC.cam = camId;
  REC.dayStart = startOfDay(ts * 1000);
  document.querySelector('nav button[data-tab="recordings"]').click();
  await loadRecordingsTab();
  playAt(ts - 5);
}

recVideo.addEventListener("timeupdate", renderRecHead);
recVideo.addEventListener("ended", () => {  // enchaîne sur le segment suivant
  const next = REC.segments.find(s => s.start >= REC.seg.end - 2 && s.id !== REC.seg.id);
  if (next) playSegment(next, 0);
});
$("#rec-timeline .tl-track").addEventListener("click", e => {
  const r = e.currentTarget.getBoundingClientRect();
  playAt(REC.dayStart + (e.clientX - r.left) / r.width * DAY);
});
$("#rec-cam").onchange = e => { REC.cam = e.target.value; REC.seg = null; recVideo.removeAttribute("src"); loadRecDay(); };
$("#rec-day").onchange = e => { if (e.target.value) { REC.dayStart = startOfDay(e.target.value + "T00:00"); loadRecDay(); } };
const shiftDay = n => { REC.dayStart = startOfDay((REC.dayStart + n * DAY + 3600) * 1000); $("#rec-day").value = isoDay(REC.dayStart); loadRecDay(); };
$("#rec-prev-day").onclick = () => shiftDay(-1);
$("#rec-next-day").onclick = () => shiftDay(1);
$("#rec-today").onclick = () => { REC.dayStart = startOfDay(Date.now()); $("#rec-day").value = isoDay(REC.dayStart); loadRecDay(); };
$("#rec-back").onclick = () => { recVideo.currentTime = Math.max(0, recVideo.currentTime - 10); };
$("#rec-fwd").onclick = () => { recVideo.currentTime += 10; };
const nowTs = () => REC.seg ? REC.seg.start + recVideo.currentTime : null;
$("#rec-in").onclick = () => { REC.markIn = nowTs(); if (REC.markOut && REC.markOut <= REC.markIn) REC.markOut = null; renderRecRange(); };
$("#rec-out").onclick = () => { REC.markOut = nowTs(); renderRecRange(); };
$("#rec-export").onclick = () => {
  const a = document.createElement("a");
  a.href = `/api/recordings/export?camera_id=${REC.cam}&start=${REC.markIn.toFixed(2)}&end=${REC.markOut.toFixed(2)}`;
  a.download = "";
  document.body.append(a); a.click(); a.remove();
};
$("#rec-list").addEventListener("click", async e => {
  const li = e.target.closest("li");
  const seg = li && REC.segments.find(s => s.id === +li.dataset.id);
  if (!seg) return;
  if (e.target.closest(".rec-play")) playSegment(seg, 0);
  if (e.target.closest(".rec-del")) {
    if (!confirm(t("rec_delete_confirm"))) return;
    await api(`/api/recordings/${seg.id}`, { method: "DELETE" });
    if (REC.seg?.id === seg.id) { REC.seg = null; recVideo.removeAttribute("src"); }
    loadRecDay();
  }
});
// segment en cours : rafraîchit la ligne de temps de temps en temps
setInterval(() => { if ($("#tab-recordings").classList.contains("active") && !recVideo.seeking) loadRecDay().catch(() => {}); }, 30000);
