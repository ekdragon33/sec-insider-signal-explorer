# Insider Activity Signal Explorer

Pulls a public company's full SEC filing history, separates insider transaction
filings (Form 4) from major disclosure events (10-K, 10-Q, 8-K), parses the
actual buy/sell transactions out of each Form 4, and flags insiders whose
trading clusters unusually close to major filings.

## Scope

This is a screening tool, not an accusation engine. It surfaces *where* insider
trading activity clusters relative to a company's disclosure calendar, so a
person can decide what's worth a closer look. It doesn't determine whether any
specific trade was improper.

## How it works

1. `resolve_cik()` — looks up a company's SEC identifier from its ticker
2. `fetch_filing_index()` — pulls the full filing history from EDGAR's
   submissions API and splits it into insider filings vs. major disclosures
3. `parse_form4()` — Form 4s are individual XML documents, not structured
   data in the index, so each one is fetched and parsed individually for the
   actual transaction detail (who, what type, how many shares, at what price)
4. `build_signal()` — joins each parsed transaction against the company's
   major filing calendar and computes days-to-next-filing
5. `summarize()` — ranks insiders by how often their trades cluster right
   before a major disclosure

## Running it

SEC EDGAR requires a real contact identifier in the request header or it
blocks you, so set this first:

```bash
export SEC_USER_AGENT="Your Name your_email@example.com"
pip install requests pandas matplotlib
python insider_signal.py --ticker AAPL
```

Outputs:
- `insider_transactions.csv` — every parsed Form 4 transaction
- `major_filings.csv` — the company's 10-K/10-Q/8-K calendar
- `insider_signal_summary.csv` — ranked signal table
- `insider_activity_timeline.png` — scatter of transactions over time (green=buy, red=sell)

## Limitations

Clustering alone isn't proof of anything improper. Insiders trade on
pre-scheduled plans (Rule 10b5-1) constantly, and this script doesn't
distinguish those from discretionary trades. A real investigation would need
to cross-reference 10b5-1 plan disclosures, look at a larger historical
sample to establish a baseline clustering rate, and compare against peer
companies before drawing any conclusion.
