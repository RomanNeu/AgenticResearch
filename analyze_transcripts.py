# analyze_transcripts.py
"""
Reads unanalyzed earnings transcripts from Supabase,
runs structured scoring via OpenAI, and writes scores
back as dedicated columns in the earnings_transcripts table.

SCORING SCHEMA (all scores 0-10 integers)
==========================================

sentiment_score
    Overall tone of the entire transcript.
    0 = very negative (warnings, losses, cuts)
    5 = neutral / mixed
    10 = very positive (records, beats, optimism)

guidance_score
    Direction and strength of forward guidance.
    0 = severely lowered or withdrawn
    5 = maintained / in line with expectations
    10 = significantly raised across multiple metrics

confidence_score
    Management's confidence level in prepared remarks.
    0 = defensive, apologetic, vague
    5 = measured, balanced
    10 = assertive, specific, conviction-driven

uncertainty_score
    Frequency and severity of uncertain/hedged outlook language.
    0 = very clear, specific, committed statements
    5 = some uncertainty acknowledged
    10 = highly uncertain, many qualifiers, unclear path forward
    NOTE: high uncertainty_score is bearish

hedge_score
    Density of hedging language ("may", "could", "subject to", "assuming").
    0 = direct, committed, no hedging
    5 = moderate hedging
    10 = heavily hedged, almost every forward statement qualified
    NOTE: high hedge_score is bearish

analyst_trust_score
    Inferred analyst satisfaction based on Q&A dynamics.
    0 = analysts frustrated, skeptical, pressing hard
    5 = neutral engagement
    10 = analysts satisfied, constructive questions, positive tone

deflection_score
    How often management redirects, avoids or gives non-answers in Q&A.
    0 = fully transparent, direct answers to all questions
    5 = occasional deflection
    10 = high evasion, repeated redirection, refusal to quantify
    NOTE: high deflection_score is bearish

forward_outlook_score
    Strength and positivity of forward-looking statements.
    0 = no outlook provided or explicitly negative
    5 = cautiously optimistic / in line
    10 = very bullish, specific targets raised, strong demand signals

risk_score
    Volume and severity of new or escalating risk factors mentioned.
    0 = no new risks, business as usual
    5 = some macro/sector risks acknowledged
    10 = many new risks, elevated macro concerns, structural headwinds
    NOTE: high risk_score is bearish

innovation_score
    Mentions of AI, new products, R&D investment, strategic initiatives.
    0 = no mention of innovation or future investment
    5 = some mentions, moderate investment signaled
    10 = heavy focus on AI/innovation, major new initiatives announced
"""

import os
import json
import logging
import time
from datetime import datetime, UTC
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_SERVICE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client   = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-5.4-mini"

SYSTEM_PROMPT = """
You are a senior financial analyst specializing in earnings call analysis.
Analyze the provided earnings call transcript and return a JSON object only —
no preamble, no markdown, no explanation.
""".strip()

USER_PROMPT = """
Analyze this earnings call transcript for {ticker} Q{quarter} {year} and return
a JSON object with exactly this structure. All scores are 0-10 integers.
No preamble, no markdown, just JSON.

{{
  "sentiment_score":       <0-10, where 0=very negative, 5=neutral, 10=very positive>,
  "guidance_score":        <0-10, where 0=severely lowered, 5=maintained, 10=significantly raised>,
  "confidence_score":      <0-10, where 0=defensive/vague, 5=measured, 10=assertive/conviction>,
  "uncertainty_score":     <0-10, where 0=very clear outlook, 5=some uncertainty, 10=highly uncertain>,
  "hedge_score":           <0-10, where 0=direct/committed, 5=moderate hedging, 10=heavily hedged>,
  "analyst_trust_score":   <0-10, where 0=analysts skeptical/pressing, 5=neutral, 10=analysts satisfied>,
  "deflection_score":      <0-10, where 0=fully transparent, 5=some deflection, 10=high evasion>,
  "forward_outlook_score": <0-10, where 0=no outlook/negative, 5=cautious, 10=very bullish>,
  "risk_score":            <0-10, where 0=no new risks, 5=some macro risks, 10=many elevated risks>,
  "innovation_score":      <0-10, where 0=no mention of innovation, 5=some investment, 10=major AI/new initiatives>,

  "top_topics":       [<up to 5 strings, most discussed themes>],
  "risk_factors":     [<up to 3 strings, specific risks mentioned>],
  "one_line_summary": "<max 20 words capturing the single most important takeaway>",
  "bull_case":        "<max 15 words>",
  "bear_case":        "<max 15 words>"
}}

Transcript:
{transcript}
"""


def analyze_transcript(ticker: str, quarter: int, year: int, text: str) -> dict:
    # truncate to ~12k words to stay within token limits
    words = text.split()
    if len(words) > 12000:
        text = " ".join(words[:12000]) + "\n[transcript truncated]"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_PROMPT.format(
                ticker=ticker, quarter=quarter, year=year, transcript=text
            )},
        ],
        temperature=0.1,
        max_completion_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def main():
    # fetch all transcripts with content
    rows = (
        supabase.table("earnings_transcripts")
        .select(
            "id, ticker, year, quarter, transcript_text, sentiment_score"
        )
        .not_.is_("transcript_text", "null")
        .execute()
        .data
    )

    # only process rows not yet scored
    unanalyzed = [
        r for r in rows
        if r.get("sentiment_score") is None
    ]

    log.info(f"{len(unanalyzed)} transcripts to score (of {len(rows)} total)")

    success, failed = 0, 0

    for i, row in enumerate(unanalyzed):
        ticker  = row["ticker"]
        year    = row["year"]
        quarter = row["quarter"]
        log.info(f"[{i+1}/{len(unanalyzed)}] {ticker} Q{quarter} {year}...")

        try:
            scores = analyze_transcript(ticker, quarter, year, row["transcript_text"])

            supabase.table("earnings_transcripts").update({
                "sentiment_score":       scores["sentiment_score"],
                "guidance_score":        scores["guidance_score"],
                "confidence_score":      scores["confidence_score"],
                "uncertainty_score":     scores["uncertainty_score"],
                "hedge_score":           scores["hedge_score"],
                "analyst_trust_score":   scores["analyst_trust_score"],
                "deflection_score":      scores["deflection_score"],
                "forward_outlook_score": scores["forward_outlook_score"],
                "risk_score":            scores["risk_score"],
                "innovation_score":      scores["innovation_score"],
                "top_topics":            scores["top_topics"],
                "risk_factors":          scores["risk_factors"],
                "one_line_summary":      scores["one_line_summary"],
                "bull_case":             scores["bull_case"],
                "bear_case":             scores["bear_case"],
                "analyzed_at":           datetime.now(UTC).isoformat(),
                "analysis_model":        MODEL,
            }).eq("id", row["id"]).execute()

            log.info(
                f"  ✓ sentiment={scores['sentiment_score']} "
                f"guidance={scores['guidance_score']} "
                f"confidence={scores['confidence_score']} "
                f"risk={scores['risk_score']} "
                f"| {scores['one_line_summary'][:80]}"
            )
            success += 1

        except Exception as e:
            log.error(f"  Failed for {ticker} Q{quarter} {year}: {e}")
            failed += 1

        time.sleep(0.5)

    log.info(f"\nDone — {success} scored, {failed} failed")


if __name__ == "__main__":
    main()