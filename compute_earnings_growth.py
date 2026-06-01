# compute_earnings_growth.py
"""
Computes YoY EPS and Revenue growth % for every row in the earnings table
where eps_actual is not null, and writes it back to the same row.
Looks for the closest quarter 9-15 months prior (handles non-calendar fiscal years).
Re-run safe — upserts on (stock_id, date).
"""
import os
import logging
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def compute_growth(current, prior, field):
    c = current.get(field)
    p = prior.get(field)
    if c is None or p is None or float(p) == 0:
        return None
    return round((float(c) - float(p)) / abs(float(p)) * 100, 4)


def main():
    # fetch all completed earnings rows grouped by ticker
    log.info("Fetching all earnings with actuals...")
    rows = (
        supabase.table("earnings")
        .select("id, stock_id, ticker, date, eps_actual, revenue_actual")
        .not_.is_("eps_actual", "null")
        .order("stock_id")
        .order("date")
        .execute()
        .data
    )
    log.info(f"Loaded {len(rows)} rows")

    # group by stock_id for fast prior-quarter lookup
    from collections import defaultdict
    by_stock = defaultdict(list)
    for r in rows:
        by_stock[r["stock_id"]].append(r)

    updates = []
    skipped = 0

    for stock_id, stock_rows in by_stock.items():
        # index by date string for fast lookup
        by_date = {r["date"][:10]: r for r in stock_rows}
        dates   = sorted(by_date.keys())

        for current in stock_rows:
            cur_date = current["date"][:10]

            # find closest row 9-15 months prior
            from datetime import date, timedelta
            d      = date.fromisoformat(cur_date)
            prior  = None
            for offset in range(270, 451, 15):  # 9-15 months in 15-day steps
                candidate = (d - timedelta(days=offset)).isoformat()
                # find closest available date within ±15 days of candidate
                for pd in dates:
                    if abs((date.fromisoformat(pd) - date.fromisoformat(candidate)).days) <= 15:
                        if pd != cur_date:
                            prior = by_date[pd]
                            break
                if prior:
                    break

            if not prior:
                skipped += 1
                continue

            eps_g = compute_growth(current, prior, "eps_actual")
            rev_g = compute_growth(current, prior, "revenue_actual")

            # only update if growth values changed or are missing
            if eps_g is not None or rev_g is not None:
                updates.append({
                    "id":            current["id"],
                    "stock_id":      stock_id,
                    "ticker":        current["ticker"],
                    "date":          cur_date,
                    "eps_growth_pct": eps_g,
                    "rev_growth_pct": rev_g,
                })

    log.info(f"Computed growth for {len(updates)} rows, skipped {skipped} (no prior quarter)")

    # upsert in batches of 500
    batch_size = 500
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        supabase.table("earnings").upsert(
            batch, on_conflict="stock_id,date"
        ).execute()
        log.info(f"  Upserted batch {i//batch_size + 1} ({len(batch)} rows)")

    log.info("Done")


if __name__ == "__main__":
    main()