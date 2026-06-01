# debug_financials.py
import os, requests
from dotenv import load_dotenv
load_dotenv()

FMP_API_KEY = os.environ["FMP_API_KEY"]
FMP_BASE    = "https://financialmodelingprep.com/stable"

print("=== RATIOS ===")
resp = requests.get(f"{FMP_BASE}/ratios",
    params={"symbol": "AAPL", "period": "quarter", "apikey": FMP_API_KEY}, timeout=20)
print(f"Status: {resp.status_code}")
data = resp.json()
if data:
    print("First row:", {k: v for k, v in data[0].items() if v is not None})