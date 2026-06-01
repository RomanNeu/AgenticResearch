# debug_shares.py
import os, requests
from dotenv import load_dotenv
load_dotenv()

FMP_API_KEY = os.environ["FMP_API_KEY"]
FMP_BASE    = "https://financialmodelingprep.com/stable"

# fetch all shares
resp = requests.get(f"{FMP_BASE}/shares-float-all",
    params={"apikey": FMP_API_KEY}, timeout=60)
data = resp.json()
all_shares = {item["symbol"]: item.get("outstandingShares") for item in data}

print(f"Total symbols in response: {len(all_shares)}")

# check our missing tickers
missing = ["HON", "VZ", "ORCL", "AAPL", "MSFT"]
for ticker in missing:
    found = all_shares.get(ticker)
    print(f"  {ticker}: {found}")

# print a few sample keys to see the format
sample = list(all_shares.keys())[:20]
print(f"\nSample keys: {sample}")