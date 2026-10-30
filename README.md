# Parallax

A Chrome extension that checks a news article while you read it. It pulls the main claims out of the page, looks for other outlets covering the same claims in the US, UK, France and UAE editions of Google News, and shows whether each claim is confirmed, contested, from a single source, or not found elsewhere. It also adds a short note on who owns the outlet.

## Context

Parallax started at Hack Day Dubai (MLH x Legesher, 30 October 2026) as the quick-check part of a larger idea called Angles. Angles compares how different countries and political camps tell the same story. Parallax brings the first step of that to any article you are reading: before you share or believe a piece, see what the rest of the press says about its claims.

It is built for three challenges: Best Use of Gemma 4, Best Open-Source AI Project, and Best Innovation in Your Language.

## How it works

1. The extension reads the text of the page you are on.
2. Gemma 4 (26B-A4B, through the Gemini API) extracts up to four checkable claims and a search query for each.
3. Each query runs against Google News RSS in four editions (US, UK, FR, AE), and the outlets found are collected, excluding the article's own site.
4. Gemma compares the claims with those headlines and returns a status per claim plus a note on the outlet.

Statuses:
- Confirmed: several independent outlets, or a wire agency such as Reuters, AP or AFP, report it.
- Contested: other outlets report something different.
- Single source: only this article reports it, or everyone repeats one origin.
- No coverage found: nothing in the headlines, which proves nothing either way.

The tool shows gaps between sources. It never says who is lying and never labels an outlet reliable or unreliable.

## Install

1. Open `chrome://extensions` and turn on Developer mode.
2. Click Load unpacked and choose the `extension` folder.
3. Open a news article, click the icon, paste a Gemini API key, and click Check this story.

The key is saved in your browser's local extension storage and is only sent to the Gemini API.

## Limits

- Judgments rest on Google News headlines, not on full articles.
- The outlet note comes from the model's general knowledge and is not verified.
- Tested on English articles. The output language selector exists, but Arabic failed once in testing.
- Paywalled pages give the extension less text to read.

## License

MIT. Gemma 4 is an open-weight model released by Google DeepMind.
