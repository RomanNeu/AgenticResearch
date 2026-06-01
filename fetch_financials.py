# fetch_financials.py
"""
Fetches 10 years of quarterly financial ratios for every active ticker
in stock_universe and upserts into stock_financials.

Note: Financial ratios are quarterly data — not daily.
      The most granular available from FMP is per reporting period.

Endpoints used:
  - /stable/ratios?symbol=AAPL&period=quarter       → margins, valuation, leverage, liquidity
  - /stable/key-metrics?symbol=AAPL&period=quarter  → ROA, ROE
  - /stable/shares-float?symbol=AAPL               → shares outstanding (per ticker)

Re-run behaviour:
  - Tickers with >= 36 quarters and no missing ROA → skipped
  - Otherwise re-fetched and upserted
"""
import os
import time
import logging
import requests
from datetime import datetime, date, UTC
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FMP_API_KEY  = os.environ["FMP_API_KEY"]
FMP_BASE     = "https://financialmodelingprep.com/stable"

supabase     = create_client(SUPABASE_URL, SUPABASE_KEY)

_now         = datetime.now(UTC).date()
CUTOFF_DATE  = date(_now.year - 10, _now.month, _now.day).isoformat()


def fetch_ratios(symbol: str) -> list[dict]:
    resp = requests.get(
        f"{FMP_BASE}/ratios",
        params={"symbol": symbol, "period": "quarter", "apikey": FMP_API_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def fetch_key_metrics(symbol: str) -> list[dict]:
    """Fetches ROA, ROE — not in the ratios endpoint."""
    resp = requests.get(
        f"{FMP_BASE}/key-metrics",
        params={"symbol": symbol, "period": "quarter", "apikey": FMP_API_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def fetch_shares(symbol: str) -> int | None:
    """Fetch current shares outstanding for a single symbol."""
    try:
        resp = requests.get(
            f"{FMP_BASE}/shares-float",
            params={"symbol": symbol, "apikey": FMP_API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("outstandingShares")
        return None
    except Exception as e:
        log.warning(f"  Shares fetch failed for {symbol}: {e}")
        return None


def build_rows(stock_id: str, ticker: str, symbol: str,
               ratios: list[dict], metrics: list[dict],
               shares: int | None) -> list[dict]:

    metrics_by_date = {m.get("date", "")[:10]: m for m in metrics}

    rows = []
    for r in ratios:
        item_date = r.get("date", "")[:10]
        if not item_date or item_date < CUTOFF_DATE:
            continue

        m = metrics_by_date.get(item_date, {})

        rows.append({
            "stock_id":            stock_id,
            "ticker":              ticker,
            "date":                item_date,
            "period":              r.get("period"),

            # margins
            "gross_profit_margin": r.get("grossProfitMargin"),
            "operating_margin":    r.get("operatingProfitMargin"),
            "net_profit_margin":   r.get("netProfitMargin"),
            "ebitda_margin":       r.get("ebitdaMargin"),

            # valuation
            "pe_ratio":            r.get("priceToEarningsRatio"),
            "peg_ratio":           r.get("priceToEarningsGrowthRatio"),
            "forward_peg_ratio":   r.get("forwardPriceToEarningsGrowthRatio"),
            "price_to_book":       r.get("priceToBookRatio"),
            # divide by 4 to annualise quarterly revenue → TTM P/S
            "price_to_sales":      r.get("priceToSalesRatio") / 4 if r.get("priceToSalesRatio") else None,
            "price_to_fcf":        r.get("priceToFreeCashFlowRatio") / 4 if r.get("priceToFreeCashFlowRatio") else None,

            # leverage
            "debt_to_equity":      r.get("debtToEquityRatio"),
            "debt_to_assets":      r.get("debtToAssetsRatio"),

            # returns
            "roa":                 m.get("returnOnAssets"),
            "roe":                 m.get("returnOnEquity"),

            # income
            "dividend_yield":      r.get("dividendYield"),

            # liquidity
            "current_ratio":       r.get("currentRatio"),
            "quick_ratio":         r.get("quickRatio"),

            # shares outstanding — current value applied to all quarters
            "shares_outstanding":  shares,

            "fetched_at":          datetime.now(UTC).isoformat(),
        })
    return rows

def should_skip(stock_id: str) -> tuple[bool, str]:
    """Skip if fully loaded with no missing ROA values."""
    total = (
        supabase.table("stock_financials")
        .select("id", count="exact")
        .eq("stock_id", stock_id)
        .execute()
        .count
    )


    if total < 36:
        return False, f"{total} rows — needs backfill"

    missing = (
        supabase.table("stock_financials")
        .select("id", count="exact")
        .eq("stock_id", stock_id)
        .is_("roa", "null")
        .execute()
        .count
    )

    if missing > 0:
        return False, f"{total} rows, {missing} missing roa"

    return True, f"{total} rows, fully loaded"


def main():
    stocks = (
        supabase.table("stock_universe")
        .select("id, ticker, fmp_symbol")
        .eq("active", True)
        .execute()
        .data
    )
    log.info(f"Fetching financials for {len(stocks)} active tickers (cutoff: {CUTOFF_DATE})...")

    success, skipped, failed = 0, 0, 0

    for i, stock in enumerate(stocks):
        ticker   = stock["ticker"]
        symbol   = stock["fmp_symbol"] or ticker
        stock_id = stock["id"]

        log.info(f"[{i+1}/{len(stocks)}] {symbol}...")

        skip, reason = should_skip(stock_id)
        if skip:
            log.info(f"  ↷ {reason} — skipping")
            skipped += 1
            continue

        log.info(f"  → {reason}")

        try:
            ratios  = fetch_ratios(symbol)
            time.sleep(0.25)
            metrics = fetch_key_metrics(symbol)
            time.sleep(0.25)
            shares  = fetch_shares(symbol)
            rows    = build_rows(stock_id, ticker, symbol, ratios, metrics, shares)

            if not rows:
                log.warning(f"  No financial data found for {symbol}")
                skipped += 1
            else:
                supabase.table("stock_financials").upsert(
                    rows, on_conflict="stock_id,date"
                ).execute()
                shares_str = f"{shares:,}" if shares else "N/A"
                log.info(f"  ✓ {len(rows)} quarters upserted (shares: {shares_str})")
                success += 1

        except Exception as e:
            log.error(f"  Failed for {ticker}: {e}")
            failed += 1

        time.sleep(0.25)

    log.info(f"\nDone — {success} tickers loaded, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()