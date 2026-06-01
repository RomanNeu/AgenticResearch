# stock_context_builder.py
"""
Builds a structured JSON context for a given ticker, ready for LLM consumption.
Includes all available data from the database with sector/industry comparisons.

Usage:
    python stock_context_builder.py MSFT
    python stock_context_builder.py AAPL --output aapl_context.json
    python stock_context_builder.py NVDA --pretty
"""
import os
import json
import argparse
import logging
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

def db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


# ── helpers ───────────────────────────────────────────────────────────────────

def safe_float(v, decimals=4):
    try: return round(float(v), decimals) if v is not None else None
    except: return None

def safe_int(v):
    try: return int(v) if v is not None else None
    except: return None

def pct(v):
    return safe_float(v, 2)

def ratio(v):
    return safe_float(v, 2)

def vs(ticker_val, compare_val):
    """Return delta and direction signal."""
    if ticker_val is None or compare_val is None:
        return None
    diff = round(ticker_val - compare_val, 4)
    return {"delta": diff, "signal": "above" if diff > 0 else "below" if diff < 0 else "inline"}


# ── fetchers ──────────────────────────────────────────────────────────────────

def get_stock_info(ticker):
    r = db().table("stock_universe").select("*").eq("ticker", ticker.upper()).limit(1).execute().data
    return r[0] if r else None

def get_latest_earnings(stock_id):
    r = db().table("earnings").select("*").eq("stock_id", stock_id)\
        .not_.is_("eps_actual", "null").order("date", desc=True).limit(8).execute().data
    return r or []

def get_latest_financials(stock_id):
    r = db().table("stock_financials").select("*").eq("stock_id", stock_id)\
        .not_.is_("net_profit_margin", "null").order("date", desc=True).limit(1).execute().data
    return r[0] if r else None

def get_transcript(stock_id):
    r = db().table("earnings_transcripts").select("*").eq("stock_id", stock_id)\
        .not_.is_("sentiment_score", "null")\
        .order("year", desc=True).order("quarter", desc=True).limit(1).execute().data
    return r[0] if r else None

def get_technicals(stock_id):
    r = db().table("stock_technicals").select("*").eq("stock_id", stock_id).limit(1).execute().data
    return r[0] if r else None

def get_daily_valuation(stock_id):
    r = db().table("stock_daily_valuation").select("*").eq("stock_id", stock_id)\
        .order("date", desc=True).limit(1).execute().data
    return r[0] if r else None

def get_sector_earnings(sector, year, quarter):
    r = db().table("sector_earnings_matrix").select("*").eq("sector", sector)\
        .eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_industry_earnings(industry, year, quarter):
    r = db().table("industry_earnings_matrix").select("*").eq("industry", industry)\
        .eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_sector_sentiment(sector, year, quarter):
    r = db().table("sector_sentiment_matrix").select("*").eq("sector", sector)\
        .eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_industry_sentiment(industry, year, quarter):
    r = db().table("industry_sentiment_matrix").select("*").eq("industry", industry)\
        .eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_sector_financials(sector, year, quarter):
    r = db().table("sector_financials_matrix").select("*").eq("sector", sector)\
        .eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_industry_financials(industry, year, quarter):
    r = db().table("industry_financials_matrix").select("*").eq("industry", industry)\
        .eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_sector_vol(sector):
    r = db().table("sector_volatility_matrix").select("*").eq("sector", sector).limit(1).execute().data
    return r[0] if r else None

def get_industry_vol(industry):
    r = db().table("industry_volatility_matrix").select("*").eq("industry", industry).limit(1).execute().data
    return r[0] if r else None

def get_sector_returns(sector):
    r = db().table("sector_returns").select("*").eq("sector", sector).limit(1).execute().data
    return r[0] if r else None

def get_industry_returns(industry):
    r = db().table("industry_returns").select("*").eq("industry", industry).limit(1).execute().data
    return r[0] if r else None

def get_stock_returns(stock_id):
    today = date.today()
    def price_on(target):
        r = db().table("stock_prices").select("price").eq("stock_id", stock_id)\
            .lte("date", target.isoformat()).order("date", desc=True).limit(1).execute().data
        return float(r[0]["price"]) if r else None

    latest_r = db().table("stock_prices").select("price,date").eq("stock_id", stock_id)\
        .order("date", desc=True).limit(1).execute().data
    if not latest_r:
        return {}
    latest = float(latest_r[0]["price"])
    latest_date = latest_r[0]["date"][:10]

    def ret(months=None, days=None):
        if months:
            m, y = today.month - months, today.year
            while m <= 0: m += 12; y -= 1
            try: target = today.replace(year=y, month=m)
            except: import calendar; target = today.replace(year=y, month=m, day=calendar.monthrange(y,m)[1])
        else:
            target = today - timedelta(days=days)
        p = price_on(target)
        return round((latest - p) / p * 100, 2) if p and p > 0 else None

    return {
        "latest_price": latest,
        "latest_date":  latest_date,
        "return_1w":    ret(days=7),
        "return_1m":    ret(months=1),
        "return_2m":    ret(months=2),
        "return_3m":    ret(months=3),
        "return_6m":    ret(months=6),
    }


# ── builder ───────────────────────────────────────────────────────────────────

def build_context(ticker: str) -> dict:
    ticker = ticker.upper()
    log.info(f"Building context for {ticker}...")

    info = get_stock_info(ticker)
    if not info:
        raise ValueError(f"Ticker '{ticker}' not found in stock_universe")

    stock_id = info["id"]
    sector   = info.get("sector") or ""
    industry = info.get("industry") or ""

    # ── fetch all data ────────────────────────────────────────────────────────
    earnings   = get_latest_earnings(stock_id)
    fin        = get_latest_financials(stock_id)
    transcript = get_transcript(stock_id)
    tech       = get_technicals(stock_id)
    valuation  = get_daily_valuation(stock_id)
    stock_ret  = get_stock_returns(stock_id)

    # sector/industry context
    latest_e   = earnings[0] if earnings else None
    e_year     = int(latest_e["date"][:4])                         if latest_e else None
    e_qtr      = (int(latest_e["date"][5:7]) - 1) // 3 + 1        if latest_e else None

    sec_e   = get_sector_earnings(sector, e_year, e_qtr)           if e_year else None
    ind_e   = get_industry_earnings(industry, e_year, e_qtr)       if e_year else None
    sec_s   = get_sector_sentiment(sector, transcript["year"], transcript["quarter"]) if transcript else None
    ind_s   = get_industry_sentiment(industry, transcript["year"], transcript["quarter"]) if transcript else None
    sec_f   = get_sector_financials(sector, e_year, e_qtr)         if e_year else None
    ind_f   = get_industry_financials(industry, e_year, e_qtr)     if e_year else None
    sec_vol = get_sector_vol(sector)
    ind_vol = get_industry_vol(industry)
    sec_ret = get_sector_returns(sector)
    ind_ret = get_industry_returns(industry)

    # ── assemble context ──────────────────────────────────────────────────────
    ctx = {
        "meta": {
            "ticker":        ticker,
            "generated_at":  date.today().isoformat(),
            "data_sources":  ["stock_universe","earnings","stock_financials",
                              "earnings_transcripts","stock_technicals",
                              "stock_daily_valuation","sector/industry matrices"],
        },

        # ── COMPANY ───────────────────────────────────────────────────────────
        "company": {
            "name":        info.get("name"),
            "sector":      sector,
            "industry":    industry,
            "country":     info.get("country"),
            "exchange":    info.get("exchange"),
            "employees":   safe_int(info.get("employees")),
            "website":     info.get("website"),
            "address":     info.get("address"),
            "description": info.get("description"),
        },

        # ── PRICE & TECHNICALS ────────────────────────────────────────────────
        "price_technicals": {
            "latest_price":       safe_float(tech.get("price"), 2)    if tech else None,
            "date":               tech.get("date")                    if tech else None,
            "sma_20":             safe_float(tech.get("sma_20"), 2)   if tech else None,
            "sma_50":             safe_float(tech.get("sma_50"), 2)   if tech else None,
            "sma_100":            safe_float(tech.get("sma_100"), 2)  if tech else None,
            "sma_200":            safe_float(tech.get("sma_200"), 2)  if tech else None,
            "vs_sma_20":          tech.get("vs_sma_20")               if tech else None,
            "vs_sma_50":          tech.get("vs_sma_50")               if tech else None,
            "vs_sma_200":         tech.get("vs_sma_200")              if tech else None,
            "pct_from_sma_200":   pct(tech.get("pct_from_sma_200"))   if tech else None,
            "rsi_14":             safe_float(tech.get("rsi_14"), 1)   if tech else None,
            "rsi_signal":         ("overbought" if (tech.get("rsi_14") or 0) > 70
                                   else "oversold" if (tech.get("rsi_14") or 0) < 30
                                   else "neutral")                    if tech else None,
            "hvol_10d":           pct(tech.get("hvol_10d"))           if tech else None,
            "hvol_30d":           pct(tech.get("hvol_30d"))           if tech else None,
            "hvol_90d":           pct(tech.get("hvol_90d"))           if tech else None,
            "hvol_252d":          pct(tech.get("hvol_252d"))          if tech else None,
            "vol_vs_sector": {
                "hvol_30d_delta":  vs(pct(tech.get("hvol_30d"))  if tech else None,
                                      pct(sec_vol.get("avg_hvol_30d")) if sec_vol else None),
                "hvol_252d_delta": vs(pct(tech.get("hvol_252d")) if tech else None,
                                      pct(sec_vol.get("avg_hvol_252d")) if sec_vol else None),
                "sector_vol_regime":   sec_vol.get("vol_regime")   if sec_vol else None,
                "industry_vol_regime": ind_vol.get("vol_regime")   if ind_vol else None,
            }
        },

        # ── PRICE RETURNS ─────────────────────────────────────────────────────
        "price_returns": {
            "stock": {
                "latest_price": stock_ret.get("latest_price"),
                "latest_date":  stock_ret.get("latest_date"),
                "return_1w":    pct(stock_ret.get("return_1w")),
                "return_1m":    pct(stock_ret.get("return_1m")),
                "return_3m":    pct(stock_ret.get("return_3m")),
                "return_6m":    pct(stock_ret.get("return_6m")),
            },
            "sector_avg": {
                "return_1w":  pct(sec_ret.get("avg_return_1w"))  if sec_ret else None,
                "return_1m":  pct(sec_ret.get("avg_return_1m"))  if sec_ret else None,
                "return_3m":  pct(sec_ret.get("avg_return_3m"))  if sec_ret else None,
                "return_6m":  pct(sec_ret.get("avg_return_6m"))  if sec_ret else None,
            },
            "industry_avg": {
                "return_1w":  pct(ind_ret.get("avg_return_1w"))  if ind_ret else None,
                "return_1m":  pct(ind_ret.get("avg_return_1m"))  if ind_ret else None,
                "return_3m":  pct(ind_ret.get("avg_return_3m"))  if ind_ret else None,
                "return_6m":  pct(ind_ret.get("avg_return_6m"))  if ind_ret else None,
            },
            "vs_sector": {
                "return_1m":  vs(pct(stock_ret.get("return_1m")),
                                 pct(sec_ret.get("avg_return_1m")) if sec_ret else None),
                "return_3m":  vs(pct(stock_ret.get("return_3m")),
                                 pct(sec_ret.get("avg_return_3m")) if sec_ret else None),
                "return_6m":  vs(pct(stock_ret.get("return_6m")),
                                 pct(sec_ret.get("avg_return_6m")) if sec_ret else None),
            },
        },

        # ── EARNINGS ──────────────────────────────────────────────────────────
        "earnings": {
            "latest_quarter": {
                "date":              latest_e.get("date")                 if latest_e else None,
                "eps_actual":        safe_float(latest_e.get("eps_actual"), 4) if latest_e else None,
                "eps_estimated":     safe_float(latest_e.get("eps_estimated"), 4) if latest_e else None,
                "eps_surprise_pct":  pct(latest_e.get("eps_surprise_pct")) if latest_e else None,
                "eps_growth_pct":    pct(latest_e.get("eps_growth_pct"))   if latest_e else None,
                "revenue_actual":    safe_int(latest_e.get("revenue_actual")) if latest_e else None,
                "revenue_estimated": safe_int(latest_e.get("revenue_estimated")) if latest_e else None,
                "rev_surprise_pct":  pct(latest_e.get("rev_surprise_pct")) if latest_e else None,
                "rev_growth_pct":    pct(latest_e.get("rev_growth_pct"))   if latest_e else None,
            },
            "sector_comparison": {
                "avg_eps_surprise_pct":    pct(sec_e.get("avg_eps_surprise_pct"))    if sec_e else None,
                "avg_rev_surprise_pct":    pct(sec_e.get("avg_rev_surprise_pct"))    if sec_e else None,
                "avg_eps_growth_pct":      pct(sec_e.get("avg_eps_growth_pct"))      if sec_e else None,
                "avg_revenue_growth_pct":  pct(sec_e.get("avg_revenue_growth_pct"))  if sec_e else None,
                "eps_beat_rate_pct":       pct(sec_e.get("eps_beat_rate_pct"))        if sec_e else None,
                "rev_beat_rate_pct":       pct(sec_e.get("rev_beat_rate_pct"))        if sec_e else None,
                "vs_eps_surprise":         vs(pct(latest_e.get("eps_surprise_pct")) if latest_e else None,
                                              pct(sec_e.get("avg_eps_surprise_pct")) if sec_e else None),
                "vs_eps_growth":           vs(pct(latest_e.get("eps_growth_pct")) if latest_e else None,
                                              pct(sec_e.get("avg_eps_growth_pct")) if sec_e else None),
            },
            "industry_comparison": {
                "avg_eps_surprise_pct":    pct(ind_e.get("avg_eps_surprise_pct"))    if ind_e else None,
                "avg_rev_surprise_pct":    pct(ind_e.get("avg_rev_surprise_pct"))    if ind_e else None,
                "avg_eps_growth_pct":      pct(ind_e.get("avg_eps_growth_pct"))      if ind_e else None,
                "avg_revenue_growth_pct":  pct(ind_e.get("avg_revenue_growth_pct"))  if ind_e else None,
                "eps_beat_rate_pct":       pct(ind_e.get("eps_beat_rate_pct"))        if ind_e else None,
                "vs_eps_surprise":         vs(pct(latest_e.get("eps_surprise_pct")) if latest_e else None,
                                              pct(ind_e.get("avg_eps_surprise_pct")) if ind_e else None),
            },
            "history_last_8q": [
                {
                    "date":             e.get("date"),
                    "eps_actual":       safe_float(e.get("eps_actual"), 4),
                    "eps_estimated":    safe_float(e.get("eps_estimated"), 4),
                    "eps_surprise_pct": pct(e.get("eps_surprise_pct")),
                    "eps_growth_pct":   pct(e.get("eps_growth_pct")),
                    "revenue_actual":   safe_int(e.get("revenue_actual")),
                    "rev_growth_pct":   pct(e.get("rev_growth_pct")),
                    "rev_surprise_pct": pct(e.get("rev_surprise_pct")),
                }
                for e in earnings
            ],
        },

        # ── SENTIMENT ─────────────────────────────────────────────────────────
        "sentiment": {
            "period": f"Q{transcript['quarter']} {transcript['year']}" if transcript else None,
            "transcript_date":   transcript.get("earnings_date")       if transcript else None,
            "one_line_summary":  transcript.get("one_line_summary")    if transcript else None,
            "bull_case":         transcript.get("bull_case")           if transcript else None,
            "bear_case":         transcript.get("bear_case")           if transcript else None,
            "top_topics":        transcript.get("top_topics")          if transcript else None,
            "risk_factors":      transcript.get("risk_factors")        if transcript else None,
            "scores": {
                s: {
                    "stock":    safe_float(transcript.get(f"{s}_score"), 1) if transcript else None,
                    "sector":   safe_float(sec_s.get(f"avg_{s}"), 1)       if sec_s else None,
                    "industry": safe_float(ind_s.get(f"avg_{s}"), 1)       if ind_s else None,
                    "vs_sector": vs(
                        safe_float(transcript.get(f"{s}_score"), 1) if transcript else None,
                        safe_float(sec_s.get(f"avg_{s}"), 1)        if sec_s else None
                    ),
                    "higher_is_better": s not in ("uncertainty","hedge","deflection","risk"),
                }
                for s in ["sentiment","guidance","confidence","uncertainty","hedge",
                          "analyst_trust","deflection","forward_outlook","risk","innovation"]
            },
            "composite": {
                "stock":    None,  # computed below
                "sector":   safe_float(sec_s.get("composite_score"), 2) if sec_s else None,
                "industry": safe_float(ind_s.get("composite_score"), 2) if ind_s else None,
            }
        },

        # ── FINANCIALS ────────────────────────────────────────────────────────
        "financials": {
            "period": fin.get("date") if fin else None,
            "margins": {
                "gross_margin_pct":     pct(safe_float(fin.get("gross_profit_margin"), 6) * 100 if fin and fin.get("gross_profit_margin") else None),
                "operating_margin_pct": pct(safe_float(fin.get("operating_margin"), 6) * 100    if fin and fin.get("operating_margin") else None),
                "net_margin_pct":       pct(safe_float(fin.get("net_profit_margin"), 6) * 100   if fin and fin.get("net_profit_margin") else None),
                "ebitda_margin_pct":    pct(safe_float(fin.get("ebitda_margin"), 6) * 100       if fin and fin.get("ebitda_margin") else None),
                "vs_sector": {
                    "gross":     vs(pct(safe_float(fin.get("gross_profit_margin"),4)*100 if fin and fin.get("gross_profit_margin") else None), pct(sec_f.get("avg_gross_margin_pct")) if sec_f else None),
                    "net":       vs(pct(safe_float(fin.get("net_profit_margin"),4)*100   if fin and fin.get("net_profit_margin") else None),   pct(sec_f.get("avg_net_margin_pct"))   if sec_f else None),
                    "operating": vs(pct(safe_float(fin.get("operating_margin"),4)*100    if fin and fin.get("operating_margin") else None),    pct(sec_f.get("avg_operating_margin_pct")) if sec_f else None),
                },
                "vs_industry": {
                    "gross":     vs(pct(safe_float(fin.get("gross_profit_margin"),4)*100 if fin and fin.get("gross_profit_margin") else None), pct(ind_f.get("avg_gross_margin_pct")) if ind_f else None),
                    "net":       vs(pct(safe_float(fin.get("net_profit_margin"),4)*100   if fin and fin.get("net_profit_margin") else None),   pct(ind_f.get("avg_net_margin_pct"))   if ind_f else None),
                },
            },
            "valuation": {
                "pe_ratio":             ratio(fin.get("pe_ratio"))        if fin else None,
                "ps_ratio":             ratio(fin.get("price_to_sales"))  if fin else None,
                "pb_ratio":             ratio(fin.get("price_to_book"))   if fin else None,
                "peg_ratio":            ratio(fin.get("peg_ratio"))       if fin else None,
                "price_to_fcf":         ratio(fin.get("price_to_fcf"))    if fin else None,
                "pe_1y_avg":            ratio(valuation.get("pe_1y_avg")) if valuation else None,
                "ps_1y_avg":            ratio(valuation.get("ps_1y_avg")) if valuation else None,
                "pe_vs_1y_avg_pct":     pct(valuation.get("pe_vs_1y_avg_pct")) if valuation else None,
                "ps_vs_1y_avg_pct":     pct(valuation.get("ps_vs_1y_avg_pct")) if valuation else None,
                "vs_sector": {
                    "pe": vs(ratio(fin.get("pe_ratio"))       if fin else None, ratio(sec_f.get("avg_pe_ratio"))        if sec_f else None),
                    "ps": vs(ratio(fin.get("price_to_sales")) if fin else None, ratio(sec_f.get("avg_price_to_sales"))  if sec_f else None),
                    "pb": vs(ratio(fin.get("price_to_book"))  if fin else None, ratio(sec_f.get("avg_price_to_book"))   if sec_f else None),
                },
                "vs_industry": {
                    "pe": vs(ratio(fin.get("pe_ratio"))       if fin else None, ratio(ind_f.get("avg_pe_ratio"))        if ind_f else None),
                    "ps": vs(ratio(fin.get("price_to_sales")) if fin else None, ratio(ind_f.get("avg_price_to_sales"))  if ind_f else None),
                },
            },
            "quality": {
                "roe_pct":              pct(safe_float(fin.get("roe"), 4) * 100 if fin and fin.get("roe") else None),
                "roa_pct":              pct(safe_float(fin.get("roa"), 4) * 100 if fin and fin.get("roa") else None),
                "debt_to_equity":       ratio(fin.get("debt_to_equity"))   if fin else None,
                "current_ratio":        ratio(fin.get("current_ratio"))    if fin else None,
                "dividend_yield_pct":   pct(safe_float(fin.get("dividend_yield"), 4) * 100 if fin and fin.get("dividend_yield") else None),
                "vs_sector": {
                    "roe": vs(pct(safe_float(fin.get("roe"),4)*100 if fin and fin.get("roe") else None), pct(sec_f.get("avg_roe_pct")) if sec_f else None),
                    "roa": vs(pct(safe_float(fin.get("roa"),4)*100 if fin and fin.get("roa") else None), pct(sec_f.get("avg_roa_pct")) if sec_f else None),
                    "debt_to_equity": vs(ratio(fin.get("debt_to_equity")) if fin else None, ratio(sec_f.get("avg_debt_to_equity")) if sec_f else None),
                },
            },
        },
    }

    # compute composite sentiment score
    if transcript:
        scores     = ctx["sentiment"]["scores"]
        bearish    = {"uncertainty","hedge","deflection","risk"}
        comp_parts = []
        for s, v in scores.items():
            raw = v["stock"]
            if raw is not None:
                comp_parts.append(10 - raw if s in bearish else raw)
        if comp_parts:
            comp = round(sum(comp_parts) / len(comp_parts), 2)
            ctx["sentiment"]["composite"]["stock"] = comp
            ctx["sentiment"]["composite"]["vs_sector"] = vs(comp, ctx["sentiment"]["composite"]["sector"])
            ctx["sentiment"]["composite"]["vs_industry"] = vs(comp, ctx["sentiment"]["composite"]["industry"])

    return ctx


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build LLM context JSON for a ticker.")
    parser.add_argument("ticker",             help="Ticker symbol (e.g. AAPL, NESN.SW)")
    parser.add_argument("--output",  "-o",    help="Output file path (default: <ticker>_context.json)")
    parser.add_argument("--pretty",  "-p",    action="store_true", help="Pretty-print JSON")
    parser.add_argument("--print",            action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    ctx      = build_context(args.ticker)
    indent   = 2 if args.pretty else None
    json_str = json.dumps(ctx, indent=indent, default=str)

    # write to file
    outfile = args.output or f"{args.ticker.upper()}_context.json"
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(json_str)
    log.info(f"Context written to {outfile}  ({len(json_str):,} chars)")

    if args.print:
        print(json_str)

    # summary
    s = ctx["sentiment"]
    e = ctx["earnings"]["latest_quarter"]
    p = ctx["price_returns"]["stock"]
    log.info(f"\n── Summary for {args.ticker.upper()} ──")
    log.info(f"  Composite sentiment:  {s['composite']['stock']} / 10  (sector: {s['composite']['sector']})")
    log.info(f"  Latest EPS surprise:  {e['eps_surprise_pct']}%")
    log.info(f"  EPS growth YoY:       {e['eps_growth_pct']}%")
    log.info(f"  Rev growth YoY:       {e['rev_growth_pct']}%")
    log.info(f"  1M return:            {p['return_1m']}%")
    log.info(f"  3M return:            {p['return_3m']}%")


if __name__ == "__main__":
    main()
