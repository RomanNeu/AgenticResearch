# fetch_prices.py
"""
Fetches 10 years of daily EOD closing prices for every active ticker
in stock_universe and upserts into the stock_prices table.
After loading, refreshes all materialized views:
  - stock_technicals
  - sector_volatility_matrix
  - industry_volatility_matrix
  - stock_daily_valuation

Re-run behaviour:
  - Tickers with price up to last business day → skips full fetch but
    always refreshes the most recent price row (FMP may update it)
  - Tickers missing recent prices → full re-fetch and upsert
  - New tickers added to the universe → full 10-year backfill
"""
import os
import time
import logging
import requests
import zoneinfo
from datetime import datetime, date, timedelta
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

# use Zurich local time so "today" matches your calendar
LOCAL_TZ    = zoneinfo.ZoneInfo("Europe/Zurich")
_now        = datetime.now(LOCAL_TZ).date()
CUTOFF_DATE = date(_now.year - 10, _now.month, _now.day).isoformat()


def last_business_day() -> date:
    """
    Returns the most recent completed trading day in Zurich local time.
    Tuesday → Monday
    Monday  → Friday
    Sunday  → Friday
    """
    d = _now - timedelta(days=1)
    while d.weekday() >= 5:  # skip Saturday (5) and Sunday (6)
        d -= timedelta(days=1)
    return d


def fetch_prices(symbol: str) -> list[dict]:
    resp = requests.get(
        f"{FMP_BASE}/historical-price-eod/light",
        params={"symbol": symbol, "apikey": FMP_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def build_rows(stock_id: str, ticker: str, items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        item_date = item.get("date", "")[:10]
        if not item_date or item_date < CUTOFF_DATE:
            continue  # skip data older than 10 years
        rows.append({
            "stock_id": stock_id,
            "ticker":   ticker,
            "date":     item_date,
            "price":    item.get("price"),
            "volume":   item.get("volume"),
        })
    return rows


def upsert_latest_price(stock_id: str, ticker: str, symbol: str):
    """
    Always re-fetch and upsert the most recent available price.
    FMP sometimes publishes a preliminary price and updates it later —
    this ensures we always have the finalized closing price.
    """
    try:
        resp = requests.get(
            f"{FMP_BASE}/historical-price-eod/light",
            params={"symbol": symbol, "apikey": FMP_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return
        # take only the most recent row
        latest    = data[0]
        item_date = latest.get("date", "")[:10]
        if not item_date:
            return
        supabase.table("stock_prices").upsert({
            "stock_id": stock_id,
            "ticker":   ticker,
            "date":     item_date,
            "price":    latest.get("price"),
            "volume":   latest.get("volume"),
        }, on_conflict="stock_id,date").execute()
        log.info(f"  ↻ latest price refreshed: {item_date} @ {latest.get('price')}")
    except Exception as e:
        log.warning(f"  Latest price refresh failed for {symbol}: {e}")


def should_skip(stock_id: str) -> tuple[bool, str]:
    """Skip full fetch if latest stored price matches the last business day."""
    result = (
        supabase.table("stock_prices")
        .select("date")
        .eq("stock_id", stock_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )

    if not result:
        return False, "no data yet — full backfill needed"

    latest_stored = date.fromisoformat(result[0]["date"])
    last_biz_day  = last_business_day()
    days_behind   = (last_biz_day - latest_stored).days

    if days_behind <= 0:
        return True, f"up to date (latest: {latest_stored})"

    return False, f"stale — latest: {latest_stored}, {days_behind} trading days behind"


def refresh_materialized_views(any_updates: bool):
    """Refresh all materialized views that depend on stock_prices."""
    if not any_updates:
        log.info("No new prices loaded — skipping materialized view refresh")
        return

    for view, label in [
        ("sector_volatility_matrix",   "sector volatility matrix"),
        ("industry_volatility_matrix", "industry volatility matrix"),
        ("stock_daily_valuation",      "stock daily valuation"),
    ]:
        try:
            log.info(f"Refreshing {label}...")
            supabase.rpc("refresh_view_with_timeout", {"view_name": view}).execute()
            log.info(f"  ✓ {label} refreshed")
        except Exception as e:
            log.error(f"  Failed to refresh {label}: {e}")

    # stock_technicals via direct psycopg2 connection (extended timeout)
    refresh_technicals_direct()


def refresh_technicals_direct():
    """Refresh stock_technicals via RPC."""
    try:
        log.info("Refreshing stock_technicals...")
        supabase.rpc("refresh_view_with_timeout", {"view_name": "stock_technicals"}).execute()
        log.info("  ✓ stock_technicals refreshed")
    except Exception as e:
        log.error(f"  Failed to refresh stock_technicals: {e}")


def main():
    stocks = (
        supabase.table("stock_universe")
        .select("id, ticker, fmp_symbol")
        .eq("active", True)
        .execute()
        .data
    )

    last_biz = last_business_day()
    log.info(f"Fetching prices for {len(stocks)} active tickers")
    log.info(f"Cutoff: {CUTOFF_DATE} | Last business day: {last_biz} | Today (Zurich): {_now}")

    success, skipped, failed = 0, 0, 0

    for i, stock in enumerate(stocks):
        ticker   = stock["ticker"]
        symbol   = stock["fmp_symbol"] or ticker
        stock_id = stock["id"]

        log.info(f"[{i+1}/{len(stocks)}] {symbol}...")

        skip, reason = should_skip(stock_id)

        if skip:
            log.info(f"  ↷ {reason}")
            # always refresh latest price even if up to date
            # FMP may have updated the finalized closing price
            upsert_latest_price(stock_id, ticker, symbol)
            skipped += 1
            time.sleep(0.25)
            continue

        log.info(f"  → {reason}")

        try:
            items = fetch_prices(symbol)
            rows  = build_rows(stock_id, ticker, items)

            if not rows:
                log.warning(f"  No price data found for {symbol}")
                skipped += 1
            else:
                # upsert in batches of 500 to avoid request size limits
                batch_size = 500
                for batch_start in range(0, len(rows), batch_size):
                    batch = rows[batch_start:batch_start + batch_size]
                    supabase.table("stock_prices").upsert(
                        batch, on_conflict="stock_id,date"
                    ).execute()

                log.info(f"  ✓ {len(rows)} rows upserted")
                success += 1

        except Exception as e:
            log.error(f"  Failed for {ticker}: {e}")
            failed += 1

        time.sleep(0.25)

    log.info(f"\nDone — {success} tickers loaded, {skipped} skipped, {failed} failed")

    # refresh all materialized views after price updates
    refresh_materialized_views(any_updates=success > 0)


if __name__ == "__main__":
    main()