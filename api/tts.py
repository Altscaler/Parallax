"""Vercel serverless function: POST /api/tts -> ElevenLabs MP3.

Mirrors the ElevenLabs path in server.py so the hosted (static) Vercel demo
can play audio too. Reads ELEVENLABS_API_KEY from the Vercel project env.
Static hosting alone can't do this; Vercel runs files under /api as functions.
"""
import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

ELEVEN_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George" - premade voice (library voices need a paid plan)


class handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code, message):
        self._send(code, json.dumps({"error": message}).encode(), "application/json")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._error(400, "bad request body")

        text = (data.get("text") or "").strip()
        if not text:
            return self._error(400, "no text to speak")

        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            return self._error(500, "ELEVENLABS_API_KEY not set on the server")

        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}",
            json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
            {"Content-Type": "application/json", "xi-api-key": key, "Accept": "audio/mpeg"},
        )
        try:
            audio = urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            return self._error(502, f"ElevenLabs {e.code}: {detail}")
        except Exception as e:
            return self._error(502, f"ElevenLabs request failed: {e}")

        self._send(200, audio, "audio/mpeg")
