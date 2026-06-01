"""
daily_mover_explain.py
──────────────────────
Daily job — run once after market close (e.g. 18:00 via cron / APScheduler).

For every active stock that moved ±4 % or more on the target date:
  1. Ask gpt-4o-mini to search the internet for news on that specific date
     and explain the move in ≤ 3 sentences, zero speculation.
  2. Return a confidence score (0–100) and the sources the model found.
  3. Upsert the result into the `price_move_explanations` table.

Table DDL (run once in Supabase SQL editor):
─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_move_explanations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stock_id    UUID NOT NULL REFERENCES stock_universe(id),
    ticker      TEXT NOT NULL,
    trade_date  DATE NOT NULL,
    price       NUMERIC,
    prev_price  NUMERIC,
    change_pct  NUMERIC,
    explanation TEXT,
    confidence  INTEGER,          -- 0-100
    news_sources    JSONB,            -- [{title, url}] returned by web search
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (stock_id, trade_date)
);
─────────────────────────────────────────────

Usage:
    python daily_mover_explain.py              # yesterday by default
    python daily_mover_explain.py 2026-05-28   # specific past date
"""

import os
import sys
import json
import logging
from datetime import date, timedelta
from collections import defaultdict

import requests
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── clients ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
MODEL        = "gpt-5.4-mini"
THRESHOLD    = 4.0

_supa   = create_client(SUPABASE_URL, SUPABASE_KEY)
_openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


# ── Supabase helper ───────────────────────────────────────────────────────────

def sb_get(path: str, params) -> list:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── fetch movers from Supabase ────────────────────────────────────────────────

def fetch_movers(trade_date: date) -> list:
    cutoff = (trade_date - timedelta(days=7)).isoformat()
    until  = trade_date.isoformat()

    universe = sb_get("stock_universe", {
        "select": "id,ticker,name",
        "active": "eq.true",
    })
    if not universe:
        return []

    id_to_stock = {r["id"]: r for r in universe}
    ids_param   = "(" + ",".join(str(i) for i in id_to_stock) + ")"

    prices_raw = requests.get(
        f"{SUPABASE_URL}/rest/v1/stock_prices",
        headers={
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
        params=[
            ("select",   "stock_id,date,price"),
            ("stock_id", f"in.{ids_param}"),
            ("date",     f"gte.{cutoff}"),
            ("date",     f"lte.{until}"),
            ("order",    "stock_id.asc,date.desc"),
            ("limit",    "50000"),
        ],
        timeout=30,
    ).json()

    by_stock: dict = defaultdict(list)
    for row in prices_raw:
        by_stock[row["stock_id"]].append(row)

    movers = []
    for sid, rows in by_stock.items():
        target = next((r for r in rows if r["date"][:10] == until), None)
        if not target:
            continue
        prev = next((r for r in rows if r["date"][:10] < until), None)
        if not prev:
            continue
        p1  = float(target["price"])
        p0  = float(prev["price"])
        if p0 <= 0:
            continue
        chg = (p1 - p0) / p0 * 100
        if abs(chg) < THRESHOLD:
            continue
        stk = id_to_stock.get(sid, {})
        movers.append({
            "stock_id":   sid,
            "ticker":     stk.get("ticker", "?"),
            "name":       stk.get("name", "") or "",
            "trade_date": until,
            "price":      round(p1, 4),
            "prev_price": round(p0, 4),
            "change_pct": round(chg, 2),
        })

    movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    log.info(f"Found {len(movers)} movers on {until} (threshold ±{THRESHOLD}%)")
    return movers


# ── explain via OpenAI web search ─────────────────────────────────────────────

def explain_move(ticker: str, name: str, trade_date: str, change_pct: float) -> dict:
    """
    Use gpt-5.4-mini via the Responses API with web_search_preview
    to find real news and explain the price move.
    Returns {"explanation": str, "confidence": int, "sources": list[{title,url}]}.
    """
    sign      = "+" if change_pct > 0 else ""
    direction = "rose" if change_pct > 0 else "fell"

    prompt = (
        f"On {trade_date}, the stock {ticker} ({name}) {direction} {sign}{change_pct:.2f}%. "
        f"Search the internet for news published on or around {trade_date} that explains this move. "
        f"Base your answer ONLY on news you find. Do NOT speculate. "
        f"If no relevant news is found, state that explicitly.\n\n"
        f"Respond with a JSON object with exactly two keys:\n"
        f'  "explanation": string, max 3 sentences, strictly factual.\n'
        f'  "confidence": integer 0-100 (0=no relevant news, 100=move fully explained by news).\n'
        f"No markdown, no preamble — only the JSON object."
    )

    sources = []
    explanation_raw = ""

    try:
        resp = _openai.responses.create(
            model=MODEL,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )

        # responses API returns output blocks
        for block in resp.output:
            if getattr(block, "type", "") == "message":
                for part in getattr(block, "content", []):
                    if hasattr(part, "text"):
                        explanation_raw += part.text
                    for ann in getattr(part, "annotations", []) or []:
                        if hasattr(ann, "url"):
                            sources.append({
                                "title": getattr(ann, "title", ""),
                                "url":   ann.url,
                            })

        clean  = explanation_raw.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        return {
            "explanation": str(parsed.get("explanation", "")).strip(),
            "confidence":  max(0, min(100, int(parsed.get("confidence", 0)))),
            "sources":     sources,
        }

    except json.JSONDecodeError:
        log.warning(f"  {ticker}: non-JSON response, saving raw")
        return {
            "explanation": explanation_raw[:1000],
            "confidence":  50,
            "sources":     sources,
        }
    except Exception as exc:
        log.warning(f"  {ticker}: LLM call failed — {exc}")
        return {
            "explanation": f"LLM call failed: {exc}",
            "confidence":  0,
            "sources":     [],
        }


# ── persist to Supabase ───────────────────────────────────────────────────────

def upsert_explanation(mover: dict, result: dict):
    _supa.table("price_move_explanations").upsert(
        {
            "stock_id":    mover["stock_id"],
            "ticker":      mover["ticker"],
            "trade_date":  mover["trade_date"],
            "price":       mover["price"],
            "prev_price":  mover["prev_price"],
            "change_pct":  mover["change_pct"],
            "explanation": result["explanation"],
            "confidence":  result["confidence"],
            "news_sources": json.dumps(result["sources"]),
        },
        on_conflict="stock_id,trade_date",
    ).execute()


# ── main ──────────────────────────────────────────────────────────────────────

def run(trade_date: date):
    log.info(f"═══ daily_mover_explain  date={trade_date} ═══")

    movers = fetch_movers(trade_date)
    if not movers:
        log.info("No movers found — nothing to do.")
        return

    for i, m in enumerate(movers, 1):
        ticker = m["ticker"]
        log.info(f"[{i}/{len(movers)}]  {ticker:8s}  {m['change_pct']:+.2f}%")

        result = explain_move(ticker, m["name"], m["trade_date"], m["change_pct"])

        log.info(f"  confidence={result['confidence']}  sources={len(result['sources'])}")
        log.info(f"  {result['explanation'][:120]}…")

        upsert_explanation(m, result)
        log.info(f"  saved ✓")

    log.info(f"═══ done — {len(movers)} movers processed ═══")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = date.fromisoformat(sys.argv[1])
    else:
        target = date.today() - timedelta(days=1)

    run(target)
