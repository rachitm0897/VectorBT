import re


NAME_TO_TICKER = {
    "apple": "AAPL",
    "apple inc": "AAPL",
    "tesla": "TSLA",
    "tesla inc": "TSLA",
    "nvidia": "NVDA",
    "nvidia corporation": "NVDA",
    "microsoft": "MSFT",
    "microsoft corporation": "MSFT",
    "amazon": "AMZN",
    "amazon com": "AMZN",
    "meta": "META",
    "facebook": "META",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "netflix": "NFLX",
}


def normalize_symbol(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s.]", " ", value or "").strip()
    compact_name = re.sub(r"\s+", " ", cleaned.lower()).replace(".", "")
    if compact_name in NAME_TO_TICKER:
        return NAME_TO_TICKER[compact_name]
    return cleaned.replace(" ", "").upper()
