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
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] }),
      });
    } catch (e) {  // Gemma's API sometimes drops the connection; retry like a 500
      await new Promise(res => setTimeout(res, 3000 * (n + 1)));
      continue;
    }
    if (r.ok) {
      const d = await r.json();
      const parts = d.candidates[0].content.parts;
      return parts[parts.length - 1].text;
    }
    if (r.status === 400 || r.status === 403) throw new Error(`Gemma ${r.status}: check the API key`);
    await new Promise(res => setTimeout(res, 3000 * (n + 1)));
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
  for (const [hl, gl, ceid] of EDITIONS) {
    try {
      const r = await fetch(`https://news.google.com/rss/search?q=${encodeURIComponent(query)}&hl=${hl}&gl=${gl}&ceid=${ceid}`);
      if (!r.ok) continue;
      for (const it of parseRss(await r.text()).slice(0, 8)) {
        if (it.domain && pageHost.endsWith(it.domain)) continue;
        if (!seen.has(it.outlet)) seen.set(it.outlet, { ...it, edition: gl });
      }
    } catch (e) { /* edition unavailable, skip */ }
  }
  return [...seen.values()].slice(0, 12);
}

async function analyze(key, page, lang, onStatus = () => {}) {
  const host = new URL(page.url).hostname.replace(/^www\./, "");
  onStatus("Reading the article");
  const ex = await askJson(key, `You read a news article. Reply with JSON only:
{"outlet":"name of the outlet","story":"the story in 8 words or fewer, in English",
 "claims":[{"claim":"one checkable statement (number, quote, cause or event), in English","search":"3-6 word English search query to find other coverage","cited_source":"who the article says it comes from, or null"}]}
Give at most 4 claims, the ones the story rests on.

TITLE: ${page.title}
URL: ${page.url}
TEXT:
${page.text}`);
  onStatus("Looking for other coverage");
  const claims = ex.claims.slice(0, 4);
  const found = await Promise.all(claims.map(c => corroborate(c.search, host)));
  const evidence = claims.map((c, i) => ({ claim: c.claim, cited_source: c.cited_source,
    other_coverage: found[i].map(f => `${f.outlet} (${f.edition}): ${f.title}`) }));
  onStatus("Comparing");
  const out = await askJson(key, `You compare a news article with headlines from other outlets, found on Google News.
Judge each claim ONLY from the headlines given. Never say who is lying. Never call an outlet reliable or unreliable.
Status per claim, one of:
- "confirmed": reported by several independent outlets, or by a wire agency (Reuters, AP, AFP)
- "contested": other outlets report something different
- "single_source": only this article, or everyone repeats one origin
- "no_coverage": nothing found in the headlines, which proves nothing
Reply with JSON only, all text in ${lang}:
{"summary":"2 sentences: what the article says and how solid it looks",
 "outlet_note":"what is publicly known about ${ex.outlet || host}: owner, state funding, country. Say 'not sure' if unsure.",
 "claims":[{"claim":"...","status":"...","why":"one sentence naming the outlets that support or differ"}]}

OUTLET: ${ex.outlet || host} (${host})
EVIDENCE:
${JSON.stringify(evidence, null, 1)}`);
  out.outlet = ex.outlet || host; out.story = ex.story; out.evidence = evidence;
  return out;
}

if (typeof module !== "undefined") module.exports = { analyze };
