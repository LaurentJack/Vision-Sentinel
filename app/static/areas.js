// Éditeur des zones (comptage des personnes présentes) et lignes (comptage des passages).
// Coordonnées enregistrées en relatif (0 à 1) : indépendantes de la résolution de la caméra.
const AE = { cam: null, areas: [], mode: null, draft: [], mouse: null, hover: null };
const areaCanvas = $("#area-canvas");
const areaImg = $("#area-img");
const ZONE_RGB = "40, 180, 230";
const LINE_RGB = "255, 200, 0";
const CLOSE_PX = 12;  // clic à moins de 12 px du premier point = zone fermée

function openAreas(cam) {
  AE.cam = cam;
  AE.areas = JSON.parse(JSON.stringify(cam.areas || []));
  AE.mode = null;
  AE.draft = [];
  AE.hover = null;
  $("#areas-title").textContent = t("areas_title", { name: cam.name });
  areaImg.onload = () => { fitAreaCanvas(); renderAreaList(); drawAreaCanvas(); };
  areaImg.src = `/api/cameras/${cam.id}/frame?t=${Date.now()}`;  // image brute, sans dessins
  setAreaMode(null);
  renderAreaList();
  $("#dlg-areas").showModal();
}

function fitAreaCanvas() {
  areaCanvas.width = areaImg.clientWidth;
  areaCanvas.height = areaImg.clientHeight;
}
window.addEventListener("resize", () => { if ($("#dlg-areas").open) { fitAreaCanvas(); drawAreaCanvas(); } });

const toNorm = e => {
  const r = areaCanvas.getBoundingClientRect();
  return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))];
};
const toPx = ([x, y]) => [x * areaCanvas.width, y * areaCanvas.height];

function setAreaMode(mode) {
  AE.mode = mode;
  AE.draft = [];
  $("#tool-zone").classList.toggle("on", mode === "zone");
  $("#tool-line").classList.toggle("on", mode === "line");
  $("#tool-finish").classList.toggle("hidden", mode !== "zone");
  $("#area-hint").textContent = t(mode === "zone" ? "hint_zone" : mode === "line" ? "hint_line" : "hint_idle");
  areaCanvas.classList.toggle("drawing", !!mode);
  drawAreaCanvas();
}

function finishDraft() {
  const { mode, draft } = AE;
  if (!((mode === "zone" && draft.length >= 3) || (mode === "line" && draft.length === 2))) return;
  const n = AE.areas.filter(a => a.kind === mode).length + 1;
  AE.areas.push({
    id: Math.random().toString(36).slice(2, 10), kind: mode, points: draft.map(p => p.map(v => +v.toFixed(4))),
    name: t(mode === "zone" ? "default_zone" : "default_line", { n }),
  });
  setAreaMode(null);
  renderAreaList();
}

areaCanvas.addEventListener("click", e => {
  if (!AE.mode) return;
  const p = toNorm(e);
  if (AE.mode === "zone" && AE.draft.length >= 3) {
    const [x0, y0] = toPx(AE.draft[0]), [x, y] = toPx(p);
    if (Math.hypot(x - x0, y - y0) < CLOSE_PX) { finishDraft(); return; }
  }
  AE.draft.push(p);
  if (AE.mode === "line" && AE.draft.length === 2) finishDraft();
  else drawAreaCanvas();
});
areaCanvas.addEventListener("mousemove", e => { AE.mouse = toNorm(e); if (AE.mode) drawAreaCanvas(); });
areaCanvas.addEventListener("mouseleave", () => { AE.mouse = null; drawAreaCanvas(); });

// Échap annule le tracé en cours (sans fermer la fenêtre) ; Entrée ferme la zone
$("#dlg-areas").addEventListener("cancel", e => { if (AE.mode) { e.preventDefault(); setAreaMode(null); } });
$("#dlg-areas").addEventListener("keydown", e => {
  if (e.key === "Enter" && AE.mode === "zone" && e.target.tagName !== "INPUT") { e.preventDefault(); finishDraft(); }
});

$("#tool-zone").onclick = () => setAreaMode(AE.mode === "zone" ? null : "zone");
$("#tool-line").onclick = () => setAreaMode(AE.mode === "line" ? null : "line");
$("#tool-finish").onclick = finishDraft;
$("#areas-cancel").onclick = () => $("#dlg-areas").close();
$("#areas-save").onclick = async () => {
  try {
    await api(`/api/cameras/${AE.cam.id}/areas`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ areas: AE.areas }) });
    $("#dlg-areas").close();
    refreshCameras();
  } catch (err) { alert(err.message); }
};

// --- dessin dans l'éditeur ---------------------------------------------------------
function drawArrow(ctx, a, b, rgb) {
  const [x1, y1] = toPx(a), [x2, y2] = toPx(b);
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  let nx = -(y2 - y1), ny = x2 - x1;
  const len = Math.hypot(nx, ny) || 1;
  nx /= len; ny /= len;
  const L = 34, tx = mx + nx * L, ty = my + ny * L;
  ctx.strokeStyle = ctx.fillStyle = `rgb(${rgb})`;
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(tx, ty); ctx.stroke();
  const ang = Math.atan2(ny, nx);
  ctx.beginPath();
  ctx.moveTo(tx, ty);
  ctx.lineTo(tx - 10 * Math.cos(ang - 0.45), ty - 10 * Math.sin(ang - 0.45));
  ctx.lineTo(tx - 10 * Math.cos(ang + 0.45), ty - 10 * Math.sin(ang + 0.45));
  ctx.closePath(); ctx.fill();
}

function drawTag(ctx, text, x, y, rgb) {
  ctx.font = "600 12px system-ui, sans-serif";
  const w = ctx.measureText(text).width + 8;
  ctx.fillStyle = `rgb(${rgb})`;
  ctx.fillRect(x, y - 16, w, 16);
  ctx.fillStyle = "#000";
  ctx.fillText(text, x + 4, y - 4);
}

function drawAreaCanvas() {
  const ctx = areaCanvas.getContext("2d");
  ctx.clearRect(0, 0, areaCanvas.width, areaCanvas.height);
  for (const a of AE.areas) {
    const pts = a.points.map(toPx);
    const hot = AE.hover === a.id;
    if (a.kind === "zone") {
      ctx.beginPath();
      pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
      ctx.closePath();
      ctx.fillStyle = `rgba(${ZONE_RGB}, ${hot ? 0.35 : 0.2})`;
      ctx.fill();
      ctx.strokeStyle = `rgb(${ZONE_RGB})`; ctx.lineWidth = hot ? 4 : 2; ctx.stroke();
      const top = pts.reduce((m, p) => p[1] < m[1] ? p : m);
      drawTag(ctx, a.name, top[0], top[1] - 2, ZONE_RGB);
    } else {
      ctx.strokeStyle = `rgb(${LINE_RGB})`; ctx.lineWidth = hot ? 6 : 4;
      ctx.beginPath(); ctx.moveTo(...pts[0]); ctx.lineTo(...pts[1]); ctx.stroke();
      drawArrow(ctx, a.points[0], a.points[1], LINE_RGB);
      drawTag(ctx, a.name, Math.min(pts[0][0], pts[1][0]), Math.min(pts[0][1], pts[1][1]) - 4, LINE_RGB);
    }
  }
  // Tracé en cours
  if (AE.mode && AE.draft.length) {
    const rgb = AE.mode === "zone" ? ZONE_RGB : LINE_RGB;
    const pts = AE.draft.map(toPx);
    ctx.strokeStyle = `rgb(${rgb})`; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    ctx.beginPath();
    pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    if (AE.mouse) ctx.lineTo(...toPx(AE.mouse));
    ctx.stroke(); ctx.setLineDash([]);
    pts.forEach(([x, y], i) => {
      ctx.fillStyle = i === 0 && AE.mode === "zone" ? "#fff" : `rgb(${rgb})`;
      ctx.beginPath(); ctx.arc(x, y, i === 0 && AE.mode === "zone" ? 7 : 4, 0, 2 * Math.PI); ctx.fill();
    });
  }
}

// --- liste à droite de l'image ------------------------------------------------------
function countText(a, c) {
  if (!c) return "";
  const since = t("since", { date: new Date(c.since * 1000).toLocaleString(LOCALES[LANG]) });
  const main = a.kind === "zone" ? t("count_zone", { inside: c.inside, max: c.max }) : t("count_line", { in: c.in, out: c.out });
  return `${main}<br><span class="muted">${esc(since)}</span>`;
}

function renderAreaList() {
  const counts = AE.cam?.counts || {};
  const ul = $("#area-list");
  ul.innerHTML = AE.areas.length ? AE.areas.map(a => `
    <li data-id="${a.id}" class="${a.kind}">
      <div class="row">
        <span class="kind">${esc(t(a.kind === "zone" ? "kind_zone" : "kind_line"))}</span>
        <input class="a-name" value="${esc(a.name)}" maxlength="40">
        <button type="button" class="a-del danger" title="${esc(t("delete"))}">✕</button>
      </div>
      ${a.kind === "zone"
        ? `<label class="small">${esc(t("zone_alert"))} <input type="number" class="a-max" min="1" max="1000" value="${a.max_people ?? ""}" placeholder="—"> ${esc(t("people"))}</label>`
        : `<button type="button" class="a-invert small">${esc(t("invert"))}</button>`}
      ${counts[a.id] ? `<div class="small a-counts">${countText(a, counts[a.id])}</div>
        <button type="button" class="a-reset small">${esc(t("reset_counts"))}</button>` : ""}
    </li>`).join("") : `<li class="empty small">${esc(t("no_areas"))}</li>`;
}

const areaOf = el => AE.areas.find(a => a.id === el.closest("li")?.dataset.id);
$("#area-list").addEventListener("input", e => {
  const a = areaOf(e.target);
  if (!a) return;
  if (e.target.classList.contains("a-name")) a.name = e.target.value;
  if (e.target.classList.contains("a-max")) {
    const v = parseInt(e.target.value, 10);
    if (v > 0) a.max_people = v; else delete a.max_people;
  }
  drawAreaCanvas();
});
$("#area-list").addEventListener("click", async e => {
  const a = areaOf(e.target);
  if (!a) return;
  if (e.target.classList.contains("a-del")) {
    AE.areas = AE.areas.filter(x => x !== a);
    renderAreaList();
  } else if (e.target.classList.contains("a-invert")) {
    a.points.reverse();  // la flèche « entrée » change de côté
  } else if (e.target.classList.contains("a-reset")) {
    if (!confirm(t("confirm_reset", { name: a.name }))) return;
    AE.cam = await api(`/api/cameras/${AE.cam.id}/areas/${a.id}/reset`, { method: "POST" });
    renderAreaList();
  }
  drawAreaCanvas();
});
$("#area-list").addEventListener("mouseover", e => {
  const id = e.target.closest("li")?.dataset.id || null;
  if (id !== AE.hover) { AE.hover = id; drawAreaCanvas(); }
});
$("#area-list").addEventListener("mouseleave", () => { AE.hover = null; drawAreaCanvas(); });

// --- compteurs affichés sous chaque caméra du direct ---------------------------------
function areaChips(c) {
  return (c.areas || []).map(a => {
    const n = c.counts?.[a.id];
    if (!n) return "";
    if (a.kind === "zone") {
      const over = a.max_people && n.inside > a.max_people;
      const cap = a.max_people ? `/${a.max_people}` : "";
      return `<span class="chip zone ${over ? "over" : ""}">${esc(a.name)} : <b>${n.inside}</b>${cap}</span>`;
    }
    return `<span class="chip line">${esc(a.name)} : ${esc(t("count_line", { in: n.in, out: n.out }))}</span>`;
  }).join("");
}
