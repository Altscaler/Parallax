const $ = id => document.getElementById(id);
const LABEL = { confirmed: "Confirmed", contested: "Contested", single_source: "Single source", no_coverage: "No coverage found" };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const DEFAULT_DASH = "https://parallax-two-tawny.vercel.app";
let cfg = {};

chrome.storage.local.get(["key", "lang", "server", "dash"], v => {
  cfg = v;
  $("key").value = v.key || ""; $("server").value = v.server || ""; $("dash").value = v.dash || DEFAULT_DASH;
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
  const url = `${(cfg.dash || DEFAULT_DASH).replace(/\/$/, "")}/#save=${b64}`;
  chrome.tabs.create({ url, active: false });
  return url.split("#")[0] + "#saved";
}

let last = null;

async function go(lang, save) {
  const key = cfg.key || $("key").value.trim();
  if (!key) { $("settings").open = true; $("status").textContent = "Paste your Gemini API key first."; return; }
  document.querySelectorAll("button").forEach(b => b.disabled = true);
  $("settings").open = false;
  try {
    if (!last || (!save && last.lang !== lang)) {
      $("out").innerHTML = "";
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      const [{ result: page }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: pageText });
      const r = await summarize(key, page, lang, s => $("status").textContent = s + "…");
      $("out").className = lang === "Arabic" ? "rtl" : "";
      $("out").innerHTML = `<div class="note"><b>${esc(r.outlet)}</b><br>${esc(r.title)}</div><p>${esc(r.summary)}</p>
        <ul>${(r.key_points || []).map(p => `<li>${esc(p)}</li>`).join("")}</ul>`;
      last = { type: "summary", lang, url: page.url, page_title: page.title, ...r };
    }
    $("status").textContent = "";
    if (save) {
      last.saved_at = new Date().toISOString();
      const link = saveToParallax(last);
      $("out").insertAdjacentHTML("beforeend", `<div class="saved">✓ Saved to Parallax · <a href="${esc(link)}" target="_blank">open Saved</a></div>`);
    }
  } catch (e) {
    $("status").textContent = "Failed: " + e.message;
  } finally { document.querySelectorAll("button").forEach(b => b.disabled = false); }
}

document.querySelectorAll("#langs button").forEach(b => b.onclick = () => go(b.dataset.l, false));
$("check").onclick = () => go(last ? last.lang : cfg.lang || "English", true);
