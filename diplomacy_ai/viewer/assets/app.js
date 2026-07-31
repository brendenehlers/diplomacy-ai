(function () {
"use strict";
const G = JSON.parse(document.getElementById("data").textContent);
const M = JSON.parse(document.getElementById("mapdata").textContent);
const POWERS = G.powers;

const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const PC = p => `var(--${p})`;
const SEASON = { S: "Spring", F: "Autumn", W: "Winter" };
const KIND = { M: "Movement", R: "Retreats", A: "Adjustments" };
const $ = id => document.getElementById(id);
const nf = n => n.toLocaleString();

function phaseLabel(n) {
  const s = SEASON[n[0]], y = n.slice(1, 5), k = KIND[n[5]];
  return s && k ? `${s} ${y} · ${k}` : n;
}
const isPlayable = n => /^[SFW]\d{4}[MRA]$/.test(n);

/* ------------------------------------------------------------------ theme */
const root = document.documentElement;
$("themetog").addEventListener("click", () => {
  const dark = getComputedStyle(root).getPropertyValue("--page").trim() === "#0E1820";
  const pick = dark ? "light" : "dark";
  root.setAttribute("data-theme", pick);
  // The head applies this before the first paint, so a --watch reload does not
  // flash the system theme on its way back to the chosen one.
  try { sessionStorage.setItem("dai:theme", pick); } catch (e) { /* no storage */ }
});

/* ------------------------------------------------------------------ header */
const S = G.setup, endPhase = G.phases[G.phases.length - 1];
const years = G.phases.filter(p => isPlayable(p.n)).map(p => p.n.slice(1, 5));
const span = years.length ? `${years[0]}–${years[years.length - 1]}` : "";
const totalCalls = POWERS.reduce((a, p) => a + G.models[p].calls, 0);
const totalErr = POWERS.reduce((a, p) => a + G.models[p].errors, 0);

$("runid").textContent = "· RUN " + S.run;
$("mast-span").textContent = `${POWERS.length} POWERS · ${span}`;
$("mast-calls").textContent = `${nf(totalCalls)} MODEL CALLS · ${nf(totalErr)} ERRORS`;
$("eyebrow").textContent = `${G.phases.length} phases recorded`;
$("title").textContent = `Run ${S.run}`;

const finalC = {}; POWERS.forEach(p => finalC[p] = (endPhase.c[p] || []).length);
const leader = POWERS.reduce((a, b) => finalC[a] >= finalC[b] ? a : b);
$("dek").innerHTML = `Every phase of this game is below — the board, each power's private
  reasoning, the messages it sent, and the orders it submitted. It ended at
  <b>${esc(endPhase.n)}</b> with <b>${esc(leader)}</b> on
  <b>${finalC[leader]} supply centres</b>.`;
$("gnote").textContent = `${G.phases.length} phases · every message, every order`;

/* ------------------------------------------------------------------ setup */
(function setup() {
  const st = S.settings, rows = [];
  if (st.n_negotiation_rounds != null) rows.push([st.n_negotiation_rounds, "Press rounds / turn"]);
  if (st.max_year != null) rows.push([st.max_year, "Max year"]);
  rows.push([G.phases.length, "Phases played"]);
  if (st.temperature != null) rows.push([st.temperature, "Temperature"]);
  else rows.push(["default", "Temperature"]);
  if (st.timeout != null) rows.push([st.timeout + "s", "Timeout"]);
  $("settings").innerHTML = rows.map(([n, l]) =>
    `<div class="fig"><span class="n tnum">${esc(n)}</span><span class="l">${esc(l)}</span></div>`
  ).join("");

  $("roster").innerHTML = POWERS.map(p => {
    const c = S.powers[p], seen = Object.keys(G.models[p].models);
    const model = c.model || seen[0] || "unrecorded";
    return `<div class="rcard">
      <div class="rhead"><span class="swatch" style="background:${PC(p)}"></span>
        <span class="rname">${esc(p)}</span></div>
      <div class="model">${esc(model)}</div>
      ${c.persona ? `<p class="persona">${esc(c.persona)}</p>` : ""}
      <div class="start">${(c.units || []).join(" · ") || "no starting units"}</div>
    </div>`;
  }).join("");
  // The 1px-gap grids paint their gutter colour; without fillers a short final
  // row leaves a bare slab of it.
  fillRow($("settings"), "fig");
  fillRow($("roster"), "rcard");
})();

function fillRow(host, cls) {
  const kids = [...host.children];
  if (!kids.length) return;
  const perRow = new Set(kids.map(k => k.offsetTop)).size
    ? kids.filter(k => k.offsetTop === kids[0].offsetTop).length : kids.length;
  const short = kids.length % perRow;
  for (let i = short && perRow - short; i > 0; i--) {
    const d = document.createElement("div");
    d.className = cls;
    d.setAttribute("aria-hidden", "true");
    host.appendChild(d);
  }
}

/* ------------------------------------------------------------------ board */
function buildBoard() {
  const svg = $("board");
  svg.setAttribute("viewBox", M.vb);
  const cls = c => c === "water" ? "water" : c === "impassable" ? "imp" : "land";
  // The shapes carry the map layer's own transform; it has to ride with them or
  // they land ~200px off the unit anchors, dots and labels they belong to. It
  // goes on an inner group so #pvs still measures the transformed box.
  const shapes = M.paths.map(p =>
    `<path class="pv ${cls(p.c)}" id="pv_${p.id}" d="${p.d}"><title>${p.id}</title></path>`
  ).join("");
  svg.innerHTML =
    `<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5"
      markerHeight="4.5" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="context-stroke"/></marker></defs>` +
    `<g id="pvs">` + (M.tr ? `<g transform="${esc(M.tr)}">${shapes}</g>` : shapes) + `</g>` +
    `<g id="scs">` + Object.values(M.sc).map(v =>
      `<circle class="scdot" cx="${v[0]}" cy="${v[1]}" r="6"/>`).join("") + `</g>` +
    `<g id="lbls">` + M.labels.map(l => l.tr
      ? `<text class="lbl" transform="${esc(l.tr)}">${esc(l.t)}</text>`
      : `<text class="lbl" x="${l.x}" y="${l.y}">${esc(l.t)}</text>`).join("") + `</g>` +
    `<g id="orders"></g><g id="units"></g>`;
  fitBoard(svg);
}

function fitBoard(svg, pad = 18) {
  // The source viewBox both pads the map and clips it — on the standard board
  // Syria and Armenia sit outside it entirely. Measure what we actually drew.
  let box = null;
  for (const id of ["pvs", "lbls"]) {   // some labels overhang the province shapes
    const g = document.getElementById(id);
    if (!g || !g.getBBox) continue;
    let b;
    try { b = g.getBBox(); } catch (e) { continue; }
    if (!b || !b.width || !b.height) continue;
    box = box
      ? { x: Math.min(box.x, b.x), y: Math.min(box.y, b.y),
          r: Math.max(box.r, b.x + b.width), b: Math.max(box.b, b.y + b.height) }
      : { x: b.x, y: b.y, r: b.x + b.width, b: b.y + b.height };
  }
  if (!box) return;                              // keep the shipped viewBox
  svg.setAttribute("viewBox",
    `${(box.x - pad).toFixed(0)} ${(box.y - pad).toFixed(0)} ` +
    `${(box.r - box.x + pad * 2).toFixed(0)} ${(box.b - box.y + pad * 2).toFixed(0)}`);
}

const at = p => M.units[p] || M.units[p.split("/")[0]] || null;

function drawOrders(ph) {
  let out = "";
  for (const pw of Object.keys(ph.o || {})) {
    const col = PC(pw);
    for (const raw of ph.o[pw] || []) {   // the phase in progress has none yet
      const t = String(raw).trim(); let m;
      if ((m = t.match(/^[AF] (\S+) S [AF] (\S+) - (\S+)$/))) {
        const s = at(m[1]), b = at(m[3]);
        if (s && b) out += `<path class="osup" stroke="${col}" d="M${s[0]} ${s[1]}
          Q${(s[0] + b[0]) / 2} ${(s[1] + b[1]) / 2} ${b[0]} ${b[1]}"/>`;
      } else if ((m = t.match(/^[AF] (\S+) S [AF] (\S+)$/))) {
        const s = at(m[1]), b = at(m[2]);
        if (s && b) out += `<path class="osup" stroke="${col}" d="M${s[0]} ${s[1]} L${b[0]} ${b[1]}"/>`;
      } else if ((m = t.match(/^[AF] (\S+) C [AF] (\S+) - (\S+)$/))) {
        const s = at(m[1]), a = at(m[2]), b = at(m[3]);
        if (s && a && b) out += `<path class="oconv" stroke="${col}"
          d="M${a[0]} ${a[1]} L${s[0]} ${s[1]} L${b[0]} ${b[1]}"/>`;
      } else if ((m = t.match(/^[AF] (\S+) - (\S+)/))) {
        const a = at(m[1]), b = at(m[2]);
        if (a && b) out += `<path class="omove" stroke="${col}" d="M${a[0]} ${a[1]} L${b[0]} ${b[1]}"/>`;
      } else if ((m = t.match(/^[AF] (\S+) H$/))) {
        const a = at(m[1]);
        if (a) out += `<circle class="ohold" stroke="${col}" cx="${a[0]}" cy="${a[1]}" r="21"/>`;
      } else if ((m = t.match(/^[AF] (\S+) B$/))) {
        const a = at(m[1]);
        if (a) out += `<circle class="obuild" stroke="${col}" cx="${a[0]}" cy="${a[1]}" r="24"/>`;
      } else if ((m = t.match(/^[AF] (\S+) D$/))) {
        const a = at(m[1]);
        if (a) out += `<g class="odis" stroke="${col}"><circle cx="${a[0]}" cy="${a[1]}" r="24"/>
          <path d="M${a[0] - 16} ${a[1] - 16} l32 32 M${a[0] + 16} ${a[1] - 16} l-32 32"/></g>`;
      }
    }
  }
  $("orders").innerHTML = out;
}

function drawUnits(ph) {
  let out = "";
  for (const pw of POWERS) {
    for (const u of (ph.u[pw] || [])) {
      // A retreat phase marks a dislodged unit with a leading "*"; it shares the
      // province with whoever pushed it out, so draw it faded rather than as a
      // unit of kind "*".
      const dis = u[0] === "*", s = dis ? u.slice(1) : u;
      const kind = s[0], loc = s.slice(2).trim(), a = at(loc);
      if (!a) continue;
      // Nudged clear of the unit that dislodged it, which stands on the same dot.
      const c = dis ? [a[0] + 15, a[1] - 15] : a;
      const k = `unit${dis ? " dis" : ""}`, name = dis ? " dislodged" : "";
      out += kind === "F"
        ? `<path class="${k}" fill="${PC(pw)}" d="M${c[0] - 15} ${c[1] - 9} h30 l-6 18 h-18 z">
            <title>${pw} fleet ${loc}${name}</title></path>`
        : `<circle class="${k}" fill="${PC(pw)}" cx="${c[0]}" cy="${c[1]}" r="13">
            <title>${pw} army ${loc}${name}</title></circle>`;
      out += `<text class="utxt${dis ? " dis" : ""}" x="${c[0]}"
        y="${c[1] + (kind === "F" ? 4 : 0)}">${kind}</text>`;
    }
  }
  $("units").innerHTML = out;
}

function paint(ph) {
  const owner = {};
  for (const pw of POWERS) for (const c of (ph.c[pw] || [])) owner[c] = pw;
  document.querySelectorAll("#pvs .pv").forEach(el => {
    if (el.classList.contains("water") || el.classList.contains("imp")) return;
    const o = owner[el.id.slice(3)];
    el.style.fill = o ? PC(o) : "var(--land)";
    el.style.fillOpacity = o ? .42 : 1;
  });
  $("legend").innerHTML = POWERS.map(p =>
    `<span class="lg"><i style="background:${PC(p)}"></i>${p}
      <span class="cnt">${(ph.c[p] || []).length}</span></span>`).join("") +
    `<span class="lg" style="margin-left:auto">&#9679; army &nbsp; &#9660; fleet &nbsp;
      &#8594; move &nbsp; &#9476;&#9476; support &nbsp; &#8413; hold &nbsp; &#10005; disband</span>`;
}

/* ------------------------------------------------------------- side panel */
let cur = 0, curPower = POWERS[0], curRound = 0;

function panel() {
  const ph = G.phases[cur];
  $("ptabs").innerHTML = POWERS.map(p => {
    const has = ph.press[p] || ph.dec[p] || ((ph.o || {})[p] || []).length;
    return `<button class="ptab" role="tab" type="button" data-p="${p}" ${has ? "" : "disabled"}
      aria-selected="${p === curPower}"
      style="border-top-color:${p === curPower ? PC(p) : "transparent"}">${p.slice(0, 3)}</button>`;
  }).join("");

  const press = ph.press[curPower], dec = ph.dec[curPower];
  const orders = (ph.o || {})[curPower] || [];
  if (!press && !dec && !orders.length) {
    $("pbody").innerHTML = `<p class="none">${esc(curPower)} had nothing to do in ${esc(ph.n)}.</p>`;
    return;
  }
  let h = "";
  if (press && press.length) {
    const i = Math.min(curRound, press.length - 1), r = press[i];
    h += `<div class="pblock"><div class="plabel">Negotiation · round ${r.r} of ${press.length}</div>`;
    if (press.length > 1) h += `<div class="rounds">` + press.map((x, j) =>
      `<button class="rbtn" type="button" data-r="${j}" aria-pressed="${j === i}">R${x.r}</button>`
    ).join("") + `</div>`;
    if (r.why) h += `<p class="why">${esc(r.why)}</p>`;
    h += r.m.length ? r.m.map(([to, body]) =>
      `<div class="msg${to === "GLOBAL" ? " glob" : ""}">
        <div class="to">to <b>${esc(to)}</b></div><p>${esc(body)}</p></div>`).join("")
      : `<p class="none">No messages sent this round.</p>`;
    h += `</div>`;
  }
  if (dec || orders.length) {
    h += `<div class="pblock"><div class="plabel">Orders</div>`;
    if (dec && dec.why) h += `<p class="why">${esc(dec.why)}</p>`;
    const drop = (dec && dec.drop) || [];
    h += `<ul class="olist">` + orders.map(o => `<li>${esc(o)}</li>`).join("") +
      drop.map(o => `<li class="drop">${esc(o)}</li>`).join("") + `</ul>`;
    if (drop.length) h += `<p class="none" style="margin-top:8px">Struck orders were
      illegal and dropped; those units held.</p>`;
    h += `</div>`;
  }
  $("pbody").innerHTML = h;
  savePos();   // here, not in render(): the power tabs repaint the panel alone
}

function render() {
  const ph = G.phases[cur];
  paint(ph); drawOrders(ph); drawUnits(ph); panel();
  $("vphase").innerHTML = `${esc(ph.n)}<small>${esc(phaseLabel(ph.n))}</small>`;
  $("scrub").value = cur;
  $("vcount").textContent = `Phase ${cur + 1} of ${G.phases.length}`;
  $("prev").disabled = cur === 0;
  $("next").disabled = cur === G.phases.length - 1;
}
function goto(i) {
  cur = Math.max(0, Math.min(G.phases.length - 1, i));
  curRound = 0;
  if (!(G.phases[cur].press[curPower] || G.phases[cur].dec[curPower])) {
    const alt = POWERS.find(p => G.phases[cur].press[p] || G.phases[cur].dec[p]);
    if (alt) curPower = alt;
  }
  render();
}

/* ------------------------------------------------------------- standings */
function standings() {
  const wins = G.phases.filter(p => p.n.endsWith("A") || p === G.phases[0]);
  const series = wins.length > 1 ? wins : G.phases;
  const counts = p => series.map(ph => (ph.c[p] || []).length);
  const max = Math.max(1, ...POWERS.flatMap(counts));
  const lead = POWERS.reduce((a, b) => finalC[a] >= finalC[b] ? a : b);

  $("tiles").innerHTML = POWERS.map(p => {
    const v = counts(p), start = v[0], end = v[v.length - 1], dv = end - start;
    return `<figure class="tile${p === lead ? " lead" : ""}">
      <div class="p"><i style="background:${PC(p)}"></i>${esc(p)}</div>
      <div class="end tnum">${end}<span class="d ${dv > 0 ? "up" : "dn"}">${dv > 0 ? "+" : ""}${dv}</span></div>
      <svg class="spark" role="img" aria-label="${esc(p)}: ${start} then ${end} centres"></svg>
      <figcaption><span>from ${start}</span><span class="tip tnum"></span></figcaption></figure>`;
  }).join("");

  [...document.querySelectorAll(".tile")].forEach((tile, idx) => {
    const p = POWERS[idx], vals = counts(p), el = tile.querySelector(".spark");
    const W = 200, H = 44, PAD = 4;
    const x = i => vals.length < 2 ? W / 2 : PAD + i * (W - 2 * PAD) / (vals.length - 1);
    const y = v => H - PAD - (v / max) * (H - 2 * PAD);
    const pts = vals.map((v, i) => [x(i), y(v)]);
    const line = pts.map((q, i) => (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1)).join(" ");
    const col = tile.classList.contains("lead") ? "var(--brass)" : "var(--steel)";
    el.setAttribute("viewBox", `0 0 ${W} ${H}`);
    el.setAttribute("preserveAspectRatio", "none");
    el.innerHTML =
      `<line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}" stroke="var(--rule)"/>` +
      `<path d="${line} L${x(vals.length - 1).toFixed(1)} ${H - PAD} L${x(0).toFixed(1)} ${H - PAD} Z"
        fill="${col}" opacity=".13"/>` +
      `<path d="${line}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"
        stroke-linecap="round" vector-effect="non-scaling-stroke"/>` +
      `<circle cx="${pts[pts.length - 1][0].toFixed(1)}" cy="${pts[pts.length - 1][1].toFixed(1)}"
        r="4" fill="${col}" stroke="var(--panel)" stroke-width="2"/>` +
      `<g>` + vals.map((v, i) =>
        `<rect x="${(x(i) - (W / vals.length) / 2).toFixed(1)}" y="0"
          width="${(W / vals.length).toFixed(1)}" height="${H}" fill="transparent"
          data-i="${i}" data-v="${v}"/>`).join("") + `</g>` +
      `<circle class="cur" r="4.5" fill="${col}" stroke="var(--panel)" stroke-width="2"
        opacity="0" style="pointer-events:none"/>`;
    const dot = el.querySelector(".cur"), tip = tile.querySelector(".tip");
    el.addEventListener("pointermove", e => {
      const r = e.target.closest("rect[data-i]"); if (!r) return;
      const i = +r.dataset.i;
      dot.setAttribute("cx", pts[i][0].toFixed(1));
      dot.setAttribute("cy", pts[i][1].toFixed(1));
      dot.setAttribute("opacity", "1");
      tip.textContent = `${series[i].n.slice(1, 5)} · ${r.dataset.v}`;
      tip.style.opacity = "1";
    });
    el.addEventListener("pointerleave", () => {
      dot.setAttribute("opacity", "0"); tip.style.opacity = "0";
    });
  });
}

/* ---------------------------------------------------------------- report */
function report() {
  const anyCost = POWERS.some(p => G.models[p].cost_known);
  const head = ["Power", "Model(s) actually called", "Calls", "Errors",
    "Prompt tokens", "Completion tokens", "Avg latency"];
  if (anyCost) head.push("Cost");
  let h = `<thead><tr>` + head.map(x => `<th>${esc(x)}</th>`).join("") + `</tr></thead><tbody>`;
  for (const p of POWERS) {
    const s = G.models[p];
    const ok = s.calls - s.errors;
    const models = Object.keys(s.models);
    h += `<tr>
      <td><span class="pw"><i style="background:${PC(p)}"></i>${esc(p)}</span></td>
      <td class="mdl">${models.length ? models.map(esc).join("<br>") : "—"}</td>
      <td class="tnum">${nf(s.calls)}</td>
      <td class="tnum${s.errors ? " err" : ""}">${nf(s.errors)}</td>
      <td class="tnum">${nf(s.prompt_tokens)}</td>
      <td class="tnum">${nf(s.completion_tokens)}</td>
      <td class="tnum">${ok ? (s.latency / ok).toFixed(2) + "s" : "—"}</td>`;
    if (anyCost) h += `<td class="tnum">${s.cost_known ? "$" + s.cost.toFixed(4) : "—"}</td>`;
    h += `</tr>`;
  }
  h += `</tbody>`;
  $("report").innerHTML = h;
  const bits = ["Models are read from the metadata on each completion, so this is what ran, " +
    "not what was configured."];
  if (!anyCost) bits.push("No per-call cost was reported by the provider for this run.");
  if (!S.has_config) bits.push("No config.json was saved with this run, so personas and " +
    "settings above may be incomplete.");
  $("reportnote").textContent = bits.join(" ");
  $("foot").textContent = `Generated from run ${S.run}. ` +
    `${G.phases.length} phases, ${nf(totalCalls)} model calls.`;
}

/* -------------------------------------------------- position across reloads */
/* A viewer built with --watch reloads itself on a timer while the game is still
   being played, so everything the reader has touched has to survive a reload.
   Phase and power ride in the URL fragment: no storage permission is involved,
   which matters because browsers disagree about storage on file:// URLs, and it
   makes a position linkable. Scroll offset goes to sessionStorage, where losing
   it costs little. Theme is restored in the page head, before the first paint. */
function savePos() {
  // The trailing marker means "was on the newest phase" — such a reader is
  // watching the game, not reading back, so a new phase should carry them along.
  const at = `#${cur}/${curPower}${cur === G.phases.length - 1 ? "/live" : ""}`;
  if (location.hash !== at) location.replace(at);   // replace: no history entry
}
function restorePos() {
  const [i, p, live] = decodeURIComponent(location.hash.slice(1)).split("/");
  const last = G.phases.length - 1;
  if (POWERS.indexOf(p) >= 0) curPower = p;
  cur = live ? last : Math.min(Math.max(0, parseInt(i, 10) || 0), last);
}
function restoreScroll() {
  let y = 0;
  try { y = +sessionStorage.getItem(YKEY) || 0; } catch (e) { return; }
  // After render(), so the page is its full height and the offset still lands.
  if (y) requestAnimationFrame(() => scrollTo(0, y));
}

/* ---------------------------------------------------------------- wiring */
buildBoard(); standings(); report();
const scrub = $("scrub");
scrub.max = G.phases.length - 1;
scrub.addEventListener("input", e => goto(+e.target.value));
$("prev").addEventListener("click", () => goto(cur - 1));
$("next").addEventListener("click", () => goto(cur + 1));
$("ptabs").addEventListener("click", e => {
  const t = e.target.closest(".ptab");
  if (!t || t.disabled) return;
  curPower = t.dataset.p; curRound = 0; panel();
});
$("pbody").addEventListener("click", e => {
  const r = e.target.closest(".rbtn");
  if (!r) return;
  curRound = +r.dataset.r; panel();
});
document.addEventListener("keydown", e => {
  if (e.target.matches("input,textarea,select")) return;
  if (e.key === "ArrowLeft") goto(cur - 1);
  else if (e.key === "ArrowRight") goto(cur + 1);
});

let timer = null;
$("play").addEventListener("click", () => {
  if (timer) { clearInterval(timer); timer = null; $("play").innerHTML = "&#9654;"; return; }
  $("play").innerHTML = "&#10073;&#10073;";
  timer = setInterval(() => {
    if (cur >= G.phases.length - 1) { clearInterval(timer); timer = null; $("play").innerHTML = "&#9654;"; }
    else goto(cur + 1);
  }, 1400);
});

const YKEY = "dai:y:" + G.setup.run;
addEventListener("scroll", () => {
  try { sessionStorage.setItem(YKEY, String(Math.round(scrollY))); } catch (e) { /**/ }
}, { passive: true });
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

restorePos();
goto(cur);          // via goto: it renders, and covers a power idle this phase
restoreScroll();

/* --watch builds set this; the run keeps writing, so pick up what it wrote. */
if (window.DAI_REFRESH) {
  const tick = () => document.hidden ? setTimeout(tick, 1000) : location.reload();
  setTimeout(tick, window.DAI_REFRESH * 1000);   // a hidden tab waits its turn
}
})();
