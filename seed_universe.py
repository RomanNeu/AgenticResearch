# seed_universe.py
"""
Seeds stock_universe with:
  - S&P 100  (filtered from S&P 500 via FMP stable API)
  - Nasdaq 100 (via FMP stable API)
  - DAX 40   (hardcoded — no FMP constituent endpoint)
  - CAC 40   (hardcoded — no FMP constituent endpoint)
  - SMI 20   (hardcoded — no FMP constituent endpoint)
Deduplicates across indices. Enriches all tickers via FMP bulk profile.
Company info: description, employees, website, address, city, zip, state.
"""
import os
import time
import logging
import requests
from collections import Counter
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL    = os.environ["SUPABASE_URL"]
SUPABASE_KEY    = os.environ["SUPABASE_SERVICE_KEY"]
FMP_API_KEY     = os.environ["FMP_API_KEY"]
FMP_BASE_V3     = "https://financialmodelingprep.com/api/v3"
FMP_BASE_STABLE = "https://financialmodelingprep.com/stable"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── S&P 100 ───────────────────────────────────────────────────────────────────
SP100_TICKERS = {
    "AAPL","ABBV","ABT","ACN","ADBE","AIG","AMD","AMGN","AMT","AMZN",
    "AVGO","AXP","BA","BAC","BK","BKNG","BLK","BMY","BRK.B","C",
    "CAT","CHTR","CL","CMCSA","COF","COP","COST","CRM","CSCO","CVS",
    "CVX","DE","DHR","DIS","DUK","EMR","EXC","F","FDX","GD",
    "GE","GILD","GM","GOOGL","GS","HD","HON","IBM","INTC","INTU",
    "JNJ","JPM","KHC","KO","LIN","LLY","LMT","LOW","MA","MCD",
    "MDLZ","MDT","MET","META","MMC","MMM","MO","MRK","MS","MSFT",
    "NEE","NFLX","NOW","NSC","NVDA","ORCL","PEP","PFE","PG","PM",
    "PYPL","QCOM","RTX","SBUX","SCHW","SO","SPG","T","TGT","TMO",
    "TMUS","TSLA","TXN","UNH","UNP","UPS","USB","V","VZ","WFC",
    "WMT","XOM",
}

# ── DAX 40 ────────────────────────────────────────────────────────────────────
DAX_TICKERS = {
    "ADS.DE","AIR.DE","ALV.DE","BAS.DE","BAYN.DE","BEI.DE","BMW.DE",
    "BNR.DE","CON.DE","1COV.DE","DHER.DE","DB1.DE","DBK.DE","DHL.DE",
    "DTE.DE","EOAN.DE","FRE.DE","FME.DE","G1A.DE","HNR1.DE","HEI.DE",
    "HEN3.DE","IFX.DE","MBG.DE","MRK.DE","MTX.DE","MUV2.DE","P911.DE",
    "PAH3.DE","QGEN.DE","RHM.DE","RWE.DE","SAP.DE","SIE.DE","SRT3.DE",
    "SY1.DE","VOW3.DE","VNA.DE","ZAL.DE","ENR.DE",
}

# ── CAC 40 ────────────────────────────────────────────────────────────────────
CAC_TICKERS = {
    "AC.PA","ACA.PA","AI.PA","AIR.PA","ALO.PA","BN.PA","BNP.PA","CA.PA",
    "CAP.PA","CS.PA","DG.PA","DSY.PA","ENGI.PA","EL.PA","ERF.PA","GLE.PA",
    "HO.PA","KER.PA","LR.PA","MC.PA","ML.PA","MT.PA","OR.PA","ORA.PA",
    "PUB.PA","RI.PA","RMS.PA","SAF.PA","SAN.PA","SGO.PA","STLAP.PA",
    "STM.PA","SU.PA","TEP.PA","TTE.PA","URW.PA","VIE.PA","VIV.PA",
    "WLN.PA","FR.PA",
}

# ── SMI 20 ────────────────────────────────────────────────────────────────────
SMI_TICKERS = {
    "ABBN.SW","ADEN.SW","ALC.SW","CSGN.SW","CFR.SW","GEBN.SW","GIVN.SW",
    "HOLN.SW","KNIN.SW","LONN.SW","LOGN.SW","NESN.SW","NOVN.SW","PGHN.SW",
    "ROG.SW","SCMN.SW","SGSN.SW","SREN.SW","UBSG.SW","ZURN.SW",
}

# ── FMP helpers ───────────────────────────────────────────────────────────────
def get_fmp(endpoint: str, params: dict = {}, stable: bool = False) -> list:
    base = FMP_BASE_STABLE if stable else FMP_BASE_V3
    resp = requests.get(
        f"{base}/{endpoint}",
        params={"apikey": FMP_API_KEY, **params},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()

def get_all_profiles_bulk() -> dict[str, dict]:
    """Fetch all profiles in 4 bulk calls."""
    profiles = {}
    for part in range(4):
        log.info(f"Fetching bulk profiles part {part}...")
        try:
            data = get_fmp(f"profile-bulk?part={part}", stable=True)
            for p in data:
                sym = p.get("symbol")
                if sym:
                    profiles[sym] = p
            log.info(f"  Part {part}: {len(data)} profiles")
        except Exception as e:
            log.warning(f"  Bulk profile part {part} failed: {e}")
        time.sleep(1)
    log.info(f"Total profiles loaded: {len(profiles)}")
    return profiles

def get_company_profile(ticker: str) -> dict:
    """Individual profile fallback for tickers not in bulk."""
    try:
        resp = requests.get(
            f"{FMP_BASE_STABLE}/profile",
            params={"symbol": ticker, "apikey": FMP_API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict) and data:
            return data
        # last resort: v3
        data = get_fmp(f"profile/{ticker}", stable=False)
        return data[0] if data else {}
    except Exception:
        return {}

# ── Build master ticker list ──────────────────────────────────────────────────
def build_ticker_list() -> list[dict]:
    log.info("Fetching S&P 500 constituents...")
    sp500         = get_fmp("sp500-constituent", stable=True)
    sp500_symbols = {c["symbol"] for c in sp500}
    sp100_found   = [c for c in sp500 if c["symbol"] in SP100_TICKERS]
    sp100_symbols = {c["symbol"] for c in sp100_found}

    missing_sp100 = SP100_TICKERS - sp500_symbols
    if missing_sp100:
        log.warning(f"S&P 100 tickers not in FMP S&P 500: {sorted(missing_sp100)}")

    log.info("Fetching Nasdaq 100 constituents...")
    ndx100         = get_fmp("nasdaq-constituent", stable=True)
    ndx100_symbols = {c["symbol"] for c in ndx100}
    ndx_only       = ndx100_symbols - sp100_symbols

    entries: dict[str, str] = {}
    for sym in sp100_symbols:  entries[sym] = "SP100"
    for sym in ndx_only:       entries[sym] = "NDX100"
    for sym in DAX_TICKERS:    entries[sym] = "DAX40"
    for sym in CAC_TICKERS:    entries[sym] = "CAC40"
    for sym in SMI_TICKERS:    entries[sym] = "SMI20"

    log.info(
        f"Master universe: {len(entries)} unique tickers "
        f"(SP100={len(sp100_symbols)}, NDX100-only={len(ndx_only)}, "
        f"DAX={len(DAX_TICKERS)}, CAC={len(CAC_TICKERS)}, SMI={len(SMI_TICKERS)})"
    )
    return [{"ticker": t, "source": s} for t, s in entries.items()]

# ── Build row from profile ────────────────────────────────────────────────────
def build_row(ticker: str, profile: dict) -> dict:
    # parse employee count safely
    emp = profile.get("fullTimeEmployees")
    try:
        employees = int(str(emp).replace(",", "")) if emp else None
    except (ValueError, TypeError):
        employees = None

    # build address string
    parts = [
        profile.get("address"),
        profile.get("city"),
        profile.get("state"),
        profile.get("zip"),
    ]
    address = ", ".join(p for p in parts if p) or None

    return {
        "ticker":      ticker,
        "name":        profile.get("companyName"),
        "exchange":    profile.get("exchangeShortName"),
        "sector":      profile.get("sector"),
        "industry":    profile.get("industry"),
        "country":     profile.get("country"),
        "fmp_symbol":  None,
        "active":      True,
        "description": profile.get("description"),
        "employees":   employees,
        "website":     profile.get("website"),
        "address":     address,
        "city":        profile.get("city"),
        "zip":         profile.get("zip"),
        "state":       profile.get("state"),
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    tickers = build_ticker_list()
    total   = len(tickers)

    # fetch all profiles in bulk upfront
    bulk_profiles = get_all_profiles_bulk()
    log.info(f"Bulk profiles cover {len(bulk_profiles)} symbols")

    rows = []
    for i, entry in enumerate(tickers):
        ticker = entry["ticker"]

        profile = bulk_profiles.get(ticker)
        if not profile:
            log.info(f"[{i+1}/{total}] Bulk miss for {ticker}, fetching individually...")
            profile = get_company_profile(ticker)
            time.sleep(0.25)
        else:
            log.info(f"[{i+1}/{total}] {ticker} ({entry['source']}) — from bulk")

        rows.append(build_row(ticker, profile))

    log.info(f"\nUpserting {len(rows)} rows into stock_universe...")
    result = (
        supabase.table("stock_universe")
        .upsert(rows, on_conflict="ticker")
        .execute()
    )
    log.info(f"Done — {len(result.data)} rows upserted")

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("\nCountry breakdown:")
    for country, n in Counter(r["country"] for r in rows if r["country"]).most_common():
        log.info(f"  {country}: {n}")

    log.info("\nSector breakdown:")
    for sector, n in Counter(r["sector"] for r in rows if r["sector"]).most_common():
        log.info(f"  {sector}: {n}")

    # coverage stats
    with_desc = sum(1 for r in rows if r.get("description"))
    with_emp  = sum(1 for r in rows if r.get("employees"))
    with_web  = sum(1 for r in rows if r.get("website"))
    log.info(f"\nCompany info coverage:")
    log.info(f"  Description: {with_desc}/{total}")
    log.info(f"  Employees:   {with_emp}/{total}")
    log.info(f"  Website:     {with_web}/{total}")


if __name__ == "__main__":
    main()
