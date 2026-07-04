"""
Insider Activity Signal Explorer
----------------------------------
Pulls a company's full filing history from SEC EDGAR, separates insider
transaction filings (Form 4) from major disclosure filings (10-K, 10-Q, 8-K),
parses the actual buy/sell transactions out of each Form 4, and flags
insider activity that clusters unusually close to major filing events.

Two disconnected pieces of SEC data (the filings index and the individual
Form 4 transaction documents) joined into one signal.

Usage:
    python insider_signal.py --ticker AAPL
    python insider_signal.py --cik 0000320193 --lookback-days 10

Requires: requests, pandas, matplotlib
    pip install requests pandas matplotlib

IMPORTANT: SEC EDGAR requires a descriptive User-Agent with a real contact
email, or it will block requests. Set this before running:
    export SEC_USER_AGENT="Your Name your_email@example.com"
"""

import argparse
import os
import time
import re
import requests
import pandas as pd
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
TICKER_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik_short}/{accession_nodash}/{doc}"

MAJOR_FORMS = {"10-K", "10-Q", "8-K"}
INSIDER_FORMS = {"4", "4/A"}


def get_headers():
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise SystemExit(
            "Set SEC_USER_AGENT env var first, e.g.\n"
            '  export SEC_USER_AGENT="Your Name your_email@example.com"\n'
            "SEC EDGAR blocks requests without a real contact identifier."
        )
    return {"User-Agent": ua}


def resolve_cik(ticker):
    """Look up a 10-digit zero-padded CIK from a ticker symbol."""
    resp = requests.get(TICKER_LOOKUP_URL, headers=get_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    for entry in data.values():
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker {ticker} not found in SEC ticker lookup")


def fetch_filing_index(cik):
    """Get the full recent filing history for a company."""
    url = SUBMISSIONS_URL.format(cik=cik)
    resp = requests.get(url, headers=get_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    recent = data["filings"]["recent"]
    df = pd.DataFrame({
        "form": recent["form"],
        "filingDate": recent["filingDate"],
        "accessionNumber": recent["accessionNumber"],
        "primaryDocument": recent["primaryDocument"],
    })
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    return df, data.get("name", "")


_debug_shown = {"count": 0}


def parse_form4(cik_short, accession, primary_doc):
    """Fetch and parse a single Form 4 XML for its transactions."""
    if not primary_doc:
        if _debug_shown["count"] < 3:
            print(f"  [DEBUG] empty primaryDocument for accession {accession}, skipping")
            _debug_shown["count"] += 1
        return []
    # primaryDocument sometimes points at the XSL-rendered human-readable view
    # (e.g. "xslF345X06/wk-form4_123.xml"), which returns HTML, not raw XML.
    # The actual data file sits directly in the accession folder, so strip any
    # subfolder and keep just the filename.
    doc_filename = primary_doc.split("/")[-1]
    accession_nodash = accession.replace("-", "")
    url = ARCHIVE_BASE.format(cik_short=cik_short, accession_nodash=accession_nodash, doc=doc_filename)
    resp = requests.get(url, headers=get_headers(), timeout=30)
    if resp.status_code != 200:
        if _debug_shown["count"] < 3:
            print(f"  [DEBUG] fetch failed ({resp.status_code}) for {url}")
            _debug_shown["count"] += 1
        return []
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        if _debug_shown["count"] < 3:
            print(f"  [DEBUG] parse failed for {url}")
            print(f"  [DEBUG] error: {e}")
            print(f"  [DEBUG] first 300 chars of response: {resp.text[:300]}")
            _debug_shown["count"] += 1
        return []

    owner_name = ""
    owner_el = root.find(".//reportingOwner/reportingOwnerId/rptOwnerName")
    if owner_el is not None:
        owner_name = owner_el.text

    transactions = []
    for txn in root.findall(".//nonDerivativeTable/nonDerivativeTransaction"):
        date_el = txn.find(".//transactionDate/value")
        code_el = txn.find(".//transactionCoding/transactionCode")
        shares_el = txn.find(".//transactionAmounts/transactionShares/value")
        price_el = txn.find(".//transactionAmounts/transactionPricePerShare/value")
        transactions.append({
            "owner": owner_name,
            "transaction_date": date_el.text if date_el is not None else None,
            "code": code_el.text if code_el is not None else None,  # P=purchase, S=sale
            "shares": float(shares_el.text) if shares_el is not None else None,
            "price": float(price_el.text) if price_el is not None else None,
        })
    return transactions


def build_signal(cik, lookback_days=10, max_form4=100):
    cik_short = str(int(cik))  # strip leading zeros for archive URLs
    filings, company_name = fetch_filing_index(cik)
    print(f"Company: {company_name}")
    print(f"Total filings retrieved: {len(filings)}")

    major = filings[filings["form"].isin(MAJOR_FORMS)].sort_values("filingDate")
    insider = filings[filings["form"].isin(INSIDER_FORMS)].sort_values("filingDate", ascending=False).head(max_form4)
    print(f"Major disclosure filings (10-K/10-Q/8-K): {len(major)}")
    print(f"Form 4 filings to parse (most recent {max_form4}): {len(insider)}")

    all_txns = []
    for _, row in insider.iterrows():
        txns = parse_form4(cik_short, row["accessionNumber"], row["primaryDocument"])
        for t in txns:
            t["filingDate"] = row["filingDate"]
        all_txns.extend(txns)
        time.sleep(0.15)  # SEC rate limit courtesy

    txn_df = pd.DataFrame(all_txns)
    if txn_df.empty:
        print("No parsed transactions found.")
        return txn_df, major

    txn_df["transaction_date"] = pd.to_datetime(txn_df["transaction_date"], errors="coerce")

    # For each transaction, find days to the nearest subsequent major filing
    major_dates = major["filingDate"].sort_values().tolist()

    def days_to_next_major(txn_date):
        future = [d for d in major_dates if d >= txn_date]
        if not future:
            return None
        return (min(future) - txn_date).days

    txn_df["days_to_next_major_filing"] = txn_df["transaction_date"].apply(
        lambda d: days_to_next_major(d) if pd.notna(d) else None
    )
    txn_df["flagged_pre_filing_cluster"] = txn_df["days_to_next_major_filing"] <= lookback_days

    return txn_df, major


def summarize(txn_df):
    if txn_df.empty:
        return None
    code_map = {"P": "Purchase", "S": "Sale", "A": "Grant/Award", "G": "Gift"}
    txn_df["transaction_type"] = txn_df["code"].map(code_map).fillna(txn_df["code"])

    summary = (
        txn_df.groupby(["owner", "transaction_type"])
        .agg(
            transactions=("shares", "count"),
            total_shares=("shares", "sum"),
            flagged_count=("flagged_pre_filing_cluster", "sum"),
        )
        .reset_index()
        .sort_values("flagged_count", ascending=False)
    )
    return summary


def plot_transactions(txn_df, company_name, outpath="insider_activity_timeline.png"):
    if txn_df.empty or txn_df["transaction_date"].isna().all():
        print("Not enough dated transactions to plot.")
        return
    plotted = txn_df.dropna(subset=["transaction_date", "shares"]).copy()
    colors = plotted["code"].map({"P": "green", "S": "red"}).fillna("gray")
    plt.figure(figsize=(10, 5))
    plt.scatter(plotted["transaction_date"], plotted["shares"], c=colors, alpha=0.7)
    plt.title(f"Insider Transactions Over Time: {company_name}")
    plt.xlabel("Date")
    plt.ylabel("Shares")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    print(f"Saved chart to {outpath} (green=purchase, red=sale)")


def main():
    parser = argparse.ArgumentParser(description="SEC Insider Activity Signal Explorer")
    parser.add_argument("--ticker", default=None, help="Stock ticker, e.g. AAPL")
    parser.add_argument("--cik", default=None, help="10-digit zero-padded CIK (alternative to ticker)")
    parser.add_argument("--lookback-days", type=int, default=10,
                         help="Flag insider transactions within N days before a major filing")
    parser.add_argument("--max-form4", type=int, default=100,
                         help="Max number of recent Form 4 filings to parse")
    args = parser.parse_args()

    if not args.ticker and not args.cik:
        raise SystemExit("Provide --ticker or --cik")

    cik = args.cik or resolve_cik(args.ticker)
    txn_df, major = build_signal(cik, lookback_days=args.lookback_days, max_form4=args.max_form4)

    if txn_df.empty:
        return

    txn_df.to_csv("insider_transactions.csv", index=False)
    major.to_csv("major_filings.csv", index=False)

    summary = summarize(txn_df)
    if summary is not None:
        summary.to_csv("insider_signal_summary.csv", index=False)
        print("\nInsiders ranked by transactions clustered near major filings:")
        print(summary.head(15).to_string(index=False))

    company_name = args.ticker or cik
    plot_transactions(txn_df, company_name)


if __name__ == "__main__":
    main()
