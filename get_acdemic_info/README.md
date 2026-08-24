# Academic information crawler

The module uses official APIs for arXiv and PubMed. Google Scholar requests are
routed to the OpenAlex public API because direct automated Scholar scraping is
fragile and commonly triggers captchas.

For other sites, the service fetches public HTML, asks the configured Codex
model for CSS selectors, validates those selectors, generates a reviewable
Python crawler under `generated/`, and executes only the constrained generic
engine. Model-generated Python is never executed directly.

Optional JavaScript rendering requires:

```bash
pip install playwright
playwright install chromium
```

Sites that require login, captchas, or institutional access are not bypassed.
Use an official API, RSS/export endpoint, institutional proxy, or an authorized
Playwright storage state. Do not automate around access controls. Google
Scholar is intentionally mapped to OpenAlex for this reason.

API endpoint: `POST /api/academic/crawl`. The request accepts `source_url`,
`keywords`, `time_range_days`, `min_citations`, `recent_days`, `max_results`,
`render_javascript`, `output_format`, and an optional `selectors` object.
