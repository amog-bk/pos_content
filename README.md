# pos_content — Weekly India business-insurance roundup

A small, config-driven Python scraper that pulls business-insurance updates
from the sources in `india_insurance_intelligence_source_map.md`, filters them
for what matters to BimaKavach Partners (POSP/agents selling commercial
insurance to SMEs), and produces two artifacts each week:

- `roundups/<YYYY-Www>/digest.md` — long-form internal review (everything
  worth a look, bucketed by topic)
- `roundups/<YYYY-Www>/partner-messages.md` — 3–5 short WhatsApp messages in
  the BimaKavach Partner voice (per `pos-engagement-skill/SKILL.md`), ready for
  the content team to review and send

## How it runs

GitHub Actions cron: every Monday 03:00 UTC (08:30 IST). The workflow checks
out the repo, runs the scraper, and commits the new `roundups/<week>/` folder.

You can also trigger a run manually from the **Actions** tab → **Weekly
insurance roundup** → **Run workflow**. Optional inputs: ISO week label and
minimum classifier score.

## Local run

```bash
pip install -r requirements.txt
python -m scraper.main -v
# → roundups/2026-W20/digest.md
# → roundups/2026-W20/partner-messages.md
```

Flags:
- `--week 2026-W20` — override the auto-detected ISO week
- `--out roundups` — change output directory
- `--min-score N` — raise/lower the relevance threshold (default 5)

## Picking sources

`scraper/sources.yml` lists every source from the source map. To add/remove
sources from the next weekly run, flip `enabled: true|false`. Each source has:

- `tier` (1=critical, 2=news, 3=advanced) — used as a small score boost
- `partner_relevance` (1–5) — base relevance score for items from this source
- `categories` — fed to the classifier as hints
- `parser` — `irdai_listing` for IRDAI table-style pages, `generic_html` for
  most news sites. Add a new file under `scraper/parsers/` to hand-tune a
  source.

Two sources ship **disabled** (Swiss Re Institute, Lloyd's Insights) because
their content is global-focused and rarely useful to Partners selling Indian
SME business insurance. Flip `enabled: true` if you want them in.

## Voice rules

`scraper/whatsapp.py` is template-driven, not LLM-driven. Every Partner draft
follows the structure in `pos-engagement-skill/SKILL.md`:

- Namaste / Hello greeting
- One-line context
- The headline
- One-line "why this matters for you" explainer
- Source + link
- Warm closing ("We are here to support you. Team BimaKavach")

No emojis other than the optional 🙏🏽. No jargon. No marketing hype. The
"50-year-old uncle on WhatsApp" test applies to every message.

If a category isn't covered by a template, add it to `CATEGORY_HOOK` and
`CATEGORY_EXPLAINER` in `whatsapp.py`.

## Layout

```
scraper/
  main.py           # entry point — fetch, parse, score, write
  config.py         # loads sources.yml
  fetcher.py        # HTTP with retry/backoff
  classifier.py     # Partner-relevance scoring
  roundup.py        # internal long-form digest writer
  whatsapp.py       # Partner WhatsApp draft writer
  sources.yml       # source list — edit to add/remove
  parsers/
    base.py
    generic_html.py # default — news sites
    irdai_listing.py # IRDAI tables of circulars + PDFs

roundups/
  <YYYY-Www>/
    digest.md
    partner-messages.md

.github/workflows/
  weekly-scrape.yml # Monday 03:00 UTC + manual trigger
```

## Iterating

After the first real run lands:
1. Skim `digest.md`, note sources that are noisy or low-signal → flip
   `enabled: false` in `sources.yml`.
2. Note signals the classifier missed → add a row to `SIGNALS` in
   `classifier.py`.
3. Note messages that don't sound right → tweak `CATEGORY_HOOK` /
   `CATEGORY_EXPLAINER` in `whatsapp.py`.
4. Commit and let the next Monday's run pick up the changes.
