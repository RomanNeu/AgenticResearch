# stock_analysis_view.py
"""
Stock Analysis — Agentic Portfolio Management Platform
Institutional design: clean, data-dense, Bloomberg-inspired dark theme.
Tabs: Stock Analysis | Portfolio Construction | Portfolio Management (placeholders)
"""
import os
import asyncio
from datetime import date, timedelta
import requests
import logging
import threading
from dotenv import load_dotenv
from nicegui import ui
from supabase import create_client
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load_dotenv()
log = logging.getLogger(__name__)

_SUPABASE_URL = os.environ["SUPABASE_URL"]
_SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FMP_API_KEY   = os.environ["FMP_API_KEY"]
FMP_BASE      = "https://financialmodelingprep.com/stable"

def db():
    """Return a fresh Supabase client — avoids stale connection errors."""
    return create_client(_SUPABASE_URL, _SUPABASE_KEY)

# ── colour palette — institutional dark ───────────────────────────────────────
BG      = "#0d0d0d"       # near-black page
PANEL   = "#141414"       # panel background
CARD    = "#1a1a1a"       # card / input background
BORDER  = "#2a2a2a"       # subtle border
BORDER2 = "#333333"       # slightly stronger border
TEXT    = "#d4d4d4"       # primary text
MUTED   = "#737373"       # secondary / label text
DIM     = "#404040"       # very muted
ACCENT  = "#4a9eff"       # blue accent (Bloomberg-ish)
GREEN   = "#00c076"       # positive
RED     = "#ff5252"       # negative
AMBER   = "#e8b84b"       # warning / SMA50
PURPLE  = "#9d7fe0"       # SMA100
ORANGE  = "#d4804a"       # SMA200
WHITE   = "#f0f0f0"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
* {{ box-sizing:border-box; }}
body, .nicegui-content {{
    background:{BG} !important;
    font-family:'Inter',sans-serif;
    color:{TEXT};
}}
.sa-page {{ background:{BG}; min-height:100vh; }}

/* header */
.sa-header {{
    background:{PANEL};
    border-bottom:1px solid {BORDER2};
    padding:10px 20px;
}}
.sa-title {{
    font-size:14px; font-weight:600; letter-spacing:0.5px;
    color:{WHITE};
}}
.sa-subtitle {{ color:{MUTED}; font-size:11px; margin-top:1px; }}

/* tabs */
.sa-tab-bar {{
    background:{PANEL};
    border-bottom:1px solid {BORDER2};
    padding:0 20px;
    gap:0;
}}
.sa-tab {{
    color:{MUTED}; font-size:12px; font-weight:400;
    padding:8px 16px; cursor:pointer;
    border-bottom:2px solid transparent;
    transition:color 0.15s;
    text-transform:none; letter-spacing:0;
}}
.sa-tab:hover {{ color:{TEXT}; }}
.sa-tab.active {{ color:{WHITE}; border-bottom:2px solid {ACCENT}; font-weight:500; }}
.sa-tab.dim {{ color:{DIM}; cursor:default; }}

/* body */
.sa-body {{ padding:16px 20px; gap:12px; }}

/* panels */
.sa-panel {{
    background:{PANEL};
    border:1px solid {BORDER};
    border-radius:3px;
}}
.sa-panel-header {{
    padding:7px 12px;
    border-bottom:1px solid {BORDER};
    font-size:11px; font-weight:500;
    color:{MUTED}; letter-spacing:0.3px;
    text-transform:uppercase;
    display:flex; align-items:center; justify-content:space-between;
}}
.sa-panel-header span.hl {{ color:{TEXT}; }}

/* metric tiles */
.sa-metric {{
    background:{CARD};
    border:1px solid {BORDER};
    border-radius:2px;
    padding:8px 12px;
    min-width:100px;
}}
.sa-metric-label {{
    color:{MUTED}; font-size:10px; font-weight:400;
    text-transform:uppercase; letter-spacing:0.3px;
}}
.sa-metric-value {{
    color:{WHITE}; font-size:15px; font-weight:500;
    margin-top:2px; font-variant-numeric:tabular-nums;
}}
.sa-metric-sub {{ color:{MUTED}; font-size:10px; margin-top:1px; }}

/* inputs */
.sa-input .q-field__control {{
    background:{CARD} !important;
    border:1px solid {BORDER2} !important;
    border-radius:2px !important;
}}
.sa-input .q-field__native {{
    color:{TEXT} !important;
    font-family:'Inter',sans-serif !important;
    font-size:13px !important;
}}
.sa-input .q-field__label {{ color:{MUTED} !important; font-size:12px !important; }}
.sa-input.q-field--focused .q-field__control {{
    border-color:{ACCENT} !important;
}}

/* buttons */
.sa-btn {{
    background:{ACCENT} !important; color:#000 !important;
    font-family:'Inter',sans-serif !important;
    font-size:12px !important; font-weight:600 !important;
    border-radius:2px !important; letter-spacing:0.3px !important;
    min-height:34px !important;
}}
.sa-btn:hover {{ background:#5aaeff !important; }}
.sa-period-btn {{
    background:transparent !important; color:{MUTED} !important;
    border:1px solid {BORDER2} !important;
    font-family:'Inter',sans-serif !important;
    font-size:11px !important; padding:3px 9px !important;
    border-radius:2px !important; min-height:24px !important;
    font-weight:400 !important;
}}
.sa-period-btn.active {{
    background:{ACCENT}18 !important; color:{ACCENT} !important;
    border-color:{ACCENT} !important; font-weight:500 !important;
}}

/* score bars */
.score-row {{ display:flex; align-items:center; padding:4px 0; border-bottom:1px solid {BORDER}; gap:8px; }}
.score-lbl {{ color:{MUTED}; font-size:10px; width:100px; flex-shrink:0; }}
.score-track {{ flex:1; height:4px; background:{BORDER2}; border-radius:1px; overflow:hidden; }}
.score-fill  {{ height:100%; border-radius:1px; }}
.score-val   {{ font-size:11px; width:18px; text-align:right; font-variant-numeric:tabular-nums; }}
.score-cmp   {{ font-size:10px; color:{MUTED}; width:40px; text-align:right; font-variant-numeric:tabular-nums; }}

/* empty state */
.empty-state {{
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    height:380px; gap:10px;
}}

/* summary */
.summary-box {{
    border-left:2px solid {BORDER2};
    padding:10px 14px;
    color:{TEXT}; font-size:12px; line-height:1.65;
}}
.case-box {{
    border-top:1px solid {BORDER};
    padding:8px 0; margin-top:6px;
}}
.topic-tag {{
    display:inline-block;
    border:1px solid {BORDER2};
    color:{MUTED}; font-size:10px;
    padding:1px 7px; border-radius:2px;
    margin:2px;
}}
</style>
"""

# ── plotly base ───────────────────────────────────────────────────────────────
def base_layout(**kw):
    d = dict(
        paper_bgcolor=PANEL, plot_bgcolor=CARD,
        font=dict(family="Inter, sans-serif", color=MUTED, size=11),
        margin=dict(l=52, r=16, t=24, b=36),
        xaxis=dict(showgrid=True, gridcolor=BORDER, gridwidth=0.5,
                   showline=True, linecolor=BORDER2,
                   tickfont=dict(color=MUTED, size=10), zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=BORDER, gridwidth=0.5,
                   showline=True, linecolor=BORDER2,
                   tickfont=dict(color=MUTED, size=10), zeroline=False),
    )
    d.update(kw)
    return d


# ── data helpers ──────────────────────────────────────────────────────────────
def get_stock_info(ticker):
    r = db().table("stock_universe").select("*").eq("ticker", ticker.upper()).limit(1).execute().data
    return r[0] if r else None

def get_prices(stock_id, days):
    from_date = (date.today() - timedelta(days=days)).isoformat()
    return db().table("stock_prices").select("date,price,volume").eq("stock_id", stock_id).gte("date", from_date).order("date").execute().data

def get_sma_history(stock_id, days):
    # fetch 200 extra trading-day equivalent calendar days for accurate SMA200
    from_date = (date.today() - timedelta(days=days + 300)).isoformat()
    return db().table("stock_prices").select("date,price").eq("stock_id", stock_id).gte("date", from_date).order("date").execute().data

def get_technicals(stock_id):
    r = db().table("stock_technicals").select("*").eq("stock_id", stock_id).limit(1).execute().data
    return r[0] if r else None

def get_earnings_history(stock_id):
    return db().table("earnings").select("*").eq("stock_id", stock_id).not_.is_("eps_actual", "null").order("date").execute().data

def get_transcript(stock_id):
    r = db().table("earnings_transcripts").select("*").eq("stock_id", stock_id).not_.is_("sentiment_score", "null").order("year", desc=True).order("quarter", desc=True).limit(1).execute().data
    return r[0] if r else None

def get_sector_sentiment(sector, year, quarter):
    r = db().table("sector_sentiment_matrix").select("*").eq("sector", sector).eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_industry_sentiment(industry, year, quarter):
    r = db().table("industry_sentiment_matrix").select("*").eq("industry", industry).eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_tickers_in_category(field, value):
    """Return list of {ticker, name} for all active stocks in a category."""
    r = db().table("stock_universe").select("ticker,name").eq(field, value).eq("active", True).order("ticker").execute().data
    return r or []

def get_sector_vol(sector):
    """Get sector avg hvol for all windows."""
    r = db().table("sector_volatility_matrix").select(
        "avg_hvol_10d,avg_hvol_20d,avg_hvol_30d,avg_hvol_60d,avg_hvol_90d,avg_hvol_180d,avg_hvol_252d"
    ).eq("sector", sector).limit(1).execute().data
    return r[0] if r else None

def get_industry_vol(industry):
    """Get industry avg hvol for all windows."""
    r = db().table("industry_volatility_matrix").select(
        "avg_hvol_10d,avg_hvol_20d,avg_hvol_30d,avg_hvol_60d,avg_hvol_90d,avg_hvol_180d,avg_hvol_252d"
    ).eq("industry", industry).limit(1).execute().data
    return r[0] if r else None

def get_stock_returns(stock_id, ticker):
    """Compute 1W, 1M, 2M, 3M, 6M returns from stock_prices."""
    from datetime import date, timedelta
    today = date.today()

    def price_on(target):
        r = db().table("stock_prices").select("price,date").eq("stock_id", stock_id)            .lte("date", target.isoformat()).order("date", desc=True).limit(1).execute().data
        return r[0]["price"] if r else None

    latest_r = db().table("stock_prices").select("price,date").eq("stock_id", stock_id)        .order("date", desc=True).limit(1).execute().data
    if not latest_r:
        return None
    latest = latest_r[0]["price"]

    def ret(days=None, months=None):
        if months:
            m = today.month - months
            y = today.year
            while m <= 0:
                m += 12; y -= 1
            try:    target = today.replace(year=y, month=m)
            except: import calendar; target = today.replace(year=y, month=m, day=calendar.monthrange(y,m)[1])
        else:
            target = today - timedelta(days=days)
        p = price_on(target)
        return round((latest - p) / p * 100, 2) if p and p > 0 else None

    return {"1W": ret(days=7), "1M": ret(months=1), "2M": ret(months=2),
            "3M": ret(months=3), "6M": ret(months=6)}

def get_sector_returns(sector):
    r = db().table("sector_returns").select(
        "avg_return_1w,avg_return_1m,avg_return_2m,avg_return_3m,avg_return_6m"
    ).eq("sector", sector).limit(1).execute().data
    return r[0] if r else None

def get_industry_returns(industry):
    r = db().table("industry_returns").select(
        "avg_return_1w,avg_return_1m,avg_return_2m,avg_return_3m,avg_return_6m"
    ).eq("industry", industry).limit(1).execute().data
    return r[0] if r else None

def get_earnings_dates(stock_id):
    """Return last earnings date, next earnings date (future, eps_actual=null), and latest transcript date."""
    # last actual earnings
    last_r = db().table("earnings").select("date").eq("stock_id", stock_id)        .not_.is_("eps_actual", "null").order("date", desc=True).limit(1).execute().data
    last_date = last_r[0]["date"][:10] if last_r else None

    # next earnings (future estimate — eps_actual is null)
    next_r = db().table("earnings").select("date").eq("stock_id", stock_id)        .is_("eps_actual", "null").order("date").limit(1).execute().data
    next_date = next_r[0]["date"][:10] if next_r else None

    # latest transcript date
    tr_r = db().table("earnings_transcripts").select("earnings_date,year,quarter")        .eq("stock_id", stock_id).not_.is_("transcript_text", "null")        .order("year", desc=True).order("quarter", desc=True).limit(1).execute().data
    if tr_r:
        t = tr_r[0]
        tr_date = t.get("earnings_date") or f"Q{t['quarter']} {t['year']}"
        if tr_date and len(tr_date) > 10:
            tr_date = tr_date[:10]
    else:
        tr_date = None

    return last_date, next_date, tr_date

def get_live_quote(symbol: str) -> dict | None:
    """
    Fetch:
      - latest real-time price via /stable/pre-post-market-trade (or /stable/quote)
      - aftermarket bid/ask via /stable/aftermarket-quote
    Returns dict with keys: price, prev_close, chg, chg_pct, am_price, am_chg, am_pct, am_time
    """
    result = {}

    # ── real-time / latest trade price ────────────────────────────────────────
    for endpoint in [
        f"{FMP_BASE}/pre-post-market-trade",
        f"{FMP_BASE}/quote-short",
    ]:
        try:
            r = requests.get(endpoint, params={"symbol": symbol, "apikey": FMP_API_KEY}, timeout=8)
            r.raise_for_status()
            data = r.json()
            q = data[0] if isinstance(data, list) and data else None
            if q:
                price = q.get("price") or q.get("lastPrice") or q.get("ask")
                prev  = q.get("previousClose") or q.get("prevClose")
                if price:
                    result["price"]      = round(float(price), 2)
                    result["prev_close"] = round(float(prev), 2) if prev else None
                    if result["prev_close"]:
                        result["chg"]     = round(result["price"] - result["prev_close"], 2)
                        result["chg_pct"] = round(result["chg"] / result["prev_close"] * 100, 2)
                    break
        except Exception:
            continue

    # ── aftermarket bid/ask ───────────────────────────────────────────────────
    try:
        r = requests.get(f"{FMP_BASE}/aftermarket-quote",
            params={"symbol": symbol, "apikey": FMP_API_KEY}, timeout=8)
        r.raise_for_status()
        data = r.json()
        q = data[0] if isinstance(data, list) and data else None
        if q:
            bid, ask = q.get("bidPrice"), q.get("askPrice")
            if bid and ask:
                am_price = round((float(bid) + float(ask)) / 2, 2)
                base     = result.get("price") or result.get("prev_close")
                if base:
                    am_chg = round(am_price - float(base), 2)
                    am_pct = round(am_chg / float(base) * 100, 2)
                else:
                    am_chg = am_pct = None
                ts = q.get("timestamp", 0)
                if ts:
                    from datetime import datetime, timezone
                    am_time = datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime("%H:%M UTC")
                else:
                    am_time = ""
                result["am_price"] = am_price
                result["am_chg"]   = am_chg
                result["am_pct"]   = am_pct
                result["am_time"]  = am_time
    except Exception:
        pass

    return result if result else None

def get_universe_counts(sector, industry):
    """Return (sector_count, industry_count) of active tickers."""
    sec_r = db().table("stock_universe").select("id", count="exact").eq("sector", sector).eq("active", True).execute()
    ind_r = db().table("stock_universe").select("id", count="exact").eq("industry", industry).eq("active", True).execute()
    return (sec_r.count or 0), (ind_r.count or 0)

def get_latest_financials(stock_id):
    r = db().table("stock_financials").select("*").eq("stock_id", stock_id).not_.is_("net_profit_margin", "null").order("date", desc=True).limit(1).execute().data
    return r[0] if r else None

def get_sector_financials_latest(sector):
    """Get most recent quarter of sector financial averages."""
    r = db().table("sector_financials_matrix").select("*").eq("sector", sector).order("year", desc=True).order("quarter", desc=True).limit(1).execute().data
    return r[0] if r else None

def get_industry_financials_latest(industry):
    """Get most recent quarter of industry financial averages."""
    r = db().table("industry_financials_matrix").select("*").eq("industry", industry).order("year", desc=True).order("quarter", desc=True).limit(1).execute().data
    return r[0] if r else None


def get_sector_earnings(sector, year, quarter):
    r = db().table("sector_earnings_matrix").select("*").eq("sector", sector).eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_industry_earnings_avg(industry, year, quarter):
    r = db().table("industry_earnings_matrix").select("*").eq("industry", industry).eq("year", year).eq("quarter", quarter).limit(1).execute().data
    return r[0] if r else None

def get_sector_earnings_history(sector):
    """Fetch last 12 quarters of sector avg EPS surprise for chart comparison."""
    r = db().table("sector_earnings_matrix").select(
        "year,quarter,period_label,avg_eps_surprise_pct"
    ).eq("sector", sector).order("year", desc=True).order("quarter", desc=True).limit(12).execute().data
    return list(reversed(r)) if r else []

def get_industry_earnings_history(industry):
    """Fetch last 12 quarters of industry avg EPS surprise for chart comparison."""
    r = db().table("industry_earnings_matrix").select(
        "year,quarter,period_label,avg_eps_surprise_pct"
    ).eq("industry", industry).order("year", desc=True).order("quarter", desc=True).limit(12).execute().data
    return list(reversed(r)) if r else []


def get_sector_growth_history(sector):
    """Fetch last 12 quarters of sector avg EPS and revenue growth for chart."""
    r = db().table("sector_earnings_matrix").select(
        "year,quarter,period_label,avg_eps_growth_pct,avg_revenue_growth_pct"
    ).eq("sector", sector).order("year", desc=True).order("quarter", desc=True).limit(12).execute().data
    return list(reversed(r)) if r else []

def get_industry_growth_history(industry):
    """Fetch last 12 quarters of industry avg EPS and revenue growth for chart."""
    r = db().table("industry_earnings_matrix").select(
        "year,quarter,period_label,avg_eps_growth_pct,avg_revenue_growth_pct"
    ).eq("industry", industry).order("year", desc=True).order("quarter", desc=True).limit(12).execute().data
    return list(reversed(r)) if r else []

def compute_sma(prices, window):
    return [round(sum(prices[max(0,i-window+1):i+1])/min(i+1,window),4) if i>=window-1 else None for i in range(len(prices))]

def compute_yoy(earnings):
    by_date = {e["date"]: e for e in earnings}
    result  = []
    for e in earnings:
        d, eg, rg = date.fromisoformat(e["date"]), None, None
        for offset in range(270, 451, 30):
            prior = by_date.get((d - timedelta(days=offset)).isoformat())
            if prior:
                if prior.get("eps_actual") and prior["eps_actual"] != 0:
                    eg = round((e["eps_actual"] - prior["eps_actual"]) / abs(prior["eps_actual"]) * 100, 2)
                if prior.get("revenue_actual") and prior["revenue_actual"] != 0:
                    rg = round((e["revenue_actual"] - prior["revenue_actual"]) / abs(prior["revenue_actual"]) * 100, 2)
                break
        result.append({**e, "eps_growth": eg, "rev_growth": rg})
    return result


# ── chart builders ────────────────────────────────────────────────────────────
def build_price_chart(stock_id, ticker, days, price_target=None, pt_bull=None, pt_bear=None, news_events=None):
    # Fetch display window
    prices = get_prices(stock_id, days)
    if not prices:
        return go.Figure()

    dates  = [r["date"]  for r in prices]
    closes = [r["price"] for r in prices]
    vols   = [r["volume"] or 0 for r in prices]

    # For SMA calculation fetch extra history (200 extra days) and compute directly
    # This avoids relying on pre-computed SMA columns in Supabase
    sma_raw = get_sma_history(stock_id, days)
    all_p   = [r["price"] for r in sma_raw]
    all_d   = [r["date"]  for r in sma_raw]
    from_s  = prices[0]["date"]
    idx     = [i for i, d in enumerate(all_d) if d >= from_s]

    def _sma(window):
        full = compute_sma(all_p, window)
        return [full[i] for i in idx]

    sma20  = _sma(20)
    sma50  = _sma(50)
    sma100 = _sma(100)
    sma200 = _sma(200)

    pct    = round((closes[-1]-closes[0])/closes[0]*100,2) if closes[0] else 0
    lcolor = GREEN if pct >= 0 else RED

    # meaningful y-axis range — pad 3% above/below price range
    valid  = [c for c in closes if c]
    lo     = min(valid) * 0.97
    hi     = max(valid) * 1.03
    # include SMAs in range
    for sma in [sma20, sma50, sma100, sma200]:
        vals = [v for v in sma if v]
        if vals:
            lo = min(lo, min(vals) * 0.97)
            hi = max(hi, max(vals) * 1.03)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, row_heights=[0.78, 0.22])

    # price line
    fig.add_trace(go.Scatter(
        x=dates, y=closes, name="Price",
        line=dict(color=lcolor, width=1.5),
        hovertemplate="<b>%{x}</b>  %{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # SMAs
    for sma, name, color, w in [
        (sma20,"SMA 20",ACCENT,1.0),
        (sma50,"SMA 50",AMBER,1.0),
        (sma100,"SMA 100",PURPLE,1.0),
        (sma200,"SMA 200",ORANGE,1.2),
    ]:
        fig.add_trace(go.Scatter(
            x=dates, y=sma, name=name,
            line=dict(color=color, width=w),
            opacity=0.8,
            hovertemplate=f"{name}: %{{y:.2f}}<extra></extra>",
        ), row=1, col=1)

    # volume bars
    vol_colors = [GREEN if i==0 or closes[i]>=closes[i-1] else RED for i in range(len(closes))]
    fig.add_trace(go.Bar(
        x=dates, y=vols, name="Volume",
        marker_color=vol_colors, marker_opacity=0.4,
        hovertemplate="%{y:,.0f}<extra></extra>",
        showlegend=False,
    ), row=2, col=1)

    # ── price target lines (if research available) ───────────────────────
    def _pt_label(fig, y, label, color, dash, width):
        """Draw a horizontal line with a solid labelled box anchored inside the plot."""
        fig.add_hline(
            y=y, row=1, col=1,
            line=dict(color=color, width=width, dash=dash),
        )
        fig.add_annotation(
            y=y, x=0.99, xref="paper", yref="y",
            text=f"<b>{label}</b>",
            showarrow=False,
            xanchor="right",
            yanchor="middle",
            font=dict(color="#0a0e1a", size=10, family="JetBrains Mono, monospace"),
            bgcolor=color,
            bordercolor=color,
            borderwidth=1,
            borderpad=4,
            opacity=0.95,
        )

    if price_target:
        _pt_label(fig, price_target, f"PT  {price_target:,.0f}", AMBER, "dash", 1.2)
    if pt_bull:
        _pt_label(fig, pt_bull,      f"Bull {pt_bull:,.0f}",     GREEN, "dot",  0.8)
    if pt_bear:
        _pt_label(fig, pt_bear,      f"Bear {pt_bear:,.0f}",     RED,   "dot",  0.8)

    fig.update_layout(
        **base_layout(
            height=400,
            hovermode="closest",
            legend=dict(
                orientation="h", x=0, y=1.01,
                bgcolor="rgba(0,0,0,0)",
                font=dict(size=10, color=MUTED),
                itemsizing="constant",
            ),
        )
    )

    # price axis — meaningful range, no zero
    fig.update_yaxes(range=[lo, hi], row=1, col=1,
        showgrid=True, gridcolor=BORDER, tickfont=dict(color=MUTED, size=10),
        tickformat=",.2f")
    # volume axis
    fig.update_yaxes(row=2, col=1,
        showgrid=False, tickfont=dict(color=DIM, size=9),
        tickformat=".2s")
    fig.update_xaxes(
        showgrid=True, gridcolor=BORDER,
        tickfont=dict(color=MUTED, size=10),
        rangeslider=dict(visible=False),
    )

    # ── news event markers ───────────────────────────────────────────────────
    if news_events:
        from datetime import datetime as _dt
        date_set = set(dates)
        ev_dates, ev_prices, ev_custom, ev_colors = [], [], [], []

        for ev in news_events:
            d = str(ev.get("trade_date", ""))[:10]
            if d not in date_set:
                try:
                    ev_dt   = _dt.fromisoformat(d)
                    closest = min(dates, key=lambda x: abs((_dt.fromisoformat(x) - ev_dt).days))
                    if abs((_dt.fromisoformat(closest) - ev_dt).days) > 3:
                        continue
                    d = closest
                except Exception:
                    continue
            idx_d = dates.index(d)
            price = closes[idx_d]
            chg   = float(ev.get("change_pct", 0))
            conf  = int(ev.get("confidence", 0))
            expl  = (ev.get("explanation") or "No explanation available.")
            sign  = "+" if chg >= 0 else ""
            ev_dates.append(d)
            ev_prices.append(price)          # pin to exact close price
            ev_custom.append(f"{d}  {sign}{chg:.2f}%  ·  confidence {conf}/100<br>{expl}")
            ev_colors.append(GREEN if chg >= 0 else RED)

        if ev_dates:
            # wrap explanation at ~40 chars per line → narrow box
            wrapped = []
            for raw in ev_custom:
                header, _, body = raw.partition("<br>")
                words = body.split()
                lines, cur = [], []
                for w in words:
                    cur.append(w)
                    if len(" ".join(cur)) >= 40:
                        lines.append(" ".join(cur))
                        cur = []
                if cur:
                    lines.append(" ".join(cur))
                wrapped.append(header + "<br>" + "<br>".join(lines))

            # circle background
            fig.add_trace(go.Scatter(
                x=ev_dates,
                y=ev_prices,
                mode="markers",
                marker=dict(
                    symbol="circle",
                    size=18,
                    color="#2e5080",
                    line=dict(color="#5b8ec4", width=1.5),
                    opacity=0.92,
                ),
                hoverinfo="skip",
                showlegend=False,
            ), row=1, col=1)
            # ℹ icon on top — this trace carries the tooltip
            fig.add_trace(go.Scatter(
                x=ev_dates,
                y=ev_prices,
                mode="markers+text",
                marker=dict(
                    symbol="circle",
                    size=18,
                    color="rgba(0,0,0,0)",
                    line=dict(color="rgba(0,0,0,0)", width=0),
                ),
                text=["𝒊" for _ in ev_dates],
                textposition="middle center",
                textfont=dict(size=11, color="#ffffff", family="Georgia,serif"),
                name="News",
                customdata=wrapped,
                hovertemplate="%{customdata}<extra></extra>",
                hoverlabel=dict(
                    bgcolor="#0d1526",
                    bordercolor="#2a3a55",
                    font=dict(color="#c8d8f0", size=11, family="Sora,sans-serif"),
                    align="left",
                    namelength=0,
                ),
                showlegend=False,
            ), row=1, col=1)

    return fig


def fetch_news_events(ticker: str, days: int) -> list:
    """Fetch price_move_explanations with confidence >= 70 for the chart window."""
    from datetime import date as _date, timedelta
    import logging as _log
    cutoff = (_date.today() - timedelta(days=days)).isoformat()
    try:
        rows = (
            db()
            .table("price_move_explanations")
            .select("trade_date,change_pct,explanation,confidence")
            .eq("ticker", ticker)
            .gte("confidence", 70)
            .gte("trade_date", cutoff)
            .order("trade_date", desc=False)
            .execute()
            .data
        )
        _log.getLogger(__name__).info(f"fetch_news_events {ticker}: {len(rows or [])} events")
        return rows or []
    except Exception as e:
        _log.getLogger(__name__).warning(f"fetch_news_events failed for {ticker}: {e}")
        return []


def build_growth_chart(earnings, sec_hist=None, ind_hist=None):
    """
    Two-panel line chart:
      Top:    EPS Growth % YoY — stock vs sector avg vs industry avg
      Bottom: Revenue Growth % YoY — stock vs sector avg vs industry avg
    Uses eps_growth_pct / rev_growth_pct from earnings table (pre-computed).
    Falls back to on-the-fly YoY if columns are null.
    """
    if not earnings:
        return go.Figure()

    # use pre-computed growth if available, else compute on the fly
    enriched = compute_yoy(earnings)[-12:]
    dates    = [e["date"] for e in enriched]

    def get_growth(e, key_stored, key_computed):
        v = e.get(key_stored)
        if v is not None:
            return float(v)
        return e.get(key_computed)

    eps_g = [get_growth(e, "eps_growth_pct", "eps_growth") for e in enriched]
    rev_g = [get_growth(e, "rev_growth_pct", "rev_growth") for e in enriched]

    # sector/industry series
    s_dates   = [r["period_label"] for r in sec_hist]  if sec_hist else []
    s_eps_g   = [r.get("avg_eps_growth_pct")     for r in sec_hist]  if sec_hist else []
    s_rev_g   = [r.get("avg_revenue_growth_pct") for r in sec_hist]  if sec_hist else []
    i_dates   = [r["period_label"] for r in ind_hist]  if ind_hist else []
    i_eps_g   = [r.get("avg_eps_growth_pct")     for r in ind_hist]  if ind_hist else []
    i_rev_g   = [r.get("avg_revenue_growth_pct") for r in ind_hist]  if ind_hist else []

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=False,
        vertical_spacing=0.08, row_heights=[0.50, 0.50],
        subplot_titles=["EPS Growth % YoY", "Revenue Growth % YoY"],
    )

    # ── EPS Growth — top panel ────────────────────────────────────────────────
    if any(v is not None for v in i_eps_g):
        fig.add_trace(go.Scatter(x=i_dates, y=i_eps_g, name="Industry EPS",
            line=dict(color=ORANGE, width=1.2, dash="dot"),
            mode="lines+markers", marker=dict(size=3),
            hovertemplate="Industry EPS %{x}: %{y:.1f}%<extra></extra>"), row=1, col=1)
    if any(v is not None for v in s_eps_g):
        fig.add_trace(go.Scatter(x=s_dates, y=s_eps_g, name="Sector EPS",
            line=dict(color=ACCENT, width=1.2, dash="dash"),
            mode="lines+markers", marker=dict(size=3),
            hovertemplate="Sector EPS %{x}: %{y:.1f}%<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=dates, y=eps_g, name="EPS Growth",
        line=dict(color=GREEN, width=2),
        mode="lines+markers", marker=dict(size=5, color=GREEN),
        hovertemplate="EPS Growth %{x}: %{y:.1f}%<extra></extra>"), row=1, col=1)

    # ── Revenue Growth — bottom panel ─────────────────────────────────────────
    if any(v is not None for v in i_rev_g):
        fig.add_trace(go.Scatter(x=i_dates, y=i_rev_g, name="Industry Rev",
            line=dict(color=ORANGE, width=1.2, dash="dot"),
            mode="lines+markers", marker=dict(size=3),
            hovertemplate="Industry Rev %{x}: %{y:.1f}%<extra></extra>"), row=2, col=1)
    if any(v is not None for v in s_rev_g):
        fig.add_trace(go.Scatter(x=s_dates, y=s_rev_g, name="Sector Rev",
            line=dict(color=ACCENT, width=1.2, dash="dash"),
            mode="lines+markers", marker=dict(size=3),
            hovertemplate="Sector Rev %{x}: %{y:.1f}%<extra></extra>"), row=2, col=1)
    fig.add_trace(go.Scatter(x=dates, y=rev_g, name="Rev Growth",
        line=dict(color=AMBER, width=2),
        mode="lines+markers", marker=dict(size=5, color=AMBER),
        hovertemplate="Rev Growth %{x}: %{y:.1f}%<extra></extra>"), row=2, col=1)

    fig.add_hline(y=0, line_color=BORDER2, line_width=0.8, row=1, col=1)
    fig.add_hline(y=0, line_color=BORDER2, line_width=0.8, row=2, col=1)

    for ann in fig.layout.annotations:
        ann.font.color = MUTED
        ann.font.size  = 10

    fig.update_layout(**base_layout(
        height=480, hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.06, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10, color=MUTED)),
    ))
    fig.update_yaxes(showgrid=True, gridcolor=BORDER, tickfont=dict(color=MUTED, size=10),
                     ticksuffix="%", zeroline=False)
    fig.update_xaxes(showgrid=False, tickfont=dict(color=MUTED, size=10))
    return fig


def build_earnings_chart(earnings):
    """
    Two-panel chart:
      Top:    Quarterly EPS actual (bars) + EPS estimated (line)
      Bottom: Quarterly Revenue actual in $B (bars)
    Last 12 quarters.
    """
    if not earnings:
        return go.Figure()

    recent = earnings[-12:]
    dates  = [e["date"]                for e in recent]
    eps_a  = [e.get("eps_actual")      for e in recent]
    eps_e  = [e.get("eps_estimated")   for e in recent]
    rev_a  = [round(e["revenue_actual"] / 1e9, 2) if e.get("revenue_actual") else None for e in recent]
    rev_e  = [round(e["revenue_estimated"] / 1e9, 2) if e.get("revenue_estimated") else None for e in recent]

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.06, row_heights=[0.50, 0.50],
        subplot_titles=["EPS  —  Actual vs Estimated ($)", "Revenue  —  Actual vs Estimated ($B)"],
    )

    # ── EPS bars (actual) ─────────────────────────────────────────────────────
    beat_colors = []
    for a, e in zip(eps_a, eps_e):
        if a is None:
            beat_colors.append(DIM)
        elif e is not None and a >= e:
            beat_colors.append(GREEN)
        else:
            beat_colors.append(RED)

    fig.add_trace(go.Bar(
        x=dates, y=eps_a, name="EPS Actual",
        marker_color=beat_colors, marker_opacity=0.85,
        hovertemplate="<b>%{x}</b><br>EPS Actual: $%{y:.2f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=eps_e, name="EPS Est.",
        mode="lines+markers",
        line=dict(color=AMBER, width=1.5, dash="dash"),
        marker=dict(size=5, color=AMBER, symbol="diamond"),
        hovertemplate="EPS Est.: $%{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # ── Revenue bars — use ACCENT blue to distinguish from EPS green/red ──────
    rev_beat_colors = []
    for a, e in zip(rev_a, rev_e):
        if a is None:
            rev_beat_colors.append(DIM)
        elif e is not None and a >= e:
            rev_beat_colors.append(ACCENT)
        else:
            rev_beat_colors.append(ORANGE)

    fig.add_trace(go.Bar(
        x=dates, y=rev_a, name="Revenue Actual",
        marker_color=rev_beat_colors, marker_opacity=0.85,
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:.2f}B<extra></extra>",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=rev_e, name="Revenue Est.",
        mode="lines+markers",
        line=dict(color=AMBER, width=1.5, dash="dash"),
        marker=dict(size=5, color=AMBER, symbol="diamond"),
        hovertemplate="Rev Est.: $%{y:.2f}B<extra></extra>",
    ), row=2, col=1)

    for ann in fig.layout.annotations:
        ann.font.color = MUTED
        ann.font.size  = 10

    fig.update_layout(**base_layout(
        height=480, hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.06, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10, color=MUTED)),
    ))
    fig.update_yaxes(showgrid=True, gridcolor=BORDER, tickfont=dict(color=MUTED, size=10),
                     zeroline=False, tickprefix="$", row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor=BORDER, tickfont=dict(color=MUTED, size=10),
                     zeroline=False, tickprefix="$", ticksuffix="B", row=2, col=1)
    fig.update_xaxes(showgrid=False, tickfont=dict(color=MUTED, size=10))
    return fig


def build_returns_chart(stock_ret, sec_ret, ind_ret, ticker):
    """
    Grouped bar chart: stock vs sector avg vs industry avg for 1W/1M/2M/3M/6M returns.
    """
    periods = ["1W", "1M", "2M", "3M", "6M"]
    s_keys  = ["avg_return_1w","avg_return_1m","avg_return_2m","avg_return_3m","avg_return_6m"]
    t_vals  = [stock_ret.get(p) if stock_ret else None for p in periods]
    s_vals  = [sec_ret.get(k)   if sec_ret  else None for k in s_keys]
    i_vals  = [ind_ret.get(k)   if ind_ret  else None for k in s_keys]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Industry avg", x=periods, y=i_vals,
        marker_color=ORANGE, marker_opacity=0.55,
        hovertemplate="Industry %{x}: %{y:+.2f}%<extra></extra>"))
    fig.add_trace(go.Bar(name="Sector avg", x=periods, y=s_vals,
        marker_color=ACCENT, marker_opacity=0.65,
        hovertemplate="Sector %{x}: %{y:+.2f}%<extra></extra>"))
    fig.add_trace(go.Bar(name=ticker, x=periods, y=t_vals,
        marker_color=[GREEN if (v or 0)>=0 else RED for v in t_vals],
        marker_opacity=0.9,
        hovertemplate=ticker + " %{x}: %{y:+.2f}%<extra></extra>"))
    fig.add_hline(y=0, line_color=BORDER2, line_width=0.8)
    fig.update_layout(**base_layout(
        height=200, barmode="group", bargap=0.25, bargroupgap=0.05,
        hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.14, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10, color=MUTED)),
    ))
    fig.update_yaxes(showgrid=True, gridcolor=BORDER, ticksuffix="%",
                     tickfont=dict(color=MUTED, size=10), zeroline=False)
    fig.update_xaxes(showgrid=False, tickfont=dict(color=MUTED, size=10))
    return fig


def build_volatility_chart(tech, sec_vol=None, ind_vol=None):
    if not tech:
        return go.Figure()
    labels = ["10d","20d","30d","60d","90d","180d","252d"]
    t_keys = ["hvol_10d","hvol_20d","hvol_30d","hvol_60d","hvol_90d","hvol_180d","hvol_252d"]
    s_keys = ["avg_hvol_10d","avg_hvol_20d","avg_hvol_30d","avg_hvol_60d","avg_hvol_90d","avg_hvol_180d","avg_hvol_252d"]

    t_vals = [tech.get(k)        for k in t_keys]
    s_vals = [sec_vol.get(k) if sec_vol else None for k in s_keys]
    i_vals = [ind_vol.get(k) if ind_vol else None for k in s_keys]

    fig = go.Figure()

    # industry line
    if any(v is not None for v in i_vals):
        fig.add_trace(go.Scatter(
            x=labels, y=i_vals, name="Industry avg",
            mode="lines+markers",
            line=dict(color=ORANGE, width=1.2, dash="dot"),
            marker=dict(color=ORANGE, size=4),
            hovertemplate="Industry %{x}: %{y:.1f}%<extra></extra>",
        ))

    # sector line
    if any(v is not None for v in s_vals):
        fig.add_trace(go.Scatter(
            x=labels, y=s_vals, name="Sector avg",
            mode="lines+markers",
            line=dict(color=ACCENT, width=1.2, dash="dash"),
            marker=dict(color=ACCENT, size=4),
            hovertemplate="Sector %{x}: %{y:.1f}%<extra></extra>",
        ))

    # stock line — on top
    fig.add_trace(go.Scatter(
        x=labels, y=t_vals, name="Stock",
        mode="lines+markers",
        line=dict(color=GREEN, width=2),
        marker=dict(color=GREEN, size=5),
        hovertemplate="Stock %{x}: %{y:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=CARD,
        font=dict(family="Inter, sans-serif", color=MUTED, size=10),
        height=210, showlegend=True,
        legend=dict(orientation="h", x=0, y=1.12, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10, color=MUTED)),
        margin=dict(l=52, r=16, t=28, b=32),
        yaxis=dict(showgrid=True, gridcolor=BORDER, ticksuffix="%",
                   tickfont=dict(color=MUTED, size=10), zeroline=False),
        xaxis=dict(showgrid=False, tickfont=dict(color=MUTED, size=10)),
        hovermode="x unified",
    )
    return fig


def build_valuation_spider(fin, sec_f, ind_f, sector, industry):
    """
    Spider chart: valuation + profitability vs sector and industry.
    Axes: P/E, P/S, P/B, Gross Margin, Net Margin, ROE, ROA, Debt/Equity
    All normalised 0-10 relative to peers. Lower valuation ratios score higher.
    """
    if not fin:
        return go.Figure()

    def safe(d, k, mult=1):
        v = d.get(k) if d else None
        return round(v * mult, 4) if v is not None else None

    def norm(val, lo_ref, hi_ref, invert=False):
        """Normalise val between lo_ref and hi_ref to 0-10."""
        if val is None or hi_ref == lo_ref:
            return 5.0
        v = max(lo_ref, min(hi_ref, val))
        n = (v - lo_ref) / (hi_ref - lo_ref) * 10
        return round(10 - n if invert else n, 2)

    # collect all three data points per metric
    metrics = [
        # (label, t_val, s_val, i_val, invert, lo, hi)
        ("P/E",          safe(fin,"pe_ratio"),             safe(sec_f,"avg_pe_ratio"),          safe(ind_f,"avg_pe_ratio"),          True,  0,  80),
        ("P/S",          safe(fin,"price_to_sales"),       safe(sec_f,"avg_price_to_sales"),     safe(ind_f,"avg_price_to_sales"),     True,  0,  40),
        ("P/B",          safe(fin,"price_to_book"),        safe(sec_f,"avg_price_to_book"),      safe(ind_f,"avg_price_to_book"),      True,  0,  30),
        ("Gross Margin", safe(fin,"gross_profit_margin",100), safe(sec_f,"avg_gross_margin_pct"), safe(ind_f,"avg_gross_margin_pct"),  False, 0, 100),
        ("Net Margin",   safe(fin,"net_profit_margin",100),  safe(sec_f,"avg_net_margin_pct"),   safe(ind_f,"avg_net_margin_pct"),    False,-20,  60),
        ("ROE",          safe(fin,"roe",100),              safe(sec_f,"avg_roe_pct"),            safe(ind_f,"avg_roe_pct"),            False,-20,  60),
        ("ROA",          safe(fin,"roa",100),              safe(sec_f,"avg_roa_pct"),            safe(ind_f,"avg_roa_pct"),            False,  0,  30),
        ("Debt/Equity",  safe(fin,"debt_to_equity"),       safe(sec_f,"avg_debt_to_equity"),     safe(ind_f,"avg_debt_to_equity"),     True,  0,   5),
    ]

    labels  = [m[0] for m in metrics]
    t_scores, s_scores, i_scores = [], [], []
    t_raw,    s_raw,    i_raw    = [], [], []

    for label, tv, sv, iv, invert, lo, hi in metrics:
        # use actual min/max of the three values to set range if fixed range too tight
        vals = [v for v in [tv, sv, iv] if v is not None]
        if vals:
            lo = min(lo, min(vals))
            hi = max(hi, max(vals))
        t_scores.append(norm(tv, lo, hi, invert))
        s_scores.append(norm(sv, lo, hi, invert))
        i_scores.append(norm(iv, lo, hi, invert))
        sfx = "x" if label in ("P/E","P/S","P/B","Debt/Equity") else "%"
        t_raw.append(f"{tv:.1f}{sfx}" if tv is not None else "N/A")
        s_raw.append(f"{sv:.1f}{sfx}" if sv is not None else "N/A")
        i_raw.append(f"{iv:.1f}{sfx}" if iv is not None else "N/A")

    cl = lambda v: v + [v[0]]

    fig = go.Figure()
    if any(v is not None for v in [safe(ind_f,"avg_pe_ratio")]):
        fig.add_trace(go.Scatterpolar(
            r=cl(i_scores), theta=cl(labels), fill="toself",
            fillcolor="rgba(212,128,74,0.06)",
            line=dict(color=ORANGE, width=1, dash="dot"),
            name="Industry",
            customdata=cl(i_raw),
            hovertemplate="<b>%{theta}</b>  Industry: %{customdata}<extra></extra>",
        ))
    if any(v is not None for v in [safe(sec_f,"avg_pe_ratio")]):
        fig.add_trace(go.Scatterpolar(
            r=cl(s_scores), theta=cl(labels), fill="toself",
            fillcolor="rgba(74,158,255,0.06)",
            line=dict(color=ACCENT, width=1.2, dash="dash"),
            name="Sector",
            customdata=cl(s_raw),
            hovertemplate="<b>%{theta}</b>  Sector: %{customdata}<extra></extra>",
        ))
    fig.add_trace(go.Scatterpolar(
        r=cl(t_scores), theta=cl(labels), fill="toself",
        fillcolor="rgba(0,192,118,0.10)",
        line=dict(color=GREEN, width=1.8),
        name="Stock",
        customdata=cl(t_raw),
        hovertemplate="<b>%{theta}</b>  Stock: %{customdata}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=PANEL,
        font=dict(family="Inter, sans-serif", color=MUTED, size=10),
        polar=dict(
            bgcolor=CARD,
            radialaxis=dict(visible=True, range=[0,10], tickvals=[2,4,6,8,10],
                tickfont=dict(size=9, color=DIM), gridcolor=BORDER,
                linecolor=BORDER2, angle=90),
            angularaxis=dict(tickfont=dict(size=10, color=TEXT),
                gridcolor=BORDER, linecolor=BORDER2, direction="clockwise"),
        ),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center",
            font=dict(size=10, color=MUTED), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=36, r=36, t=20, b=60),
        height=340,
        annotations=[dict(
            text="Higher = better vs peers  ·  P/E, P/S, P/B, D/E inverted",
            x=0.5, y=-0.22, xref="paper", yref="paper",
            showarrow=False, font=dict(size=9, color=DIM), xanchor="center",
        )],
    )
    return fig


def build_spider_chart(transcript, sec_s, ind_s, sector, industry):
    categories = [
        ("Sentiment",    "sentiment_score",       "avg_sentiment",       False),
        ("Guidance",     "guidance_score",        "avg_guidance",        False),
        ("Confidence",   "confidence_score",      "avg_confidence",      False),
        ("Fwd Outlook",  "forward_outlook_score", "avg_forward_outlook", False),
        ("Innovation",   "innovation_score",      "avg_innovation",      False),
        ("Analyst Trust","analyst_trust_score",   "avg_analyst_trust",   False),
        ("Low Risk",     "risk_score",            "avg_risk",            True),
        ("Low Deflect",  "deflection_score",      "avg_deflection",      True),
        ("Low Hedge",    "hedge_score",           "avg_hedge",           True),
        ("Low Uncert",   "uncertainty_score",     "avg_uncertainty",     True),
    ]
    labels = [c[0] for c in categories]
    t_vals, s_vals, i_vals = [], [], []
    for _, t_key, s_key, inv in categories:
        t = transcript.get(t_key) or 0
        s = sec_s.get(s_key) if sec_s else None
        i = ind_s.get(s_key) if ind_s else None
        t_vals.append(round(10-t,2) if inv else t)
        s_vals.append(round(10-s,2) if inv and s else (s or 0))
        i_vals.append(round(10-i,2) if inv and i else (i or 0))

    cl = lambda v: v + [v[0]]
    fig = go.Figure()
    if ind_s:
        fig.add_trace(go.Scatterpolar(r=cl(i_vals), theta=cl(labels),
            fill="toself", fillcolor="rgba(212,128,74,0.06)",
            line=dict(color=ORANGE, width=1, dash="dot"),
            name=f"Industry"))
    if sec_s:
        fig.add_trace(go.Scatterpolar(r=cl(s_vals), theta=cl(labels),
            fill="toself", fillcolor="rgba(74,158,255,0.06)",
            line=dict(color=ACCENT, width=1.2, dash="dash"),
            name=f"Sector"))
    fig.add_trace(go.Scatterpolar(r=cl(t_vals), theta=cl(labels),
        fill="toself", fillcolor="rgba(0,192,118,0.10)",
        line=dict(color=GREEN, width=1.8),
        name="Stock",
        hovertemplate="<b>%{theta}</b>: %{r:.1f}/10<extra></extra>"))
    fig.update_layout(
        paper_bgcolor=PANEL,
        font=dict(family="Inter, sans-serif", color=MUTED, size=10),
        polar=dict(
            bgcolor=CARD,
            radialaxis=dict(visible=True, range=[0,10],
                tickvals=[2,4,6,8,10],
                tickfont=dict(size=9, color=DIM),
                gridcolor=BORDER, linecolor=BORDER2, angle=90),
            angularaxis=dict(
                tickfont=dict(size=10, color=TEXT),
                gridcolor=BORDER, linecolor=BORDER2,
                direction="clockwise")),
        legend=dict(orientation="h", y=-0.12, x=0.5, xanchor="center",
            font=dict(size=10, color=MUTED), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=36, r=36, t=16, b=50),
        height=320,
    )
    return fig


# ── state ─────────────────────────────────────────────────────────────────────
class S:
    period_days = 365
    info = tech = transcript = None
    earnings = []
    research_result = None   # None=idle, "running"=in progress, dict=done, Exception=error
    saved_research  = None   # cached saved report dict from Supabase
    research_result = None   # None = idle, dict = done, Exception = error


# ── page ──────────────────────────────────────────────────────────────────────
@ui.page("/")
async def main_page():
    ui.add_head_html(CSS)
    s = S()

    refs = dict(
        price_plot=None, earnings_plot=None,
        vol_plot=None, spider_plot=None,
        valuation_plot=None,
        returns_plot=None,
        growth_plot=None,
        popup_score_col=None,
        popup_summary_box=None,
        price_header=None,
        price_box=None,
        company_info=None,
        metrics_row=None, score_col=None,
        summary_box=None, ticker_label=None,
        tech_col=None, empty_state=None,
        charts_col=None, period_row=None,
        period_btns={},
    )

    # ── expand state — must be defined before UI layout so lambdas can close over it
    chart_heights  = {}
    chart_expanded = {}

    def toggle_expand(key, btn):
        """Toggle chart between normal and 2x height."""
        if key not in refs or refs[key] is None:
            return
        normal_h = chart_heights.get(key, 400)
        expanded = chart_expanded.get(key, False)
        new_h    = normal_h if expanded else normal_h * 2
        chart_expanded[key] = not expanded
        refs[key].style(f"width:100%;height:{new_h}px")
        new_icon = "fullscreen_exit" if not expanded else "fullscreen"
        btn.props(f"icon={new_icon}")

    # ── chart popup state ────────────────────────────────────────────────────────
    chart_heights = {}   # key -> normal height
    chart_figs    = {}   # key -> latest figure dict

    def toggle_expand(key, btn):
        """Open chart in a popup modal — sized to content, no empty space."""
        if key not in chart_figs:
            return

        # re-render figure at popup height so it fills exactly
        popup_h   = 780
        fig_dict  = dict(chart_figs[key])
        if "layout" in fig_dict:
            fig_dict["layout"] = dict(fig_dict["layout"])
            fig_dict["layout"]["height"] = popup_h

        title = key.replace("_plot", "").replace("_", " ").upper()

        # card sized exactly to header (40px) + chart (popup_h)
        total_h = popup_h + 40

        with ui.dialog() as dlg, ui.card().style(
            f"background:{PANEL};"
            f"border:1px solid {BORDER2};"
            f"border-radius:4px;"
            f"padding:0;"
            f"width:92vw;"
            f"max-width:1400px;"
            f"height:{total_h}px;"
            f"overflow:hidden;"
            f"display:flex;flex-direction:column;"
        ):
            # header row — fixed 40px
            with ui.row().classes("w-full items-center justify-between").style(
                f"height:40px;flex-shrink:0;"
                f"padding:0 16px;"
                f"border-bottom:1px solid {BORDER2};"
                f"background:{BG};"
            ):
                ui.label(title).style(
                    f"color:{TEXT};font-size:12px;font-weight:500;letter-spacing:0.5px"
                )
                ui.button(icon="close", on_click=dlg.close).props("flat dense round").style(
                    f"color:{MUTED}"
                )
            # chart fills remaining space exactly
            ui.plotly(fig_dict).style(
                f"width:100%;height:{popup_h}px;flex-shrink:0;"
            )
        dlg.open()

    with ui.column().classes("sa-page w-full"):

        # ── header ────────────────────────────────────────────────────────────
        with ui.row().classes("sa-header w-full items-center justify-between"):
            with ui.column().style("gap:1px"):
                ui.label("AGENTIC PORTFOLIO MANAGEMENT").classes("sa-title")
                ui.label("Equity Analytics  ·  AI Scoring  ·  Portfolio Intelligence").classes("sa-subtitle")
            with ui.row().classes("items-center gap-2"):
                ticker_input = ui.input(placeholder="Ticker…").props(
                    "outlined dense dark").classes("sa-input").style("width:140px")
                search_btn    = ui.button("Analyse").classes("sa-btn")
                research_btn      = ui.button("Research", icon="psychology").classes("sa-btn").style("display:none")
                view_research_btn = ui.button("View Research", icon="menu_book").classes("sa-btn").style("display:none;background:#2a3a2a;border:1px solid #00c076")
                rating_history_btn = ui.button("Rating History", icon="timeline").classes("sa-btn").style("display:none;background:#1a2a3a;border:1px solid #4a90d9")

        # ── tab bar ───────────────────────────────────────────────────────────
        with ui.row().classes("sa-tab-bar w-full items-center"):
            tab_stock = ui.label("Stock Analysis").classes("sa-tab active")
            ui.label("Portfolio Construction").classes("sa-tab dim")
            ui.label("Portfolio Management").classes("sa-tab dim")
            tab_admin = ui.label("Admin").classes("sa-tab").style("margin-left:auto")

        # ── body ──────────────────────────────────────────────────────────────
        admin_panel = ui.column().classes("w-full").style("display:none;padding:24px 0;gap:16px")
        with ui.column().classes("w-full sa-body") as stock_panel:

            # order: price box → company info → metrics → period
            refs["price_box"]   = ui.row().classes("w-full gap-2 flex-wrap items-center").style("display:none")
            refs["company_info"] = ui.column().classes("co-info w-full").style("display:none")
            refs["metrics_row"] = ui.row().classes("w-full gap-2 flex-wrap")

            # period row — hidden until first search
            refs["period_row"] = ui.row().classes("w-full items-center gap-1").style("display:none")
            with refs["period_row"]:
                ui.label("Period:").style(f"color:{MUTED};font-size:11px;margin-right:4px")
                for lbl, days in [("1M",30),("3M",90),("6M",180),("1Y",365),("2Y",730),("3Y",1095),("5Y",1825),("10Y",3650)]:
                    btn = ui.button(lbl).classes("sa-period-btn" + (" active" if days==365 else ""))
                    refs["period_btns"][days] = btn

            # empty state
            refs["empty_state"] = ui.column().classes("w-full empty-state")
            with refs["empty_state"]:
                ui.icon("show_chart").style(f"font-size:48px;color:{DIM}")
                ui.label("Enter a ticker to load analysis").style(f"color:{MUTED};font-size:13px")
                ui.label("Coverage: S&P 100  ·  Nasdaq 100  ·  DAX 40  ·  CAC 40  ·  SMI 20").style(f"color:{DIM};font-size:11px")

            # charts — hidden until first search
            refs["charts_col"] = ui.column().classes("w-full").style("display:none;gap:12px")
            with refs["charts_col"]:

                # price chart + returns comparison side by side
                with ui.row().classes("w-full gap-3"):
                    with ui.column().classes("sa-panel flex-1"):
                        with ui.row().classes("sa-panel-header w-full items-center justify-between"):
                            ui.label("Price  ·  SMA 20/50/100/200  ·  Volume").style(f"color:{MUTED};font-size:11px")
                            refs["ticker_label"] = ui.label("").style(f"color:{TEXT};font-size:11px;font-weight:500")
                            _exp_price_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_price_plot.on("click", lambda e, k="price_plot", b=_exp_price_plot: toggle_expand(k, b))
                        refs["price_plot"] = ui.element("div").style("width:100%;height:400px")

                    with ui.column().classes("sa-panel").style("width:450px"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("Price Returns  ·  vs Sector & Industry").style(f"color:{MUTED};font-size:11px")
                            _exp_returns_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_returns_plot.on("click", lambda e, k="returns_plot", b=_exp_returns_plot: toggle_expand(k, b))
                        refs["returns_plot"] = ui.element("div").style("width:100%;height:400px")

                # earnings + growth + volatility
                with ui.row().classes("w-full gap-3"):
                    with ui.column().classes("sa-panel flex-1"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("EPS & Revenue  ·  Actual vs Estimated").style(f"color:{MUTED};font-size:11px")
                            _exp_earnings_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_earnings_plot.on("click", lambda e, k="earnings_plot", b=_exp_earnings_plot: toggle_expand(k, b))
                        refs["earnings_plot"] = ui.element("div").style("width:100%;height:480px")

                    with ui.column().classes("sa-panel flex-1"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("EPS & Revenue Growth %  ·  YoY  ·  vs Sector & Industry").style(f"color:{MUTED};font-size:11px")
                            _exp_growth_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_growth_plot.on("click", lambda e, k="growth_plot", b=_exp_growth_plot: toggle_expand(k, b))
                        refs["growth_plot"] = ui.element("div").style("width:100%;height:480px")

                    with ui.column().classes("sa-panel").style("width:450px"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("Historical Volatility  ·  Annualised").style(f"color:{MUTED};font-size:11px")
                            _exp_vol_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_vol_plot.on("click", lambda e, k="vol_plot", b=_exp_vol_plot: toggle_expand(k, b))
                        refs["vol_plot"] = ui.element("div").style("width:100%;height:210px")
                        with ui.column().classes("w-full").style("padding:8px 12px;gap:0"):
                            refs["tech_col"] = ui.column().classes("w-full")

                # sentiment + summary
                with ui.row().classes("w-full gap-3"):
                    with ui.column().classes("sa-panel").style("width:380px"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("Sentiment Scores  ·  Spider").style(f"color:{MUTED};font-size:11px")
                            _exp_spider_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_spider_plot.on("click", lambda e, k="spider_plot", b=_exp_spider_plot: toggle_expand(k, b))
                        refs["spider_plot"] = ui.element("div").style("width:100%;height:320px")

                    with ui.column().classes("sa-panel").style("width:380px"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("Valuation & Profitability  ·  Spider").style(f"color:{MUTED};font-size:11px")
                            _exp_valuation_plot = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")
                            _exp_valuation_plot.on("click", lambda e, k="valuation_plot", b=_exp_valuation_plot: toggle_expand(k, b))
                        refs["valuation_plot"] = ui.element("div").style("width:100%;height:320px")

                    with ui.column().classes("sa-panel flex-1"):
                        with ui.row().classes("sa-panel-header w-full items-center"):
                            ui.label("Sentiment Detail  ·  Summary").style(f"color:{MUTED};font-size:11px")
                            _exp_sentiment = ui.button(icon="open_in_full").props("flat dense round").classes("sa-expand-btn")

                        with ui.column().classes("w-full").style("padding:10px 12px;gap:8px"):
                            refs["score_col"]   = ui.column().classes("w-full")
                            refs["summary_box"] = ui.column().classes("w-full")

                        # popup dialog for sentiment detail
                        with ui.dialog() as sentiment_dlg, ui.card().style(
                            f"background:{PANEL};border:1px solid {BORDER2};border-radius:4px;"
                            f"padding:0;width:72vw;max-width:900px;overflow:hidden;"
                            f"display:flex;flex-direction:column;"
                        ):
                            with ui.row().classes("w-full items-center justify-between").style(
                                f"height:40px;flex-shrink:0;padding:0 16px;"
                                f"border-bottom:1px solid {BORDER2};background:{BG}"
                            ):
                                ui.label("SENTIMENT DETAIL  ·  SUMMARY").style(
                                    f"color:{TEXT};font-size:12px;font-weight:500;letter-spacing:0.5px"
                                )
                                ui.button(icon="close", on_click=sentiment_dlg.close).props("flat dense round").style(f"color:{MUTED}")
                            with ui.column().classes("w-full").style(
                                f"padding:14px 18px;gap:10px;overflow-y:auto;max-height:80vh"
                            ):
                                refs["popup_score_col"]   = ui.column().classes("w-full")
                                refs["popup_summary_box"] = ui.column().classes("w-full")

                        _exp_sentiment.on("click", sentiment_dlg.open)

    # ── render helpers ────────────────────────────────────────────────────────

    def render_price_box(ticker, stock_id, symbol):
        """Fetch latest real-time price + aftermarket and render as a tile in the metrics row."""
        import asyncio as _asyncio

        async def _load():
            # always fetch last 2 stored closes — needed for prev_close baseline
            close_r = await _asyncio.to_thread(
                lambda: db().table("stock_prices").select("price,date")
                    .eq("stock_id", stock_id).order("date", desc=True).limit(2).execute().data
            )
            stored_price = float(close_r[0]["price"])      if close_r else None
            stored_prev  = float(close_r[1]["price"])      if len(close_r) > 1 else None
            stored_date  = close_r[0]["date"][:10]         if close_r else ""

            # try real-time quote
            quote = await _asyncio.to_thread(get_live_quote, symbol)
            rt_price = quote.get("price") if quote else None

            # decide which price to show
            if rt_price:
                price    = rt_price
                date_lbl = "real-time"
                # compare live price against most recent stored close (close_r[0])
                prev_close = stored_price
            else:
                price    = stored_price
                date_lbl = stored_date
                # compare stored price against the one before it
                prev_close = stored_prev

            if not price:
                return
            chg     = round(price - prev_close, 2)              if prev_close else None
            chg_pct = round(chg / prev_close * 100, 2)         if prev_close else None
            chg_pos = (chg or 0) >= 0

            # aftermarket from quote
            am_price = quote.get("am_price") if quote else None
            am_chg   = quote.get("am_chg")   if quote else None
            am_pct   = quote.get("am_pct")   if quote else None
            am_time  = quote.get("am_time","") if quote else ""
            am_pos   = (am_chg or 0) >= 0

            am_price = quote.get("am_price")
            am_chg   = quote.get("am_chg")
            am_pct   = quote.get("am_pct")
            am_time  = quote.get("am_time", "")
            am_pos   = (am_chg or 0) >= 0

            # render into price_box row
            refs["price_box"].clear()
            refs["price_box"].style("display:flex")
            with refs["price_box"]:

                # ── LAST PRICE tile — same .sa-metric style as other boxes ────
                with ui.element("div").classes("sa-metric").style("min-width:140px"):
                    ui.label("Last Price").classes("sa-metric-label")
                    ui.label(f"{price:,.2f}").classes("sa-metric-value")
                    if chg is not None:
                        sign  = "+" if chg_pos else ""
                        color = GREEN if chg_pos else RED
                        ui.label(f"{sign}{chg:,.2f}  ({sign}{chg_pct:.2f}%)").style(
                            f"color:{color};font-size:11px;font-variant-numeric:tabular-nums;margin-top:1px"
                        )
                    ui.label(f"vs close {stored_date}  ·  {date_lbl}").classes("sa-metric-sub")

                # ── RESEARCH RECOMMENDATION badge ─────────────────────────────
                _res = s.saved_research
                if _res:
                    _as   = _res.get("analyst_summary") or {}
                    _rec  = _as.get("recommendation", "")
                    _pt   = _as.get("price_target")
                    _conf = _as.get("confidence_score")
                    _pt   = _as.get("price_target")
                    # recalculate upside from live price rather than stale report price
                    if _pt and price:
                        _up = round((_pt - price) / price * 100, 1)
                    else:
                        _up = _as.get("upside_potential_pct")
                    if _rec:
                        _rec_color = GREEN if "BUY" in _rec.upper() else RED if "SELL" in _rec.upper() else AMBER
                        _up_sign   = "+" if (_up or 0) >= 0 else ""
                        with ui.element("div").classes("sa-metric").style(
                            f"min-width:130px;border-left:2px solid {_rec_color}55"
                        ):
                            ui.label("AI Research").classes("sa-metric-label")
                            ui.label(_rec).style(
                                f"color:{_rec_color};font-size:18px;font-weight:700;letter-spacing:0.5px"
                            )
                            if _pt:
                                ui.label(f"PT  {_as.get('price_target_currency','')} {_pt:,.2f}").style(
                                    f"color:{AMBER};font-size:11px;font-variant-numeric:tabular-nums;margin-top:1px"
                                )
                            if _up is not None:
                                ui.label(f"{_up_sign}{_up:.1f}% upside  ·  {_conf}/100").style(
                                    f"color:{MUTED};font-size:10px"
                                )

                # ── AFTER HOURS tile ──────────────────────────────────────────
                if am_price:
                    am_sign  = "+" if am_pos else ""
                    am_color = GREEN if am_pos else RED
                    with ui.element("div").classes("sa-metric").style(
                        f"min-width:140px;border-left:2px solid {AMBER}55"
                    ):
                        ui.label(f"After Hours  ·  {am_time}").classes("sa-metric-label")
                        ui.label(f"{am_price:,.2f}").classes("sa-metric-value")
                        ui.label(f"{am_sign}{am_chg:,.2f}  ({am_sign}{am_pct:.2f}%)").style(
                            f"color:{am_color};font-size:11px;font-variant-numeric:tabular-nums;margin-top:1px"
                        )
                        ui.label("vs last close").classes("sa-metric-sub")

        _asyncio.create_task(_load())

    def render_company_info(info):
        refs["company_info"].clear()
        refs["company_info"].style("display:flex")
        with refs["company_info"]:
            desc      = info.get("description") or ""
            employees = info.get("employees")
            website   = info.get("website") or ""
            city      = info.get("city") or ""
            state     = info.get("state") or ""
            country   = info.get("country") or ""
            zip_code  = info.get("zip") or ""
            address   = info.get("address") or ""

            # description — truncate at 420 chars
            if desc:
                short = desc[:420] + ("…" if len(desc) > 420 else "")
                with ui.element("div").classes("co-desc w-full"):
                    ui.label(short).style(f"color:{TEXT};font-size:13px;line-height:1.7")

            # meta row: employees · location · website
            with ui.row().classes("w-full items-center flex-wrap gap-4").style("margin-top:4px"):
                if employees:
                    with ui.row().classes("co-tag items-center gap-1"):
                        ui.icon("people").style(f"font-size:14px;color:{MUTED}")
                        ui.label(f"{employees:,} employees").style(f"color:{MUTED};font-size:11px")

                if city or address:
                    loc_parts = [p for p in [address or city, state, zip_code, country] if p]
                    loc = "  ·  ".join(loc_parts[:3])
                    with ui.row().classes("co-tag items-center gap-1"):
                        ui.icon("location_on").style(f"font-size:14px;color:{MUTED}")
                        ui.label(loc).style(f"color:{MUTED};font-size:11px")

                if website:
                    clean = website.replace("https://","").replace("http://","").rstrip("/")
                    with ui.row().classes("co-tag items-center gap-1"):
                        ui.icon("language").style(f"font-size:14px;color:{MUTED}")
                        ui.html(f"<a href=\"{website}\" target=\"_blank\" style=\"color:{ACCENT};font-size:11px\">{clean}</a>")

    def render_metrics(info, tech, sec_count=0, ind_count=0,
                       last_earn=None, next_earn=None, tr_date=None):
        refs["metrics_row"].clear()
        with refs["metrics_row"]:

            # ── clickable category tiles (Sector, Industry, Country) ──────────
            for label, field, val, sub in [
                ("Sector",   "sector",   info.get("sector")   or "—", f"{sec_count} stocks"),
                ("Industry", "industry", info.get("industry") or "—", f"{ind_count} stocks"),
                ("Country",  "country",  info.get("country")  or "—", ""),
            ]:
                # build dialog first, outside the tile
                with ui.dialog() as cat_dlg, ui.card().style(
                    f"background:#1a1a1a;border:1px solid {BORDER2};"
                    f"border-radius:4px;padding:0;min-width:320px;max-width:440px;max-height:540px;overflow:hidden"
                ):
                    with ui.row().classes("w-full items-center justify-between").style(
                        f"padding:12px 16px;border-bottom:1px solid {BORDER2};background:#111"
                    ):
                        ui.label(f"{label}: {val}").style(f"color:{WHITE};font-size:13px;font-weight:600")
                        ui.button(icon="close", on_click=cat_dlg.close).props("flat dense round").style(f"color:{MUTED}")
                    ticker_list_col = ui.column().classes("w-full").style(
                        f"overflow-y:auto;max-height:470px;gap:0"
                    )

                async def open_category(dlg=cat_dlg, col=ticker_list_col, f=field, v=val, lbl=label):
                    col.clear()
                    tickers = await asyncio.to_thread(get_tickers_in_category, f, v)
                    parent  = col.parent_slot.parent
                    with parent:
                        col.clear()
                        if not tickers:
                            with col:
                                ui.label("No tickers found").style(f"color:{MUTED};font-size:11px;padding:12px 16px")
                        else:
                            with col:
                                for idx2, t in enumerate(tickers):
                                    with ui.row().classes("w-full items-center").style(
                                        f"padding:6px 16px;"
                                        f"background:{'#161616' if idx2%2==0 else '#111'};"
                                        f"border-bottom:1px solid {BORDER}"
                                    ):
                                        ui.label(t["ticker"]).style(
                                            f"color:{ACCENT};font-size:11px;font-weight:500;width:72px;flex-shrink:0"
                                        )
                                        ui.label((t.get("name") or "")[:38]).style(
                                            f"color:{TEXT};font-size:11px"
                                        )
                    dlg.open()

                # tile as div with JS click
                tile = ui.element("div").classes("sa-metric").style("cursor:pointer;min-width:100px")
                with tile:
                    ui.label(label).classes("sa-metric-label")
                    ui.label(val).classes("sa-metric-value")
                    if sub:
                        ui.label(sub).classes("sa-metric-sub")
                tile.on("click", lambda e, fn=open_category: asyncio.create_task(fn()))

            # ── static tiles ──────────────────────────────────────────────────
            static_items = [
                ("Name",             (info.get("name") or "—")[:24], ""),
                ("Last Earnings",    last_earn  or "—", ""),
                ("Next Earnings",    next_earn  or "—", ""),
                ("Transcript Date",  tr_date    or "—", ""),
            ]
            if tech:
                rsi = tech.get("rsi_14")
                static_items += [
                    ("RSI (14)",   f"{rsi:.1f}" if rsi else "—",
                     "Overbought" if rsi and rsi>70 else "Oversold" if rsi and rsi<30 else "Neutral"),
                    ("vs SMA 200", "Above" if tech.get("vs_sma_200")=="above" else "Below",
                     f"{tech.get('pct_from_sma_200',0):+.1f}%"),
                    ("HVol 30d",   f"{tech.get('hvol_30d',0):.1f}%", "ann."),
                    ("HVol 252d",  f"{tech.get('hvol_252d',0):.1f}%", "ann."),
                ]
            for label, val, sub in static_items:
                with ui.element("div").classes("sa-metric"):
                    ui.label(label).classes("sa-metric-label")
                    ui.label(val).classes("sa-metric-value")
                    if sub:
                        ui.label(sub).classes("sa-metric-sub")

    def render_technicals(tech):
        refs["tech_col"].clear()
        if not tech:
            return
        with refs["tech_col"]:
            ui.label("Moving Averages").style(f"color:{MUTED};font-size:10px;text-transform:uppercase;letter-spacing:0.3px;padding:4px 0 2px")
            for period, sk, pk in [
                ("SMA 20","sma_20","pct_from_sma_20"),
                ("SMA 50","sma_50","pct_from_sma_50"),
                ("SMA 100","sma_100","pct_from_sma_100"),
                ("SMA 200","sma_200","pct_from_sma_200"),
            ]:
                sv  = tech.get(sk)
                pv  = tech.get(pk)
                vs  = tech.get(f"vs_{sk}")
                col = GREEN if vs=="above" else RED
                with ui.row().classes("w-full items-center justify-between").style(
                    f"padding:4px 0;border-bottom:1px solid {BORDER}"
                ):
                    ui.label(period).style(f"color:{MUTED};font-size:10px")
                    ui.label(f"{sv:,.2f}" if sv else "—").style(f"color:{TEXT};font-size:11px;font-variant-numeric:tabular-nums")
                    ui.label(f"{pv:+.1f}%" if pv else "—").style(f"color:{col};font-size:11px;font-variant-numeric:tabular-nums")

    # score descriptions shown on hover
    SCORE_DESC = {
        "Sentiment":      "Overall tone of the transcript. 10 = very positive (beats, records, optimism). 0 = very negative (warnings, losses, cuts).",
        "Guidance":       "Direction of forward guidance. 10 = significantly raised across metrics. 5 = maintained. 0 = lowered or withdrawn.",
        "Confidence":     "Management conviction in prepared remarks. 10 = assertive, specific, committed. 0 = defensive, vague, apologetic.",
        "Fwd Outlook":    "Strength of forward-looking statements. 10 = very bullish with specific targets. 0 = no outlook or explicitly negative.",
        "Innovation":     "Emphasis on AI, new products, R&D and strategic initiatives. 10 = major new initiatives. 0 = no mention.",
        "Analyst Trust":  "Analyst satisfaction inferred from Q&A tone. 10 = constructive, satisfied. 0 = skeptical, pressing hard.",
        "Low Risk":       "Absence of new or escalating risks. 10 = no new risks mentioned. 0 = many elevated risks and headwinds. (Inverted: lower raw score = better.)",
        "Low Deflection": "Management transparency in Q&A. 10 = direct answers to all questions. 0 = high evasion and redirection. (Inverted.)",
        "Low Hedging":    "Absence of hedging language (may / could / subject to). 10 = direct and committed. 0 = heavily hedged. (Inverted.)",
        "Low Uncertainty":"Clarity of forward outlook. 10 = very specific and committed. 0 = highly uncertain with many qualifiers. (Inverted.)",
    }

    def render_scores(transcript, sec_s, ind_s,
                      score_target=None, summary_target=None):
        sc = score_target   if score_target   is not None else refs["score_col"]
        sb = summary_target if summary_target is not None else refs["summary_box"]
        sc.clear()
        sb.clear()

        if not transcript:
            with sc:
                ui.label("No scored transcript available").style(f"color:{MUTED};font-size:11px;padding:8px 0")
            return

        scores = [
            ("Sentiment",     "sentiment_score",       "avg_sentiment",       False, GREEN),
            ("Guidance",      "guidance_score",        "avg_guidance",        False, ACCENT),
            ("Confidence",    "confidence_score",      "avg_confidence",      False, ACCENT),
            ("Fwd Outlook",   "forward_outlook_score", "avg_forward_outlook", False, GREEN),
            ("Innovation",    "innovation_score",      "avg_innovation",      False, PURPLE),
            ("Analyst Trust", "analyst_trust_score",   "avg_analyst_trust",   False, ACCENT),
            ("Low Risk",      "risk_score",            "avg_risk",            True,  AMBER),
            ("Low Deflection","deflection_score",      "avg_deflection",      True,  AMBER),
            ("Low Hedging",   "hedge_score",           "avg_hedge",           True,  ORANGE),
            ("Low Uncertainty","uncertainty_score",    "avg_uncertainty",     True,  ORANGE),
        ]

        with sc:
            # column headers
            with ui.row().classes("w-full").style(f"padding:0 0 4px;border-bottom:1px solid {BORDER2}"):
                ui.label("Score").style(f"color:{DIM};font-size:9px;width:104px;text-transform:uppercase;letter-spacing:0.3px")
                ui.element("div").style("flex:1")
                ui.label("Ticker").style(f"color:{DIM};font-size:9px;width:28px;text-align:right;text-transform:uppercase;letter-spacing:0.3px")
                ui.label("Sector").style(f"color:{DIM};font-size:9px;width:40px;text-align:right;text-transform:uppercase;letter-spacing:0.3px")
                ui.label("Ind").style(f"color:{DIM};font-size:9px;width:32px;text-align:right;text-transform:uppercase;letter-spacing:0.3px")

            composite = 0
            for label, t_key, s_key, inv, color in scores:
                t_val = transcript.get(t_key)
                s_val = sec_s.get(s_key)  if sec_s else None
                i_val = ind_s.get(s_key)  if ind_s else None
                disp  = (10-t_val) if inv and t_val is not None else (t_val or 0)
                composite += disp

                s_disp = round(10-s_val,1) if inv and s_val else (round(s_val,1) if s_val else None)
                i_disp = round(10-i_val,1) if inv and i_val else (round(i_val,1) if i_val else None)
                delta  = ""
                if t_val is not None and s_disp is not None:
                    d = disp - s_disp
                    delta = f"<span style='color:{GREEN}'>▲</span>" if d>0.2 else f"<span style='color:{RED}'>▼</span>" if d<-0.2 else ""

                desc = SCORE_DESC.get(label, "")
                with ui.row().classes("w-full items-center score-row"):
                    # label + info icon that opens a dialog
                    with ui.row().classes("items-center gap-1").style("width:104px;flex-shrink:0"):
                        ui.label(label).style(f"color:{MUTED};font-size:10px")
                        with ui.dialog() as dlg, ui.card().style(
                            f"background:#1a1a1a;border:1px solid {BORDER2};border-radius:4px;padding:16px 18px;max-width:320px;gap:8px"
                        ):
                            ui.label(label).style(f"color:{WHITE};font-size:13px;font-weight:600")
                            ui.label(desc).style(f"color:{TEXT};font-size:12px;line-height:1.6")
                            ui.button("Close", on_click=dlg.close).props("flat dense").style(
                                f"color:{MUTED};font-size:11px;margin-top:6px"
                            )
                        ui.button(icon="info_outline", on_click=dlg.open).props("flat dense round").style(
                            f"color:{MUTED};font-size:14px;width:18px;height:18px;min-width:18px;padding:0;"
                            f"transition:color 0.15s;"
                        ).on("mouseenter", lambda btn=None: None).classes("score-info-btn")
                    with ui.element("div").classes("score-track"):
                        ui.element("div").classes("score-fill").style(f"width:{disp*10}%;background:{color}")
                    ui.html(f"<span class='score-val' style='color:{color}'>{t_val:.0f}</span>" if t_val is not None else f"<span class='score-val' style='color:{DIM}'>—</span>")
                    ui.html(f"<span class='score-cmp'>{s_disp or '—'} {delta}</span>")
                    ui.html(f"<span class='score-cmp'>{i_disp:.1f}</span>" if i_disp else f"<span class='score-cmp' style='color:{DIM}'>—</span>")

            comp = round(composite/10, 1)
            s_comp = round(sec_s.get("composite_score"),1) if sec_s and sec_s.get("composite_score") else None
            comp_color = GREEN if (s_comp and comp > s_comp) else RED if (s_comp and comp < s_comp) else TEXT
            with ui.row().classes("w-full items-center justify-between").style(
                f"padding:6px 0 2px;border-top:1px solid {BORDER2};margin-top:2px"
            ):
                ui.label("Composite Score").style(f"color:{TEXT};font-size:11px;font-weight:500")
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{comp} / 10").style(f"color:{comp_color};font-size:13px;font-weight:600;font-variant-numeric:tabular-nums")
                    if s_comp:
                        ui.label(f"Sector avg: {s_comp}").style(f"color:{MUTED};font-size:10px")

        # mirror score rows into popup
        if refs.get("popup_score_col") and transcript:
            refs["popup_score_col"].clear()
            with refs["popup_score_col"]:
                ui.label("See scores in panel below ↓").style(f"color:{MUTED};font-size:11px;padding:8px 0")

        def fill_summary(target_col):
            with target_col:
                period_lbl = f"Q{transcript['quarter']} {transcript['year']}"
                with ui.column().classes("w-full").style(f"gap:6px;margin-top:4px;padding-top:8px;border-top:1px solid {BORDER}"):
                    ui.label(f"Earnings call  ·  {period_lbl}").style(f"color:{MUTED};font-size:10px;text-transform:uppercase;letter-spacing:0.3px")
                    if transcript.get("one_line_summary"):
                        with ui.element("div").classes("summary-box w-full"):
                            ui.label(transcript["one_line_summary"]).style(f"color:{TEXT};font-size:12px")
                    if transcript.get("bull_case") or transcript.get("bear_case"):
                        with ui.row().classes("w-full gap-3 flex-wrap").style("margin-top:4px"):
                            if transcript.get("bull_case"):
                                with ui.column().classes("flex-1").style(f"gap:3px"):
                                    ui.label("Bull case").style(f"color:{GREEN};font-size:10px;text-transform:uppercase;letter-spacing:0.3px")
                                    ui.label(transcript["bull_case"]).style(f"color:{TEXT};font-size:11px")
                            if transcript.get("bear_case"):
                                with ui.column().classes("flex-1").style(f"gap:3px"):
                                    ui.label("Bear case").style(f"color:{RED};font-size:10px;text-transform:uppercase;letter-spacing:0.3px")
                                    ui.label(transcript["bear_case"]).style(f"color:{TEXT};font-size:11px")
                    if transcript.get("top_topics"):
                        with ui.row().classes("w-full flex-wrap").style("margin-top:4px;gap:4px"):
                            for topic in transcript["top_topics"]:
                                ui.html(f"<span class='topic-tag'>{topic}</span>")

        fill_summary(sb)
        # populate popup summary too
        if refs.get("popup_summary_box"):
            refs["popup_summary_box"].clear()
            fill_summary(refs["popup_summary_box"])

    def swap_plot(key, fig, height):
        chart_heights[key] = height
        chart_figs[key]    = fig.to_dict()   # store for popup
        parent = refs[key].parent_slot.parent
        refs[key].delete()
        with parent:
            refs[key] = ui.plotly(chart_figs[key]).style(f"width:100%;height:{height}px")

    # ── analysis ──────────────────────────────────────────────────────────────
    def _fill_research_report(report: dict, dlg, show_save: bool = True):
        """Fill research report content into parent element."""
        a_sum  = report.get("analyst_summary", {})
        thesis = report.get("investment_thesis", {})
        fund   = report.get("fundamental_analysis", {})
        sent   = report.get("sentiment_analysis", {})
        tech   = report.get("technical_analysis", {})
        ptd    = report.get("price_target_derivation") or {}
        risks  = report.get("risk_factors") or []
        cats   = report.get("catalysts") or {}

        # fallback: if ptd is empty, reconstruct from analyst_summary
        if not ptd and a_sum.get("price_target"):
            ptd = {
                "methodology":          report.get("methodology", "—"),
                "derived_price_target": a_sum.get("price_target"),
                "bull_case_target":     a_sum.get("price_target"),
                "bear_case_target":     a_sum.get("price_target"),
            }
        # fallback: catalysts may be stored flat as top-level columns
        if not cats.get("upside_catalysts") and not cats.get("downside_catalysts"):
            up_flat   = report.get("upside_catalysts") or []
            down_flat = report.get("downside_catalysts") or []
            if up_flat or down_flat:
                cats = {"upside_catalysts": up_flat, "downside_catalysts": down_flat}

        # fallback: sentiment section sometimes carries key_positives/key_concerns
        # which can substitute as upside/downside catalysts
        if not cats.get("upside_catalysts") and not cats.get("downside_catalysts"):
            sent_pos = report.get("sentiment_key_positives") or                        (report.get("sentiment_analysis") or {}).get("key_positives") or []
            sent_neg = report.get("sentiment_key_concerns") or                        (report.get("sentiment_analysis") or {}).get("key_concerns") or []
            if sent_pos or sent_neg:
                cats = {"upside_catalysts": sent_pos, "downside_catalysts": sent_neg}

        rec    = a_sum.get("recommendation", "—")
        ccy    = a_sum.get("price_target_currency", "")
        pt     = a_sum.get("price_target")
        curr   = a_sum.get("current_price")
        up     = a_sum.get("upside_potential_pct")
        conf   = a_sum.get("confidence_score", 0)
        ticker = report.get("ticker", "")

        rec_color = GREEN if "BUY" in rec else RED if "SELL" in rec else AMBER
        up_color  = GREEN if (up or 0) >= 0 else RED
        up_sign   = "+" if (up or 0) >= 0 else ""

        # ── action bar ────────────────────────────────────────────────────
        with ui.row().classes("w-full items-center justify-between").style(
            f"padding:8px 20px;border-bottom:1px solid {BORDER2};background:{BG};flex-shrink:0"
        ):
            ui.label(f"{report.get('report_date','')}  ·  gpt-5.4-mini").style(
                f"color:{MUTED};font-size:10px"
            )
            save_btn = ui.button("Save Report", icon="save").props("flat").style(
                f"color:{ACCENT};font-size:11px"
            )
            if not show_save:
                save_btn.style("display:none")

        # ── scrollable body ───────────────────────────────────────────────
        with ui.scroll_area().style("width:100%;height:calc(90vh - 100px);overflow-y:auto"):
            with ui.column().classes("w-full").style("padding:20px;gap:0"):

                # ── top strip: rec + price target + confidence ─────────────
                with ui.row().classes("w-full gap-4 flex-wrap items-start").style(
                    f"padding-bottom:16px;border-bottom:1px solid {BORDER}"
                ):
                    # recommendation
                    with ui.element("div").classes("sa-metric").style("min-width:140px"):
                        ui.label("Recommendation").classes("sa-metric-label")
                        ui.label(rec).style(f"color:{rec_color};font-size:20px;font-weight:700;margin-top:2px")
                        ui.label(f"Confidence: {conf}/100").classes("sa-metric-sub")
                        ui.label(a_sum.get("conviction","").upper()).style(
                            f"color:{rec_color};font-size:9px;letter-spacing:1px"
                        )

                    # price target
                    with ui.element("div").classes("sa-metric").style("min-width:140px"):
                        ui.label("Price Target").classes("sa-metric-label")
                        ui.label(f"{ccy} {pt:,.2f}" if pt else "—").classes("sa-metric-value")
                        ui.label(f"{up_sign}{up:.1f}% upside" if up is not None else "").style(
                            f"color:{up_color};font-size:11px;margin-top:2px"
                        )
                        ui.label(f"Current: {ccy} {curr:,.2f}" if curr else "").classes("sa-metric-sub")

                    # methodology
                    with ui.element("div").classes("sa-metric").style("min-width:160px"):
                        ui.label("Methodology").classes("sa-metric-label")
                        ui.label(ptd.get("methodology","—")).classes("sa-metric-value")
                        ui.label(f"{ptd.get('base_metric','')}").classes("sa-metric-sub")
                        ui.label(f"× {ptd.get('target_multiple','')}").classes("sa-metric-sub")

                    # bull/base/bear
                    with ui.element("div").classes("sa-metric").style("min-width:160px"):
                        ui.label("Scenario Targets").classes("sa-metric-label")
                        ui.label(f"Bull   {ccy} {ptd.get('bull_case_target','—')}").style(
                            f"color:{GREEN};font-size:11px;margin-top:3px;font-variant-numeric:tabular-nums"
                        )
                        ui.label(f"Base   {ccy} {ptd.get('derived_price_target','—')}").style(
                            f"color:{TEXT};font-size:11px;font-variant-numeric:tabular-nums"
                        )
                        ui.label(f"Bear   {ccy} {ptd.get('bear_case_target','—')}").style(
                            f"color:{RED};font-size:11px;font-variant-numeric:tabular-nums"
                        )

                    # sentiment
                    sc   = sent.get("composite_score")
                    s_vs = sent.get("composite_vs_sector")
                    with ui.element("div").classes("sa-metric").style("min-width:130px"):
                        ui.label("Sentiment").classes("sa-metric-label")
                        ui.label(f"{sc:.1f} / 10" if sc else "—").classes("sa-metric-value")
                        ui.label(sent.get("overall_assessment","")).classes("sa-metric-sub")
                        if s_vs is not None:
                            sv_sign = "+" if s_vs >= 0 else ""
                            sv_col  = GREEN if s_vs >= 0 else RED
                            ui.label(f"vs sector: {sv_sign}{s_vs:.2f}").style(
                                f"color:{sv_col};font-size:10px"
                            )

                # ── thesis ────────────────────────────────────────────────
                ui.label("Thesis").style(
                    f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                    f"letter-spacing:0.5px;margin-top:14px;margin-bottom:4px;"
                    f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                )
                ui.label(f'"{a_sum.get("one_line_thesis","")}"').style(
                    f"color:{ACCENT};font-size:13px;font-style:italic;margin-bottom:8px"
                )
                ui.label(report.get("executive_summary","")).style(
                    f"color:{TEXT};font-size:12px;line-height:1.65"
                )

                # ── investment thesis ─────────────────────────────────────
                ui.label("Investment Thesis").style(
                    f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                    f"letter-spacing:0.5px;margin-top:14px;margin-bottom:6px;"
                    f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                )
                with ui.row().classes("w-full gap-3"):
                    for label, text, color in [
                        ("Bull Case", thesis.get("bull_case",""), GREEN),
                        ("Base Case", thesis.get("base_case",""), ACCENT),
                        ("Bear Case", thesis.get("bear_case",""), RED),
                    ]:
                        with ui.column().classes("flex-1").style(
                            f"background:{BG};border-left:2px solid {color}44;"
                            f"padding:10px 12px;border-radius:0 3px 3px 0"
                        ):
                            ui.label(label).style(f"color:{color};font-size:10px;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px")
                            ui.label(text).style(f"color:{TEXT};font-size:11px;line-height:1.6")

                # ── fundamental analysis ──────────────────────────────────
                ui.label("Fundamental Analysis").style(
                    f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                    f"letter-spacing:0.5px;margin-top:14px;margin-bottom:6px;"
                    f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                )
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    for section_title, section_data, items in [
                        ("Earnings Quality", fund.get("earnings_quality",{}), [
                            ("Assessment", "assessment"),
                            ("EPS Growth", "eps_growth_trend"),
                            ("Revenue Growth", "revenue_growth_trend"),
                            ("Beat/Miss Pattern", "beat_miss_pattern"),
                            ("vs Sector", "vs_sector_commentary"),
                        ]),
                        ("Profitability", fund.get("profitability",{}), [
                            ("Assessment", "assessment"),
                            ("Gross Margin", "gross_margin_commentary"),
                            ("Net Margin", "net_margin_commentary"),
                            ("Returns", "return_metrics_commentary"),
                        ]),
                        ("Valuation", fund.get("valuation",{}), [
                            ("Assessment", "assessment"),
                            ("Key Multiple", "key_multiple"),
                            ("Target Multiple", "target_multiple"),
                            ("vs Sector", "vs_sector_commentary"),
                            ("vs History", "vs_own_history_commentary"),
                        ]),
                        ("Financial Health", fund.get("financial_health",{}), [
                            ("Assessment", "assessment"),
                            ("Debt", "debt_commentary"),
                            ("Liquidity", "liquidity_commentary"),
                        ]),
                    ]:
                        with ui.column().style(
                            f"background:{BG};border:1px solid {BORDER};"
                            f"border-radius:3px;padding:10px 12px;flex:1;min-width:220px;gap:4px"
                        ):
                            ui.label(section_title).style(
                                f"color:{ACCENT};font-size:10px;text-transform:uppercase;"
                                f"letter-spacing:0.5px;margin-bottom:4px"
                            )
                            for lbl, key in items:
                                val = section_data.get(key)
                                if val:
                                    with ui.row().classes("w-full").style("gap:6px;flex-wrap:wrap"):
                                        ui.label(f"{lbl}:").style(f"color:{MUTED};font-size:10px;flex-shrink:0")
                                        ui.label(val).style(f"color:{TEXT};font-size:10px;line-height:1.5")

                # ── sentiment ─────────────────────────────────────────────
                ui.label("Sentiment Analysis").style(
                    f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                    f"letter-spacing:0.5px;margin-top:14px;margin-bottom:6px;"
                    f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                )
                with ui.row().classes("w-full gap-3"):
                    with ui.column().classes("flex-1").style(
                        f"background:{BG};border:1px solid {BORDER};border-radius:3px;padding:10px 12px;gap:4px"
                    ):
                        if sent.get("key_positives"):
                            ui.label("Key Positives").style(f"color:{GREEN};font-size:10px;text-transform:uppercase;letter-spacing:0.5px")
                            for p in sent["key_positives"]:
                                ui.label(f"+ {p}").style(f"color:{TEXT};font-size:11px")
                    with ui.column().classes("flex-1").style(
                        f"background:{BG};border:1px solid {BORDER};border-radius:3px;padding:10px 12px;gap:4px"
                    ):
                        if sent.get("key_concerns"):
                            ui.label("Key Concerns").style(f"color:{AMBER};font-size:10px;text-transform:uppercase;letter-spacing:0.5px")
                            for c in sent["key_concerns"]:
                                ui.label(f"– {c}").style(f"color:{TEXT};font-size:11px")
                if sent.get("transcript_highlights"):
                    ui.label(f"Transcript: {sent['transcript_highlights']}").style(
                        f"color:{MUTED};font-size:11px;margin-top:6px;font-style:italic"
                    )

                # ── risks ─────────────────────────────────────────────────
                if risks:
                    ui.label("Risk Factors").style(
                        f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                        f"letter-spacing:0.5px;margin-top:14px;margin-bottom:6px;"
                        f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                    )
                    for r in risks:
                        sev   = r.get("severity","medium")
                        s_col = RED if sev=="high" else AMBER if sev=="medium" else MUTED
                        with ui.row().classes("w-full items-start gap-2").style(
                            f"padding:5px 0;border-bottom:1px solid {BORDER}22"
                        ):
                            ui.label(f"[{sev.upper()}]").style(f"color:{s_col};font-size:10px;width:52px;flex-shrink:0;margin-top:1px")
                            ui.label(r.get("risk","")).style(f"color:{TEXT};font-size:11px;line-height:1.5")

                # ── catalysts ─────────────────────────────────────────────
                ui.label("Catalysts").style(
                    f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                    f"letter-spacing:0.5px;margin-top:14px;margin-bottom:6px;"
                    f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                )
                with ui.row().classes("w-full gap-3"):
                    with ui.column().classes("flex-1").style(
                        f"background:{BG};border:1px solid {BORDER};border-radius:3px;padding:10px 12px;gap:3px"
                    ):
                        ui.label("Upside").style(f"color:{GREEN};font-size:10px;text-transform:uppercase;letter-spacing:0.5px")
                        for c in cats.get("upside_catalysts",[]):
                            ui.label(f"↑ {c}").style(f"color:{TEXT};font-size:11px")
                    with ui.column().classes("flex-1").style(
                        f"background:{BG};border:1px solid {BORDER};border-radius:3px;padding:10px 12px;gap:3px"
                    ):
                        ui.label("Downside").style(f"color:{RED};font-size:10px;text-transform:uppercase;letter-spacing:0.5px")
                        for c in cats.get("downside_catalysts",[]):
                            ui.label(f"↓ {c}").style(f"color:{TEXT};font-size:11px")

                if ptd.get("multiple_justification"):
                    ui.label("Price Target Rationale").style(
                        f"color:{MUTED};font-size:10px;text-transform:uppercase;"
                        f"letter-spacing:0.5px;margin-top:14px;margin-bottom:4px;"
                        f"padding-bottom:4px;border-bottom:1px solid {BORDER}"
                    )
                    ui.label(ptd["multiple_justification"]).style(
                        f"color:{TEXT};font-size:11px;line-height:1.65;margin-bottom:16px"
                    )

        # ── save handler — plain thread, result stored in list cell ─────────
        def on_save():
            save_btn.props("loading=true").set_enabled(False)
            result_box = [None]   # list cell avoids closure/forward-ref issues

            def _thread():
                try:
                    from stock_research_agent import save_report as _save
                    result_box[0] = ("ok", _save(report, {}))
                except Exception as e:
                    result_box[0] = ("err", e)

            threading.Thread(target=_thread, daemon=True).start()

            def _poll():
                if result_box[0] is None:
                    return   # still running
                t.active = False
                status, val = result_box[0]
                save_btn.props("loading=false").set_enabled(True)
                if status == "ok":
                    ui.notify(f"Report saved — ID: {val}", type="positive")
                    save_btn.props("icon=check_circle").style(f"color:{GREEN}")
                    # update the view research button with the freshly saved report
                    s.saved_research = report
                    rdate = report.get("report_date", "")
                    view_research_btn.set_text(f"View Research  ·  {rdate}")
                    view_research_btn.style("display:inline-flex")
                else:
                    ui.notify(f"Save failed: {val}", type="negative")

            t = ui.timer(0.5, _poll)

        save_btn.on("click", on_save)

    def fetch_saved_research(ticker: str):
        """Fetch most recent saved research report for ticker from Supabase.
        Reconstructs the nested dict shape that _fill_research_report expects
        from the flat jsonb columns that save_report writes.
        """
        try:
            resp = db().table("stock_research")                 .select("*")                 .eq("ticker", ticker)                 .order("report_date", desc=True)                 .limit(1)                 .execute()
            if not resp.data:
                return None
            row = resp.data[0]
            # Full report is stored in full_report_json column
            report = row.get("full_report_json") or {}
            # Ensure report_date is present (use row-level date as fallback)
            report.setdefault("report_date", row.get("report_date", ""))
            return report
        except Exception as e:
            log.warning(f"Could not fetch saved research for {ticker}: {e}")
        return None

    def fetch_rating_history(ticker: str) -> list:
        """Fetch all research reports for ticker, ordered oldest→newest."""
        try:
            rows = (
                db().table("stock_research")
                .select(
                    "report_date,recommendation,confidence_score,conviction,"
                    "price_target,price_target_currency,current_price,"
                    "upside_potential_pct,one_line_thesis,executive_summary,"
                    "bull_case,bear_case,pt_methodology,bull_case_target,bear_case_target,"
                    "prior_target_commentary,recommendation_change,move_commentary"
                )
                .eq("ticker", ticker)
                .order("report_date", desc=False)
                .execute()
                .data
            )
            return rows or []
        except Exception as e:
            log.warning(f"fetch_rating_history failed: {e}")
            return []

    def open_rating_history(ticker: str, current_price: float):
        """Build and open the rating history dialog."""
        import plotly.graph_objects as go

        reports = fetch_rating_history(ticker)

        REC_COLOR = {
            "STRONG BUY": "#00e676", "BUY": "#00c076",
            "HOLD": "#ffc107",
            "SELL": "#ff5252", "STRONG SELL": "#b71c1c",
        }

        with ui.dialog() as dlg, ui.card().style(
            f"background:{PANEL};border:1px solid {BORDER2};border-radius:4px;"
            f"padding:0;width:94vw;max-width:1200px;max-height:90vh"
        ):
            # ── header ────────────────────────────────────────────────────────
            with ui.row().classes("w-full items-center justify-between").style(
                f"padding:12px 20px;border-bottom:1px solid {BORDER2};background:{BG}"
            ):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("timeline").style(f"color:#4a90d9;font-size:20px")
                    ui.label(f"Rating & Price Target History  ·  {ticker}").style(
                        f"color:{TEXT};font-size:13px;font-weight:500"
                    )
                    if reports:
                        ui.badge(f"{len(reports)} reports").style(
                            f"background:#4a90d933;color:#4a90d9;"
                            f"font-size:10px;padding:2px 8px;border-radius:10px"
                        )
                ui.button(icon="close", on_click=dlg.close).props("flat dense round").style(
                    f"color:{MUTED}"
                )

            # ── body — plain column with overflow scroll ───────────────────────
            with ui.column().classes("w-full").style(
                f"padding:20px;gap:16px;overflow-y:auto;max-height:calc(90vh - 60px)"
            ):
                if not reports:
                    ui.label(f"No research reports found for {ticker}.").style(
                        f"color:{MUTED};font-size:12px"
                    )
                else:
                    # ── chart ──────────────────────────────────────────────────
                    dates  = [r["report_date"] for r in reports]
                    pts    = [r.get("price_target") for r in reports]
                    bulls  = [r.get("bull_case_target") for r in reports]
                    bears  = [r.get("bear_case_target") for r in reports]
                    recs   = [r.get("recommendation", "") for r in reports]
                    confs  = [r.get("confidence_score") or 0 for r in reports]
                    marker_colors = [REC_COLOR.get(r, MUTED) for r in recs]

                    fig = go.Figure()

                    # bull/bear shaded band
                    valid = [(d, bu, be) for d, bu, be in zip(dates, bulls, bears)
                             if bu is not None and be is not None]
                    if valid:
                        vd, vbu, vbe = zip(*valid)
                        fig.add_trace(go.Scatter(
                            x=list(vd) + list(reversed(vd)),
                            y=list(vbu) + list(reversed(vbe)),
                            fill="toself", fillcolor="rgba(74,144,217,0.07)",
                            line=dict(color="rgba(0,0,0,0)"),
                            name="Bull/Bear Range", hoverinfo="skip",
                        ))

                    fig.add_trace(go.Scatter(
                        x=dates, y=bears, mode="lines",
                        line=dict(color=RED, width=1, dash="dot"),
                        name="Bear PT", opacity=0.55,
                    ))
                    fig.add_trace(go.Scatter(
                        x=dates, y=bulls, mode="lines",
                        line=dict(color=GREEN, width=1, dash="dot"),
                        name="Bull PT", opacity=0.55,
                    ))
                    fig.add_trace(go.Scatter(
                        x=dates, y=pts, mode="lines+markers",
                        line=dict(color="#4a90d9", width=2),
                        marker=dict(color=marker_colors, size=11,
                                    line=dict(color=BG, width=2)),
                        name="Base PT",
                        text=[f"{rc}  {cf}/100" for rc, cf in zip(recs, confs)],
                        hovertemplate="<b>%{x}</b><br>PT: %{y:,.2f}<br>%{text}<extra></extra>",
                    ))
                    if current_price:
                        fig.add_hline(
                            y=current_price,
                            line_color=AMBER, line_dash="dash", line_width=1.5,
                            annotation_text=f"  Current {current_price:,.2f}",
                            annotation_font_color=AMBER, annotation_font_size=10,
                        )

                    fig.update_layout(
                        paper_bgcolor=PANEL, plot_bgcolor=BG,
                        font=dict(family="Sora,sans-serif", color=MUTED, size=11),
                        margin=dict(l=50, r=20, t=10, b=40),
                        height=280,
                        legend=dict(orientation="h", y=-0.28, font=dict(size=10)),
                        xaxis=dict(gridcolor=BORDER, showgrid=True, tickfont=dict(size=10)),
                        yaxis=dict(gridcolor=BORDER, showgrid=True, tickfont=dict(size=10)),
                        hovermode="x unified",
                    )
                    ui.plotly(fig).classes("w-full")

                    # ── report cards ───────────────────────────────────────────
                    ui.label("ALL REPORTS  ·  newest first").style(
                        f"color:{MUTED};font-size:10px;font-weight:600;letter-spacing:1px"
                    )
                    for r in reversed(reports):
                        rec     = r.get("recommendation", "")
                        ccy     = r.get("price_target_currency", "") or ""
                        pt      = r.get("price_target")
                        conf    = r.get("confidence_score")
                        conv    = (r.get("conviction") or "").upper()
                        cp      = r.get("current_price")
                        bull_t  = r.get("bull_case_target")
                        bear_t  = r.get("bear_case_target")
                        rec_col = REC_COLOR.get(rec, MUTED)
                        chg     = r.get("recommendation_change") or ""
                        chg_col = GREEN if chg == "upgraded" else RED if chg == "downgraded" else MUTED

                        try:
                            up = round((pt - cp) / cp * 100, 1) if pt and cp else r.get("upside_potential_pct")
                        except Exception:
                            up = r.get("upside_potential_pct")
                        up_sign = "+" if (up or 0) >= 0 else ""
                        up_col  = GREEN if (up or 0) >= 0 else RED

                        with ui.column().classes("w-full").style(
                            f"background:{BG};border:1px solid {BORDER2};"
                            f"border-left:3px solid {rec_col};"
                            f"border-radius:3px;padding:12px 16px;gap:6px"
                        ):
                            # row 1 — date · rec · badge · conv · PT
                            with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                                ui.label(r.get("report_date","")).style(
                                    f"color:{DIM};font-size:10px;flex-shrink:0"
                                )
                                ui.label(rec).style(
                                    f"color:{rec_col};font-size:14px;font-weight:700;flex-shrink:0"
                                )
                                if chg and chg not in ("unchanged", "initiated", ""):
                                    ui.badge(chg.upper()).style(
                                        f"background:{chg_col}22;color:{chg_col};"
                                        f"font-size:9px;padding:1px 6px;border-radius:8px;flex-shrink:0"
                                    )
                                if conv:
                                    ui.label(conv).style(
                                        f"color:{MUTED};font-size:10px;flex-shrink:0"
                                    )
                                # PT on the right
                                with ui.row().classes("items-center gap-2").style("margin-left:auto;flex-shrink:0"):
                                    if bear_t:
                                        ui.label(f"Bear {ccy} {bear_t:,.2f}").style(
                                            f"color:{RED};font-size:10px"
                                        )
                                    if pt:
                                        ui.label(f"Base {ccy} {pt:,.2f}").style(
                                            f"color:{AMBER};font-size:11px;font-weight:600"
                                        )
                                    if bull_t:
                                        ui.label(f"Bull {ccy} {bull_t:,.2f}").style(
                                            f"color:{GREEN};font-size:10px"
                                        )
                                    if up is not None:
                                        ui.label(f"({up_sign}{up:.1f}%)").style(
                                            f"color:{up_col};font-size:10px"
                                        )
                                    if conf is not None:
                                        ui.label(f"{conf}/100").style(
                                            f"color:{MUTED};font-size:10px"
                                        )

                            # thesis / summary
                            if r.get("one_line_thesis"):
                                ui.label(r["one_line_thesis"]).style(
                                    f"color:{TEXT};font-size:11px;font-style:italic"
                                )
                            if r.get("executive_summary"):
                                ui.label(r["executive_summary"]).style(
                                    f"color:{MUTED};font-size:10px;line-height:1.5"
                                )
                            for lbl, field in [
                                ("Prior Target", "prior_target_commentary"),
                                ("Move Impact",  "move_commentary"),
                            ]:
                                val = r.get(field)
                                if val:
                                    with ui.row().classes("items-start gap-2"):
                                        ui.label(f"{lbl}:").style(
                                            f"color:{DIM};font-size:9px;font-weight:600;"
                                            f"letter-spacing:0.5px;flex-shrink:0;margin-top:1px"
                                        )
                                        ui.label(val).style(
                                            f"color:{MUTED};font-size:10px;line-height:1.5"
                                        )

        dlg.open()

    def open_research_dialog(report: dict):
        """Build and open the research dialog from a saved report dict."""
        with ui.dialog() as research_dlg, ui.card().style(
            f"background:{PANEL};border:1px solid {BORDER2};border-radius:4px;"
            f"padding:0;width:92vw;max-width:1100px;"
            f"max-height:90vh;overflow:hidden;display:flex;flex-direction:column"
        ):
            with ui.row().classes("w-full items-center justify-between").style(
                f"padding:12px 20px;border-bottom:1px solid {BORDER2};"
                f"background:{BG};flex-shrink:0"
            ):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("psychology").style(f"color:{AMBER};font-size:20px")
                    ui.label(f"Research Report  ·  {report.get('ticker','')}").style(
                        f"color:{TEXT};font-size:13px;font-weight:500"
                    )
                ui.button(icon="close", on_click=research_dlg.close).props("flat dense round").style(f"color:{MUTED}")

            _fill_research_report(report, research_dlg, show_save=False)

        research_dlg.open()

    def run_research_for_ticker():
        """
        Spin up a plain daemon thread for the agent, store result on s.research_result,
        and let a ui.timer poll in the normal UI context to render the dialog.
        Avoids all slot-context issues caused by asyncio.create_task / await.
        """
        if not s.info:
            ui.notify("Load a ticker first", type="warning")
            return
        if s.research_result == "running":
            return  # already in progress

        ticker = s.info["ticker"]
        s.research_result = "running"
        research_btn.props("loading=true").set_enabled(False)
        running_notif = ui.notification(f"Running research for {ticker}…", type="ongoing", timeout=0, spinner=True, close_button=False)

        def _thread():
            try:
                from stock_context_builder import build_context as _bc
                from stock_research_agent  import run_research  as _rr
                ctx = _bc(ticker)
                s.research_result = _rr(ticker, ctx)
            except Exception as e:
                log.error(f"Research error: {e}", exc_info=True)
                s.research_result = e

        threading.Thread(target=_thread, daemon=True).start()

        t = [None]  # list cell to hold timer ref — avoids forward-reference issue

        def _poll():
            if s.research_result == "running":
                return  # still working — timer will fire again
            if t[0]: t[0].active = False
            running_notif.dismiss()
            research_btn.props("loading=false").set_enabled(True)

            result = s.research_result
            s.research_result = None

            if isinstance(result, Exception):
                ui.notify(f"Research failed: {str(result)[:80]}", type="negative")
                return

            # Build and open dialog entirely inside the timer callback —
            # timer callbacks always run in the normal UI event loop context.
            with ui.dialog() as research_dlg, ui.card().style(
                f"background:{PANEL};border:1px solid {BORDER2};border-radius:4px;"
                f"padding:0;width:92vw;max-width:1100px;"
                f"max-height:90vh;overflow:hidden;display:flex;flex-direction:column"
            ):
                with ui.row().classes("w-full items-center justify-between").style(
                    f"padding:12px 20px;border-bottom:1px solid {BORDER2};"
                    f"background:{BG};flex-shrink:0"
                ):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("psychology").style(f"color:{AMBER};font-size:20px")
                        ui.label(f"Research Report  ·  {result.get('ticker','')}").style(
                            f"color:{TEXT};font-size:13px;font-weight:500"
                        )
                    ui.button(icon="close", on_click=research_dlg.close).props("flat dense round").style(f"color:{MUTED}")

                _fill_research_report(result, research_dlg)

            research_dlg.open()
            rec = (result.get("analyst_summary") or {}).get("recommendation", "—")
            ui.notify(f"Research complete — {rec}", type="positive")

        t[0] = ui.timer(0.5, _poll)


    # ── main analysis ──────────────────────────────────────────────────────────
    async def run_analysis(ticker: str):
        ticker = ticker.strip().upper()
        if not ticker:
            return
        info = await asyncio.to_thread(get_stock_info, ticker)
        if not info:
            ui.notify(f"Ticker '{ticker}' not found", type="warning")
            return
        stock_id = info["id"]
        sector   = info.get("sector", "")
        industry = info.get("industry", "")
        refs["ticker_label"].set_text(f"{ticker}  ·  {(info.get('name') or '')[:30]}")
        refs["empty_state"].style("display:none")
        refs["charts_col"].style("display:flex;flex-direction:column;gap:12px")
        refs["period_row"].style("display:flex")
        research_btn.style("display:inline-flex")
        view_research_btn.style("display:none")
        rating_history_btn.style("display:inline-flex")
        s.saved_research = None

        # check Supabase for existing research — use to_thread so we stay in async context
        saved = await asyncio.to_thread(fetch_saved_research, ticker)
        if saved:
            s.saved_research = saved
            rdate = saved.get("report_date", "")
            view_research_btn.set_text(f"View Research  ·  {rdate}")
            view_research_btn.style("display:inline-flex")

        render_company_info(info)
        tech, transcript, earnings = await asyncio.gather(
            asyncio.to_thread(get_technicals, stock_id),
            asyncio.to_thread(get_transcript, stock_id),
            asyncio.to_thread(get_earnings_history, stock_id),
        )
        sec_s, ind_s = None, None
        if transcript:
            sec_s, ind_s = await asyncio.gather(
                asyncio.to_thread(get_sector_sentiment, sector, transcript["year"], transcript["quarter"]),
                asyncio.to_thread(get_industry_sentiment, industry, transcript["year"], transcript["quarter"]),
            )
        fin, sec_f, ind_f, (sec_count, ind_count), sec_vol, ind_vol,         stock_ret, sec_ret, ind_ret,         (last_earn, next_earn, tr_date),         sec_growth, ind_growth = await asyncio.gather(
            asyncio.to_thread(get_latest_financials, stock_id),
            asyncio.to_thread(get_sector_financials_latest, sector),
            asyncio.to_thread(get_industry_financials_latest, industry),
            asyncio.to_thread(get_universe_counts, sector, industry),
            asyncio.to_thread(get_sector_vol, sector),
            asyncio.to_thread(get_industry_vol, industry),
            asyncio.to_thread(get_stock_returns, stock_id, ticker),
            asyncio.to_thread(get_sector_returns, sector),
            asyncio.to_thread(get_industry_returns, industry),
            asyncio.to_thread(get_earnings_dates, stock_id),
            asyncio.to_thread(get_sector_growth_history, sector),
            asyncio.to_thread(get_industry_growth_history, industry),
        )
        s.info = info; s.tech = tech; s.transcript = transcript; s.earnings = earnings
        render_price_box(ticker, stock_id, info.get("fmp_symbol") or ticker)
        render_metrics(info, tech, sec_count, ind_count, last_earn, next_earn, tr_date)
        render_technicals(tech)
        render_scores(transcript, sec_s, ind_s)
        if refs.get("popup_score_col") and refs.get("popup_summary_box"):
            render_scores(transcript, sec_s, ind_s,
                          score_target=refs["popup_score_col"],
                          summary_target=refs["popup_summary_box"])
        _news_ev = await asyncio.to_thread(fetch_news_events, ticker, s.period_days)
        price_fig, earn_fig, growth_fig, vol_fig, val_fig, ret_fig = await asyncio.gather(
            asyncio.to_thread(
            build_price_chart, stock_id, ticker, s.period_days,
            price_target=(s.saved_research or {}).get("analyst_summary", {}).get("price_target"),
            pt_bull=(s.saved_research or {}).get("price_target_derivation", {}).get("bull_case_target"),
            pt_bear=(s.saved_research or {}).get("price_target_derivation", {}).get("bear_case_target"),
            news_events=_news_ev,
        ),
            asyncio.to_thread(build_earnings_chart, earnings),
            asyncio.to_thread(build_growth_chart, earnings, sec_growth, ind_growth),
            asyncio.to_thread(build_volatility_chart, tech, sec_vol, ind_vol),
            asyncio.to_thread(build_valuation_spider, fin, sec_f, ind_f, sector, industry),
            asyncio.to_thread(build_returns_chart, stock_ret, sec_ret, ind_ret, ticker),
        )
        spider_fig = None
        if transcript:
            spider_fig = await asyncio.to_thread(
                build_spider_chart, transcript, sec_s, ind_s, sector, industry
            )
        swap_plot("price_plot",     price_fig, 400)
        swap_plot("returns_plot",   ret_fig,   400)
        swap_plot("earnings_plot",  earn_fig,  480)
        swap_plot("growth_plot",    growth_fig, 480)
        swap_plot("vol_plot",       vol_fig,   210)
        swap_plot("valuation_plot", val_fig,   340)
        if spider_fig:
            swap_plot("spider_plot", spider_fig, 320)

    async def on_period(days: int):
        s.period_days = days
        for d, btn in refs["period_btns"].items():
            btn.classes(add="active" if d == days else "")
            btn.classes(remove="" if d == days else "active")
        if s.info:
            _news_ev2 = await asyncio.to_thread(fetch_news_events, s.info["ticker"], days)
            fig = await asyncio.to_thread(
                build_price_chart, s.info["id"], s.info["ticker"], days,
                price_target=(s.saved_research or {}).get("analyst_summary", {}).get("price_target"),
                pt_bull=(s.saved_research or {}).get("price_target_derivation", {}).get("bull_case_target"),
                pt_bear=(s.saved_research or {}).get("price_target_derivation", {}).get("bear_case_target"),
                news_events=_news_ev2,
            )
            if hasattr(refs["price_plot"], "update_figure"):
                refs["price_plot"].update_figure(fig.to_dict())
            else:
                swap_plot("price_plot", fig, 400)

    # ── admin tab ─────────────────────────────────────────────────────────

    def _sb_headers():
        return {
            "apikey":        _SUPABASE_KEY,
            "Authorization": f"Bearer {_SUPABASE_KEY}",
        }

    def _sb_get(path, params, timeout=30):
        r = requests.get(
            _SUPABASE_URL + "/rest/v1/" + path,
            headers=_sb_headers(),
            params=params,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()

    # ── fetch functions ────────────────────────────────────────────────────

    def fetch_large_movers(threshold_pct: float = 4.0) -> list:
        from collections import defaultdict
        cutoff = (date.today() - timedelta(days=5)).isoformat()

        universe = _sb_get("stock_universe", {"select": "id,ticker,name", "active": "eq.true"})
        if not universe:
            return []
        id_to_stock = {r["id"]: r for r in universe}
        ids_param = "(" + ",".join(str(i) for i in id_to_stock) + ")"

        prices_raw = _sb_get("stock_prices", {
            "select":   "stock_id,date,price",
            "stock_id": f"in.{ids_param}",
            "date":     f"gte.{cutoff}",
            "order":    "stock_id.asc,date.desc",
            "limit":    "10000",
        })

        by_stock = defaultdict(list)
        for row in prices_raw:
            sid = row["stock_id"]
            if len(by_stock[sid]) < 2:
                by_stock[sid].append(row)

        results = []
        for sid, rows in by_stock.items():
            if len(rows) < 2:
                continue
            p1 = float(rows[0]["price"])
            p0 = float(rows[1]["price"])
            if p0 <= 0:
                continue
            chg = (p1 - p0) / p0 * 100
            if abs(chg) >= threshold_pct:
                stk = id_to_stock.get(sid, {})
                results.append({
                    "ticker":     stk.get("ticker", "?"),
                    "name":       stk.get("name", "") or "",
                    "date":       str(rows[0]["date"])[:10],
                    "price":      p1,
                    "change_pct": round(chg, 2),
                    "prev":       p0,
                })
        results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return results

    def fetch_stock_news(ticker: str, trade_date: str, max_items: int = 8) -> list:
        """
        Fetch news from FMP for a ticker around the move date.
        Returns list of {title, url, source, published_date, text}.
        """
        from datetime import datetime as _dt
        try:
            # fetch up to 50 articles then filter to ±2 days of the move date
            r = requests.get(
                f"{FMP_BASE}/news/stock",
                params={"symbols": ticker, "apikey": FMP_API_KEY, "limit": 50},
                timeout=15,
            )
            r.raise_for_status()
            articles = r.json() if isinstance(r.json(), list) else []
        except Exception:
            return []

        move_dt = _dt.fromisoformat(trade_date)
        results = []
        for a in articles:
            pub = (a.get("publishedDate") or a.get("date") or "")[:10]
            try:
                pub_dt = _dt.fromisoformat(pub)
            except ValueError:
                continue
            if abs((pub_dt - move_dt).days) <= 2:
                results.append({
                    "title":   (a.get("title") or "").strip(),
                    "url":     a.get("url") or "",
                    "source":  a.get("site") or a.get("source") or "",
                    "date":    pub,
                    "text":    (a.get("text") or a.get("summary") or "").strip(),
                })
            if len(results) >= max_items:
                break
        return results

    def fetch_upcoming_earnings(days_ahead: int = 5) -> list:
        today = date.today().isoformat()
        until = (date.today() + timedelta(days=days_ahead)).isoformat()

        # Fetch all earnings in the date window regardless of eps_actual,
        # then filter to future (unactualised) ones in Python.
        # Using list-of-tuples so requests sends two separate date= params.
        import requests as _rq
        resp = _rq.get(
            _SUPABASE_URL + "/rest/v1/earnings",
            headers={
                "apikey":        _SUPABASE_KEY,
                "Authorization": f"Bearer {_SUPABASE_KEY}",
            },
            params=[
                ("select", "stock_id,date,eps_estimated,revenue_estimated,eps_actual"),
                ("date",   f"gte.{today}"),
                ("date",   f"lte.{until}"),
                ("order",  "date.asc"),
                ("limit",  "500"),
            ],
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Supabase {resp.status_code}: {resp.text[:300]}")
        all_rows = resp.json()

        # keep only rows where eps_actual is null (= not yet reported)
        rows = [r for r in all_rows if r.get("eps_actual") is None]
        if not rows:
            return []

        stock_ids = list({r["stock_id"] for r in rows})
        ids_param = "(" + ",".join(str(i) for i in stock_ids) + ")"
        universe  = _sb_get("stock_universe", {
            "select": "id,ticker,name,sector",
            "id":     f"in.{ids_param}",
        })
        id_to_stock = {s["id"]: s for s in universe}

        results = []
        for r in rows:
            stk = id_to_stock.get(r["stock_id"], {})
            results.append({
                "ticker":           stk.get("ticker", "?"),
                "name":             stk.get("name", "") or "",
                "sector":           stk.get("sector", "") or "",
                "date":             str(r["date"])[:10],
                "eps_estimated":     r.get("eps_estimated"),
                "revenue_estimated": r.get("revenue_estimated"),
            })
        return results

    def fetch_transcript_lag(threshold_days: int = 7) -> list:
        from datetime import datetime as _dt

        # 1) get all active stocks
        universe = _sb_get("stock_universe", {
            "select": "id,ticker,name",
            "active": "eq.true",
        })
        if not universe:
            return []
        id_to_stock = {s["id"]: s for s in universe}
        stock_ids   = list(id_to_stock.keys())
        ids_param   = "(" + ",".join(str(i) for i in stock_ids) + ")"

        # 2) ALL actual earnings rows for active stocks — no limit trick,
        #    fetch everything and find max date per stock in Python
        earn_rows = _sb_get("earnings", {
            "select":     "stock_id,date",
            "stock_id":   f"in.{ids_param}",
            "eps_actual": "not.is.null",
            "order":      "date.desc",
            "limit":      "50000",
        })
        # latest earnings date per stock
        latest_earn = {}
        for r in earn_rows:
            sid = r["stock_id"]
            d   = r["date"][:10]
            if sid not in latest_earn or d > latest_earn[sid]:
                latest_earn[sid] = d

        # 3) ALL transcript rows for active stocks
        trans_rows = _sb_get("earnings_transcripts", {
            "select":          "stock_id,earnings_date,year,quarter",
            "stock_id":        f"in.{ids_param}",
            "transcript_text": "not.is.null",
            "order":           "year.desc,quarter.desc",
            "limit":           "50000",
        })
        # latest transcript per stock — pick highest (year, quarter)
        latest_trans = {}
        for r in trans_rows:
            sid = r["stock_id"]
            if sid not in latest_trans:
                latest_trans[sid] = r
            else:
                prev = latest_trans[sid]
                if (r["year"], r["quarter"]) > (prev["year"], prev["quarter"]):
                    latest_trans[sid] = r

        # 4) compare and collect lags
        results = []
        for sid, ed in latest_earn.items():
            tr = latest_trans.get(sid)
            if not tr:
                continue
            td = (tr.get("earnings_date") or "")[:10]
            if not td:
                continue
            try:
                delta = (_dt.fromisoformat(ed) - _dt.fromisoformat(td)).days
                # delta can be negative if transcript date is ahead of earnings date
                # we only care about transcript LAGGING behind earnings (positive delta)
                if delta <= threshold_days:
                    continue
            except ValueError:
                continue
            stk = id_to_stock.get(sid)
            if not stk:
                continue
            results.append({
                "ticker":          stk.get("ticker", "?"),
                "name":            stk.get("name", "") or "",
                "earnings_date":   ed,
                "transcript_date": td,
                "lag_days":        delta,
                "quarter":         f"Q{tr['quarter']} {tr['year']}",
            })
        results.sort(key=lambda x: x["lag_days"], reverse=True)
        return results

    # ── admin panel UI ─────────────────────────────────────────────────────

    def _admin_section():
        return ui.column().classes("w-full").style(
            f"background:{PANEL};border:1px solid {BORDER2};"
            f"border-radius:4px;padding:16px 20px;gap:8px"
        )

    def _admin_col_hdr(*labels):
        with ui.row().classes("w-full").style(
            f"border-bottom:1px solid {BORDER2};padding-bottom:6px;margin-bottom:2px"
        ):
            for lbl, w in labels:
                ui.label(lbl).style(
                    f"color:{MUTED};font-size:10px;font-weight:600;"
                    f"letter-spacing:0.8px;width:{w}px;flex-shrink:0"
                )

    def _admin_spinner(container, msg="Loading…"):
        container.clear()
        with container:
            with ui.row().classes("items-center gap-2").style("padding:12px 0"):
                ui.spinner(size="20px").style(f"color:{AMBER}")
                ui.label(msg).style(f"color:{MUTED};font-size:11px")

    def _admin_error(container, exc):
        container.clear()
        with container:
            with ui.column().style("padding:12px 0;gap:4px"):
                ui.label("Error:").style(f"color:{RED};font-size:11px;font-weight:600")
                ui.label(str(exc)).style(f"color:{MUTED};font-size:10px;white-space:pre-wrap")

    def build_admin_panel():
        admin_panel.clear()
        with admin_panel:
            # ── page header ────────────────────────────────────────────────
            ui.label("ADMIN · DATA QUALITY & ALERTS").style(
                f"color:{MUTED};font-size:10px;font-weight:600;letter-spacing:1px"
            )

            # ── 3 action buttons ───────────────────────────────────────────
            with ui.row().classes("items-center gap-2").style("margin:8px 0 16px"):
                btn_movers   = ui.button("1D Movers ≥ 4%",   icon="trending_up").style(
                    f"background:{CARD};color:{TEXT};border:1px solid {BORDER2};"
                    f"font-size:12px;font-weight:500;border-radius:3px"
                )
                btn_earnings = ui.button("Upcoming Earnings", icon="event").style(
                    f"background:{CARD};color:{TEXT};border:1px solid {BORDER2};"
                    f"font-size:12px;font-weight:500;border-radius:3px"
                )
                btn_lag      = ui.button("Transcript Lag > 7d", icon="schedule").style(
                    f"background:{CARD};color:{TEXT};border:1px solid {BORDER2};"
                    f"font-size:12px;font-weight:500;border-radius:3px"
                )
                btn_upload   = ui.button("Upload Transcript", icon="upload_file").style(
                    f"background:{CARD};color:{TEXT};border:1px solid {BORDER2};"
                    f"font-size:12px;font-weight:500;border-radius:3px"
                )

            # ── result area ────────────────────────────────────────────────
            result_area = ui.column().classes("w-full").style("gap:0")

            # ── button handlers ────────────────────────────────────────────

            async def on_movers():
                _admin_spinner(result_area, "Fetching movers…")
                try:
                    movers = await asyncio.to_thread(fetch_large_movers)
                except Exception as exc:
                    log.exception("fetch_large_movers failed")
                    _admin_error(result_area, exc)
                    return
                result_area.clear()
                with result_area:
                    with _admin_section():
                        with ui.row().classes("items-center gap-2").style("margin-bottom:10px"):
                            ui.icon("trending_up").style(f"color:{AMBER};font-size:16px")
                            ui.label("1D PRICE MOVES  ≥ 4%").style(
                                f"color:{TEXT};font-size:12px;font-weight:600;letter-spacing:0.5px"
                            )
                            ui.badge(str(len(movers))).style(
                                f"background:{AMBER}33;color:{AMBER};font-size:10px;padding:2px 8px;border-radius:10px"
                            )
                        if not movers:
                            ui.label("No stocks moved ≥ 4% in the last session.").style(
                                f"color:{MUTED};font-size:11px"
                            )
                        else:
                            _admin_col_hdr(
                                ("TICKER",80),("NAME",220),("DATE",100),
                                ("PRICE",90),("1D CHG %",90),("PREV CLOSE",90),("",80)
                            )
                            for m in movers:
                                col  = GREEN if m["change_pct"] > 0 else RED
                                sign = "+" if m["change_pct"] > 0 else ""

                                with ui.column().classes("w-full").style("gap:0"):
                                    with ui.row().classes("w-full items-center").style(
                                        f"padding:5px 0;border-bottom:1px solid {BORDER}22"
                                    ):
                                        ui.label(m["ticker"]).style(
                                            f"color:{ACCENT};font-size:11px;font-weight:600;"
                                            f"width:80px;flex-shrink:0;cursor:pointer"
                                        ).on("click", lambda t=m["ticker"]: (
                                            ticker_input.set_value(t),
                                            asyncio.create_task(run_analysis(t)),
                                            switch_to_stock(),
                                        ))
                                        ui.label(m["name"][:28]).style(f"color:{MUTED};font-size:11px;width:220px;flex-shrink:0")
                                        ui.label(m["date"]).style(f"color:{MUTED};font-size:11px;width:100px;flex-shrink:0")
                                        ui.label(f"{m['price']:,.2f}").style(f"color:{TEXT};font-size:11px;width:90px;flex-shrink:0;font-variant-numeric:tabular-nums")
                                        ui.label(f"{sign}{m['change_pct']:.2f}%").style(f"color:{col};font-size:11px;font-weight:600;width:90px;flex-shrink:0")
                                        ui.label(f"{m['prev']:,.2f}").style(f"color:{MUTED};font-size:11px;width:90px;flex-shrink:0;font-variant-numeric:tabular-nums")
                                        news_btn = ui.button("News", icon="newspaper").props("flat dense").style(
                                            f"color:{MUTED};font-size:10px;flex-shrink:0"
                                        )

                                    news_panel = ui.column().classes("w-full").style(
                                        f"background:{BG};border-left:2px solid {ACCENT}44;"
                                        f"padding:10px 14px 6px;gap:8px;margin-bottom:2px"
                                    )
                                    news_panel.set_visibility(False)

                                    # capture loop vars in closure
                                    def _wire(ticker, trade_date, panel, btn):
                                        loaded = {"done": False}
                                        open_  = {"v": False}

                                        async def _on_click():
                                            open_["v"] = not open_["v"]
                                            panel.set_visibility(open_["v"])
                                            btn.style(
                                                f"color:{ACCENT};font-size:10px;flex-shrink:0"
                                                if open_["v"] else
                                                f"color:{MUTED};font-size:10px;flex-shrink:0"
                                            )
                                            if not open_["v"] or loaded["done"]:
                                                return
                                            # first open: fetch
                                            loaded["done"] = True
                                            panel.clear()
                                            with panel:
                                                with ui.row().classes("items-center gap-2"):
                                                    ui.spinner(size="14px").style(f"color:{AMBER}")
                                                    ui.label(f"Loading news for {ticker}…").style(f"color:{MUTED};font-size:10px")
                                            try:
                                                arts = await asyncio.to_thread(fetch_stock_news, ticker, trade_date)
                                            except Exception as exc:
                                                panel.clear()
                                                with panel:
                                                    ui.label(f"Error: {exc}").style(f"color:{RED};font-size:10px")
                                                return
                                            panel.clear()
                                            with panel:
                                                if not arts:
                                                    ui.label(f"No news around {trade_date}.").style(f"color:{MUTED};font-size:10px")
                                                for art in arts:
                                                    with ui.column().classes("w-full").style(f"gap:2px;padding:5px 0;border-bottom:1px solid {BORDER}33"):
                                                        with ui.row().classes("items-center gap-3"):
                                                            ui.label(art["date"]).style(f"color:{DIM};font-size:10px;flex-shrink:0")
                                                            ui.label(art["source"]).style(f"color:{MUTED};font-size:10px;font-weight:500;flex-shrink:0")
                                                        ui.link(art["title"], art["url"], new_tab=True).style(
                                                            f"color:{ACCENT};font-size:11px;font-weight:500;line-height:1.35;text-decoration:none"
                                                        )
                                                        if art["text"]:
                                                            ui.label(art["text"]).style(
                                                                f"color:{MUTED};font-size:10px;line-height:1.6;margin-top:2px"
                                                            )

                                        btn.on("click", lambda _: asyncio.create_task(_on_click()))

                                    _wire(m["ticker"], m["date"], news_panel, news_btn)

            async def on_earnings():
                _admin_spinner(result_area, "Fetching upcoming earnings…")
                try:
                    rows = await asyncio.to_thread(fetch_upcoming_earnings)
                except Exception as exc:
                    log.exception("fetch_upcoming_earnings failed")
                    _admin_error(result_area, exc)
                    return
                result_area.clear()
                today_s = date.today().isoformat()
                with result_area:
                    with _admin_section():
                        with ui.row().classes("items-center gap-2").style("margin-bottom:10px"):
                            ui.icon("event").style(f"color:{ACCENT};font-size:16px")
                            ui.label(f"UPCOMING EARNINGS  ·  Today → +5 days").style(
                                f"color:{TEXT};font-size:12px;font-weight:600;letter-spacing:0.5px"
                            )
                            ui.badge(str(len(rows))).style(
                                f"background:{ACCENT}33;color:{ACCENT};font-size:10px;padding:2px 8px;border-radius:10px"
                            )
                        if not rows:
                            ui.label("No earnings scheduled in the next 5 days.").style(
                                f"color:{MUTED};font-size:11px"
                            )
                        else:
                            _admin_col_hdr(
                                ("TICKER",80),("NAME",220),("SECTOR",160),
                                ("DATE",100),("EPS EST",90),("REV EST",110)
                            )
                            for r in rows:
                                is_today = r["date"] == today_s
                                date_col = GREEN if is_today else TEXT
                                date_lbl = "TODAY" if is_today else r["date"]
                                eps  = f"{r['eps_estimated']:,.2f}"  if r["eps_estimated"]  is not None else "—"
                                rev  = f"{r['revenue_estimated']/1e6:,.0f}M" if r["revenue_estimated"] is not None else "—"
                                with ui.row().classes("w-full items-center").style(
                                    f"padding:5px 0;border-bottom:1px solid {BORDER}22"
                                ):
                                    ui.label(r["ticker"]).style(
                                        f"color:{ACCENT};font-size:11px;font-weight:600;"
                                        f"width:80px;flex-shrink:0;cursor:pointer"
                                    ).on("click", lambda t=r["ticker"]: (
                                        ticker_input.set_value(t),
                                        asyncio.create_task(run_analysis(t)),
                                        switch_to_stock(),
                                    ))
                                    ui.label(r["name"][:28]).style(f"color:{MUTED};font-size:11px;width:220px;flex-shrink:0")
                                    ui.label(r["sector"][:22]).style(f"color:{MUTED};font-size:11px;width:160px;flex-shrink:0")
                                    ui.label(date_lbl).style(f"color:{date_col};font-size:11px;font-weight:600;width:100px;flex-shrink:0")
                                    ui.label(eps).style(f"color:{TEXT};font-size:11px;width:90px;flex-shrink:0;font-variant-numeric:tabular-nums")
                                    ui.label(rev).style(f"color:{MUTED};font-size:11px;width:110px;flex-shrink:0;font-variant-numeric:tabular-nums")

            async def on_lag():
                _admin_spinner(result_area, "Checking transcript lag…")
                try:
                    rows = await asyncio.to_thread(fetch_transcript_lag)
                except Exception as exc:
                    log.exception("fetch_transcript_lag failed")
                    _admin_error(result_area, exc)
                    return
                result_area.clear()
                with result_area:
                    with _admin_section():
                        with ui.row().classes("items-center gap-2").style("margin-bottom:10px"):
                            ui.icon("schedule").style(f"color:{RED};font-size:16px")
                            ui.label("EARNINGS  vs  TRANSCRIPT DATE  > 7 DAYS").style(
                                f"color:{TEXT};font-size:12px;font-weight:600;letter-spacing:0.5px"
                            )
                            ui.badge(str(len(rows))).style(
                                f"background:{RED}33;color:{RED};font-size:10px;padding:2px 8px;border-radius:10px"
                            )
                        if not rows:
                            ui.label("All transcripts are within 7 days of earnings.").style(
                                f"color:{MUTED};font-size:11px"
                            )
                        else:
                            _admin_col_hdr(
                                ("TICKER",80),("NAME",220),("QUARTER",80),
                                ("EARNINGS DATE",120),("TRANSCRIPT DATE",130),("LAG",60)
                            )
                            for r in rows:
                                lag_col = RED if r["lag_days"] > 30 else AMBER
                                with ui.row().classes("w-full items-center").style(
                                    f"padding:5px 0;border-bottom:1px solid {BORDER}22"
                                ):
                                    ui.label(r["ticker"]).style(f"color:{ACCENT};font-size:11px;font-weight:600;width:80px;flex-shrink:0")
                                    ui.label(r["name"][:28]).style(f"color:{MUTED};font-size:11px;width:220px;flex-shrink:0")
                                    ui.label(r["quarter"]).style(f"color:{MUTED};font-size:11px;width:80px;flex-shrink:0")
                                    ui.label(r["earnings_date"]).style(f"color:{TEXT};font-size:11px;width:120px;flex-shrink:0")
                                    ui.label(r["transcript_date"]).style(f"color:{TEXT};font-size:11px;width:130px;flex-shrink:0")
                                    ui.label(f"{r['lag_days']}d").style(f"color:{lag_col};font-size:11px;font-weight:600;width:60px;flex-shrink:0")

            async def on_upload():
                result_area.clear()
                with result_area:
                    with _admin_section():
                        with ui.row().classes("items-center gap-2").style("margin-bottom:14px"):
                            ui.icon("upload_file").style(f"color:{ACCENT};font-size:16px")
                            ui.label("UPLOAD EARNINGS TRANSCRIPT").style(
                                f"color:{TEXT};font-size:12px;font-weight:600;letter-spacing:0.5px"
                            )

                        LABEL = f"color:{MUTED};font-size:10px;font-weight:600;letter-spacing:0.6px;margin-bottom:2px"
                        INP   = f"background:{BG};border:1px solid {BORDER2};border-radius:3px;"                                 f"color:{TEXT};font-size:12px;padding:6px 10px"

                        # ── stock search ───────────────────────────────────
                        ui.label("STOCK").style(LABEL)
                        stock_options = {
                            r["ticker"]: r["id"]
                            for r in _sb_get("stock_universe", {
                                "select": "id,ticker,name",
                                "active": "eq.true",
                                "order":  "ticker.asc",
                            })
                        }
                        ticker_sel = ui.select(
                            options=list(stock_options.keys()),
                            label="Select ticker",
                            with_input=True,
                        ).style(f"width:200px")

                        # ── year / quarter / date row ──────────────────────
                        with ui.row().classes("items-center gap-4").style("margin-top:10px"):
                            with ui.column().style("gap:2px"):
                                ui.label("YEAR").style(LABEL)
                                year_inp = ui.number(
                                    label="Year",
                                    value=date.today().year,
                                    min=2000, max=2100, step=1,
                                    format="%.0f",
                                ).style("width:100px")

                            with ui.column().style("gap:2px"):
                                ui.label("QUARTER").style(LABEL)
                                quarter_sel = ui.select(
                                    options=[1, 2, 3, 4],
                                    label="Q",
                                    value=((date.today().month - 1) // 3) + 1,
                                ).style("width:80px")

                            with ui.column().style("gap:2px"):
                                ui.label("EARNINGS DATE").style(LABEL)
                                date_inp = ui.input(
                                    label="YYYY-MM-DD",
                                    value=date.today().isoformat(),
                                ).style("width:160px")

                        # ── transcript text ────────────────────────────────
                        ui.label("TRANSCRIPT TEXT").style(f"{LABEL};margin-top:12px")
                        transcript_area = ui.textarea(
                            label="Paste full transcript text here…",
                        ).style(
                            f"width:100%;min-height:320px;font-family:monospace;"
                            f"font-size:11px;line-height:1.5"
                        ).props("outlined autogrow")

                        # ── status label + submit ──────────────────────────
                        status_lbl = ui.label("").style(f"font-size:11px;min-height:18px")

                        async def do_submit():
                            ticker_val = ticker_sel.value
                            year_val   = int(year_inp.value or 0)
                            qtr_val    = int(quarter_sel.value or 0)
                            date_val   = (date_inp.value or "").strip()
                            text_val   = (transcript_area.value or "").strip()

                            # validation
                            errors = []
                            if not ticker_val:
                                errors.append("Select a ticker")
                            if year_val < 2000:
                                errors.append("Enter a valid year")
                            if qtr_val not in (1, 2, 3, 4):
                                errors.append("Select a quarter")
                            if not date_val:
                                errors.append("Enter the earnings date")
                            if not text_val:
                                errors.append("Transcript text is empty")
                            if errors:
                                status_lbl.style(f"color:{RED};font-size:11px")
                                status_lbl.set_text("  ·  ".join(errors))
                                return

                            stock_id = stock_options.get(ticker_val)
                            if not stock_id:
                                status_lbl.style(f"color:{RED};font-size:11px")
                                status_lbl.set_text(f"Ticker '{ticker_val}' not found in universe")
                                return

                            status_lbl.style(f"color:{MUTED};font-size:11px")
                            status_lbl.set_text("Saving…")
                            submit_btn.props("disabled")

                            def _upsert():
                                return db().table("earnings_transcripts").upsert({
                                    "stock_id":        stock_id,
                                    "ticker":          ticker_val,
                                    "year":            year_val,
                                    "quarter":         qtr_val,
                                    "earnings_date":   date_val,
                                    "transcript_text": text_val,
                                }, on_conflict="stock_id,year,quarter").execute()

                            try:
                                await asyncio.to_thread(_upsert)
                                status_lbl.style(f"color:{GREEN};font-size:11px")
                                status_lbl.set_text(
                                    f"✓  Saved transcript for {ticker_val} Q{qtr_val} {year_val}"
                                )
                                submit_btn.props(remove="disabled")
                                transcript_area.set_value("")
                            except Exception as exc:
                                log.exception("transcript upsert failed")
                                status_lbl.style(f"color:{RED};font-size:11px")
                                status_lbl.set_text(f"Save failed: {exc}")
                                submit_btn.props(remove="disabled")

                        with ui.row().classes("items-center gap-3").style("margin-top:10px"):
                            submit_btn = ui.button("Save Transcript", icon="save").style(
                                f"background:{ACCENT};color:#000;font-size:12px;"
                                f"font-weight:600;border-radius:3px"
                            )
                            status_lbl

                        submit_btn.on("click", lambda _: asyncio.create_task(do_submit()))

            btn_movers.on("click",   lambda: asyncio.create_task(on_movers()))
            btn_earnings.on("click", lambda: asyncio.create_task(on_earnings()))
            btn_lag.on("click",      lambda: asyncio.create_task(on_lag()))
            btn_upload.on("click",   lambda: asyncio.create_task(on_upload()))

    # ── tab switching ──────────────────────────────────────────────────────
    def switch_to_admin():
        tab_stock.classes(remove="active")
        tab_admin.classes(add="active")
        stock_panel.style("display:none")
        admin_panel.style("display:flex")
        build_admin_panel()

    def switch_to_stock():
        tab_admin.classes(remove="active")
        tab_stock.classes(add="active")
        admin_panel.style("display:none")
        stock_panel.style("display:flex")

    tab_admin.on("click", switch_to_admin)
    tab_stock.on("click", switch_to_stock)

    search_btn.on("click", lambda: asyncio.create_task(run_analysis(ticker_input.value)))
    ticker_input.on("keydown.enter", lambda: asyncio.create_task(run_analysis(ticker_input.value)))
    research_btn.on("click", run_research_for_ticker)
    view_research_btn.on("click", lambda: open_research_dialog(s.saved_research) if s.saved_research else None)
    rating_history_btn.on("click", lambda: open_rating_history(
        ticker_input.value.strip().upper(),
        (s.saved_research or {}).get("analyst_summary", {}).get("current_price") or 0,
    ))
    for days, btn in refs["period_btns"].items():
        btn.on("click", lambda d=days: asyncio.create_task(on_period(d)))


ui.run(
    title="Agentic Portfolio Management",
    port=8722, dark=True, reload=False,
    storage_secret="apm-secret-2026",
)
