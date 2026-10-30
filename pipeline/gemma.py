import json, os, re, time, urllib.request, urllib.error
ENV = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(ENV):  # on Render the keys come from environment variables instead
    for line in open(ENV):
        if "=" in line:
            k, v = line.strip().split("=", 1); os.environ.setdefault(k, v)

MODEL = "gemma-4-26b-a4b-it"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

def ask(prompt, retries=4):
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    for n in range(retries):
        req = urllib.request.Request(URL, body, {"Content-Type": "application/json",
                                                 "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][-1]["text"]
        except (OSError, KeyError) as e:
            print("retry", n, e); time.sleep(5 * (n + 1))
    raise RuntimeError("gemma failed")

def ask_json(prompt):
    txt = ask(prompt)
    m = re.search(r"(\[.*\]|\{.*\})", txt, re.S)
    return json.loads(m.group(1))
