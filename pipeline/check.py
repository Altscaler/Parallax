"""Check pasted text (or an Instagram post) against other outlets. Python port of extension/analyze.js."""
import json, os, re, urllib.parse, urllib.request
from gemma import ask_json
from stories import EDITIONS, search

def instagram(url):
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        raise RuntimeError("APIFY_TOKEN missing in .env")
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items?token={token}",
        json.dumps({"directUrls": [url], "resultsType": "posts", "resultsLimit": 1}).encode(),
        {"Content-Type": "application/json"})
    post = json.load(urllib.request.urlopen(req, timeout=120))[0]
    return f"@{post.get('ownerUsername')}", post.get("caption") or ""

def corroborate(query):
    seen = {}
    for ed in ("US", "GB", "FR", "AE"):
        try:
            for it in search(query, ed)[:8]:
                seen.setdefault(it["outlet_name"], f"{it['outlet_name']} ({ed}): {it['title']}")
        except Exception:
            pass
    return list(seen.values())[:12]

CHECKERS = ["factcheck.afp.com", "snopes.com", "politifact.com", "fullfact.org", "factcheck.org",
            "leadstories.com", "maldita.es", "newtral.es", "factual.afp.com", "checknews.fr"]
WIRES = ["reuters.com", "apnews.com", "afp.com"]

def sites(domains):
    return "(" + " OR ".join("site:" + d for d in domains) + ")"

def fact_checks(query):
    """Published fact-checks (AFP Fact Check, Snopes, PolitiFact, Full Fact, Maldita...) on this claim, last 90 days."""
    seen = {}
    for ed, q in (("US", f'{sites(CHECKERS)} "fact check" {query}'), ("FR", f"{sites(CHECKERS)} vérification {query}"),
                  ("ES", f"{sites(CHECKERS)} verificación {query}")):
        try:
            for it in search(q, ed, "90d")[:6]:
                seen.setdefault(it["link"], {"outlet": it["outlet_name"], "title": it["title"], "link": it["link"]})
        except Exception:
            pass
    return list(seen.values())[:6]

def wire_coverage(query):
    try:
        return [{"outlet": it["outlet_name"], "title": it["title"], "link": it["link"]} for it in search(f"{sites(WIRES)} {query}", "US", "30d")[:4]]
    except Exception:
        return []

def check(text, lang="English", insta=None):
    source = None
    if insta:
        who, caption = instagram(insta)
        source = f"Instagram post by {who}"
        text = caption + "\n\n" + (text or "")
    if not text.strip():
        raise RuntimeError("Nothing to check")
    ex = ask_json(f"""Extract the checkable claims from this text. Reply with JSON only:
{{"claims":[{{"claim":"one checkable statement, in English","search":"3-6 word English news search query"}}]}}
At most 4 claims, the ones the text rests on.
TEXT:
{text[:6000]}""")
    claims = ex["claims"][:4]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as pool:
        jobs = [(pool.submit(corroborate, c["search"]), pool.submit(fact_checks, c["search"]), pool.submit(wire_coverage, c["search"])) for c in claims]
        found = [tuple(f.result() for f in j) for j in jobs]
    evidence = [{"claim": c["claim"], "other_coverage": o, "fact_checks_published": f, "wire_agencies": w}
                for c, (o, f, w) in zip(claims, found)]
    out = ask_json(f"""You compare claims with three kinds of evidence found on Google News: other outlets, published fact-checks
(Reuters, AP, AFP, Snopes, PolitiFact, Full Fact, Maldita...) and wire agency coverage (Reuters, AP, AFP).
Judge each claim ONLY from the evidence given. Cross several independent sources before saying "confirmed".
If a published fact-check addresses the claim, say what it concludes, naming the outlet, and use "contested" if it disputes the claim. Never say who is lying. Never call an outlet reliable or unreliable.
Status: "confirmed" (several independent outlets or a wire agency), "contested" (outlets report something different),
"single_source" (one origin only), "no_coverage" (nothing found, which proves nothing).
Reply with JSON only, all text in {lang}:
{{"summary":"2 sentences: what the text claims and how solid it looks","claims":[{{"claim":"...","status":"...","why":"one or two sentences naming the outlets and fact-checkers used"}}]}}
EVIDENCE:
{json.dumps(evidence, ensure_ascii=False, indent=1)}""")
    for c, e in zip(out.get("claims", []), evidence):
        c["fact_checks"] = e["fact_checks_published"]; c["wires"] = e["wire_agencies"]
    out["source"] = source
    return out
