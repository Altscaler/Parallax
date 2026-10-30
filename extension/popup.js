const $ = id => document.getElementById(id);
const LABEL = { confirmed: "Confirmed", contested: "Contested", single_source: "Single source", no_coverage: "No coverage found" };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const FLAG = { US: "🇺🇸", GB: "🇬🇧", FR: "🇫🇷", ES: "🇪🇸", CN: "🇨🇳", AE: "🇦🇪" };
const flag = c => FLAG[(c.code || "").toUpperCase()] || "";
const DEFAULT_DASH = "https://parallax-two-tawny.vercel.app";
let cfg = {};

chrome.storage.local.get(["key", "lang", "server", "dash"], v => {
  cfg = v;
  $("key").value = v.key || ""; $("server").value = v.server || ""; $("dash").value = v.dash && !v.dash.includes("localhost") ? v.dash : DEFAULT_DASH;
  if (!v.key) { $("settings").open = true; $("status").textContent = "Paste your Gemini API key once, it stays in this browser."; }
});

$("saveSettings").onclick = () => {
  cfg = { ...cfg, key: $("key").value.trim(), server: $("server").value.trim(), dash: $("dash").value.trim() || DEFAULT_DASH };
  chrome.storage.local.set(cfg); $("settings").open = false; $("status").textContent = "Settings saved.";
};

function pageText() {
  const el = document.querySelector("article") || document.querySelector("main") || document.body;
  return { url: location.href, title: document.title, text: el.innerText.replace(/\n{3,}/g, "\n\n").slice(0, 9000) };
}

// Results are saved to the Parallax dashboard's "Saved" list by opening it in a background tab.
function saveToParallax(item) {
  const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(item))));
  const dash = cfg.dash && !cfg.dash.includes("localhost") ? cfg.dash : DEFAULT_DASH;  // old local setting would hide saves from the live site
  const url = `${dash.replace(/\/$/, "")}/#save=${b64}`;
  chrome.tabs.create({ url, active: false });
  return url.split("#")[0] + "#saved";
}

async function go(kind, lang) {
  const key = cfg.key || $("key").value.trim();
  if (!key) { $("settings").open = true; $("status").textContent = "Paste your Gemini API key first."; return; }
  if (cfg.server) setServer(cfg.server);
  document.querySelectorAll("button").forEach(b => b.disabled = true);
  $("out").innerHTML = ""; $("settings").open = false;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result: page }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: pageText });
    const status = s => $("status").textContent = s + "…";
    const dir = lang === "Arabic" ? "rtl" : "";
    $("out").className = dir;
    let item;
    if (kind === "summary") {
      const r = await summarize(key, page, lang, status);
      $("out").innerHTML = `<div class="note"><b>${esc(r.outlet)}</b><br>${esc(r.title)}</div><p>${esc(r.summary)}</p>
        <ul>${(r.key_points || []).map(p => `<li>${esc(p)}</li>`).join("")}</ul>`;
      item = { type: "summary", lang, url: page.url, page_title: page.title, ...r };
    } else if (kind === "world") {
      const r = await compareCountries(key, page, lang, status);
      $("out").innerHTML = `<div class="note"><b>${esc(r.story)}</b></div>` +
        (r.countries || []).map(c => `<div class="claim"><b>${flag(c)} ${esc(c.country)}</b> <span class="why">${esc((c.outlets || []).join(", "))}</span><div>${esc(c.angle)}</div></div>`).join("") +
        `<p><b>This article:</b> ${esc(r.this_article)}</p><p><b>Biggest difference:</b> ${esc(r.difference)}</p>`;
      item = { type: "compare", lang, url: page.url, page_title: page.title, outlet: r.outlet, title: r.story,
               summary: `${r.this_article} ${r.difference}`, key_points: (r.countries || []).map(c => `${flag(c)} ${c.country}: ${c.angle}`) };
    } else {
      const r = await analyze(key, page, lang, status);
      const acc = Math.max(0, Math.min(100, Number(r.accuracy) || 0));
      $("out").innerHTML = `<div class="note"><b>${esc(r.outlet)}</b><br>${esc(r.outlet_note)}</div>
        <div class="score">Accuracy estimate <div class="bar"><i style="width:${acc}%"></i></div>${acc}/100</div>
        <div class="why">${esc(r.accuracy_why)}</div><p>${esc(r.summary)}</p>` +
        r.claims.map(c => `<div class="claim"><span class="tag ${esc(c.status)}">${esc(LABEL[c.status] || c.status)}</span><div>${esc(c.claim)}</div><div class="why">${esc(c.why)}</div></div>`).join("");
      item = { type: "factcheck", lang, url: page.url, page_title: page.title, outlet: r.outlet, outlet_note: r.outlet_note,
               story: r.story, summary: r.summary, accuracy: acc, accuracy_why: r.accuracy_why, claims: r.claims };
    }
    item.saved_at = new Date().toISOString();
    const link = saveToParallax(item);
    $("out").insertAdjacentHTML("beforeend", `<div class="saved">✓ Saved to Parallax · <a href="${esc(link)}" target="_blank">open Saved</a></div>`);
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = "Failed: " + e.message;
  } finally { document.querySelectorAll("button").forEach(b => b.disabled = false); }
}

document.querySelectorAll("#langs button").forEach(b => b.onclick = () => go("summary", b.dataset.l));
$("check").onclick = () => go("factcheck", cfg.lang || "English");
$("world").onclick = () => go("world", cfg.lang || "English");
