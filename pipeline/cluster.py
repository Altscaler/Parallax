"""Group this week's headlines into stories across languages (EmbeddingGemma, local),
then rank stories with criteria anyone can check. Writes cache/stories.json."""
import json, math, urllib.request
from datetime import datetime, timezone

WIRES = {"reuters", "associated press", "ap news", "afp", "agence france-presse", "bloomberg"}
THRESHOLD = 0.72

def embed(texts, batch=64):
    out = []
    for i in range(0, len(texts), batch):
        req = urllib.request.Request("http://localhost:11434/api/embed",
            json.dumps({"model": "embeddinggemma", "input": texts[i:i+batch]}).encode(),
            {"Content-Type": "application/json"})
        out += json.load(urllib.request.urlopen(req, timeout=300))["embeddings"]
        print("embedded", len(out), "/", len(texts), flush=True)
    return out

def norm(v):
    n = math.sqrt(sum(x*x for x in v)) or 1
    return [x/n for x in v]

def dot(a, b): return sum(x*y for x, y in zip(a, b))

def run():
    items = json.load(open("cache/items.json"))
    import os, sys
    if os.path.exists("cache/emb.json") and len(json.load(open("cache/emb.json"))) == len(items):
        raw = json.load(open("cache/emb.json"))
    else:
        raw = embed([i["title"] for i in items]); json.dump(raw, open("cache/emb.json", "w"))
    vecs = [norm(v) for v in raw]
    global THRESHOLD
    THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else THRESHOLD
    clusters = []  # each: {"centroid", "members"}
    for idx, v in enumerate(vecs):
        best, bs = None, THRESHOLD
        for c in clusters:
            s = dot(v, c["centroid"])
            if s > bs: best, bs = c, s
        if best is None:
            clusters.append({"centroid": v, "members": [idx]})
        else:
            best["members"].append(idx)
            n = len(best["members"])
            best["centroid"] = norm([(c*(n-1) + x)/n for c, x in zip(best["centroid"], v)])
    now = datetime.now(timezone.utc)
    stories = []
    for c in clusters:
        its = [items[i] for i in c["members"]]
        countries = sorted({i["country"] for i in its})
        outlets = sorted({i["outlet"] for i in its if i["outlet"]})
        if len(countries) < 3:
            continue
        wires = sorted({o for o in outlets if o.lower() in WIRES})
        newest = max(datetime.fromisoformat(i["published"]) for i in its)
        age_h = (now - newest).total_seconds()/3600
        score = len(countries)*10 + min(len(outlets), 30) + (5 if wires else 0) + max(0, 10 - age_h/12)
        stories.append({"score": round(score, 1), "countries": countries, "n_outlets": len(outlets),
                        "wires": wires, "newest_hours_ago": round(age_h),
                        "why": f"covered in {len(countries)} countries by {len(outlets)} outlets"
                               + (f", including {', '.join(wires)}" if wires else "")
                               + f", newest {round(age_h)} h ago",
                        "items": [{k: i[k] for k in ("country", "title", "outlet", "link", "published")} for i in its]})
    stories.sort(key=lambda s: -s["score"])
    json.dump(stories, open("cache/stories.json", "w"), ensure_ascii=False, indent=1)
    print(len(clusters), "clusters,", len(stories), "stories in 3+ countries")
    for s in stories[:12]:
        t = next((i["title"] for i in s["items"] if i["country"] in ("US", "GB")), s["items"][0]["title"])
        print(s["score"], "|", "".join(s["countries"]), "|", t[:80])

if __name__ == "__main__":
    run()
