"""Índice de empresas SEC: buscar por nombre o ticker."""
import json
import os
from typing import Dict, List, Optional

import requests

CACHE_PATH = os.path.join("data", "company_tickers.json")
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
HEADERS = {"User-Agent": "earnings-call-nlp research@example.com"}

POPULAR = [
    ("AAPL", "Apple Inc."),
    ("MSFT", "Microsoft Corporation"),
    ("NVDA", "NVIDIA Corporation"),
    ("GOOGL", "Alphabet Inc."),
    ("AMZN", "Amazon.com, Inc."),
    ("META", "Meta Platforms, Inc."),
    ("TSLA", "Tesla, Inc."),
    ("JPM", "JPMorgan Chase & Co."),
    ("NFLX", "Netflix, Inc."),
    ("AMD", "Advanced Micro Devices, Inc."),
]


def _normalize(entry: Dict) -> Dict:
    return {
        "ticker": str(entry.get("ticker", "")).upper(),
        "title": str(entry.get("title", "")).strip(),
        "cik": str(entry.get("cik_str", "")).zfill(10) if entry.get("cik_str") is not None else "",
    }


def load_companies(force_refresh: bool = False) -> List[Dict]:
    os.makedirs("data", exist_ok=True)
    if not force_refresh and os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass

    try:
        r = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=8)
        r.raise_for_status()
        raw = r.json()
        companies = [_normalize(v) for v in raw.values()]
        companies = [c for c in companies if c["ticker"]]
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(companies, f)
        return companies
    except Exception as e:
        print(f"[companies] No se pudo descargar el índice SEC: {e}")
        return [{"ticker": t, "title": n, "cik": ""} for t, n in POPULAR]


def search_companies(query: str, limit: int = 12) -> List[Dict]:
    companies = load_companies()
    q = (query or "").strip().lower()
    if not q:
        popular_map = {t: n for t, n in POPULAR}
        found = [c for c in companies if c["ticker"] in popular_map]
        if len(found) < len(POPULAR):
            found = [{"ticker": t, "title": n, "cik": ""} for t, n in POPULAR]
        return found[:limit]

    scored = []
    for c in companies:
        ticker = c["ticker"].lower()
        title = c["title"].lower()
        if q == ticker:
            score = 0
        elif ticker.startswith(q):
            score = 1
        elif q in ticker:
            score = 2
        elif title.startswith(q):
            score = 3
        elif q in title:
            score = 4
        else:
            continue
        scored.append((score, c["title"], c))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [c for _, _, c in scored[:limit]]


def company_name(ticker: str) -> Optional[str]:
    t = (ticker or "").upper()
    for c in load_companies():
        if c["ticker"] == t:
            return c["title"]
    for pt, pn in POPULAR:
        if pt == t:
            return pn
    return None
