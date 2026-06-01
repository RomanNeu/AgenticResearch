# fetch_transcripts.py
"""
Fetches earnings call transcripts for every active ticker in stock_universe.
- First run: fetches the latest available transcript.
- Subsequent runs: checks if the next quarter is available and fetches it if so.
- Preserves full history — old rows are never overwritten.
"""
import os
import time
import logging
import requests
from datetime import datetime, UTC
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL  = os.environ["SUPABASE_URL"]
SUPABASE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]
FMP_API_KEY   = os.environ["FMP_API_KEY"]
FMP_BASE      = "https://financialmodelingprep.com/stable"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_latest_transcript(ticker: str) -> dict | None:
    """
    Try the last 6 quarters working backwards from today until we get a hit.
    Used on first run when no transcript is stored yet.
    """
    now     = datetime.now(UTC)
    year    = now.year
    quarter = (now.month - 1) // 3 + 1

    for _ in range(6):
        try:
            resp = requests.get(
                f"{FMP_BASE}/earning-call-transcript",
                params={
                    "symbol":  ticker,
                    "year":    year,
                    "quarter": quarter,
                    "apikey":  FMP_API_KEY,
                },
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data and data[0].get("content"):
                    return data[0]
                if isinstance(data, dict) and data.get("content"):
                    return data
        except Exception as e:
            log.warning(f"  {ticker} Q{quarter} {year}: {e}")

        # step back one quarter
        quarter -= 1
        if quarter == 0:
            quarter = 4
            year -= 1

    return None


def get_specific_transcript(ticker: str, year: int, quarter: int) -> dict | None:
    """
    Fetch a specific quarter — returns None if not yet available.
    Used on subsequent runs to check if the next quarter has been published.
    """
    try:
        resp = requests.get(
            f"{FMP_BASE}/earning-call-transcript",
            params={
                "symbol":  ticker,
                "year":    year,
                "quarter": quarter,
                "apikey":  FMP_API_KEY,
            },
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data and data[0].get("content"):
                return data[0]
            if isinstance(data, dict) and data.get("content"):
                return data
    except Exception as e:
        log.warning(f"  {ticker} Q{quarter} {year}: {e}")
    return None


def upsert_transcript(stock_id: str, ticker: str, transcript: dict):
    raw_date      = transcript.get("date", "")
    earnings_date = raw_date[:10] if raw_date else None

    # stable endpoint returns "period": "Q3", v3 returns "quarter": 3
    raw_quarter = transcript.get("quarter") or transcript.get("period", "")
    if isinstance(raw_quarter, str):
        raw_quarter = int(raw_quarter.replace("Q", "").strip())

    raw_year = transcript.get("year")

    if not raw_quarter or not raw_year:
        raise ValueError(f"Missing quarter/year in response: {transcript.keys()}")

    row = {
        "stock_id":        stock_id,
        "ticker":          ticker,
        "year":            int(raw_year),
        "quarter":         int(raw_quarter),
        "earnings_date":   earnings_date,
        "transcript_text": transcript.get("content"),
        "metadata": {
            "title":  transcript.get("title"),
            "symbol": transcript.get("symbol"),
        },
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    supabase.table("earnings_transcripts").upsert(
        row, on_conflict="stock_id,year,quarter"
    ).execute()


def main():
    # load all active tickers from stock_universe
    stocks = (
        supabase.table("stock_universe")
        .select("id, ticker, fmp_symbol")
        .eq("active", True)
        .execute()
        .data
    )
    log.info(f"Processing transcripts for {len(stocks)} active tickers...")

    success, skipped, failed = 0, 0, 0

    for i, stock in enumerate(stocks):
        ticker   = stock["ticker"]
        symbol   = stock["fmp_symbol"] or ticker
        stock_id = stock["id"]

        log.info(f"[{i+1}/{len(stocks)}] {symbol}...")

        # find the most recently stored transcript for this stock
        latest_stored = (
            supabase.table("earnings_transcripts")
            .select("year, quarter")
            .eq("stock_id", stock_id)
            .order("year", desc=True)
            .order("quarter", desc=True)
            .limit(1)
            .execute()
            .data
        )

        if latest_stored:
            last_y = latest_stored[0]["year"]
            last_q = latest_stored[0]["quarter"]

            # compute the next expected quarter
            next_q = last_q + 1
            next_y = last_y
            if next_q > 4:
                next_q = 1
                next_y += 1

            # try to fetch that specific next quarter
            transcript = get_specific_transcript(symbol, next_y, next_q)
            if not transcript:
                log.info(f"  ↷ no new quarter available yet (last: Q{last_q} {last_y})")
                skipped += 1
                continue
        else:
            # no transcript stored yet — fetch the latest available
            transcript = get_latest_transcript(symbol)

        if not transcript:
            log.warning(f"  No transcript found for {symbol}")
            skipped += 1
        else:
            try:
                upsert_transcript(stock_id, ticker, transcript)
                period = transcript.get("period") or f"Q{transcript.get('quarter')}"
                log.info(f"  ✓ {period} {transcript['year']}")
                success += 1
            except Exception as e:
                log.error(f"  Upsert failed for {ticker}: {e}")
                failed += 1

        time.sleep(0.25)

    log.info(f"\nDone — {success} new transcripts stored, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()