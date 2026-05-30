---
name: BimaKavach Weekly Industry Briefing
description: Write the weekly "Insurance this week" industry briefing for BimaKavach team members, from the ranked material the scraper produces each Friday. Covers tone, structure, and formatting. This is a SEPARATE voice from the POS Partner WhatsApp skill — the audience here is internal, industry-savvy team members, not agents.
version: 0.1.0
---

# BimaKavach Weekly Industry Briefing

Write the weekly insurance industry briefing for BimaKavach **team members**.
The input is the ranked material in `roundups/<week>/briefing-material.md`
(and the "Briefing" tab in the sheet). The output is one briefing per Friday.

> This is a DRAFT voice guide seeded from one example. Add more past
> briefings to `briefing-voice/examples/` to sharpen the voice match.

## Audience

- Internal BimaKavach team members who follow the insurance market.
- Comfortable with industry terms, but they value clarity and speed.
- They read this to stay current in 2 minutes — not to study.

## Voice

Blend two things:
- **BimaKavach clarity** (from the POS Engagement Skill): simple words,
  short sentences, one idea per sentence, no hype, no fluff. If a technical
  term is unavoidable (combined ratio, REIT, expense of management), use it
  but keep the sentence plain.
- **Briefing precision**: name the companies, the numbers, and the amounts.
  Be specific and factual. This is intelligence, not marketing.

Avoid:
- Marketing hype ("game-changing", "revolutionary", "exciting").
- Long, clause-heavy sentences.
- Vague summaries ("there were some developments in regulation").

## Structure

Follow the structure of the example below.

1. **Opening headline paragraph** — titled *Insurance this week*. In 2–3
   sentences, name the single biggest story, then 1–2 other notable threads.
   This is a synthesis, not a list.
2. **Major Business & Market Deals** — M&A, stake sales, IPOs, fundraises,
   company results, bonuses, expansion plans.
3. **Regulatory Actions & Corporate Governance** — IRDAI actions,
   governance, executive pay/KPIs, investment norms.
4. **Industry & Premium Trends** — premium growth, pricing, segment trends,
   distribution economics, claims/consumer themes.

Within each section:
- Use an *italic-bold sub-headline* naming the specific development
  (e.g. *Prudential's Strategic Acquisition:*).
- Follow with 1–2 plain sentences: what happened + the key number/amount.
- Include the source link for each item.

## Selection rules

- Pick only the most relevant stories for the team — not everything in the
  material file. 3–5 items per section is plenty; fewer is fine.
- Skip a section entirely if nothing this week is worth it.
- Prefer this week's news; the material file applies a recency window
  anchored to the scrape's ISO week, but double-check the date on every
  item before including it (see "Timeline correctness" below).

## Importance ranking (ordering)

Order news from most to least important — both across the brief and within
each section. This is the spine of the briefing, not an afterthought.

- **The opener** names the single most important story of the week first,
  then the next 1–2 threads in descending importance.
- **Within each section**, the first item is the biggest story in that
  section; the rest follow in descending importance.
- The material file gives each item a score and a rank — use that as the
  starting signal, then apply judgement. A high-score item that is stale,
  niche, or off-audience can drop below a lower-scored item that genuinely
  matters more to the team.
- Rank on impact to the Indian insurance market and to BimaKavach's world
  (commercial/SME distribution, regulation that moves the channel),
  not on how dramatic the headline sounds.

## Length

**Hard rule — each piece in the brief is 30 to 50 words.**
This applies to:
- The opening "*Insurance this week*" paragraph
- Every section item (the text after the `_Sub-headline:_`)

Count words in the body only — the `_Sub-headline:_` label itself does
not count toward the budget. Under 30 = pad with a relevant fact, figure,
or implication. Over 50 = cut filler, drop a secondary clause, or split
into two items.

The whole brief is roughly 350–450 words — short enough to read in 2
minutes, long enough to carry the week's substance.

## Format

The briefing is delivered as a chat/WhatsApp message — use WhatsApp text
formatting, NOT Markdown:

- `*Section Title*` — single asterisks for bold (section headings and the
  opener "*Insurance this week*")
- `_Story sub-headline:_` — underscores for italics on each item's
  sub-headline, with a trailing colon
- Plain text for the body sentence(s) after the sub-headline
- One blank line between items
- **No inline source URLs in the message body.** Sources stay in the
  `briefing-material.md` file and the sheet's section columns for
  internal traceability — they do not appear in the shareable message.
  This keeps the body clean and readable.

## The reference example (the team's current format)

```
*Insurance this week*

The headline in the insurance sector this week is Prudential's ₹3,500
crore acquisition of a 75% stake in Bharti Life Insurance. In parallel,
India's non-life sector is seeing surging retail health premiums, up
31% year-on-year. Meanwhile, IRDAI is cracking down on corporate
governance by withholding the variable pay of multiple insurance CEOs.

*Major Business & Market Deals*

_Prudential's Strategic Acquisition:_ Global giant Prudential agreed to
buy a 75% stake in Bharti Life Insurance for ₹3,500 crore, with an
additional ₹700 crore contingent on milestones.

_ICICI Pru Rebalancing:_ To comply with rules, Prudential will pare its
12% stake in ICICI Prudential Life over the next 12 to 18 months.

_Tata AIA Bonus Growth:_ Tata AIA Life raised its bonus payout to
participating policyholders by 18%, totaling $217 million.

_IndusInd Nippon Profit Jump:_ IndusInd Nippon Life posted a 15% profit
surge for FY2026 and announced plans to open 200 new sales units across
India.

*Regulatory Actions & Corporate Governance*

_CEO Pay Withheld:_ IRDAI withheld variable pay for certain insurance
CEOs due to a failure to meet 'expense of management' targets.

_Tightening Performance Metrics:_ Life insurers are resisting a push to
tie executive pay to strict KPIs involving claims settlement and
customer service.

_Investment Easing:_ IRDAI is considering easing norms to allow insurers
to invest more in REITs and InvITs.

*Industry & Premium Trends*

_Health Insurance Booms:_ Retail health remains the engine of growth for
the non-life segment, up 31% YoY per Kotak Institutional Securities.

_Tier-2 & Tier-3 Discounts:_ Star Health rolled out products 20% cheaper
for smaller cities.

_High Operational Costs:_ A Praxis Global Alliance report highlighted
that general insurance costs remain elevated due to heavy intermediary
commissions on renewal business.
```

## Editorial standards — self-check before delivery

Run this pass on the finished brief BEFORE it goes out. These are the
mistakes that have slipped through before; catch them yourself.

### Timeline correctness (it's a weekly roundup, not a daily)

The brief is read across the week and archived, so relative-time words go
stale the moment it's sent. Never use them. Rewrite to absolute references
without changing the meaning.

- Ban: "today", "yesterday", "tomorrow", "this morning", "now", "currently".
- Ban as the *only* anchor: a bare "this week" tied to a dated event — be
  specific instead.
- Use: the actual date or weekday ("on Friday, May 29", "effective FY27",
  "record date 29 May").
- Example: "takes Friday, May 29 as its record date — shareholders on the
  books today receive…" → "set Friday, May 29 as the record date —
  shareholders on the register that day receive…".

### No redundancy

Don't say the same thing twice in one item. If two phrases carry the same
fact, keep the stronger one and cut the other.

- Example: "first-ever 1:1 bonus … marking its maiden bonus issue since its
  2022 listing" — "first-ever" and "maiden … since 2022 listing" duplicate.
  Keep one.

### Headline ↔ body consistency

Every `_Sub-headline:_` must be supported by its body sentences. The
sub-headline is a claim; the body must back it up. If the body doesn't
support the claim, either change the sub-headline to match the body or add
the supporting fact to the body.

- Example: "_Niva Bupa Eyes Top Two:_" with a body that never mentions a
  top-two ambition → rename to "_Niva Bupa Targets Above-Market Growth:_".

### Pre-flight checklist

- [ ] Opener and every section ordered most → least important.
- [ ] No relative-time words; all dates absolute.
- [ ] No item repeats a fact within itself.
- [ ] Every sub-headline is supported by its body.
- [ ] Every item is from the scrape's week (or, if older, kept on purpose
      and still the freshest version of that story).
- [ ] Each piece is 30–50 words.
- [ ] Every item in the brief has a matching entry in the Sources block
      (sources stay in `sources.md` / the sheet — never in the brief body).

## Friday workflow

1. The scraper (GitHub Actions, Friday ~08:00 IST) writes
   `roundups/<week>/briefing-material.md` and fills the sheet's "Briefing"
   tab with ranked stories per section.
2. In a chat session, read the material file, pick the best stories, and
   produce TWO outputs:
   a. **The briefing** in WhatsApp format (asterisks + underscores, no
      inline links) — goes in the sheet's "Final Briefing" column and is
      what the team shares.
   b. **The sources block** — one bullet per item with publisher name,
      date, and link — goes in the separate "Sources" column for
      internal traceability. Format example:
      ```
      • 100% FDI — BusinessToday, 2 May 2026
        https://www.businesstoday.in/.../528574-2026-05-02
      • LIC stake sale — Business Standard, 27 May 2026
        https://www.business-standard.com/markets/news/...
      ```
3. Save both to `roundups/<week>/briefing.md` and
   `roundups/<week>/sources.md` for the git record, and paste each into
   its column in the sheet.
