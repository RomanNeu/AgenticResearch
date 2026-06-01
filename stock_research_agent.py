# stock_research_agent.py
"""
Senior Financial Analyst Research Agent.
Uses OpenAI gpt-4o-mini to produce a structured research report
with Buy/Hold/Sell recommendation, confidence score and price target.

Usage:
    python stock_research_agent.py MSFT
    python stock_research_agent.py AAPL --rebuild
    python stock_research_agent.py NVDA --output nvda_report.json
"""
import os
import json
import argparse
import logging
from datetime import date
from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

client   = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
MODEL    = "gpt-5.4-mini"


# ── context enrichment: price move explanations & prior research ──────────────

def fetch_price_move_explanations(ticker: str, limit: int = 10) -> list:
    """
    Fetch recent high-confidence price move explanations for ticker
    from price_move_explanations table (confidence >= 70).
    """
    try:
        rows = (
            supabase.table("price_move_explanations")
            .select("trade_date,change_pct,explanation,confidence,news_sources")
            .eq("ticker", ticker)
            .gte("confidence", 70)
            .order("trade_date", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return rows or []
    except Exception as e:
        log.warning(f"  fetch_price_move_explanations failed: {e}")
        return []


def fetch_previous_research(ticker: str, limit: int = 3) -> list:
    """
    Fetch most recent saved research reports for ticker so the agent can
    assess whether prior price targets and recommendations are still valid.
    """
    try:
        rows = (
            supabase.table("stock_research")
            .select(
                "report_date,recommendation,confidence_score,conviction,"
                "price_target,price_target_currency,current_price,"
                "upside_potential_pct,one_line_thesis,executive_summary,"
                "bull_case,bear_case,forward_guidance,data_quality_notes"
            )
            .eq("ticker", ticker)
            .order("report_date", desc=True)
            .limit(limit)
            .execute()
            .data
        )
        return rows or []
    except Exception as e:
        log.warning(f"  fetch_previous_research failed: {e}")
        return []


# ── system prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Senior Financial Analyst at a leading institutional investment firm with 20+ years of experience in equity research across global markets. You have deep expertise in fundamental analysis, quantitative factor models, earnings quality assessment, and management communication analysis.

Your research reports are known for:
- Rigorous, evidence-based analysis grounded in data
- Clear, actionable recommendations with well-reasoned conviction
- Transparent risk disclosure and scenario analysis
- Institutional-grade writing: precise, structured, no filler language

You have access to a comprehensive data package for the stock under analysis, including:
- Latest earnings results vs estimates and sector/industry averages
- Quarterly EPS and revenue growth history (last 8 quarters)
- AI-scored earnings call sentiment (10 dimensions, 0-10 scale) vs sector/industry
- Key financial ratios vs sector and industry peers with deltas
- Technical indicators and price momentum (SMAs, RSI, volatility)
- Historical volatility vs sector/industry, vol regime signals
- Price return performance across multiple time windows vs sector/industry
- Recent significant price moves (±4%+) with news-backed explanations and confidence scores
- Previously issued research reports for this stock with price targets and recommendations

PRICE MOVE EXPLANATIONS USAGE:
- Only incorporate move explanations with confidence >= 70
- Use them to identify recent catalysts, news flow, and sentiment shifts
- If a move reveals a material development (earnings surprise, guidance change, M&A, regulatory
  event), reflect it in your risk factors, catalysts, and thesis
- High-confidence negative moves should pressure your price target; positive moves may support it

PRIOR RESEARCH USAGE:
- Review previous price targets: are they still valid given current price and data?
- If the stock has moved significantly since the last report, assess whether the thesis still holds
- If prior target has been exceeded: determine whether to raise, maintain, or flag as stretched
- If prior target has been missed: assess whether thesis is broken or catalyst is delayed
- Explicitly reference prior recommendations when relevant — do NOT simply repeat prior analysis

SENTIMENT SCORE INTERPRETATION (scores 0-10, higher always better — bearish scores already inverted):
- 8-10: strongly positive signal
- 6-8: constructive
- 4-6: neutral / mixed
- Below 4: cautionary signal
- Composite synthesises all 10 dimensions

RECOMMENDATION CRITERIA:
- STRONG BUY: Multiple strongly aligned bullish signals, high conviction
- BUY: Strong fundamental momentum, favorable valuation, positive sentiment
- HOLD: Mixed signals, fair valuation, await catalyst
- SELL: Deteriorating fundamentals, expensive vs peers, weak sentiment
- STRONG SELL: Multiple strongly aligned bearish signals, high conviction

CONFIDENCE SCORE (0-100):
- 85-100: Multiple strongly aligned signals, high data quality
- 70-84: Majority aligned, some uncertainty
- 55-69: Mixed signals
- Below 55: High uncertainty

PRICE TARGET METHODOLOGY — choose the most appropriate and justify:
- P/E relative valuation (for profitable companies with predictable earnings)
- P/S (for high-growth or pre-profit companies)
- EV/EBITDA (for mature businesses)
- DCF (when long-term visibility is high)

Output ONLY valid JSON — no markdown, no preamble, no text outside the JSON object."""


# ── user prompt ───────────────────────────────────────────────────────────────

def build_user_prompt(ctx: dict) -> str:
    ticker   = ctx["meta"]["ticker"]
    company  = ctx["company"]["name"]
    sector   = ctx["company"]["sector"]
    industry = ctx["company"]["industry"]
    ctx_json = json.dumps(ctx, indent=2, default=str)

    schema = f"""{{
  "ticker": "{ticker}",
  "company": "{company}",
  "report_date": "{date.today().isoformat()}",
  "analyst_summary": {{
    "recommendation": "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
    "confidence_score": <integer 0-100>,
    "conviction": "high | medium | low",
    "price_target": <float>,
    "price_target_currency": "USD | EUR | CHF | GBP",
    "current_price": <float from context>,
    "upside_potential_pct": <float, positive=upside negative=downside>,
    "time_horizon": "12 months",
    "one_line_thesis": "<max 20 words>"
  }},
  "executive_summary": "<3-4 sentence investment case>",
  "investment_thesis": {{
    "bull_case": "<paragraph: key upside drivers from data>",
    "bear_case": "<paragraph: key risks and downside>",
    "base_case": "<paragraph: most likely path to price target>"
  }},
  "fundamental_analysis": {{
    "earnings_quality": {{
      "assessment": "strong | good | mixed | weak | deteriorating",
      "eps_growth_trend": "<analysis>",
      "revenue_growth_trend": "<analysis>",
      "beat_miss_pattern": "<consistency analysis>",
      "vs_sector_commentary": "<peer comparison>"
    }},
    "profitability": {{
      "assessment": "strong | good | mixed | weak",
      "gross_margin_commentary": "<analysis>",
      "net_margin_commentary": "<analysis>",
      "return_metrics_commentary": "<ROE/ROA vs peers>"
    }},
    "valuation": {{
      "assessment": "cheap | fair | expensive | very expensive",
      "methodology": "P/E | P/S | EV/EBITDA | DCF | P/B",
      "methodology_rationale": "<why appropriate>",
      "key_multiple": "<e.g. P/E 28x>",
      "target_multiple": "<e.g. P/E 32x>",
      "vs_sector_commentary": "<premium or discount vs peers>",
      "vs_own_history_commentary": "<vs 1Y avg P/E and P/S>"
    }},
    "financial_health": {{
      "assessment": "strong | good | adequate | stretched | concerning",
      "debt_commentary": "<leverage analysis>",
      "liquidity_commentary": "<current ratio and cash generation>"
    }}
  }},
  "sentiment_analysis": {{
    "overall_assessment": "very bullish | bullish | neutral | bearish | very bearish",
    "composite_score": <float>,
    "composite_vs_sector": <float delta>,
    "key_positives": ["<signal 1>", "<signal 2>", "<signal 3>"],
    "key_concerns": ["<concern 1>", "<concern 2>"],
    "management_credibility": "high | medium | low",
    "management_credibility_rationale": "<based on analyst_trust, deflection, confidence>",
    "forward_guidance_quality": "raised | maintained | lowered | withdrawn",
    "transcript_highlights": "<2-3 most important themes from earnings call>"
  }},
  "technical_analysis": {{
    "trend": "strong uptrend | uptrend | sideways | downtrend | strong downtrend",
    "momentum": "overbought | positive | neutral | negative | oversold",
    "key_levels_commentary": "<SMA analysis>",
    "volatility_commentary": "<hvol vs sector, vol regime>",
    "performance_vs_sector": "<return comparison>"
  }},
  "risk_factors": [
    {{"risk": "<description>", "severity": "high | medium | low", "likelihood": "high | medium | low"}},
    {{"risk": "<description>", "severity": "high | medium | low", "likelihood": "high | medium | low"}},
    {{"risk": "<description>", "severity": "high | medium | low", "likelihood": "high | medium | low"}}
  ],
  "catalysts": {{
    "upside_catalysts": ["<catalyst 1>", "<catalyst 2>", "<catalyst 3>"],
    "downside_catalysts": ["<catalyst 1>", "<catalyst 2>"]
  }},
  "price_target_derivation": {{
    "methodology": "<name>",
    "base_metric": "<e.g. NTM EPS of $X.XX>",
    "target_multiple": "<e.g. 28x P/E>",
    "multiple_justification": "<why this multiple given growth, quality, peers>",
    "derived_price_target": <float>,
    "bull_case_target": <float>,
    "bear_case_target": <float>
  }},
  "prior_research_assessment": {{
    "has_prior_reports": <true | false>,
    "prior_target_valid": <true | false | null>,
    "prior_target_commentary": "<is prior PT still valid? was it hit? revised up/down and why>",
    "recommendation_change": "<unchanged | upgraded | downgraded | initiated>",
    "key_changes_since_last_report": "<what has materially changed>"
  }},
  "recent_move_impact": {{
    "material_moves_found": <true | false>,
    "move_commentary": "<how recent price moves and their explanations affect the thesis>",
    "incorporated_in_target": <true | false>
  }},
  "data_quality_notes": "<gaps or caveats>"
}}"""

    # fetch enrichment data
    price_moves   = fetch_price_move_explanations(ticker)
    prior_reports = fetch_previous_research(ticker)

    price_moves_section = ""
    if price_moves:
        lines = []
        for m in price_moves:
            sign = "+" if float(m.get("change_pct", 0)) >= 0 else ""
            lines.append(
                f"  {m['trade_date']}  {sign}{m['change_pct']:.2f}%  "
                f"(confidence: {m['confidence']}/100)\n"
                f"  Explanation: {m['explanation']}"
            )
        price_moves_section = (
            "\n\nRECENT SIGNIFICANT PRICE MOVES (confidence >= 70, news-backed):\n"
            + "\n\n".join(lines)
        )
    else:
        price_moves_section = "\n\nRECENT SIGNIFICANT PRICE MOVES: None on record with confidence >= 70."

    prior_research_section = ""
    if prior_reports:
        lines = []
        for r in prior_reports:
            ccy = r.get("price_target_currency", "")
            pt  = r.get("price_target")
            up  = r.get("upside_potential_pct")
            up_str = f"{up:+.1f}%" if up is not None else "N/A"
            lines.append(
                f"  Report date: {r['report_date']}\n"
                f"  Recommendation: {r.get('recommendation')}  "
                f"Confidence: {r.get('confidence_score')}/100  "
                f"Conviction: {r.get('conviction')}\n"
                f"  Price target: {ccy} {pt}  |  Upside at issuance: {up_str}\n"
                f"  Thesis: {r.get('one_line_thesis')}\n"
                f"  Summary: {r.get('executive_summary', '')[:300]}"
            )
        prior_research_section = (
            "\n\nPREVIOUSLY ISSUED RESEARCH REPORTS (most recent first):\n"
            + "\n\n".join(lines)
            + "\n\nINSTRUCTION: Assess whether prior price targets are still valid. "
            "Revise your recommendation and target accordingly. "
            "Reference prior reports explicitly in prior_research_assessment."
        )
    else:
        prior_research_section = "\n\nPREVIOUSLY ISSUED RESEARCH REPORTS: None on record."

    return f"""Produce a complete equity research report for {ticker} ({company}).

SECTOR: {sector}
INDUSTRY: {industry}
REPORT DATE: {date.today().isoformat()}

DATA PACKAGE:
{ctx_json}{price_moves_section}{prior_research_section}

Return your analysis matching this exact JSON schema:
{schema}"""


# ── agent ─────────────────────────────────────────────────────────────────────

def run_research(ticker: str, context: dict) -> dict:
    log.info(f"Running research agent for {ticker} using {MODEL}...")

    user_prompt = build_user_prompt(context)
    log.info(f"  Prompt size: {len(user_prompt):,} chars")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.1,          # near-deterministic for consistent analysis
        max_completion_tokens=4096,
        response_format={"type": "json_object"},  # enforce JSON output
    )

    raw = response.choices[0].message.content.strip()
    log.info(f"  Response: {len(raw):,} chars  |  "
             f"Tokens: {response.usage.prompt_tokens} in / {response.usage.completion_tokens} out")

    try:
        report = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e}")
        log.error(f"Raw: {raw[:500]}")
        raise

    return report


# ── console summary ───────────────────────────────────────────────────────────

def print_summary(report: dict):
    s   = report.get("analyst_summary", {})
    rec = s.get("recommendation", "N/A")
    ccy = s.get("price_target_currency", "")
    up  = s.get("upside_potential_pct", "N/A")
    w   = 72

    # colour-code recommendation
    rec_colours = {
        "STRONG BUY": "▲▲", "BUY": "▲",
        "HOLD": "■",
        "SELL": "▼", "STRONG SELL": "▼▼",
    }
    symbol = rec_colours.get(rec, "?")

    print(f"\n{'█' * w}")
    print(f"  EQUITY RESEARCH REPORT  ·  {report.get('ticker')}  ·  {report.get('report_date')}")
    print(f"{'█' * w}")
    print(f"  {report.get('company', '')}")
    print(f"{'═' * w}")
    print(f"  {symbol}  RECOMMENDATION:    {rec}")
    print(f"     CONFIDENCE SCORE:  {s.get('confidence_score', 'N/A')} / 100  ({s.get('conviction','').upper()})")
    print(f"     PRICE TARGET:      {ccy} {s.get('price_target', 'N/A')}")
    print(f"     CURRENT PRICE:     {ccy} {s.get('current_price', 'N/A')}")
    up_str = f"+{up}%" if isinstance(up, (int,float)) and up >= 0 else f"{up}%"
    print(f"     UPSIDE POTENTIAL:  {up_str}  ({s.get('time_horizon','12 months')})")
    print(f"{'─' * w}")
    print(f"  THESIS: {s.get('one_line_thesis','')}")
    print(f"{'═' * w}")

    if report.get("executive_summary"):
        print(f"\n  {report['executive_summary']}")

    # sentiment
    sent = report.get("sentiment_analysis", {})
    comp = sent.get("composite_score", "N/A")
    vs_s = sent.get("composite_vs_sector", "N/A")
    vs_str = f"+{vs_s}" if isinstance(vs_s,(int,float)) and vs_s >= 0 else str(vs_s)
    print(f"\n  SENTIMENT: {sent.get('overall_assessment','').upper()}"
          f"  ·  Composite: {comp}/10  ·  vs Sector: {vs_str}")
    if sent.get("key_positives"):
        for p in sent["key_positives"]:
            print(f"    + {p}")
    if sent.get("key_concerns"):
        for c in sent["key_concerns"]:
            print(f"    – {c}")

    # price target derivation
    ptd = report.get("price_target_derivation", {})
    print(f"\n  PRICE TARGET: {ptd.get('methodology','')}  ·  "
          f"{ptd.get('base_metric','')} × {ptd.get('target_multiple','')}")
    print(f"    Bear: {ccy} {ptd.get('bear_case_target','N/A')}"
          f"  ·  Base: {ccy} {ptd.get('derived_price_target','N/A')}"
          f"  ·  Bull: {ccy} {ptd.get('bull_case_target','N/A')}")

    # risks
    risks = report.get("risk_factors", [])
    if risks:
        print(f"\n  KEY RISKS:")
        for r in risks:
            sev = r.get("severity","?").upper()
            print(f"    [{sev}] {r.get('risk','')}")

    # catalysts
    cats = report.get("catalysts", {})
    if cats.get("upside_catalysts"):
        print(f"\n  UPSIDE CATALYSTS:")
        for c in cats["upside_catalysts"]:
            print(f"    ↑ {c}")

    print(f"\n{'═' * w}\n")


# ── save to supabase ─────────────────────────────────────────────────────────

def save_report(report: dict, context: dict) -> str:
    """Save research report to stock_research table. Returns the new row id."""
    ticker   = report.get("ticker", "").upper()
    s        = report.get("analyst_summary", {})
    fund     = report.get("fundamental_analysis", {})
    earn     = fund.get("earnings_quality", {})
    prof     = fund.get("profitability", {})
    val      = fund.get("valuation", {})
    health   = fund.get("financial_health", {})
    sent     = report.get("sentiment_analysis", {})
    tech     = report.get("technical_analysis", {})
    thesis   = report.get("investment_thesis", {})
    ptd      = report.get("price_target_derivation", {})
    cats     = report.get("catalysts", {})

    # look up stock_id
    stock_res = supabase.table("stock_universe").select("id").eq("ticker", ticker).limit(1).execute()
    stock_id  = stock_res.data[0]["id"] if stock_res.data else None

    def safe_num(v):
        try: return float(v) if v is not None else None
        except: return None

    def safe_int(v):
        try: return int(v) if v is not None else None
        except: return None

    row = {
        "stock_id":               stock_id,
        "ticker":                 ticker,

        # recommendation
        "recommendation":         s.get("recommendation"),
        "confidence_score":       safe_int(s.get("confidence_score")),
        "conviction":             s.get("conviction"),
        "time_horizon":           s.get("time_horizon", "12 months"),

        # price target
        "current_price":          safe_num(s.get("current_price")),
        "price_target":           safe_num(s.get("price_target")),
        "price_target_currency":  s.get("price_target_currency"),
        "upside_potential_pct":   safe_num(s.get("upside_potential_pct")),
        "bull_case_target":       safe_num(ptd.get("bull_case_target")),
        "bear_case_target":       safe_num(ptd.get("bear_case_target")),
        "pt_methodology":         ptd.get("methodology"),
        "pt_base_metric":         ptd.get("base_metric"),
        "pt_target_multiple":     ptd.get("target_multiple"),
        "pt_multiple_justification": ptd.get("multiple_justification"),

        # thesis
        "one_line_thesis":        s.get("one_line_thesis"),
        "executive_summary":      report.get("executive_summary"),
        "bull_case":              thesis.get("bull_case"),
        "bear_case":              thesis.get("bear_case"),
        "base_case":              thesis.get("base_case"),

        # fundamental
        "earnings_quality":        earn.get("assessment"),
        "eps_growth_trend":        earn.get("eps_growth_trend"),
        "revenue_growth_trend":    earn.get("revenue_growth_trend"),
        "beat_miss_pattern":       earn.get("beat_miss_pattern"),
        "earnings_vs_sector":      earn.get("vs_sector_commentary"),
        "profitability_assessment":prof.get("assessment"),
        "gross_margin_commentary": prof.get("gross_margin_commentary"),
        "net_margin_commentary":   prof.get("net_margin_commentary"),
        "return_metrics_commentary":prof.get("return_metrics_commentary"),
        "valuation_assessment":    val.get("assessment"),
        "valuation_vs_sector":     val.get("vs_sector_commentary"),
        "valuation_vs_history":    val.get("vs_own_history_commentary"),
        "financial_health":        health.get("assessment"),
        "debt_commentary":         health.get("debt_commentary"),
        "liquidity_commentary":    health.get("liquidity_commentary"),

        # sentiment
        "sentiment_overall":       sent.get("overall_assessment"),
        "sentiment_composite":     safe_num(sent.get("composite_score")),
        "sentiment_vs_sector":     safe_num(sent.get("composite_vs_sector")),
        "management_credibility":  sent.get("management_credibility"),
        "forward_guidance":        sent.get("forward_guidance_quality"),
        "transcript_highlights":   sent.get("transcript_highlights"),
        "sentiment_key_positives": sent.get("key_positives") or [],
        "sentiment_key_concerns":  sent.get("key_concerns") or [],

        # technical
        "trend":                   tech.get("trend"),
        "momentum":                tech.get("momentum"),
        "technical_commentary":    tech.get("key_levels_commentary"),
        "volatility_commentary":   tech.get("volatility_commentary"),
        "performance_vs_sector":   tech.get("performance_vs_sector"),

        # risks & catalysts
        "risk_factors":            report.get("risk_factors") or [],
        "upside_catalysts":        cats.get("upside_catalysts") or [],
        "downside_catalysts":      cats.get("downside_catalysts") or [],

        # full report
        "full_report_json":        report,
        "model":                   MODEL,
        "data_quality_notes":      report.get("data_quality_notes"),
        "report_date":             report.get("report_date"),
    }

    result = supabase.table("stock_research").insert(row).execute()
    new_id = result.data[0]["id"] if result.data else None
    log.info(f"  Saved to stock_research — id: {new_id}")
    return new_id


# ── save to supabase ─────────────────────────────────────────────────────────

def save_report(report: dict, context: dict) -> str:
    """Save research report to stock_research table. Returns the new row id."""
    ticker = report.get("ticker", "").upper()
    s      = report.get("analyst_summary", {})
    fund   = report.get("fundamental_analysis", {})
    earn   = fund.get("earnings_quality", {})
    prof   = fund.get("profitability", {})
    val    = fund.get("valuation", {})
    health = fund.get("financial_health", {})
    sent   = report.get("sentiment_analysis", {})
    tech   = report.get("technical_analysis", {})
    thesis = report.get("investment_thesis", {})
    ptd    = report.get("price_target_derivation", {})
    cats   = report.get("catalysts", {})

    stock_res = supabase.table("stock_universe").select("id").eq("ticker", ticker).limit(1).execute()
    stock_id  = stock_res.data[0]["id"] if stock_res.data else None

    def sn(v):
        try: return float(v) if v is not None else None
        except: return None

    def si(v):
        try: return int(v) if v is not None else None
        except: return None

    row = {
        "stock_id": stock_id, "ticker": ticker,
        "recommendation":           s.get("recommendation"),
        "confidence_score":         si(s.get("confidence_score")),
        "conviction":               s.get("conviction"),
        "time_horizon":             s.get("time_horizon", "12 months"),
        "current_price":            sn(s.get("current_price")),
        "price_target":             sn(s.get("price_target")),
        "price_target_currency":    s.get("price_target_currency"),
        "upside_potential_pct":     sn(s.get("upside_potential_pct")),
        "bull_case_target":         sn(ptd.get("bull_case_target")),
        "bear_case_target":         sn(ptd.get("bear_case_target")),
        "pt_methodology":           ptd.get("methodology"),
        "pt_base_metric":           ptd.get("base_metric"),
        "pt_target_multiple":       ptd.get("target_multiple"),
        "pt_multiple_justification":ptd.get("multiple_justification"),
        "one_line_thesis":          s.get("one_line_thesis"),
        "executive_summary":        report.get("executive_summary"),
        "bull_case":                thesis.get("bull_case"),
        "bear_case":                thesis.get("bear_case"),
        "base_case":                thesis.get("base_case"),
        "earnings_quality":         earn.get("assessment"),
        "eps_growth_trend":         earn.get("eps_growth_trend"),
        "revenue_growth_trend":     earn.get("revenue_growth_trend"),
        "beat_miss_pattern":        earn.get("beat_miss_pattern"),
        "earnings_vs_sector":       earn.get("vs_sector_commentary"),
        "profitability_assessment": prof.get("assessment"),
        "gross_margin_commentary":  prof.get("gross_margin_commentary"),
        "net_margin_commentary":    prof.get("net_margin_commentary"),
        "return_metrics_commentary":prof.get("return_metrics_commentary"),
        "valuation_assessment":     val.get("assessment"),
        "valuation_vs_sector":      val.get("vs_sector_commentary"),
        "valuation_vs_history":     val.get("vs_own_history_commentary"),
        "financial_health":         health.get("assessment"),
        "debt_commentary":          health.get("debt_commentary"),
        "liquidity_commentary":     health.get("liquidity_commentary"),
        "sentiment_overall":        sent.get("overall_assessment"),
        "sentiment_composite":      sn(sent.get("composite_score")),
        "sentiment_vs_sector":      sn(sent.get("composite_vs_sector")),
        "management_credibility":   sent.get("management_credibility"),
        "forward_guidance":         sent.get("forward_guidance_quality"),
        "transcript_highlights":    sent.get("transcript_highlights"),
        "sentiment_key_positives":  sent.get("key_positives") or [],
        "sentiment_key_concerns":   sent.get("key_concerns") or [],
        "trend":                    tech.get("trend"),
        "momentum":                 tech.get("momentum"),
        "technical_commentary":     tech.get("key_levels_commentary"),
        "volatility_commentary":    tech.get("volatility_commentary"),
        "performance_vs_sector":    tech.get("performance_vs_sector"),
        "risk_factors":             report.get("risk_factors") or [],
        "upside_catalysts":         cats.get("upside_catalysts") or [],
        "downside_catalysts":       cats.get("downside_catalysts") or [],
        "full_report_json":         report,
        "model":                    MODEL,
        "data_quality_notes":       report.get("data_quality_notes"),
        "report_date":              report.get("report_date"),
        # new enrichment fields
        "prior_target_valid":       report.get("prior_research_assessment", {}).get("prior_target_valid"),
        "prior_target_commentary":  report.get("prior_research_assessment", {}).get("prior_target_commentary"),
        "recommendation_change":    report.get("prior_research_assessment", {}).get("recommendation_change"),
        "key_changes_since_last":   report.get("prior_research_assessment", {}).get("key_changes_since_last_report"),
        "move_commentary":          report.get("recent_move_impact", {}).get("move_commentary"),
    }

    result = supabase.table("stock_research").insert(row).execute()
    new_id = result.data[0]["id"] if result.data else None
    log.info(f"  Saved to stock_research — id: {new_id}")
    return new_id


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Senior Financial Analyst Research Agent (OpenAI)")
    parser.add_argument("ticker",               help="Ticker symbol (e.g. AAPL, NESN.SW)")
    parser.add_argument("--context", "-c",      help="Path to pre-built context JSON")
    parser.add_argument("--rebuild", "-r",      action="store_true",
                        help="Rebuild context even if file exists")
    parser.add_argument("--output",  "-o",      help="Output JSON file (default: <TICKER>_report.json)")
    parser.add_argument("--no-print",           action="store_true",
                        help="Suppress console summary")
    args = parser.parse_args()

    ticker   = args.ticker.upper()
    ctx_file = args.context or f"{ticker}_context.json"
    out_file = args.output  or f"{ticker}_report.json"

    # ── load or build context ─────────────────────────────────────────────────
    if os.path.exists(ctx_file) and not args.rebuild:
        log.info(f"Loading context from {ctx_file}...")
        with open(ctx_file) as f:
            context = json.load(f)
    else:
        log.info(f"Building context for {ticker}...")
        from stock_context_builder import build_context
        context = build_context(ticker)
        with open(ctx_file, "w") as f:
            json.dump(context, f, indent=2, default=str)
        log.info(f"Context saved to {ctx_file}")

    # ── run agent ─────────────────────────────────────────────────────────────
    report = run_research(ticker, context)

    # ── save to supabase ──────────────────────────────────────────────────────
    try:
        report_id = save_report(report, context)
        report["_supabase_id"] = report_id
    except Exception as e:
        log.warning(f"Failed to save to Supabase: {e}")

    # ── save to file ───────────────────────────────────────────────────────────
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Report saved to {out_file}")

    # ── print summary ─────────────────────────────────────────────────────────
    if not args.no_print:
        print_summary(report)


if __name__ == "__main__":
    main()
