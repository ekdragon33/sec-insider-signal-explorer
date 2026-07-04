# Insider Activity Signal Explorer — Findings: Medtronic plc (MDT)

## What this is

A tool that joins two disconnected SEC data sources — individual insider
transaction filings (Form 4) and a company's major disclosure calendar
(10-K/10-Q/8-K) — to flag insiders whose trading clusters unusually close to
upcoming filings. Built as a public-data analog to internal regulatory
data-tracing work, applied outside healthcare on purpose.

## What it found (Medtronic, most recent 100 Form 4 filings)

| Insider | Activity | Total transactions | Flagged pre-filing |
|---|---|---|---|
| Smith Gregory L | Sales | 7 | 7 (100%) |
| KIIL HARRY SKIP | Sales | 9 | 7 (78%) |
| KIIL HARRY SKIP | Option exercises | 5 | 4 (80%) |

"Flagged pre-filing" means the transaction occurred within 10 days *before*
Medtronic's next major SEC disclosure went public — not after. That
directionality matters: trading shortly before a filing drops is the pattern
that actually draws regulatory attention, since it raises the question of
whether the trade was made with knowledge of what the filing would say.
Routine post-earnings trading (inside a company's normal trading window)
would show up as clustering *after* filings instead, which is not what this
shows for these two individuals.

## Why this is interesting, and why it isn't a conclusion

100% and 78% clustering rates are notable on their own. Major filings aren't
evenly spread through the year, so pure chance would predict some baseline
level of overlap, worth quantifying more rigorously with a larger sample and
a proper statistical baseline before calling it a real signal. What this
tool does is exactly what a first-pass screening tool is supposed to do:
narrow hundreds of transactions down to the handful worth a second look.

Legitimate explanations exist and should be ruled out before drawing any
conclusion: pre-scheduled 10b5-1 trading plans (set up months in advance,
can coincidentally land near filing dates), option expiration deadlines
forcing exercise timing, or year-end/quarter-end compensation cycles.
This tool doesn't distinguish those from discretionary trades, that would be
the natural next iteration.

## The technical story behind it

Building this required fetching and parsing ~100 individual XML documents,
not just reading a summary index. Midway through, the parser hit a real bug:
SEC's filing index pointed to the human-readable, browser-rendered version of
each Form 4 rather than the raw data file, so every document failed to parse
with a "mismatched tag" error. Diagnosed by adding visibility into what was
previously a silent failure, found the actual raw XML sitting one directory
level up from the rendered view, and fixed it with a one-line path change.
That's the kind of "the index lied about what the document actually is"
problem that shows up constantly in real systems work, not just APIs.

## Possible next steps if extending this

- Pull a larger sample (more than 100 Form 4s, multiple years) to establish
  a real statistical baseline for expected pre-filing clustering
- Cross-reference against 10b5-1 plan disclosures (also filed with SEC) to
  separate scheduled trades from discretionary ones
- Run across a basket of med device peers to see if Medtronic's pattern is
  unusual for the industry or a sector-wide norm
