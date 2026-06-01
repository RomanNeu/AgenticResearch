# price_chart.py
"""
Generate a price chart for any ticker in the stock_universe.
Pulls data from stock_prices and stock_technicals in Supabase.
Outputs an interactive HTML file with Plotly.

Usage:
    python price_chart.py AAPL
    python price_chart.py AAPL --period 6m
    python price_chart.py NESN.SW --period 1y
"""
import os
import sys
import argparse
import webbrowser
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from supabase import create_client
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase     = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── colour palette (dark theme) ───────────────────────────────────────────────
BG_DARK   = "#0f172a"
BG_PANEL  = "#1e293b"
GRID      = "#334155"
TEXT      = "#94a3b8"
WHITE     = "#f1f5f9"
BLUE      = "#3b82f6"
TEAL      = "#14b8a6"
GREEN     = "#22c55e"
RED       = "#ef4444"
AMBER     = "#f59e0b"
PURPLE    = "#a855f7"
ORANGE    = "#f97316"
MUTED     = "#64748b"


def period_to_days(period: str) -> int:
    mapping = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730, "5y": 1825}
    return mapping.get(period.lower(), 365)


def get_stock_info(ticker: str) -> dict | None:
    result = (
        supabase.table("stock_universe")
        .select("id, ticker, name, sector, industry, exchange, country")
        .eq("ticker", ticker.upper())
        .limit(1)
        .execute()
        .data
    )
    return result[0] if result else None


def get_prices(stock_id: str, from_date: date) -> list[dict]:
    result = (
        supabase.table("stock_prices")
        .select("date, price, volume")
        .eq("stock_id", stock_id)
        .gte("date", from_date.isoformat())
        .order("date", desc=False)
        .execute()
        .data
    )
    return result


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


def get_sma_history(stock_id: str, from_date: date) -> list[dict]:
    """Compute SMAs from raw prices for the chart period."""
    # fetch extra history before from_date to warm up SMA windows
    extended_from = (from_date - timedelta(days=250)).isoformat()
    result = (
        supabase.table("stock_prices")
        .select("date, price")
        .eq("stock_id", stock_id)
        .gte("date", extended_from)
        .order("date", desc=False)
        .execute()
        .data
    )
    return result


def compute_sma(prices: list[float], window: int) -> list[float | None]:
    sma = []
    for i in range(len(prices)):
        if i < window - 1:
            sma.append(None)
        else:
            sma.append(round(sum(prices[i - window + 1:i + 1]) / window, 4))
    return sma


def build_chart(ticker: str, period: str = "1y", open_browser: bool = True):
    ticker = ticker.upper()
    print(f"Fetching data for {ticker}...")

    # ── fetch data ─────────────────────────────────────────────────────────────
    info = get_stock_info(ticker)
    if not info:
        print(f"  ✗ Ticker '{ticker}' not found in stock_universe.")
        return

    stock_id  = info["id"]
    days      = period_to_days(period)
    from_date = date.today() - timedelta(days=days)

    prices    = get_prices(stock_id, from_date)
    tech      = get_technicals(stock_id)
    sma_hist  = get_sma_history(stock_id, from_date)

    if not prices:
        print(f"  ✗ No price data found for {ticker}.")
        return

    print(f"  ✓ {len(prices)} price rows loaded")

    # ── prepare series ─────────────────────────────────────────────────────────
    dates      = [r["date"] for r in prices]
    closes     = [r["price"] for r in prices]
    volumes    = [r["volume"] or 0 for r in prices]

    # compute SMAs over extended history, then slice to chart period
    all_dates  = [r["date"] for r in sma_hist]
    all_prices = [r["price"] for r in sma_hist]

    sma20_all  = compute_sma(all_prices, 20)
    sma50_all  = compute_sma(all_prices, 50)
    sma100_all = compute_sma(all_prices, 100)
    sma200_all = compute_sma(all_prices, 200)

    # slice to the chart period
    from_str   = from_date.isoformat()
    chart_idx  = [i for i, d in enumerate(all_dates) if d >= from_str]

    sma20  = [sma20_all[i]  for i in chart_idx]
    sma50  = [sma50_all[i]  for i in chart_idx]
    sma100 = [sma100_all[i] for i in chart_idx]
    sma200 = [sma200_all[i] for i in chart_idx]

    # price change for colouring
    price_start  = closes[0]
    price_end    = closes[-1]
    price_change = round(price_end - price_start, 2)
    pct_change   = round((price_end - price_start) / price_start * 100, 2)
    line_color   = GREEN if pct_change >= 0 else RED

    # RSI from technicals (single value — shown as annotation)
    rsi = tech.get("rsi_14") if tech else None

    # ── build figure ───────────────────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # price line
    fig.add_trace(
        go.Scatter(
            x=dates, y=closes,
            name="Price",
            line=dict(color=line_color, width=2),
            hovertemplate="<b>%{x}</b><br>Price: %{y:.2f}<extra></extra>",
        ),
        row=1, col=1
    )

    # filled area under price
    fig.add_trace(
        go.Scatter(
            x=dates, y=closes,
            fill="tozeroy",
            fillcolor=f"rgba({int(line_color[1:3], 16)},{int(line_color[3:5], 16)},{int(line_color[5:7], 16)},0.08)",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1, col=1
    )

    # SMAs
    sma_configs = [
        (sma20,  "SMA 20",  BLUE,   1.2),
        (sma50,  "SMA 50",  AMBER,  1.2),
        (sma100, "SMA 100", PURPLE, 1.2),
        (sma200, "SMA 200", ORANGE, 1.5),
    ]
    for sma_data, name, color, width in sma_configs:
        fig.add_trace(
            go.Scatter(
                x=dates, y=sma_data,
                name=name,
                line=dict(color=color, width=width, dash="solid"),
                opacity=0.85,
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}<extra></extra>",
            ),
            row=1, col=1
        )

    # volume bars
    vol_colors = [
        GREEN if i == 0 or closes[i] >= closes[i-1] else RED
        for i in range(len(closes))
    ]
    fig.add_trace(
        go.Bar(
            x=dates, y=volumes,
            name="Volume",
            marker_color=vol_colors,
            marker_opacity=0.5,
            hovertemplate="<b>%{x}</b><br>Volume: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1
    )

    # current SMA levels as horizontal annotations
    if tech and closes:
        latest_price = closes[-1]
        latest_date  = dates[-1]
        for sma_key, label, color in [
            ("sma_20",  "S20",  BLUE),
            ("sma_50",  "S50",  AMBER),
            ("sma_200", "S200", ORANGE),
        ]:
            sma_val = tech.get(sma_key)
            if sma_val:
                fig.add_hline(
                    y=sma_val, line_dash="dot",
                    line_color=color, line_width=0.8,
                    opacity=0.4, row=1, col=1
                )

    # ── layout ─────────────────────────────────────────────────────────────────
    company_name = info.get("name", ticker)
    exchange     = info.get("exchange", "")
    sector       = info.get("sector", "")
    sign         = "+" if pct_change >= 0 else ""

    title_text = (
        f"<b>{ticker}</b>  —  {company_name}"
        f"<br><span style='font-size:13px;color:{MUTED}'>"
        f"{exchange}  |  {sector}  |  "
        f"<span style='color:{line_color}'>{sign}{pct_change}%  ({sign}{price_change})</span>"
        f"  over {period}"
        f"{'  |  RSI: ' + str(round(rsi, 1)) if rsi else ''}"
        f"</span>"
    )

    fig.update_layout(
        title=dict(text=title_text, font=dict(family="Arial", size=18, color=WHITE), x=0.02),
        paper_bgcolor=BG_DARK,
        plot_bgcolor=BG_PANEL,
        font=dict(family="Arial", color=TEXT),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        ),
        margin=dict(l=60, r=40, t=100, b=40),
        height=700,
        xaxis2=dict(
            rangeslider=dict(visible=False),
            showgrid=True, gridcolor=GRID, gridwidth=0.5,
            showline=True, linecolor=GRID,
            tickfont=dict(color=TEXT),
        ),
    )

    # price axis
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, gridwidth=0.5,
        showline=True, linecolor=GRID,
        tickfont=dict(color=TEXT),
        title_text="Price",
        title_font=dict(color=MUTED, size=11),
        row=1, col=1
    )

    # volume axis
    fig.update_yaxes(
        showgrid=True, gridcolor=GRID, gridwidth=0.3,
        tickfont=dict(color=MUTED, size=10),
        title_text="Volume",
        title_font=dict(color=MUTED, size=11),
        tickformat=".2s",
        row=2, col=1
    )

    # x axis
    fig.update_xaxes(
        showgrid=True, gridcolor=GRID, gridwidth=0.5,
        showline=True, linecolor=GRID,
        tickfont=dict(color=TEXT),
    )

    # ── save & open ────────────────────────────────────────────────────────────
    filename = f"{ticker}_{period}_chart.html"
    fig.write_html(filename, include_plotlyjs="cdn")
    print(f"  ✓ Chart saved: {filename}")

    if open_browser:
        webbrowser.open(f"file://{os.path.abspath(filename)}")


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


def build_sentiment_spider(ticker: str, open_browser: bool = True):
    ticker = ticker.upper()
    print(f"Fetching sentiment data for {ticker}...")

    info = get_stock_info(ticker)
    if not info:
        print(f"  ✗ Ticker '{ticker}' not found.")
        return

    transcript = get_latest_transcript(info["id"])
    if not transcript:
        print(f"  ✗ No scored transcript found for {ticker}.")
        return

    sector  = info.get("sector")
    sec_s   = get_sector_sentiment(sector, transcript["year"], transcript["quarter"]) if sector else None

    # ── score definitions ─────────────────────────────────────────────────────
    # for bearish scores we invert (10 - score) so that outward = better on all axes
    categories = [
        ("Sentiment",       "sentiment_score",       "avg_sentiment",        False),
        ("Guidance",        "guidance_score",         "avg_guidance",         False),
        ("Confidence",      "confidence_score",       "avg_confidence",       False),
        ("Fwd Outlook",     "forward_outlook_score",  "avg_forward_outlook",  False),
        ("Innovation",      "innovation_score",       "avg_innovation",       False),
        ("Analyst Trust",   "analyst_trust_score",    "avg_analyst_trust",    False),
        ("Low Risk",        "risk_score",             "avg_risk",             True),   # inverted
        ("Low Deflection",  "deflection_score",       "avg_deflection",       True),   # inverted
        ("Low Hedge",       "hedge_score",            "avg_hedge",            True),   # inverted
        ("Low Uncertainty", "uncertainty_score",      "avg_uncertainty",      True),   # inverted
    ]

    labels      = [c[0] for c in categories]
    ticker_vals = []
    sector_vals = []

    for label, t_key, s_key, invert in categories:
        t_val = transcript.get(t_key)
        s_val = sec_s.get(s_key) if sec_s else None

        ticker_vals.append(round(10 - t_val, 2) if invert and t_val is not None else (t_val or 0))
        sector_vals.append(round(10 - s_val, 2) if invert and s_val is not None else (s_val or 0))

    # close the polygon
    labels_closed      = labels + [labels[0]]
    ticker_vals_closed = ticker_vals + [ticker_vals[0]]
    sector_vals_closed = sector_vals + [sector_vals[0]]

    # ── composite scores ──────────────────────────────────────────────────────
    t_composite = round(sum(ticker_vals) / len(ticker_vals), 2)
    s_composite = round(sum(sector_vals) / len(sector_vals), 2) if sec_s else None

    # ── build chart ───────────────────────────────────────────────────────────
    fig = go.Figure()

    # sector polygon
    if sec_s:
        fig.add_trace(go.Scatterpolar(
            r=sector_vals_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor="rgba(59,130,246,0.12)",
            line=dict(color=BLUE, width=2, dash="dash"),
            name=f"Sector: {sector}  ({s_composite}/10)",
            hovertemplate="<b>%{theta}</b><br>Score: %{r:.1f}/10<extra></extra>",
        ))

    # ticker polygon
    fig.add_trace(go.Scatterpolar(
        r=ticker_vals_closed,
        theta=labels_closed,
        fill="toself",
        fillcolor="rgba(20,184,166,0.18)",
        line=dict(color=TEAL, width=2.5),
        name=f"{ticker}  ({t_composite}/10)",
        hovertemplate="<b>%{theta}</b><br>Score: %{r:.1f}/10<extra></extra>",
    ))

    company_name = info.get("name", ticker)
    period_label = f"Q{transcript['quarter']} {transcript['year']}"
    summary      = transcript.get("one_line_summary", "")

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{ticker}</b> — Earnings Call Sentiment  |  {period_label}"
                f"<br><span style='font-size:12px;color:{MUTED}'>{company_name}"
                f"{'  |  ' + summary if summary else ''}</span>"
            ),
            font=dict(family="Arial", size=17, color=WHITE),
            x=0.5, xanchor="center",
        ),
        polar=dict(
            bgcolor=BG_PANEL,
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickvals=[2, 4, 6, 8, 10],
                tickfont=dict(size=10, color=MUTED),
                gridcolor=GRID,
                linecolor=GRID,
                angle=90,
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color=WHITE, family="Arial"),
                gridcolor=GRID,
                linecolor=GRID,
                direction="clockwise",
            ),
        ),
        paper_bgcolor=BG_DARK,
        font=dict(family="Arial", color=TEXT),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.15,
            xanchor="center", x=0.5,
            font=dict(size=13, color=WHITE),
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=80, r=80, t=120, b=80),
        height=650,
        width=750,
    )

    # ── score table annotation ────────────────────────────────────────────────
    score_lines = []
    for label, t_key, s_key, invert in categories:
        t_raw = transcript.get(t_key)
        s_raw = sec_s.get(s_key) if sec_s else None
        arrow = ""
        if t_raw is not None and s_raw is not None:
            diff = (10 - t_raw if invert else t_raw) - (10 - s_raw if invert else s_raw)
            arrow = "  ▲" if diff > 0 else "  ▼" if diff < 0 else "  ="
        score_lines.append(
            f"{label:<16} {t_raw or 'N/A':>4}   {round(s_raw, 1) if s_raw else 'N/A':>5}{arrow}"
        )

    print(f"\n  {'Score':<16} {'Ticker':>4}   {'Sector':>5}   {'Signal'}")
    print(f"  {'-'*45}")
    for line in score_lines:
        print(f"  {line}")
    print(f"  {'-'*45}")
    print(f"  {'Composite':<16} {t_composite:>4}   {s_composite or 'N/A':>5}")

    if transcript.get("bull_case"):
        print(f"\n  Bull: {transcript['bull_case']}")
    if transcript.get("bear_case"):
        print(f"  Bear: {transcript['bear_case']}")

    # ── save & open ───────────────────────────────────────────────────────────
    filename = f"{ticker}_sentiment_spider.html"
    fig.write_html(filename, include_plotlyjs="cdn")
    print(f"\n  ✓ Spider chart saved: {filename}")

    if open_browser:
        webbrowser.open(f"file://{os.path.abspath(filename)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate charts for a ticker.")
    parser.add_argument("ticker", nargs="?",  help="Ticker symbol (e.g. AAPL, NESN.SW)")
    parser.add_argument("--period", "-p", default="1y",
                        help="Chart period: 1m, 3m, 6m, 1y, 2y, 5y (default: 1y)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not args.ticker:
        while True:
            ticker = input("\nEnter ticker (or 'q' to quit): ").strip()
            if ticker.lower() == "q":
                break
            if not ticker:
                continue

            print("  Chart type:")
            print("    1 — Price chart (price + SMAs + volume)")
            print("    2 — Sentiment spider chart (vs sector)")
            print("    3 — Both")
            choice = input("  Choice [1/2/3] (default: 1): ").strip() or "1"

            if choice in ("1", "3"):
                period = input("  Period [1m/3m/6m/1y/2y/5y] (default: 1y): ").strip() or "1y"
                build_chart(ticker, period, open_browser=not args.no_browser)
            if choice in ("2", "3"):
                build_sentiment_spider(ticker, open_browser=not args.no_browser)
    else:
        build_chart(args.ticker, args.period, open_browser=not args.no_browser)