"""Join earnings NLP scores with next-session stock returns (Yahoo Finance)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

CACHE_DIR = os.path.join("data", "market")


def _naive(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_localize(None)
    return t.normalize()


def _history(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    os.makedirs(CACHE_DIR, exist_ok=True)
    start_s = start.strftime("%Y-%m-%d")
    end_s = (end + timedelta(days=1)).strftime("%Y-%m-%d")
    cache = os.path.join(CACHE_DIR, f"{ticker}_{start_s}_{end_s}.csv")
    if os.path.exists(cache):
        try:
            hist = pd.read_csv(cache, index_col=0, parse_dates=True)
            if not hist.empty:
                hist.index = pd.to_datetime(hist.index).tz_localize(None)
                return hist
        except Exception:
            pass
    hist = yf.Ticker(ticker).history(start=start_s, end=end_s, auto_adjust=True)
    if hist is None or hist.empty:
        return pd.DataFrame()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    try:
        hist.to_csv(cache)
    except Exception:
        pass
    return hist


def _window_return(closes: pd.Series, filing: str) -> Optional[Dict]:
    d = _naive(filing)
    idx = pd.DatetimeIndex([_naive(i) for i in closes.index])
    series = pd.Series(closes.values, index=idx).dropna().sort_index()
    before = series[series.index <= d]
    after = series[series.index > d]
    if before.empty or after.empty:
        return None
    px0 = float(before.iloc[-1])
    px1 = float(after.iloc[0])
    px5 = float(after.iloc[min(4, len(after) - 1)])
    if px0 == 0:
        return None
    return {
        "pre_date": str(before.index[-1].date()),
        "post_date": str(after.index[0].date()),
        "close_pre": round(px0, 4),
        "close_1d": round(px1, 4),
        "ret_1d": px1 / px0 - 1.0,
        "ret_5d": px5 / px0 - 1.0,
    }


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) < 4:
        return None
    r = pd.Series(xs).corr(pd.Series(ys))
    if pd.isna(r):
        return None
    return float(r)


def attach_events(ticker: str, events: List[Dict]) -> Dict:
    """
    events: [{date, sentiment, quarter, year}, ...]
    Next-session return uses close after the 8-K date vs last close on/before it
    (typical for after-hours earnings). Excess vs SPY over the same window.
    """
    dates = [e.get("date") for e in events if e.get("date")]
    if not dates:
        return {"ticker": ticker, "events": [], "summary": {}}

    parsed = [datetime.strptime(str(d)[:10], "%Y-%m-%d") for d in dates]
    start = min(parsed) - timedelta(days=10)
    end = max(parsed) + timedelta(days=20)
    stock = _history(ticker, start, end)
    spy = _history("SPY", start, end)
    if stock.empty or "Close" not in stock.columns:
        return {"ticker": ticker, "events": [], "summary": {"error": "No price history"}}

    enriched = []
    for e in events:
        if not e.get("date"):
            continue
        stock_ret = _window_return(stock["Close"], e["date"])
        spy_ret = _window_return(spy["Close"], e["date"]) if not spy.empty and "Close" in spy.columns else None
        row = {
            **e,
            "ret_1d": None if not stock_ret else stock_ret["ret_1d"],
            "ret_5d": None if not stock_ret else stock_ret["ret_5d"],
            "excess_1d": None,
            "close_pre": None if not stock_ret else stock_ret["close_pre"],
            "alignment": "no_price",
        }
        if stock_ret and spy_ret:
            row["excess_1d"] = stock_ret["ret_1d"] - spy_ret["ret_1d"]
        sent = float(e.get("sentiment") or 0)
        ret = row["ret_1d"]
        if ret is not None:
            if sent >= 0.1 and ret > 0:
                row["alignment"] = "confirmed"
            elif sent <= -0.1 and ret < 0:
                row["alignment"] = "confirmed"
            elif sent >= 0.1 and ret < 0:
                row["alignment"] = "faded"
            elif sent <= -0.1 and ret > 0:
                row["alignment"] = "faded"
            else:
                row["alignment"] = "muted"
        enriched.append(row)

    pairs = [(r["sentiment"], r["ret_1d"]) for r in enriched if r.get("ret_1d") is not None]
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    pos = [r["ret_1d"] for r in enriched if r.get("ret_1d") is not None and (r.get("sentiment") or 0) >= 0.15]
    neg = [r["ret_1d"] for r in enriched if r.get("ret_1d") is not None and (r.get("sentiment") or 0) <= -0.15]
    confirmed = sum(1 for r in enriched if r.get("alignment") == "confirmed")
    faded = sum(1 for r in enriched if r.get("alignment") == "faded")
    n = len(pairs)
    summary = {
        "n_events": n,
        "corr_sentiment_ret1d": _pearson(xs, ys),
        "avg_ret_when_positive_tone": float(pd.Series(pos).mean()) if pos else None,
        "avg_ret_when_negative_tone": float(pd.Series(neg).mean()) if neg else None,
        "confirmed": confirmed,
        "faded": faded,
        "hit_rate": (confirmed / (confirmed + faded)) if (confirmed + faded) else None,
    }
    return {"ticker": ticker, "events": enriched, "summary": summary}


def pooled_scatter(companies: List[Tuple[str, List[Dict]]]) -> Dict:
    points = []
    for ticker, events in companies:
        payload = attach_events(ticker, events)
        for e in payload["events"]:
            if e.get("ret_1d") is None:
                continue
            points.append({
                "ticker": ticker,
                "date": e.get("date"),
                "quarter": e.get("quarter"),
                "year": e.get("year"),
                "sentiment": e.get("sentiment"),
                "ret_1d": e.get("ret_1d"),
                "excess_1d": e.get("excess_1d"),
                "alignment": e.get("alignment"),
            })
    xs = [p["sentiment"] for p in points]
    ys = [p["ret_1d"] for p in points]
    return {
        "points": points,
        "corr": _pearson(xs, ys),
        "n": len(points),
    }
