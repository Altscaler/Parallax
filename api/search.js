// Vercel function: Gemma 4 picks which stories answer a reader's search, in any language.
// Needs GEMINI_API_KEY in the Vercel project's environment variables.
const URL = "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent";

function prompt({ query, stories }) {
  const lines = (stories || []).map(s => `${s.id} | ${s.topic} | ${s.title}`).join("\n");
  return `A reader searches a news dashboard. Pick the stories that match what they are looking for, best match first, at most 6. The search may be in any language or a loose description.
Answer with only a JSON array of story ids from the list, or [] if none match.

SEARCH: ${query}
STORIES (id | topic | title):
${lines}`;
}

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const key = process.env.GEMINI_API_KEY;
  if (!key) return res.status(500).json({ error: "GEMINI_API_KEY is not set on the server" });
  const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
  for (let n = 0; n < 3; n++) {
    try {
      const r = await fetch(URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ parts: [{ text: prompt(body) }] }], generationConfig: { thinkingConfig: { thinkingLevel: "minimal" } } }),
        signal: AbortSignal.timeout(25000),
      });
      if (r.ok) {
        const d = await r.json(); const parts = d.candidates[0].content.parts;
        const m = parts[parts.length - 1].text.match(/\[.*\]/s);
        return res.status(200).json({ ids: m ? JSON.parse(m[0]) : [] });
      }
    } catch (e) { /* retry */ }
  }
  res.status(502).json({ error: "Gemma did not answer, try again" });
};

module.exports.prompt = prompt;
