"""Render docs/index.html (served by GitHub Pages)."""
from __future__ import annotations

import json
from pathlib import Path

from . import config

SECTIONS = [
    ("match", f"Matches, {config.PRICE_MIN // 1000}–{config.PRICE_MAX // 1000} 000 €", "matches",
     "Every rule confirmed: 3 or 3,5 rooms, at least 60 m², balcony, 2nd floor or higher, not in original condition."),
    ("near", f"Near misses, {config.PRICE_MAX // 1000}–{config.NEAR_MISS_MAX // 1000} 000 €", "near misses",
     "Slightly over budget. Worth an offer, especially if listed for weeks or already reduced."),
    ("check", "Needs a manual check", "to check",
     "The price fits, but the ad doesn't say something the rules need. The missing facts are listed per row."),
    ("removed", "Recently removed", "recently removed",
     "Gone from the portal in the last 60 days, most likely sold. Shows how long comparable flats lasted."),
    ("excluded", "Excluded", "excluded",
     "Candidates that failed a rule. Use this to spot filter mistakes."),
]

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>3-room flats for sale</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏠</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#E9ECEA; --panel:#F6F7F5; --ink:#1E2629; --muted:#5B666A; --rule:#CBD2CF;
  --teal:#1F5F66; --amber:#C98A12; --red:#A33B2B; --bar-bg:#D6DCD9;
  box-sizing:border-box;
  padding-top:env(safe-area-inset-top,0px); padding-bottom:env(safe-area-inset-bottom,0px);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#161B1D; --panel:#1E2528; --ink:#E4E9E7; --muted:#9AA6A9; --rule:#33403F;
    --teal:#6FB3B8; --amber:#E2A83A; --red:#E07A6A; --bar-bg:#2C3638;
  }
}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 "Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header h1{font-size:2rem;line-height:1.15;margin:0 0 6px;font-weight:700;letter-spacing:-.01em}
header p{margin:0;color:var(--muted);max-width:70ch}
.counts{display:flex;flex-wrap:wrap;gap:8px 22px;margin:18px 0 8px;padding:0;list-style:none}
.counts a{color:var(--ink);text-decoration:none;border-bottom:2px solid var(--rule)}
.counts a:hover,.counts a:focus-visible{border-color:var(--teal)}
.counts b{font-size:1.25rem}
section{margin-top:40px}
section h2{font-size:1.3rem;margin:0 0 2px}
section>p{margin:0 0 12px;color:var(--muted);font-size:.93rem;max-width:75ch}
.scroll{overflow-x:auto;background:var(--panel);border:1px solid var(--rule);border-radius:6px}
table{border-collapse:collapse;width:100%;min-width:1120px;table-layout:fixed;font-size:.93rem}
th,td{text-align:left;padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--rule)}
tr:last-child td{border-bottom:0}
th{font-weight:700;font-size:.85rem;color:var(--muted);white-space:nowrap;position:sticky;top:0;background:var(--panel)}
th button{all:unset;cursor:pointer}
th button:focus-visible,a:focus-visible{outline:2px solid var(--teal);outline-offset:2px;border-radius:2px}
th[aria-sort="ascending"] button::after{content:" ▲"}
th[aria-sort="descending"] button::after{content:" ▼"}
td.num{text-align:right}
.eff{white-space:nowrap}
.eff{font-size:1.1rem;font-weight:700}
.sub{display:block;color:var(--muted);font-size:.82rem}
a{color:var(--teal)}
.title a{font-weight:700;text-decoration:none}
.title a:hover{text-decoration:underline}
.age{min-width:120px}
.bar{height:6px;background:var(--bar-bg);border-radius:3px;margin-top:5px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--teal)}
.bar.stale i{background:var(--amber)}
.stale-note{color:var(--amber);font-weight:700}
.flag{display:block;font-size:.82rem;color:var(--amber)}
.sub.warn{color:var(--amber)}
.unk{color:var(--red);font-weight:700}
.muted{color:var(--muted)}
th.numh{text-align:right}
.miss{display:block;font-size:.82rem;color:var(--red)}
.drop{color:var(--teal);font-weight:700}
.rise{color:var(--red)}
details summary{cursor:pointer;font-size:1.3rem;font-weight:700}
.empty{padding:18px;color:var(--muted)}
@media (max-width:640px){header h1{font-size:1.6rem}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>3-room flats for sale in Bratislava</h1>
  <p>Petržalka, Ružinov, Karlova Ves, Nové Mesto, Rača. 3 or 3,5 rooms, 60 m² or more, balcony,
  2nd floor or higher, not in original condition. Updated __UPDATED__ from nehnutelnosti.sk, every 3 days.</p>
  <ul class="counts" id="counts"></ul>
</header>
<main id="sections"></main>
</div>
<script>
const DATA = __DATA__;
const SECTIONS = __SECTIONS__;
const STALE = __STALE__;
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cond = {renovated:"Renovated",partial:"Partly renovated","new":"New build",original:"Original"};

const eur = x => x == null ? "?" : Math.round(x).toLocaleString("sk-SK") + " €";
const yn = v => v === true ? "Yes" : v === false ? "No" : '<span class="unk">?</span>';
function historyCell(r){
  const p = r.history.map(x => x[1]).filter(x => x != null);
  if (p.length < 2) return "";
  const last = p[p.length-1], first = p[0];
  const steps = p.map(x => Math.round(x / 1000) + "k").join(" → ");
  const total = first - last;
  const pct = (total / first * 100).toFixed(1).replace(".", ",");
  return `<span class="sub ${total > 0 ? "drop" : "rise"}">${total > 0 ? "−" + eur(total) + " (−" + pct + " %)" : "+" + eur(-total)}</span><span class="sub">${steps}</span>`;
}
function row(r, sec){
  const days = r.days;
  const w = Math.min(100, days / (STALE * 2) * 100);
  const stale = days >= STALE;
  const links = r.links.length > 1 ? ", listed as " + r.links.map((l, i) => `<a href="${esc(l.url)}" rel="noopener" target="_blank">ad ${i + 1}</a>`).join(", ") : "";
  const notes = sec === "excluded" ? r.excluded.map(x => `<span class="miss">${esc(x)}</span>`).join("")
              : r.unknown.map(x => `<span class="miss">unknown: ${esc(x)}</span>`).join("");
  return `<tr>
    <td class="title"><a href="${esc(r.links[0].url)}" rel="noopener" target="_blank">${esc(r.title)}</a>
      <span class="sub">${esc(r.district ?? "?")}${r.rooms ? ", " + String(r.rooms).replace(".", ",") + " rooms" : ""}${links}</span></td>
    <td class="num"><span class="eff">${eur(r.price)}</span></td>
    <td class="num">${r.area ?? "?"}</td>
    <td class="num">${eur(r.ppm2)}</td>
    <td class="num">${r.floor ?? '<span class="unk">?</span>'}</td>
    <td>${yn(r.balcony)}</td>
    <td>${r.cellar === true ? "Yes" : r.cellar === false ? "No" : '<span class="muted">not stated</span>'}</td>
    <td>${cond[r.condition] ?? '<span class="unk">?</span>'}</td>
    <td class="age">${days} days${sec === "removed" ? " until removed" : ""}${stale && sec !== "removed" ? ' <span class="stale-note">negotiable</span>' : ""}
      <div class="bar${stale ? " stale" : ""}"><i style="width:${w}%"></i></div>${historyCell(r)}</td>
    <td>${r.flags.map(f => `<span class="flag">${esc(f)}</span>`).join("")}${notes}</td>
  </tr>`;
}
const COLS = [["Listing","title",23],["Price","price",10],["m²","area",6],["€/m²","ppm2",8],["Floor","floor",5],
  ["Balcony",null,7],["Cellar",null,8],["Condition",null,9],["Listed / price drops","days",13],["Notes",null,11]];

function table(sec, rows){
  if (!rows.length) return `<div class="scroll"><p class="empty">Nothing here right now.</p></div>`;
  const cols = COLS.map(c => `<col style="width:${c[2]}%">`).join("");
  const right = new Set(["price","area","ppm2","floor"]);
  const head = COLS.map(([label,key]) => key ? `<th data-key="${key}"${right.has(key) ? ' class="numh"' : ""}><button>${label}</button></th>` : `<th>${label}</th>`).join("");
  return `<div class="scroll"><table data-sec="${sec}"><colgroup>${cols}</colgroup><thead><tr>${head}</tr></thead><tbody>${rows.map(r => row(r, sec)).join("")}</tbody></table></div>`;
}
function render(){
  const main = document.getElementById("sections");
  const counts = document.getElementById("counts");
  main.innerHTML = ""; counts.innerHTML = "";
  for (const [key, title, short, desc] of SECTIONS){
    const rows = DATA.filter(r => r.section === key).sort((a,b) => (a.price ?? 1e9) - (b.price ?? 1e9));
    if (key !== "excluded") counts.insertAdjacentHTML("beforeend", `<li><a href="#${key}"><b>${rows.length}</b> ${esc(short)}</a></li>`);
    const body = `<p>${esc(desc)}</p>${table(key, rows)}`;
    main.insertAdjacentHTML("beforeend", key === "excluded"
      ? `<section id="${key}"><details><summary>${esc(title)} (${rows.length})</summary>${body}</details></section>`
      : `<section id="${key}"><h2>${esc(title)}</h2>${body}</section>`);
  }
  document.querySelectorAll("th[data-key] button").forEach(b => b.addEventListener("click", sortBy));
}
function sortBy(e){
  const th = e.currentTarget.parentElement, key = th.dataset.key;
  const tbl = th.closest("table"), sec = tbl.dataset.sec;
  const dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
  const rows = DATA.filter(r => r.section === sec).sort((a,b) => {
    const x = a[key] ?? (typeof b[key] === "string" ? "" : 1e9), y = b[key] ?? (typeof a[key] === "string" ? "" : 1e9);
    return (x > y ? 1 : x < y ? -1 : 0) * dir;
  });
  tbl.querySelector("tbody").innerHTML = rows.map(r => row(r, sec)).join("");
  tbl.querySelectorAll("th").forEach(t => t.removeAttribute("aria-sort"));
  th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
}
render();
</script>
</body>
</html>
"""


def render(rows: list[dict], updated: str, out: Path = Path("docs/index.html")) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__SECTIONS__", json.dumps(SECTIONS, ensure_ascii=False))
            .replace("__UPDATED__", updated)
            .replace("__STALE__", str(config.STALE_DAYS)))
    out.write_text(html, encoding="utf-8")
