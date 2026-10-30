// Vercel function: Gemma 4 answers live about one story, from its headlines only.
// Needs GEMINI_API_KEY in the Vercel project's environment variables.
const URL = "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent";

function prompt({ title, lang, question, length, compare, headlines, sides, common_ground }) {
  const words = length === "short" ? 40 : 120;
  const lines = (headlines || []).map(h => `${h.country} | ${h.outlet} | ${h.title}${h.translation ? " (" + h.translation + ")" : ""}`).join("\n");
  const ending = compare ? ` End with one last sentence on how media from ${compare[0]} and from ${compare[1]} tell it differently.` : "";
  const task = (question
    ? `Answer this question from a reader in ${lang}, in at most ${words} words: "${question}"`
    : `Write a spoken news briefing of about ${words} words in ${lang}, in the voice of a calm, neutral reporter: one sentence on what happened, then how each country's media tells it.`) + ending;
  return `You explain how different countries' media cover one news story. You only know the headlines below.
Never say who is right. Never call an outlet reliable or unreliable. If the headlines don't answer, say so. Plain text, no markdown.
${task}

STORY: ${title}
WHAT MOST AGREE ON: ${JSON.stringify(common_ground || [])}
EACH SIDE: ${JSON.stringify(sides || {})}
HEADLINES (country | outlet | headline):
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
        return res.status(200).json({ text: parts[parts.length - 1].text.trim() });
      }
    } catch (e) { /* retry */ }
  }
  res.status(502).json({ error: "Gemma did not answer, try again" });
};

module.exports.prompt = prompt;
