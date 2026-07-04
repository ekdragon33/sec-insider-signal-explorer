# Insider Activity Signal Explorer

Pulls a public company's full SEC filing history, separates insider transaction
filings (Form 4) from major disclosure events (10-K, 10-Q, 8-K), parses the
actual buy/sell transactions out of each Form 4 (which requires fetching and
parsing individual XML documents, not just reading an index), and flags
insiders whose trading clusters unusually close to major filings.

## Why this instead of a healthcare project

Palantir's own public case studies (Tampa General's Sepsis Hub, etc.) already
cover real-time clinical monitoring built on EHR and device telemetry. Building
something in that same lane invites a direct, losing comparison since I don't
have hospital-scale data access. This proves the same underlying pattern,
disconnected data sources joined into a decision-relevant signal, in a domain
that has nothing to do with my MPH, which is arguably a better signal for a
role that explicitly rotates across industries (defense, manufacturing,
government, refugee aid, per the JD).

## How it works

1. `resolve_cik()` — looks up a company's SEC identifier from its ticker
2. `fetch_filing_index()` — pulls the full filing history from EDGAR's
   submissions API and splits it into insider filings vs. major disclosures
3. `parse_form4()` — Form 4s are individual XML documents, not structured
   data in the index, so each one has to be fetched and parsed for the actual
   transaction (who, what code [buy/sell/grant], how many shares, at what price)
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

## Talking about this in an interview

- **Found the problem**: SEC EDGAR gives you an index of filings but not the
  actual insider trading data, that's locked inside individual XML documents,
  so most people just read the headline filing list and stop there
- **Went and got the real data**: had to fetch and parse hundreds of
  individual XML documents to get transaction-level detail, not just counts
- **Joined two disconnected views**: insider trading behavior on one side,
  the company's disclosure calendar on the other, neither of which
  references the other natively
- **Built for reuse**: works for any public company by ticker, not a one-off
  analysis of a single stock

Same shape as the BSX CN-tracing story and the device signal explorer,
disconnected systems, real judgment about what's actually decision-relevant,
built as something reusable, just proving it in a domain outside healthcare.

## Notes on interpretation

Clustering alone isn't proof of anything improper, insiders trade on
pre-scheduled plans (10b5-1) constantly, and this script doesn't distinguish
those from discretionary trades. Worth saying explicitly in an interview that
you understand this is a screening signal, not a conclusion, that mirrors how
you'd talk about any regulatory or compliance flag in your reg affairs
background.
