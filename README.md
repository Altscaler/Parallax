# Parallax

Parallax shows how the same news story is told in different countries and by different political camps, and checks the claims that hold it up.

It reads this week's headlines from the Google News editions of France, Spain, the US, the UK, China and the UAE, groups the ones about the same event across languages, and keeps the stories that at least 3 countries cover. For each story, Gemma 4 writes what most countries agree on, what each side emphasises or leaves out, which claims are confirmed, contested or come from a single source, and a one-minute spoken briefing in Arabic, Chinese, English, French or Spanish.

Built at Hack Day Dubai (MLH x Legesher), 30 October 2026, for three challenges: Best Use of Gemma 4, Best Open-Source AI Project, and Best Innovation in Your Language.

## What's in it

- **Dashboard** (`web/`): this week's stories, filters by country, political camp and topic, and the reason each story is shown ("covered in 6 countries by 40 outlets, including Reuters").
- **Story view**: compare any two countries side by side, with original headlines, English translations, each outlet's owner or funder, Gemma's reading of each side and its loaded words, a fact-check of the main claims, and the briefing read aloud.
- **Check a claim**: paste text, a WhatsApp message or an Instagram post link. Gemma pulls the claims and looks for them in other outlets.
- **Chrome extension** (`extension/`): the same check on the article you are reading.

## How Gemma is used

- **Gemma 4 26B-A4B through the Gemini API** compares headlines across countries, extracts and judges claims, translates headlines and writes the briefings in 5 languages (`pipeline/explain.py`, `pipeline/check.py`, `extension/analyze.js`).
- **EmbeddingGemma**, an open-weight Gemma model, runs locally through Ollama to group headlines about the same event across languages (`pipeline/cluster.py`).

## Voices

The briefing can be read by three engines, chosen in the sidebar:

- **Built-in voice** (default): the browser's speech engine, free and offline.
- **Piper**: open-source local text to speech with Arabic, Chinese, English, French and Spanish voices. `pip install piper-tts`, then download a voice into `voices/`.
- **ElevenLabs**: optional, paid, only used if `ELEVENLABS_API_KEY` is set.

## Run it

```
cp .env.example .env            # add GEMINI_API_KEY (and optionally APIFY_TOKEN, ELEVENLABS_API_KEY)
ollama pull embeddinggemma
cd pipeline
python3 ingest.py               # this week's headlines, 6 country editions
python3 cluster.py              # group by event, rank, keep stories in 3+ countries
python3 stories.py              # full coverage for the selected stories
python3 explain.py              # Gemma 4 writes the comparison, fact-check and briefings
cd .. && python3 server.py      # open http://localhost:8000
```

No dependencies beyond Python 3 and Ollama. Keys stay in `.env`, which is never committed. Apify (for Instagram links) and ElevenLabs are optional: everything else works without them.

## Chrome extension

The extension runs the claim check on the article you are reading: before you share or believe a piece, see what the rest of the press says about its claims.

1. It reads the text of the page you are on.
2. Gemma 4 (26B-A4B, through the Gemini API) extracts up to four checkable claims and a search query for each.
3. Each query runs against Google News RSS in four editions (US, UK, FR, AE), and the outlets found are collected, excluding the article's own site.
4. Gemma compares the claims with those headlines and returns a status per claim plus a note on the outlet.

Statuses:
- Confirmed: several independent outlets, or a wire agency such as Reuters, AP or AFP, report it.
- Contested: other outlets report something different.
- Single source: only this article reports it, or everyone repeats one origin.
- No coverage found: nothing in the headlines, which proves nothing either way.

Install: open `chrome://extensions`, turn on Developer mode, click Load unpacked and choose the `extension` folder. Open a news article, click the icon, paste a Gemini API key and click Check this story. The key is saved in your browser's local extension storage and is only sent to the Gemini API. The outlet note comes from the model's general knowledge and is not verified, and paywalled pages give it less text to read.

## How we try to stay neutral

- An outlet counts for its own country, whatever edition it appears in. Google News's China edition mostly shows Western outlets writing in Chinese (BBC, VOA, RFI), so those count as UK, US and France, and China-based outlets (Guancha, Sina, Global Times) count as China.
- Every outlet gets the same fields: owner or funder, and whether a government funds it. Left, centre or right only appears where a public rating exists (AllSides, Media Bias Fact Check), which is mostly the US, UK, France and Spain.
- Gemma is told never to say who is right and never to call an outlet reliable or unreliable.

## Limits

- Gemma only sees headlines, not full articles.
- "Single source" or "no coverage" means nothing else was found yet. It does not mean false.
- Some countries have few outlets in Google News, and the outlet table is filled by hand for about 80 outlets.
- Gemma's own training data has blind spots, so its reading is a starting point.
- The Gemini API was slow during the event, so the demo stories are prepared in advance.

## License

MIT. See `LICENSE`. Gemma 4 and EmbeddingGemma are open-weight models released by Google DeepMind.
