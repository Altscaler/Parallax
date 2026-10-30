// Pipeline for the extension popup. Also runs under node for testing.
const MODEL = "gemma-4-26b-a4b-it";
const GEMMA = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;
const EDITIONS = [["en-US", "US", "US:en"], ["en-GB", "GB", "GB:en"], ["fr", "FR", "FR:fr"], ["ar", "AE", "AE:ar"]];

async function ask(key, prompt) {
  for (let n = 0; n < 5; n++) {
    let r;
    try {
      r = await fetch(GEMMA, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }], generationConfig: { thinkingConfig: { thinkingLevel: "minimal" } } }),
        signal: AbortSignal.timeout(25000),
      });
    } catch (e) {  // Gemma's API sometimes drops the connection; retry like a 500
      await new Promise(res => setTimeout(res, 2000 * (n + 1)));
      continue;
    }
    if (r.ok) {
      const d = await r.json();
      const parts = d.candidates[0].content.parts;
      return parts[parts.length - 1].text;
    }
    if (r.status === 400 || r.status === 403) throw new Error(`Gemma ${r.status}: check the API key`);
    await new Promise(res => setTimeout(res, 2000 * (n + 1)));
  }
  throw new Error("Gemma did not answer");
}

async function askJson(key, prompt) {
  const txt = await ask(key, prompt);
  const m = txt.match(/\{[\s\S]*\}/);
  return JSON.parse(m[0]);
}

function parseRss(xml) {
  const out = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const title = (m[1].match(/<title>([\s\S]*?)<\/title>/) || [])[1] || "";
    const src = (m[1].match(/<source[^>]*>([\s\S]*?)<\/source>/) || [])[1] || "";
    const url = (m[1].match(/<source url="([^"]*)"/) || [])[1] || "";
    const clean = s => s.replace(/<!\[CDATA\[|\]\]>/g, "").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
    out.push({ title: clean(title), outlet: clean(src), domain: url.replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*/, "") });
  }
  return out;
}

async function corroborate(query, pageHost) {
  const seen = new Map();
  // all editions at once, each capped at 6 s
  const lists = await Promise.all(EDITIONS.map(async ([hl, gl, ceid]) => {
    try {
      const r = await fetch(`https://news.google.com/rss/search?q=${encodeURIComponent(query)}&hl=${hl}&gl=${gl}&ceid=${ceid}`, { signal: AbortSignal.timeout(6000) });
      return r.ok ? parseRss(await r.text()).slice(0, 8).map(it => ({ ...it, edition: gl })) : [];
    } catch (e) { return []; }
  }));
  for (const it of lists.flat()) {
    if (it.domain && pageHost.endsWith(it.domain)) continue;
    if (!seen.has(it.outlet)) seen.set(it.outlet, it);
  }
  return [...seen.values()].slice(0, 12);
}

let SERVER = "http://localhost:8787"; // popup overrides this with the deployed URL when set

// Full-text excerpts from the evidence server (publish/server). Returns null if it is not running.
async function deepEvidence(query, host) {
  try {
    const r = await fetch(`${SERVER}/evidence?q=${encodeURIComponent(query)}&host=${encodeURIComponent(host)}`);
    if (!r.ok) return null;
    return (await r.json()).map(f => ({ outlet: f.outlet, edition: f.country, title: f.title, excerpt: f.excerpt }));
  } catch (e) { return null; }
}

async function analyze(key, page, lang, onStatus = () => {}) {
  const host = new URL(page.url).hostname.replace(/^www\./, "");
  const headline = (page.title || page.text.slice(0, 100)).replace(/\s+[-|–]\s+[^-|–]+$/, "").slice(0, 120);
  onStatus("Looking for other coverage");
  const words = headline.replace(/["'«»“”‘’:]/g, " ").split(/\s+/).filter(Boolean);
  let found = await corroborate(words.slice(0, 9).join(" "), host);
  if (found.length < 4) found = found.concat(await corroborate(words.slice(0, 4).join(" "), host));
  const coverage = [...new Map(found.map(f => [f.outlet, f])).values()].slice(0, 15).map(f => `${f.outlet} (${f.edition}): ${f.title}`);
  onStatus("Checking the claims");
  const out = await askJson(key, `You fact-check a news article against headlines from other outlets found on Google News.
Pick the 3 or 4 checkable claims the article rests on (numbers, quotes, causes, events) and judge each ONLY from the headlines given.
Never say who is lying. Never call an outlet reliable or unreliable.
Status per claim: "confirmed" (several independent outlets or a wire agency such as Reuters, AP, AFP), "contested" (others report something different), "single_source" (only this article, or everyone repeats one origin), "no_coverage" (nothing found, which proves nothing).
accuracy = 0-100 estimate of how well the claims are backed: mostly confirmed scores high, contested pulls it down most, single_source and no_coverage sit in the middle.
Reply with JSON only, all text in ${lang}:
{"outlet":"name of the outlet","story":"the story in 8 words or fewer",
 "summary":"2 sentences: what the article says and how solid it looks",
 "accuracy":0,"accuracy_why":"one sentence",
 "outlet_note":"what is publicly known about the outlet: owner, state funding, country. Say 'not sure' if unsure.",
 "claims":[{"claim":"...","status":"...","why":"one sentence naming the outlets that support or differ"}]}

ARTICLE (${host}): ${page.title}
${page.text.slice(0, 5000)}

OTHER COVERAGE:
${coverage.join("\n") || "(none found)"}`);
  out.outlet = out.outlet || host; out.evidence = coverage;
  return out;
}

const WORLD = [["en-US", "US", "US:en", "USA"], ["en-GB", "GB", "GB:en", "UK"], ["fr", "FR", "FR:fr", "France"],
               ["es", "ES", "ES:es", "Spain"], ["zh-CN", "CN", "CN:zh-Hans", "China"], ["ar", "AE", "AE:ar", "UAE"]];

async function compareCountries(key, page, lang, onStatus = () => {}) {
  const host = new URL(page.url).hostname.replace(/^www\./, "");
  onStatus("Translating the story");
  const q = await askJson(key, `Give a 3-6 word news search query for this story in each language. Reply with JSON only:
{"en":"...","fr":"...","es":"...","zh":"...","ar":"..."}
STORY: ${page.title}
${page.text.slice(0, 600)}`);
  const qFor = { "en-US": q.en, "en-GB": q.en, fr: q.fr, es: q.es, "zh-CN": q.zh, ar: q.ar };
  onStatus("Searching 6 countries");
  const per = await Promise.all(WORLD.map(async ([hl, gl, ceid, name]) => {
    try {
      const r = await fetch(`https://news.google.com/rss/search?q=${encodeURIComponent((qFor[hl] || q.en) + " when:7d")}&hl=${hl}&gl=${gl}&ceid=${ceid}`, { signal: AbortSignal.timeout(6000) });
      const items = r.ok ? parseRss(await r.text()).filter(it => !(it.domain && host.endsWith(it.domain))).slice(0, 5) : [];
      return { name, items };
    } catch (e) { return { name, items: [] }; }
  }));
  onStatus("Comparing the countries");
  const out = await askJson(key, `Compare how media in different countries cover one story, from the headlines below, and how the article the reader is on tells it.
Never say who is right. Never call an outlet reliable or unreliable. If a country has no headlines, say "no coverage found".
Reply with JSON only, all text in ${lang}:
{"story":"the story in one short sentence",
 "countries":[{"code":"US, GB, FR, ES, CN or AE","country":"name","angle":"one sentence: what its media put first","outlets":["up to 3 outlet names"]}],
 "this_article":"one sentence: how this article's angle compares",
 "difference":"one sentence: the biggest difference between countries"}

THE ARTICLE (${host}): ${page.title}
${page.text.slice(0, 2500)}

HEADLINES BY COUNTRY:
${per.map(p => `${p.name}:\n` + (p.items.map(i => `  ${i.outlet}: ${i.title}`).join("\n") || "  (none)")).join("\n")}`);
  out.outlet = host;
  return out;
}

async function summarize(key, page, lang, onStatus = () => {}) {
  onStatus("Summarizing");
  return askJson(key, `Summarize this news article for a reader, in ${lang}. Neutral tone, no opinion. Reply with JSON only:
{"outlet":"name of the outlet","title":"the headline translated into ${lang}","summary":"3 to 4 sentences in ${lang}","key_points":["3 short points in ${lang}"]}

TITLE: ${page.title}
URL: ${page.url}
TEXT:
${page.text.slice(0, 5000)}`);
}

if (typeof module !== "undefined") module.exports = { analyze, summarize, compareCountries };
function setServer(url) { if (url) SERVER = url.replace(/\/$/, ""); }
