"""Pull this week's headlines from each country's Google News edition (top stories + world).
Writes cache/items.json. No AI here: this is the transparent first filter."""
import json, re, sys, time, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

EDITIONS = {  # country: (hl, gl, ceid)
    "FR": ("fr", "FR", "FR:fr"),
    "ES": ("es", "ES", "ES:es"),
    "US": ("en-US", "US", "US:en"),
    "GB": ("en-GB", "GB", "GB:en"),
    "CN": ("zh-CN", "CN", "CN:zh-Hans"),
    "AE": ("ar", "AE", "AE:ar"),
}
SECTIONS = ["", "headlines/section/topic/WORLD", "headlines/section/topic/BUSINESS",
            "headlines/section/topic/SPORTS", "headlines/section/topic/TECHNOLOGY"]
WEEK = timedelta(days=7)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def run():
    now = datetime.now(timezone.utc)
    items, seen = [], set()
    for country, (hl, gl, ceid) in EDITIONS.items():
        for sec in SECTIONS:
            path = sec or ""
            url = f"https://news.google.com/rss/{path}?hl={hl}&gl={gl}&ceid={ceid}"
            try:
                root = ET.fromstring(fetch(url))
            except Exception as e:
                print("fail", country, sec, e, file=sys.stderr); continue
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                src = it.find("source")
                outlet = src.text.strip() if src is not None and src.text else ""
                # Google appends " - Outlet" to the title
                title = re.sub(r"\s+-\s+" + re.escape(outlet) + r"$", "", title) if outlet else title
                try:
                    when = parsedate_to_datetime(it.findtext("pubDate"))
                except Exception:
                    continue
                if now - when > WEEK:
                    continue
                key = (country, title)
                if key in seen:
                    continue
                seen.add(key)
                items.append({"country": country, "lang": hl, "title": title, "outlet": outlet,
                              "outlet_url": src.get("url") if src is not None else "",
                              "link": it.findtext("link"), "published": when.isoformat(),
                              "section": sec.split("/")[-1] if sec else "TOP"})
            time.sleep(0.3)
    json.dump(items, open("cache/items.json", "w"), ensure_ascii=False, indent=1)
    by = {}
    for i in items:
        by[i["country"]] = by.get(i["country"], 0) + 1
    print(len(items), "items", by)

if __name__ == "__main__":
    run()
