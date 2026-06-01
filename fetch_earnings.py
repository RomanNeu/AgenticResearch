# fetch_earnings.py
"""
Fetches 10 years of quarterly earnings (EPS + revenue actual vs estimated)
for every active ticker in stock_universe and upserts into the earnings table.

Re-run behaviour:
  - Tickers fully loaded with no pending actuals → skipped (fast)
  - Tickers with upcoming quarters still awaiting actuals → re-fetched
  - New tickers added to the universe since last run → full backfill
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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 10-year cutoff — no relativedelta dependency needed
_now        = datetime.now(UTC)
CUTOFF_DATE = date(_now.year - 10, _now.month, _now.day).isoformat()


def fetch_earnings(symbol: str) -> list[dict]:
    resp = requests.get(
        f"{FMP_BASE}/earnings",
        params={"symbol": symbol, "apikey": FMP_API_KEY},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def compute_surprises(item: dict) -> dict:
    eps_a = item.get("epsActual")
    eps_e = item.get("epsEstimated")
    rev_a = item.get("revenueActual")
    rev_e = item.get("revenueEstimated")

    eps_surprise     = round(eps_a - eps_e, 4)                         if eps_a is not None and eps_e else None
    eps_surprise_pct = round((eps_surprise / abs(eps_e)) * 100, 4)     if eps_surprise is not None and eps_e else None
    rev_surprise     = int(rev_a - rev_e)                               if rev_a is not None and rev_e else None
    rev_surprise_pct = round((rev_surprise / rev_e) * 100, 4)          if rev_surprise is not None and rev_e else None

    return {
        "eps_surprise":     eps_surprise,
        "eps_surprise_pct": eps_surprise_pct,
        "rev_surprise":     rev_surprise,
        "rev_surprise_pct": rev_surprise_pct,
    }

def safe_bigint(val) -> int | None:
    """Convert revenue value to int, handling decimals and overflow."""
    if val is None:
        return None
    try:
        v = int(float(val))          # handles "8255777.78" → 8255777
        if abs(v) > 9_000_000_000_000:  # bigint max ~9.2T
            log.warning(f"    Revenue value {v} exceeds bigint range — skipping")
            return None
        return v
    except (ValueError, TypeError):
        return None

def compute_growth(current, prior, field):
    c = current.get(field)
    p = prior.get(field)
    if c is None or p is None or float(p) == 0:
        return None
    return round((float(c) - float(p)) / abs(float(p)) * 100, 4)

# growth is computed after all rows are built (needs prior quarter in same batch)
# so call this after building the full rows list:

def add_growth_to_rows(rows: list[dict]) -> list[dict]:
    by_date = {r["date"]: r for r in rows}
    dates   = sorted(by_date.keys())
    from datetime import date, timedelta
    for row in rows:
        d = date.fromisoformat(row["date"])
        prior = None
        for offset in range(270, 451, 15):
            candidate = (d - timedelta(days=offset)).isoformat()
            for pd in dates:
                if abs((date.fromisoformat(pd) - date.fromisoformat(candidate)).days) <= 15:
                    if pd != row["date"]:
                        prior = by_date[pd]
                        break
            if prior:
                break
        row["eps_growth_pct"] = compute_growth(row, prior, "eps_actual") if prior else None
        row["rev_growth_pct"] = compute_growth(row, prior, "revenue_actual") if prior else None
    return rows

def build_rows(stock_id: str, ticker: str, items: list[dict]) -> list[dict]:
    seen = set()
    rows = []
    for item in items:
        item_date = item.get("date", "")[:10]
        if not item_date or item_date < CUTOFF_DATE:
            continue
        key = (stock_id, item_date)
        if key in seen:
            log.warning(f"  Duplicate date {item_date} for {ticker} — skipping")
            continue
        seen.add(key)

        rev_a = safe_bigint(item.get("revenueActual"))
        rev_e = safe_bigint(item.get("revenueEstimated"))

        eps_a = item.get("epsActual")
        eps_e = item.get("epsEstimated")

        eps_surprise     = round(eps_a - eps_e, 4)                             if eps_a is not None and eps_e else None
        eps_surprise_pct = round((eps_a - eps_e) / abs(eps_e) * 100, 4)       if eps_a is not None and eps_e else None
        rev_surprise     = int(rev_a - rev_e)                                  if rev_a is not None and rev_e is not None else None
        rev_surprise_pct = round((rev_a - rev_e) / rev_e * 100, 4)            if rev_a is not None and rev_e else None

        rows.append({
            "stock_id":          stock_id,
            "ticker":            ticker,
            "date":              item_date,
            "eps_actual":        eps_a,
            "eps_estimated":     eps_e,
            "revenue_actual":    rev_a,
            "revenue_estimated": rev_e,
            "eps_surprise":      eps_surprise,
            "eps_surprise_pct":  eps_surprise_pct,
            "rev_surprise":      rev_surprise,
            "rev_surprise_pct":  rev_surprise_pct,
            "last_updated":      item.get("lastUpdated"),
        })
    rows = add_growth_to_rows(rows)
    return rows

def should_skip(stock_id: str) -> tuple[bool, str]:
    """
    Skip only if ticker is fully loaded AND has no rows with null eps_actual
    (i.e. no upcoming quarters waiting for actual results).
    """
    total = (
        supabase.table("earnings")
        .select("id", count="exact")
        .eq("stock_id", stock_id)
        .execute()
        .count
    )

    if total < 36:  # ~9 years of quarters — not fully loaded yet
        return False, f"{total} rows, needs backfill"

    pending = (
        supabase.table("earnings")
        .select("id", count="exact")
        .eq("stock_id", stock_id)
        .is_("eps_actual", "null")
        .execute()
        .count
    )

    if pending > 0:
        return False, f"{total} rows, {pending} pending actuals"

    return True, f"{total} rows, no pending actuals"


def main():
    stocks = (
        supabase.table("stock_universe")
        .select("id, ticker, fmp_symbol")
        .eq("active", True)
        .execute()
        .data
    )
    log.info(f"Fetching earnings for {len(stocks)} active tickers (cutoff: {CUTOFF_DATE})...")

    success, skipped, failed = 0, 0, 0
    failed_tickers = []   # ← add this

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
            items = fetch_earnings(symbol)
            rows  = build_rows(stock_id, ticker, items)

            if not rows:
                log.warning(f"  No earnings data found for {symbol}")
                skipped += 1
            else:
                supabase.table("earnings").upsert(
                    rows, on_conflict="stock_id,date"
                ).execute()
                log.info(f"  ✓ {len(rows)} quarters upserted")
                success += 1

        except Exception as e:
            log.error(f"  Failed for {ticker}: {e}")
            failed += 1
            failed_tickers.append({"ticker": ticker, "symbol": symbol, "error": str(e)})

        time.sleep(0.25)

    log.info(f"\nDone — {success} tickers loaded, {skipped} skipped, {failed} failed")

    # ── write failed tickers to file ──────────────────────────────────────────
    if failed_tickers:
        import json
        from datetime import datetime, UTC
        report = {
            "run_at":  datetime.now(UTC).isoformat(),
            "total":   len(stocks),
            "success": success,
            "skipped": skipped,
            "failed":  failed,
            "failed_tickers": failed_tickers,
        }
        with open("earnings_failed.json", "w") as f:
            json.dump(report, f, indent=2)
        log.info(f"Failed tickers written to earnings_failed.json")
        for ft in failed_tickers:
            log.info(f"  ✗ {ft['ticker']}: {ft['error'][:80]}")

if __name__ == "__main__":
    main()