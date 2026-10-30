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
    evidence = [{"claim": c["claim"], "other_coverage": corroborate(c["search"])} for c in claims]
    out = ask_json(f"""You compare claims with headlines from other outlets, found on Google News.
Judge each claim ONLY from the headlines given. Never say who is lying. Never call an outlet reliable or unreliable.
Status: "confirmed" (several independent outlets or a wire agency), "contested" (outlets report something different),
"single_source" (one origin only), "no_coverage" (nothing found, which proves nothing).
Reply with JSON only, all text in {lang}:
{{"summary":"2 sentences: what the text claims and how solid it looks","claims":[{{"claim":"...","status":"...","why":"one sentence naming outlets"}}]}}
EVIDENCE:
{json.dumps(evidence, ensure_ascii=False, indent=1)}""")
    out["source"] = source
    return out
