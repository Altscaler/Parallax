const $ = id => document.getElementById(id);
const LABEL = { confirmed: "Confirmed", contested: "Contested", single_source: "Single source", no_coverage: "No coverage found" };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Opening the popup checks the page right away; settings only show until a key is saved.
chrome.storage.local.get(["key", "lang", "server"], v => {
  if (v.lang) $("lang").value = v.lang;
  if (v.server) $("server").value = v.server;
  if (v.key) { $("key").value = v.key; run(); }
  else { $("settings").open = true; $("status").textContent = "Paste your Gemini API key once, it stays in this browser."; }
});

function pageText() {
  const el = document.querySelector("article") || document.querySelector("main") || document.body;
  return { url: location.href, title: document.title, text: el.innerText.replace(/\n{3,}/g, "\n\n").slice(0, 9000) };
}

async function run() {
  const key = $("key").value.trim(), lang = $("lang").value;
  if (!key) { $("status").textContent = "Paste a Gemini API key first."; return; }
  chrome.storage.local.set({ key, lang, server: $("server").value.trim() });
  setServer($("server").value.trim());
  $("go").disabled = true; $("again").disabled = true; $("out").innerHTML = ""; $("settings").open = false;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result: page }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: pageText });
    const r = await analyze(key, page, lang, s => $("status").textContent = s + "…");
    const dir = lang === "Arabic" ? "rtl" : "";
    $("out").className = dir;
    $("out").innerHTML = `<div class="note"><b>${esc(r.outlet)}</b><br>${esc(r.outlet_note)}</div><p>${esc(r.summary)}</p>` +
      r.claims.map(c => `<div class="claim"><span class="tag ${esc(c.status)}">${esc(LABEL[c.status] || c.status)}</span><div>${esc(c.claim)}</div><div class="why">${esc(c.why)}</div></div>`).join("");
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = "Failed: " + e.message;
  } finally { $("go").disabled = false; $("again").disabled = false; }
}

$("go").onclick = run;
$("again").onclick = run;
$("lang").onchange = () => { chrome.storage.local.set({ lang: $("lang").value }); run(); };
