"""Build the demo stories: targeted Google News searches in each language edition,
outlets assigned to their real country of origin (not the edition they appear in).
Writes cache/coverage.json. No AI here."""
import json, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from outlets import profile

EDITIONS = {"FR": ("fr", "FR", "FR:fr"), "ES": ("es", "ES", "ES:es"), "US": ("en-US", "US", "US:en"),
            "GB": ("en-GB", "GB", "GB:en"), "CN": ("zh-CN", "CN", "CN:zh-Hans"), "AE": ("ar", "AE", "AE:ar")}

STORIES = [
    {"id": "mbappe-mao", "topic": "Sport", "title": "Mbappé apologises for calling Mao a \"dictator\", Chinese brands drop him",
     "q": {"FR": ["Mbappé Mao"], "ES": ["Mbappé Mao"], "US": ["Mbappe Mao"], "GB": ["Mbappe Mao"],
           "CN": ["姆巴佩 毛泽东", "姆巴佩 site:guancha.cn", "姆巴佩 site:sina.com.cn", "Mbappe site:globaltimes.cn"],
           "AE": ["مبابي ماو"]}},
    {"id": "binance-hack", "topic": "Economy", "title": "Binance suspends withdrawals after hackers steal $6.3 billion",
     "q": {"FR": ["Binance piratage"], "ES": ["Binance hackeo"], "US": ["Binance hack"], "GB": ["Binance hack"],
           "CN": ["币安 黑客"], "AE": ["بينانس اختراق"]}},
    {"id": "novaya-gazeta", "topic": "Politics", "title": "Novaya Gazeta, Russia's last independent newspaper, announces it will close",
     "q": {"FR": ["Novaïa Gazeta fermeture"], "ES": ["Nóvaya Gazeta cierre"], "US": ["Novaya Gazeta shut"],
           "GB": ["Novaya Gazeta close"], "CN": ["新报 俄罗斯 停刊"], "AE": ["نوفايا غازيتا"]}},
    {"id": "ukraine-refineries", "topic": "Politics", "title": "Ukraine's strikes on Russian refineries: paused under Trump's pressure, or resumed?",
     "q": {"FR": ["Ukraine raffinerie russe Trump"], "ES": ["Ucrania refinerías rusas Trump"], "US": ["Ukraine refinery strikes Trump"],
           "GB": ["Ukraine refinery strikes pause"], "CN": ["乌克兰 炼油厂 特朗普"], "AE": ["أوكرانيا مصافي روسية ترامب"]}},
    {"id": "us-midterms", "topic": "Politics", "title": "More than 43 million ballots already cast in US midterm early voting",
     "q": {"FR": ["midterms vote anticipé"], "ES": ["elecciones de medio mandato voto anticipado"], "US": ["midterm early voting record"],
           "GB": ["US midterms early voting"], "CN": ["美国 中期选举 提前投票"], "AE": ["الانتخابات النصفية الأمريكية التصويت المبكر"]}},
]

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def search(query, edition, when="7d"):
    hl, gl, ceid = EDITIONS[edition]
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query + f" when:{when}", "hl": hl, "gl": gl, "ceid": ceid})
    out = []
    for it in ET.fromstring(fetch(url)).iter("item"):
        src = it.find("source")
        name = src.text.strip() if src is not None and src.text else ""
        domain = re.sub(r"^https?://", "", src.get("url", "")).split("/")[0] if src is not None else ""
        title = re.sub(r"\s+-\s+" + re.escape(name) + r"$", "", (it.findtext("title") or "").strip()) if name else it.findtext("title")
        try:
            when = parsedate_to_datetime(it.findtext("pubDate")).isoformat()
        except Exception:
            when = None
        out.append({"title": title, "domain": domain, "outlet_name": name, "edition": edition,
                    "lang": hl, "link": it.findtext("link"), "published": when})
    return out

def run():
    result = []
    for st in STORIES:
        seen, items = set(), []
        for ed, queries in st["q"].items():
            for q in queries:
                try:
                    found = search(q, ed)
                except Exception as e:
                    print("fail", st["id"], ed, q, e); continue
                for f in found[:15]:
                    if (f["domain"], f["title"]) in seen:
                        continue
                    seen.add((f["domain"], f["title"]))
                    p = profile(f["domain"], f["outlet_name"], ed)
                    items.append({**f, "outlet": p["name"], "country": p["country"], "ownership": p["ownership"],
                                  "leaning": p["leaning"], "profiled": p["profiled"]})
                time.sleep(0.4)
        by = {}
        for i in items:
            by[i["country"]] = by.get(i["country"], 0) + 1
        wires = sorted({i["outlet"] for i in items if i["outlet"] in ("Reuters", "AP News", "AFP")})
        outlets = {i["outlet"] for i in items}
        result.append({**{k: st[k] for k in ("id", "topic", "title")}, "by_country": by, "n_outlets": len(outlets),
                       "wires": wires, "items": items})
        print(st["id"], len(items), "items", by, "wires", wires)
    json.dump(result, open("cache/coverage.json", "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    run()
