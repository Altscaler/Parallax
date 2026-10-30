"""Run Parallax locally: python3 server.py, then open http://localhost:8000
Serves web/ and three endpoints: /api/check (claims vs other outlets), /api/tts (Piper or ElevenLabs)."""
import json, os, subprocess, sys, tempfile, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import gemma  # loads .env
from check import check

ELEVEN_VOICE = "21m00Tcm4TlvDq8ikWAM"  # a default multilingual voice
PIPER = {"en": "en_US-lessac-medium", "fr": "fr_FR-siwis-medium", "es": "es_ES-davefx-medium",
         "zh": "zh_CN-huayan-medium", "ar": "ar_JO-kareem-medium"}

def tts(text, lang, engine):
    if engine == "elevenlabs":
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("no ElevenLabs key in .env")
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}",
            json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
            {"Content-Type": "application/json", "xi-api-key": key, "Accept": "audio/mpeg"})
        return urllib.request.urlopen(req, timeout=120).read(), "audio/mpeg"
    if engine == "piper":
        voices = os.path.join(ROOT, "voices")
        model = os.path.join(voices, PIPER[lang] + ".onnx")
        if not os.path.exists(model):
            raise RuntimeError(f"Piper voice not downloaded: run python3 -m piper.download_voices {PIPER[lang]} --data-dir voices")
        out = tempfile.mktemp(suffix=".wav")
        subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", out], input=text.encode(), check=True, capture_output=True)
        return open(out, "rb").read(), "audio/wav"
    raise RuntimeError("unknown engine")

class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(ROOT, "web"), **k)

    def reply(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode())

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            if self.path == "/api/check":
                return self.reply(200, check(data.get("text", ""), data.get("lang", "English"), data.get("instagram") or None))
            if self.path == "/api/tts":
                audio, ctype = tts(data["text"], data.get("lang", "en"), data.get("engine"))
                return self.reply(200, audio, ctype)
            self.reply(404, {"error": "not found"})
        except Exception as e:
            self.reply(500, {"error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Parallax on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
