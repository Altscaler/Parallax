"""Gemma 4 (26B-A4B via Gemini API) reads each story's headlines, grouped by country of origin,
and writes: common ground, each side's framing, a claim check, and a spoken briefing in 5 languages.
Reads cache/coverage.json, writes ../web/data/stories.json."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from gemma import ask, ask_json

ORDER = ["FR", "ES", "US", "GB", "CN", "AE", "QA", "SA", "DE"]
NAMES = {"FR": "France", "ES": "Spain", "US": "USA", "GB": "UK", "CN": "China-based media", "AE": "UAE",
         "QA": "Qatar", "SA": "Saudi Arabia", "DE": "Germany", "SG": "Singapore", "RU": "Russia", "INT": "International"}
LANGS = {"en": "English", "fr": "French", "es": "Spanish", "zh": "Simplified Chinese", "ar": "Arabic"}

def pick(story, per_country=4, max_countries=5):
    by = {}
    for i in story["items"]:
        by.setdefault(i["country"], []).append(i)
    countries = sorted([c for c in by if len(by[c]) >= 2], key=lambda c: (ORDER.index(c) if c in ORDER else 99, -len(by[c])))
    chosen = []
    for c in countries[:max_countries]:
        its = sorted(by[c], key=lambda i: (not i["profiled"], i["published"] or ""), reverse=False)[:per_country]
        chosen += its
    return countries[:max_countries], chosen

def analyse(story):
    countries, its = pick(story)
    lines = "\n".join(f"{n}|{i['country']}|{i['outlet']}|{i['ownership']}|{i['title']}" for n, i in enumerate(its))
    a = ask_json(f"""You compare how outlets from different countries cover one news story. You only see headlines.
Never say who is right or lying. Never call an outlet reliable or unreliable. Be concrete and short.
STORY: {story['title']}
HEADLINES (index|country|outlet|ownership|headline):
{lines}

Reply with JSON only:
{{"common_ground":[{{"fact":"a fact most countries' headlines agree on","sources":["outlet names"]}}],
 "sides":{{"<country code>":{{"reading":"one sentence: what this country's outlets emphasise","loaded_words":["word as written (English gloss)"],"leaves_out":"one short sentence on what they don't mention, or null"}}}},
 "claims":[{{"claim":"a checkable claim from the headlines","status":"confirmed|contested|single_source","why":"one sentence naming the outlets that support or differ"}}],
 "watch_out":["one short note on a gap, a contradiction, or a source issue"],
 "divergence":0}}
Rules: max 3 common_ground, max 4 claims, max 2 watch_out, max 3 loaded_words per side. A side for each of: {', '.join(countries)}.
divergence = 0-100, how differently the countries tell the story.""")
    return countries, its, a

def briefing(story, a, lang):
    return ask(f"""Write a spoken news briefing of about 120 words in {LANGS[lang]}, for a listener, in the voice of a calm, neutral reporter.
First say in one sentence what happened. Then say how each country's media tells it, for example "Chinese media say X, while French media put more weight on Y".
Use only the analysis below. Never say who is right. Plain text only, no markdown, no title.
STORY: {story['title']}
ANALYSIS: {json.dumps({k: a.get(k) for k in ('common_ground', 'sides', 'watch_out')}, ensure_ascii=False)}
COUNTRY CODES: {json.dumps(NAMES)}""").strip()

def translate(its):
    lines = "\n".join(f"{n}|{i['title']}" for n, i in enumerate(its) if not i["lang"].startswith("en"))
    if not lines:
        return {}
    return ask_json("Translate each headline to English. Reply with JSON only: {\"<index>\": \"English translation\"}\n" + lines)

PATH = "../web/data/stories.json"
def load():
    try:
        return {s["id"]: s for s in json.load(open(PATH))}
    except Exception:
        return {}

import threading
LOCK = threading.Lock()
def save(out):
    with LOCK:
        done = load(); done[out["id"]] = out
        json.dump(list(done.values()), open(PATH, "w"), ensure_ascii=False, indent=1)

def build(story):
    prev = load().get(story["id"], {})
    out = {k: story[k] for k in ("id", "topic", "title", "by_country", "n_outlets", "wires")}
    if prev.get("sides"):
        print("reuse analysis", story["id"], flush=True)
        for k in ("countries", "country_names", "headlines", "common_ground", "sides", "claims", "watch_out", "divergence"):
            out[k] = prev.get(k)
        a = {k: prev.get(k) for k in ("common_ground", "sides", "watch_out")}
    else:
        print("analysing", story["id"], flush=True)
        countries, its, a = analyse(story)
        out["countries"] = countries
        out["country_names"] = {c: NAMES.get(c, c) for c in countries}
        out["headlines"] = [{**{k: i[k] for k in ("country", "outlet", "ownership", "leaning", "title", "link", "published", "lang")},
                             "translation": None} for i in its]
        for k in ("common_ground", "sides", "claims", "watch_out", "divergence"):
            out[k] = a.get(k)
    out["briefing"] = dict(prev.get("briefing") or {})
    save(out)
    if not any(h.get("translation") for h in out["headlines"]):
        try:
            tr = translate(out["headlines"])
            for n, h in enumerate(out["headlines"]):
                h["translation"] = tr.get(str(n))
            save(out); print("  translated", story["id"], flush=True)
        except Exception as e:
            print("  translation failed", story["id"], e, flush=True)
    for lang in LANGS:
        if out["briefing"].get(lang):
            continue
        try:
            out["briefing"][lang] = briefing(story, a, lang)
            save(out); print("  briefing", story["id"], lang, flush=True)
        except Exception as e:
            print("  briefing failed", story["id"], lang, e, flush=True)
    return out

def run(only=None):
    stories = json.load(open("cache/coverage.json"))
    if only:
        stories = [s for s in stories if s["id"] in only]
    with ThreadPoolExecutor(3) as ex:
        for res in ex.map(lambda s: _safe(build, s), stories):
            if res:
                print("done", res["id"], sorted(res["briefing"]), flush=True)

def _safe(f, s):
    try:
        return f(s)
    except Exception as e:
        print("FAILED", s["id"], e, flush=True)

if __name__ == "__main__":
    run(sys.argv[1:] or None)
