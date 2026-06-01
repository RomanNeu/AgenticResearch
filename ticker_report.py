# ticker_report.py
"""
Enter a ticker and get a comprehensive report comparing:
  - Latest earnings vs sector and industry average
  - Latest transcript sentiment scores vs sector and industry average
  - Key financials vs sector and industry average
  - Technical indicators
  - Volatility vs sector and industry
  - Daily valuation (P/E, P/S) vs sector average
  - Price returns vs sector and industry average
"""
import os
import logging
from datetime import datetime, date, timedelta, UTC
from dotenv import load_dotenv
from supabase import create_client
import zoneinfo

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase  = create_client(SUPABASE_URL, SUPABASE_KEY)
LOCAL_TZ  = zoneinfo.ZoneInfo("Europe/Zurich")


# ── HELPERS ───────────────────────────────────────────────────────────────────

def fmt_pct(val, decimals=2) -> str:
    if val is None:
        return "N/A"
    return f"{val:+.{decimals}f}%"

def fmt_num(val, decimals=2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"

def fmt_score(val) -> str:
    if val is None:
        return "N/A"
    bar = "█" * int(val) + "░" * (10 - int(val))
    return f"{val:.1f}/10  [{bar}]"

def delta_vs(ticker_val, compare_val, label="") -> str:
    if ticker_val is None or compare_val is None:
        return "N/A"
    diff  = ticker_val - compare_val
    arrow = "▲" if diff > 0 else "▼"
    return f"{arrow} {abs(diff):.2f}{(' ' + label) if label else ''}"

def score_delta(ticker_val, compare_val, higher_is_better=True) -> str:
    if ticker_val is None or compare_val is None:
        return "N/A"
    diff = ticker_val - compare_val
    if higher_is_better:
        arrow = "▲" if diff > 0 else "▼"
    else:
        arrow = "▼" if diff > 0 else "▲"
    return f"{arrow} {abs(diff):.2f}"

def section(title: str):
    width = 90
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")


# ── DATA FETCHERS ─────────────────────────────────────────────────────────────

def get_stock_info(ticker: str) -> dict | None:
    result = (
        supabase.table("stock_universe")
        .select("id, ticker, name, sector, industry, country, exchange")
        .eq("ticker", ticker.upper())
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None

def get_yoy_earnings(stock_id: str, current_date: str) -> dict | None:
    """Fetch the earnings row ~1 year prior for YoY growth calculation."""
    result = (
        supabase.table("earnings")
        .select("eps_actual, revenue_actual, date")
        .eq("stock_id", stock_id)
        .not_.is_("eps_actual", "null")
        .lte("date", (date.fromisoformat(current_date) - timedelta(days=270)).isoformat())
        .gte("date", (date.fromisoformat(current_date) - timedelta(days=450)).isoformat())
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None

def get_latest_earnings(stock_id: str) -> dict | None:
    result = (
        supabase.table("earnings")
        .select("*")
        .eq("stock_id", stock_id)
        .not_.is_("eps_actual", "null")
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_sector_earnings(sector: str, year: int, quarter: int) -> dict | None:
    result = (
        supabase.table("sector_earnings_matrix")
        .select("*")
        .eq("sector", sector)
        .eq("year", year)
        .eq("quarter", quarter)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_industry_earnings(industry: str, year: int, quarter: int) -> dict | None:
    result = (
        supabase.table("industry_earnings_matrix")
        .select("*")
        .eq("industry", industry)
        .eq("year", year)
        .eq("quarter", quarter)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_latest_transcript(stock_id: str) -> dict | None:
    result = (
        supabase.table("earnings_transcripts")
        .select("*")
        .eq("stock_id", stock_id)
        .not_.is_("sentiment_score", "null")
        .order("year", desc=True)
        .order("quarter", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_sector_sentiment(sector: str, year: int, quarter: int) -> dict | None:
    result = (
        supabase.table("sector_sentiment_matrix")
        .select("*")
        .eq("sector", sector)
        .eq("year", year)
        .eq("quarter", quarter)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_industry_sentiment(industry: str, year: int, quarter: int) -> dict | None:
    result = (
        supabase.table("industry_sentiment_matrix")
        .select("*")
        .eq("industry", industry)
        .eq("year", year)
        .eq("quarter", quarter)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_latest_financials(stock_id: str) -> dict | None:
    result = (
        supabase.table("stock_financials")
        .select("*")
        .eq("stock_id", stock_id)
        .not_.is_("net_profit_margin", "null")
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_sector_financials(sector: str, year: int, quarter: int) -> dict | None:
    result = (
        supabase.table("sector_financials_matrix")
        .select("*")
        .eq("sector", sector)
        .eq("year", year)
        .eq("quarter", quarter)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_industry_financials(industry: str, year: int, quarter: int) -> dict | None:
    result = (
        supabase.table("industry_financials_matrix")
        .select("*")
        .eq("industry", industry)
        .eq("year", year)
        .eq("quarter", quarter)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_technicals(stock_id: str) -> dict | None:
    result = (
        supabase.table("stock_technicals")
        .select("*")
        .eq("stock_id", stock_id)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_sector_volatility(sector: str) -> dict | None:
    result = (
        supabase.table("sector_volatility_matrix")
        .select("*")
        .eq("sector", sector)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_industry_volatility(industry: str) -> dict | None:
    result = (
        supabase.table("industry_volatility_matrix")
        .select("*")
        .eq("industry", industry)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_daily_valuation(stock_id: str) -> dict | None:
    result = (
        supabase.table("stock_daily_valuation")
        .select("*")
        .eq("stock_id", stock_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_sector_returns(sector: str) -> dict | None:
    result = (
        supabase.table("sector_returns")
        .select("*")
        .eq("sector", sector)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_industry_returns(industry: str) -> dict | None:
    result = (
        supabase.table("industry_returns")
        .select("*")
        .eq("industry", industry)
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_price_returns(ticker: str) -> dict | None:
    latest_result = (
        supabase.table("stock_prices")
        .select("price, date")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if not latest_result:
        return None

    latest      = latest_result[0]["price"]
    latest_date = date.fromisoformat(latest_result[0]["date"])

    def get_price_on(target_date: date) -> float | None:
        r = (
            supabase.table("stock_prices")
            .select("price, date")
            .eq("ticker", ticker)
            .lte("date", target_date.isoformat())
            .order("date", desc=True)
            .limit(1)
            .execute()
            .data
        )
        return r[0]["price"] if r else None

    def ret(days=None, months=None) -> float | None:
        if months:
            month = latest_date.month - months
            year  = latest_date.year
            while month <= 0:
                month += 12
                year  -= 1
            try:
                target = latest_date.replace(year=year, month=month)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                target   = latest_date.replace(year=year, month=month, day=last_day)
        else:
            target = latest_date - timedelta(days=days)
        past = get_price_on(target)
        if past and past > 0:
            return round((latest - past) / past * 100, 2)
        return None

    return {
        "current_price": latest,
        "latest_date":   latest_date.isoformat(),
        "return_1w":     ret(days=7),
        "return_1m":     ret(months=1),
        "return_2m":     ret(months=2),
        "return_3m":     ret(months=3),
        "return_6m":     ret(months=6),
    }


# ── REPORT PRINTER ────────────────────────────────────────────────────────────

def print_report(ticker: str):
    ticker = ticker.upper()
    print(f"\n{'█' * 90}")
    print(f"  TICKER REPORT: {ticker}")
    print(f"  Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'█' * 90}")

    # ── STOCK INFO ────────────────────────────────────────────────────────────
    info = get_stock_info(ticker)
    if not info:
        print(f"\n  ✗ Ticker '{ticker}' not found in stock_universe.")
        return

    stock_id = info["id"]
    sector   = info["sector"]
    industry = info.get("industry")

    section("COMPANY OVERVIEW")
    print(f"  Name:        {info.get('name', 'N/A')}")
    print(f"  Sector:      {sector or 'N/A'}")
    print(f"  Industry:    {industry or 'N/A'}")
    print(f"  Exchange:    {info.get('exchange', 'N/A')}")
    print(f"  Country:     {info.get('country', 'N/A')}")

    # ── LATEST EARNINGS ───────────────────────────────────────────────────────
    earnings = get_latest_earnings(stock_id)
    if earnings:
        e_date   = datetime.fromisoformat(str(earnings["date"]))
        year     = e_date.year
        quarter  = (e_date.month - 1) // 3 + 1
        sec_e    = get_sector_earnings(sector, year, quarter)     if sector   else None
        ind_e    = get_industry_earnings(industry, year, quarter) if industry else None
        yoy      = get_yoy_earnings(stock_id, earnings["date"])

        # compute ticker-level YoY growth
        eps_growth_pct = None
        rev_growth_pct = None
        if yoy:
            if yoy.get("eps_actual") and yoy["eps_actual"] != 0:
                eps_growth_pct = round(
                    (earnings["eps_actual"] - yoy["eps_actual"])
                    / abs(yoy["eps_actual"]) * 100, 2
                )
            if yoy.get("revenue_actual") and yoy["revenue_actual"] != 0:
                rev_growth_pct = round(
                    (earnings["revenue_actual"] - yoy["revenue_actual"])
                    / abs(yoy["revenue_actual"]) * 100, 2
                )

        section(f"LATEST EARNINGS  —  {earnings['date']}  (Q{quarter} {year})")
        print(f"  {'Metric':<28} {'Ticker':>10}   {'Sector Avg':>10}   {'vs Sector':>12}   {'Industry Avg':>12}   {'vs Industry':>12}")
        print(f"  {'-'*90}")

        def e_row(label, t_val, s_val, i_val, is_pct=False):
            fmt  = fmt_pct if is_pct else fmt_num
            tv   = fmt(t_val)
            sv   = fmt(s_val)
            iv   = fmt(i_val)
            d_s  = delta_vs(t_val, s_val)
            d_i  = delta_vs(t_val, i_val)
            print(f"  {label:<28} {tv:>10}   {sv:>10}   {d_s:>12}   {iv:>12}   {d_i:>12}")

        e_row("EPS Actual",
              earnings.get("eps_actual"), None, None)
        e_row("EPS Estimated",
              earnings.get("eps_estimated"), None, None)
        e_row("EPS Growth % YoY",
              eps_growth_pct,
              sec_e.get("avg_eps_growth_pct")     if sec_e else None,
              ind_e.get("avg_eps_growth_pct")     if ind_e else None,
              is_pct=True)
        e_row("EPS Surprise %",
              earnings.get("eps_surprise_pct"),
              sec_e.get("avg_eps_surprise_pct")   if sec_e else None,
              ind_e.get("avg_eps_surprise_pct")   if ind_e else None,
              is_pct=True)
        e_row("Revenue Actual ($)",
              earnings.get("revenue_actual") / 1e9 if earnings.get("revenue_actual") else None,
              None, None)
        e_row("Revenue Growth % YoY",
              rev_growth_pct,
              sec_e.get("avg_revenue_growth_pct") if sec_e else None,
              ind_e.get("avg_revenue_growth_pct") if ind_e else None,
              is_pct=True)
        e_row("Revenue Surprise %",
              earnings.get("rev_surprise_pct"),
              sec_e.get("avg_rev_surprise_pct")   if sec_e else None,
              ind_e.get("avg_rev_surprise_pct")   if ind_e else None,
              is_pct=True)
        if sec_e:
            print(f"  {'EPS Beat Rate':<28} {'—':>10}   "
                  f"{fmt_pct(sec_e.get('eps_beat_rate_pct'), 1):>10}   "
                  f"{'—':>12}   "
                  f"{fmt_pct(ind_e.get('eps_beat_rate_pct'), 1) if ind_e else 'N/A':>12}   "
                  f"{'—':>12}")
            print(f"  {'Rev Beat Rate':<28} {'—':>10}   "
                  f"{fmt_pct(sec_e.get('rev_beat_rate_pct'), 1):>10}   "
                  f"{'—':>12}   "
                  f"{fmt_pct(ind_e.get('rev_beat_rate_pct'), 1) if ind_e else 'N/A':>12}   "
                  f"{'—':>12}")
        if yoy:
            print(f"\n  YoY comparison base:  {yoy['date']}  "
                  f"(EPS: {fmt_num(yoy.get('eps_actual'))}  "
                  f"Rev: ${yoy['revenue_actual']/1e9:.2f}B)" if yoy.get('revenue_actual') else "")
    else:
        print("\n  No earnings data found.")

    # ── SENTIMENT SCORES ──────────────────────────────────────────────────────
    transcript = get_latest_transcript(stock_id)
    if transcript:
        t_year    = transcript["year"]
        t_quarter = transcript["quarter"]
        sec_s     = get_sector_sentiment(sector, t_year, t_quarter)     if sector   else None
        ind_s     = get_industry_sentiment(industry, t_year, t_quarter) if industry else None

        section(f"EARNINGS CALL SENTIMENT  —  Q{t_quarter} {t_year}")
        print(f"  {transcript.get('one_line_summary', '')}")
        print()
        print(f"  {'Score':<28} {'Ticker':<22} {'Sector':>8}   {'vs Sector':>10}   {'Industry':>10}   {'vs Industry':>12}")
        print(f"  {'-'*90}")

        scores = [
            ("Sentiment",        "sentiment_score",       "avg_sentiment",        True),
            ("Guidance",         "guidance_score",        "avg_guidance",         True),
            ("Confidence",       "confidence_score",      "avg_confidence",       True),
            ("Uncertainty ↓",    "uncertainty_score",     "avg_uncertainty",      False),
            ("Hedge ↓",          "hedge_score",           "avg_hedge",            False),
            ("Analyst Trust",    "analyst_trust_score",   "avg_analyst_trust",    True),
            ("Deflection ↓",     "deflection_score",      "avg_deflection",       False),
            ("Forward Outlook",  "forward_outlook_score", "avg_forward_outlook",  True),
            ("Risk ↓",           "risk_score",            "avg_risk",             False),
            ("Innovation",       "innovation_score",      "avg_innovation",       True),
        ]

        for label, t_key, s_key, higher_is_better in scores:
            t_val = transcript.get(t_key)
            s_val = sec_s.get(s_key)  if sec_s else None
            i_val = ind_s.get(s_key)  if ind_s else None
            print(f"  {label:<28} {fmt_score(t_val):<22} "
                  f"{fmt_num(s_val):>8}   "
                  f"{score_delta(t_val, s_val, higher_is_better):>10}   "
                  f"{fmt_num(i_val):>10}   "
                  f"{score_delta(t_val, i_val, higher_is_better):>12}")

        # composite
        score_keys = [s[1] for s in scores]
        if all(transcript.get(k) is not None for k in score_keys):
            composite = (
                transcript["sentiment_score"] +
                transcript["guidance_score"] +
                transcript["confidence_score"] +
                transcript["analyst_trust_score"] +
                transcript["forward_outlook_score"] +
                transcript["innovation_score"] +
                (10 - transcript["uncertainty_score"]) +
                (10 - transcript["hedge_score"]) +
                (10 - transcript["deflection_score"]) +
                (10 - transcript["risk_score"])
            ) / 10.0
            sec_comp = sec_s.get("composite_score") if sec_s else None
            ind_comp = ind_s.get("composite_score") if ind_s else None
            print(f"  {'-'*90}")
            print(f"  {'COMPOSITE SCORE':<28} {fmt_score(composite):<22} "
                  f"{fmt_num(sec_comp):>8}   "
                  f"{score_delta(composite, sec_comp, True):>10}   "
                  f"{fmt_num(ind_comp):>10}   "
                  f"{score_delta(composite, ind_comp, True):>12}")

        print()
        if transcript.get("top_topics"):
            print(f"  Top Topics:   {', '.join(transcript['top_topics'])}")
        if transcript.get("risk_factors"):
            print(f"  Risk Factors: {', '.join(transcript['risk_factors'])}")
        if transcript.get("bull_case"):
            print(f"  Bull Case:    {transcript['bull_case']}")
        if transcript.get("bear_case"):
            print(f"  Bear Case:    {transcript['bear_case']}")
    else:
        print("\n  No scored transcript found.")

    # ── KEY FINANCIALS ────────────────────────────────────────────────────────
    fin = get_latest_financials(stock_id)
    if fin:
        f_date    = datetime.fromisoformat(str(fin["date"]))
        f_year    = f_date.year
        f_quarter = (f_date.month - 1) // 3 + 1
        sec_f     = get_sector_financials(sector, f_year, f_quarter)     if sector   else None
        ind_f     = get_industry_financials(industry, f_year, f_quarter) if industry else None

        section(f"KEY FINANCIALS  —  {fin['date']}  ({fin.get('period', '')})")
        print(f"  {'Metric':<28} {'Ticker':>10}   {'Sector Avg':>10}   {'vs Sector':>12}   {'Industry Avg':>12}   {'vs Industry':>12}")
        print(f"  {'-'*90}")

        def fin_row(label, t_val, s_val, i_val, mult=100, suffix="%"):
            tv  = fmt_num(t_val * mult) + suffix if t_val is not None else "N/A"
            sv  = fmt_num(s_val) + suffix         if s_val is not None else "N/A"
            iv  = fmt_num(i_val) + suffix         if i_val is not None else "N/A"
            d_s = delta_vs(t_val * mult if t_val is not None else None, s_val)
            d_i = delta_vs(t_val * mult if t_val is not None else None, i_val)
            print(f"  {label:<28} {tv:>10}   {sv:>10}   {d_s:>12}   {iv:>12}   {d_i:>12}")

        def ratio_row(label, t_val, s_val, i_val, suffix="x"):
            tv  = fmt_num(t_val, 1) + suffix if t_val is not None else "N/A"
            sv  = fmt_num(s_val, 1) + suffix if s_val is not None else "N/A"
            iv  = fmt_num(i_val, 1) + suffix if i_val is not None else "N/A"
            d_s = delta_vs(t_val, s_val)
            d_i = delta_vs(t_val, i_val)
            print(f"  {label:<28} {tv:>10}   {sv:>10}   {d_s:>12}   {iv:>12}   {d_i:>12}")

        fin_row("Gross Margin",
                fin.get("gross_profit_margin"),
                sec_f.get("avg_gross_margin_pct")     if sec_f else None,
                ind_f.get("avg_gross_margin_pct")     if ind_f else None)
        fin_row("Operating Margin",
                fin.get("operating_margin"),
                sec_f.get("avg_operating_margin_pct") if sec_f else None,
                ind_f.get("avg_operating_margin_pct") if ind_f else None)
        fin_row("Net Margin",
                fin.get("net_profit_margin"),
                sec_f.get("avg_net_margin_pct")       if sec_f else None,
                ind_f.get("avg_net_margin_pct")       if ind_f else None)
        fin_row("EBITDA Margin",
                fin.get("ebitda_margin"),
                sec_f.get("avg_ebitda_margin_pct")    if sec_f else None,
                ind_f.get("avg_ebitda_margin_pct")    if ind_f else None)

        print(f"  {'-'*90}")
        ratio_row("P/E Ratio",
                  fin.get("pe_ratio"),
                  sec_f.get("avg_pe_ratio")         if sec_f else None,
                  ind_f.get("avg_pe_ratio")         if ind_f else None)
        ratio_row("P/B Ratio",
                  fin.get("price_to_book"),
                  sec_f.get("avg_price_to_book")    if sec_f else None,
                  ind_f.get("avg_price_to_book")    if ind_f else None)
        ratio_row("P/S Ratio",
                  fin.get("price_to_sales"),
                  sec_f.get("avg_price_to_sales")   if sec_f else None,
                  ind_f.get("avg_price_to_sales")   if ind_f else None)
        ratio_row("PEG Ratio",
                  fin.get("peg_ratio"),
                  None, None)
        ratio_row("Price to FCF",
                  fin.get("price_to_fcf"),
                  None, None)

        print(f"  {'-'*90}")
        fin_row("ROE",
                fin.get("roe"),
                sec_f.get("avg_roe_pct")            if sec_f else None,
                ind_f.get("avg_roe_pct")            if ind_f else None)
        fin_row("ROA",
                fin.get("roa"),
                sec_f.get("avg_roa_pct")            if sec_f else None,
                ind_f.get("avg_roa_pct")            if ind_f else None)
        ratio_row("Debt/Equity",
                  fin.get("debt_to_equity"),
                  sec_f.get("avg_debt_to_equity")   if sec_f else None,
                  ind_f.get("avg_debt_to_equity")   if ind_f else None)
        ratio_row("Current Ratio",
                  fin.get("current_ratio"),
                  sec_f.get("avg_current_ratio")    if sec_f else None,
                  ind_f.get("avg_current_ratio")    if ind_f else None)
        fin_row("Dividend Yield",
                fin.get("dividend_yield"),
                sec_f.get("avg_dividend_yield_pct") if sec_f else None,
                ind_f.get("avg_dividend_yield_pct") if ind_f else None)
    else:
        print("\n  No financial data found.")

    # ── TECHNICAL INDICATORS ──────────────────────────────────────────────────
    tech = get_technicals(stock_id)
    if tech:
        section(f"TECHNICAL INDICATORS  —  {tech.get('date', 'N/A')}")
        price = tech.get("price", 0)
        print(f"  Current Price:   ${fmt_num(price)}")
        print()
        print(f"  {'SMA':<15} {'Value':<12} {'Price vs SMA':<15} {'% Distance'}")
        print(f"  {'-'*55}")
        for period in [20, 50, 100, 200]:
            sma_val = tech.get(f"sma_{period}")
            vs      = tech.get(f"vs_sma_{period}", "N/A")
            pct     = tech.get(f"pct_from_sma_{period}")
            arrow   = "▲" if vs == "above" else "▼"
            print(f"  SMA {period:<11} "
                  f"${fmt_num(sma_val):<11} "
                  f"{arrow} {vs:<13} "
                  f"{fmt_pct(pct)}")
        print()
        rsi        = tech.get("rsi_14")
        rsi_signal = "Overbought ⚠" if rsi and rsi > 70 else "Oversold ⚠" if rsi and rsi < 30 else "Neutral"
        print(f"  RSI (14):        {fmt_num(rsi)}  →  {rsi_signal}")
    else:
        print("\n  No technical data found.")

    # ── VOLATILITY VS SECTOR / INDUSTRY ──────────────────────────────────────
    sec_vol = get_sector_volatility(sector)     if sector   else None
    ind_vol = get_industry_volatility(industry) if industry else None

    if tech and (sec_vol or ind_vol):
        section("VOLATILITY vs SECTOR / INDUSTRY")
        print(f"  {'Period':<12} {'Ticker':>8}   {'Sector Avg':>10}   {'vs Sector':>12}   {'Industry Avg':>12}   {'vs Industry':>12}")
        print(f"  {'-'*80}")

        vol_periods = [
            ("10d",  "hvol_10d",  "avg_hvol_10d"),
            ("20d",  "hvol_20d",  "avg_hvol_20d"),
            ("30d",  "hvol_30d",  "avg_hvol_30d"),
            ("60d",  "hvol_60d",  "avg_hvol_60d"),
            ("90d",  "hvol_90d",  "avg_hvol_90d"),
            ("180d", "hvol_180d", "avg_hvol_180d"),
            ("252d", "hvol_252d", "avg_hvol_252d"),
        ]

        for label, t_key, s_key in vol_periods:
            t_val  = tech.get(t_key)
            sv_val = sec_vol.get(s_key) if sec_vol else None
            iv_val = ind_vol.get(s_key) if ind_vol else None
            d_sec  = delta_vs(t_val, sv_val)
            d_ind  = delta_vs(t_val, iv_val)
            print(f"  HVol {label:<7} "
                  f"{fmt_num(t_val):>7}%   "
                  f"{fmt_num(sv_val):>10}%   "
                  f"{d_sec:>12}   "
                  f"{fmt_num(iv_val):>12}%   "
                  f"{d_ind:>12}")

        print()
        if sec_vol:
            regime      = sec_vol.get("vol_regime", "N/A")
            term_spread = sec_vol.get("vol_term_spread")
            icon        = "🔴" if regime == "elevated" else "🟢" if regime == "suppressed" else "🟡"
            stress      = "short-term stress" if term_spread and term_spread > 0 else "short-term calm"
            print(f"  Sector Vol Regime:     {icon}  {regime.upper():<12}  "
                  f"Term Spread: {fmt_num(term_spread)}pp  ({stress})")
        if ind_vol:
            ind_regime      = ind_vol.get("vol_regime", "N/A")
            ind_term_spread = ind_vol.get("vol_term_spread")
            ind_icon        = "🔴" if ind_regime == "elevated" else "🟢" if ind_regime == "suppressed" else "🟡"
            ind_stress      = "short-term stress" if ind_term_spread and ind_term_spread > 0 else "short-term calm"
            print(f"  Industry Vol Regime:   {ind_icon}  {ind_regime.upper():<12}  "
                  f"Term Spread: {fmt_num(ind_term_spread)}pp  ({ind_stress})")

    # ── PRICE RETURNS ─────────────────────────────────────────────────────────
    returns = get_price_returns(ticker)
    sec_ret = get_sector_returns(sector)     if sector   else None
    ind_ret = get_industry_returns(industry) if industry else None

    if returns:
        section(f"PRICE RETURNS  —  latest price: {returns.get('latest_date', 'N/A')}  "
                f"${fmt_num(returns.get('current_price'))}")
        print(f"  {'Period':<15} {'Ticker':>10}   {'Sector Avg':>10}   {'vs Sector':>12}   {'Industry Avg':>12}   {'vs Industry':>12}")
        print(f"  {'-'*85}")

        for period, label in [
            ("return_1w", "1 Week"),
            ("return_1m", "1 Month"),
            ("return_2m", "2 Months"),
            ("return_3m", "3 Months"),
            ("return_6m", "6 Months"),
        ]:
            t_val = returns.get(period)
            s_val = sec_ret.get(f"avg_{period}") if sec_ret else None
            i_val = ind_ret.get(f"avg_{period}") if ind_ret else None
            d_s   = delta_vs(t_val, s_val)
            d_i   = delta_vs(t_val, i_val)
            print(f"  {label:<15} "
                  f"{fmt_pct(t_val):>10}   "
                  f"{fmt_pct(s_val):>10}   "
                  f"{d_s:>12}   "
                  f"{fmt_pct(i_val):>12}   "
                  f"{d_i:>12}")

        valid_returns = {p: returns[p] for p, _ in [
            ("return_1w","1W"),("return_1m","1M"),
            ("return_2m","2M"),("return_3m","3M"),("return_6m","6M")
        ] if returns.get(p) is not None}

        if valid_returns:
            labels       = {"return_1w":"1W","return_1m":"1M","return_2m":"2M",
                            "return_3m":"3M","return_6m":"6M"}
            best_period  = max(valid_returns, key=valid_returns.get)
            worst_period = min(valid_returns, key=valid_returns.get)
            print(f"\n  Best period:   {labels[best_period]}  {fmt_pct(valid_returns[best_period])}")
            print(f"  Worst period:  {labels[worst_period]}  {fmt_pct(valid_returns[worst_period])}")

    # ── DAILY VALUATION ───────────────────────────────────────────────────────
    valuation = get_daily_valuation(stock_id)
    if valuation:
        section(f"DAILY VALUATION  —  {valuation.get('date', 'N/A')}")
        print(f"  {'Metric':<32} {'Value':<20} {'1Y Avg':<20} {'vs 1Y Avg'}")
        print(f"  {'-'*75}")

        def val_row(label, t_val, avg_val, suffix="x"):
            tv  = fmt_num(t_val, 1) + suffix  if t_val  is not None else "N/A"
            av  = fmt_num(avg_val, 1) + suffix if avg_val is not None else "N/A"
            d   = delta_vs(t_val, avg_val)
            print(f"  {label:<32} {tv:<20} {av:<20} {d}")

        val_row("P/E Ratio (daily)",
                valuation.get("pe_ratio_daily"),
                valuation.get("pe_1y_avg"))
        val_row("P/S Ratio (daily)",
                valuation.get("ps_ratio_daily"),
                valuation.get("ps_1y_avg"))

        print(f"  {'P/E vs 1Y Avg':<32} {fmt_pct(valuation.get('pe_vs_1y_avg_pct')):<20}")
        print(f"  {'P/S vs 1Y Avg':<32} {fmt_pct(valuation.get('ps_vs_1y_avg_pct')):<20}")
        print()
        print(f"  TTM EPS:              ${fmt_num(valuation.get('ttm_eps'), 4)}")
        print(f"  TTM Revenue/Share:    ${fmt_num(valuation.get('ttm_revenue_per_share'), 4)}")
        shares = valuation.get("shares_outstanding")
        print(f"  Shares Outstanding:   {shares:,}" if shares else "  Shares Outstanding:   N/A")

    print(f"\n{'═' * 90}\n")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    while True:
        ticker = input("\nEnter ticker (or 'q' to quit): ").strip()
        if ticker.lower() == "q":
            break
        if ticker:
            print_report(ticker)