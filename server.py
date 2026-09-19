"""
Servidor FastAPI para el Pipeline NLP de Earnings Calls.
Sirve la API REST y los archivos estáticos del frontend.
"""
import glob
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))

app = FastAPI(title="Earnings Call NLP Pipeline API")

os.makedirs("data/transcripts_cache", exist_ok=True)
os.makedirs("data/analyzed", exist_ok=True)
os.makedirs("public", exist_ok=True)


class AnalyzeResponse(BaseModel):
    transcripts: List[Dict[Any, Any]]
    temporal: Optional[Dict[Any, Any]]
    ticker: str
    company: Optional[str] = None
    device_used: Optional[str] = None
    gpu_name: Optional[str] = None
    from_cache: bool = False


def _cache_only() -> bool:
    return os.environ.get("RENDER") == "true" or os.environ.get("CACHE_ONLY") == "1"


def _gpu_snapshot() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "cuda_built": False,
        "torch_cuda_version": None,
        "cuda_available": False,
        "torch_version": None,
        "device_name": None,
        "utilization": None,
        "memory_used_mb": None,
        "memory_total_mb": None,
        "note": None,
    }
    if _cache_only():
        info["note"] = "Hosted demo serves cached analyses only; FinBERT is not loaded."
        return info
    try:
        import torch
    except Exception:
        info["note"] = "PyTorch is not installed."
        return info
    info["cuda_built"] = bool(torch.version.cuda)
    info["torch_cuda_version"] = torch.version.cuda
    info["cuda_available"] = torch.cuda.is_available()
    info["torch_version"] = torch.__version__
    if torch.cuda.is_available():
        info["device_name"] = torch.cuda.get_device_name(0)
    else:
        if "+cpu" in torch.__version__ or not torch.version.cuda:
            info["note"] = (
                "PyTorch is a CPU-only build, so CUDA in the UI cannot use the GPU. "
                "Install a CUDA wheel (e.g. cu126) in this venv."
            )
        else:
            info["note"] = "CUDA PyTorch is installed but no GPU was detected."

    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip().splitlines()[0]
        name, util, mem_used, mem_total = [p.strip() for p in out.split(",")]
        info["device_name"] = info["device_name"] or name
        info["utilization"] = int(float(util))
        info["memory_used_mb"] = int(float(mem_used))
        info["memory_total_mb"] = int(float(mem_total))
    except Exception:
        pass
    return info


def _load_analyzed_for_ticker(ticker: str, limit: Optional[int] = None):
    ticker = ticker.upper()
    files = sorted(glob.glob(os.path.join("data", "analyzed", f"{ticker}_*_analyzed.json")))
    transcripts = []
    for path in files:
        if path.endswith("_temporal_analysis.json"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                transcripts.append(json.load(f))
        except Exception:
            continue
    transcripts.sort(key=lambda t: (t.get("metadata") or {}).get("date", ""))
    from src.pipeline import EarningsCallPipeline
    transcripts = EarningsCallPipeline._unique_by_quarter(transcripts)
    if limit:
        transcripts = transcripts[-limit:]
    temporal_path = os.path.join("data", "analyzed", f"{ticker}_temporal_analysis.json")
    temporal = None
    if os.path.exists(temporal_path):
        try:
            with open(temporal_path, "r", encoding="utf-8") as f:
                temporal = json.load(f)
        except Exception:
            temporal = None
    if transcripts:
        from src.temporal_analyzer import TemporalAnalyzer
        ta = TemporalAnalyzer()
        if not temporal:
            if len(transcripts) > 1:
                df = ta.create_temporal_dataframe(transcripts)
                temporal = ta.analyze_temporal_trends(df)
            else:
                temporal = {}
            temporal["trading_signal"] = ta.generate_trading_signal(transcripts)
        topics = EarningsCallPipeline._extract_trending_topics(transcripts)
        if not temporal.get("trending_topics") or not (temporal["trending_topics"][0] or {}).get("series"):
            temporal["trending_topics"] = topics
        if not temporal.get("alerts"):
            temporal["alerts"] = ta.generate_alerts(transcripts, temporal)
        EarningsCallPipeline._refresh_cautions(transcripts)
    return transcripts, temporal


@app.get("/api/gpu")
def gpu_status():
    return _gpu_snapshot()


@app.get("/api/companies")
def companies(q: str = Query("", description="Nombre o ticker")):
    from src.company_index import search_companies
    return {"companies": search_companies(q, limit=12)}


@app.get("/api/analyze", response_model=AnalyzeResponse)
def analyze(
    ticker: str = Query(..., description="Símbolo de la empresa (ej: AAPL)"),
    device: str = Query("cpu", description="Dispositivo (cpu o cuda)"),
    force_refresh: bool = Query(False, description="Si True, ignora caché y descarga de nuevo"),
    limit: int = Query(8, ge=1, le=40, description="Número de trimestres a analizar"),
):
    """
    Descarga automáticamente las transcripciones reales de Earnings Calls
    de Financial Modeling Prep / SEC EDGAR y las analiza con el pipeline NLP.
    """
    try:
        from src.company_index import company_name

        requested = device.lower()

        if not force_refresh or _cache_only():
            transcripts, temporal = _load_analyzed_for_ticker(ticker.upper(), limit=limit)
            if transcripts:
                name = company_name(ticker) or ticker.upper()
                return AnalyzeResponse(
                    transcripts=transcripts,
                    temporal=temporal,
                    ticker=ticker.upper(),
                    company=name,
                    device_used="cache",
                    gpu_name=None,
                    from_cache=True,
                )

        if _cache_only():
            raise HTTPException(
                status_code=404,
                detail=f"No cached analysis for '{ticker.upper()}' on this demo host. "
                       "Cached tickers: AAPL, GOOGL, MSFT, NVDA, TSLA.",
            )

        from src.pipeline import EarningsCallPipeline
        gpu = _gpu_snapshot()
        if requested == "cuda" and not gpu["cuda_available"]:
            raise HTTPException(
                status_code=400,
                detail=gpu.get("note") or "CUDA was requested but is not available in this PyTorch install.",
            )

        pipeline = EarningsCallPipeline(source_type="real_financial", device=requested)
        pipeline.fetcher.force_refresh = force_refresh
        actual_device = pipeline.sentiment_analyzer.device

        transcripts, temporal = pipeline.analyze_company(ticker, limit=limit)

        if not transcripts:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontraron transcripciones para '{ticker.upper()}'. "
                       "Comprueba que el ticker es correcto y que tu plan de FMP incluye transcripciones.",
            )

        name = company_name(ticker) or ticker.upper()
        return AnalyzeResponse(
            transcripts=transcripts,
            temporal=temporal,
            ticker=ticker.upper(),
            company=name,
            device_used=actual_device,
            gpu_name=gpu.get("device_name") if actual_device == "cuda" else None,
            from_cache=not force_refresh,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/api/load")
def load_ticker(ticker: str = Query(...), limit: int = Query(40, ge=1, le=40)):
    ticker = ticker.upper()
    transcripts, temporal = _load_analyzed_for_ticker(ticker, limit=limit)
    if not transcripts:
        raise HTTPException(
            status_code=404,
            detail=f"No hay análisis guardado para {ticker}. Analízala primero.",
        )
    from src.company_index import company_name
    return {
        "transcripts": transcripts,
        "temporal": temporal,
        "ticker": ticker,
        "company": company_name(ticker) or ticker,
        "device_used": "cache",
        "from_cache": True,
    }


@app.get("/api/compare")
def compare(
    tickers: str = Query(..., description="Tickers separados por coma"),
    align: bool = Query(True, description="Recortar al periodo común"),
):
    from src.company_index import company_name
    from src.market_reaction import attach_events, _pearson

    result = []
    for raw in tickers.split(","):
        ticker = raw.strip().upper()
        if not ticker:
            continue
        transcripts, temporal = _load_analyzed_for_ticker(ticker)
        if not transcripts:
            continue
        series = []
        for t in transcripts:
            meta = t.get("metadata") or {}
            pr = t.get("prepared_remarks") or {}
            series.append({
                "date": meta.get("date"),
                "quarter": meta.get("quarter"),
                "year": meta.get("year"),
                "sentiment": pr.get("sentiment_score", 0),
                "uncertainty": (pr.get("uncertainty") or {}).get("uncertainty_score", 0),
                "confidence": (t.get("executive_confidence") or {})
                    .get("executive_confidence_indicator", {})
                    .get("confidence_score", 0.5),
            })
        latest = series[-1] if series else {}
        result.append({
            "ticker": ticker,
            "company": company_name(ticker) or ticker,
            "series": series,
            "latest": latest,
            "signal": (temporal or {}).get("trading_signal"),
            "coverage": {
                "start": series[0]["date"] if series else None,
                "end": series[-1]["date"] if series else None,
                "n": len(series),
            },
        })
    if not result:
        raise HTTPException(status_code=404, detail="Ninguna de las empresas tiene análisis en caché.")

    aligned_from = aligned_to = None
    if align and len(result) >= 2:
        starts = [c["coverage"]["start"] for c in result if c["coverage"]["start"]]
        ends = [c["coverage"]["end"] for c in result if c["coverage"]["end"]]
        if starts and ends:
            aligned_from, aligned_to = max(starts), min(ends)
            for c in result:
                c["series"] = [
                    s for s in c["series"]
                    if s.get("date") and aligned_from <= s["date"] <= aligned_to
                ]
                if c["series"]:
                    c["latest"] = c["series"][-1]

    for c in result:
        events = [
            {"date": s["date"], "sentiment": s["sentiment"], "quarter": s["quarter"], "year": s["year"]}
            for s in c["series"] if s.get("date")
        ]
        market = attach_events(c["ticker"], events)
        by_date = {e["date"]: e for e in market["events"] if e.get("date")}
        for s in c["series"]:
            hit = by_date.get(s.get("date")) or {}
            s["ret_1d"] = hit.get("ret_1d")
            s["excess_1d"] = hit.get("excess_1d")
            s["alignment"] = hit.get("alignment")
        c["market"] = market["summary"]
    points = []
    for c in result:
        for s in c["series"]:
            if s.get("ret_1d") is None:
                continue
            points.append({
                "ticker": c["ticker"],
                "date": s.get("date"),
                "quarter": s.get("quarter"),
                "year": s.get("year"),
                "sentiment": s.get("sentiment"),
                "ret_1d": s.get("ret_1d"),
                "excess_1d": s.get("excess_1d"),
                "alignment": s.get("alignment"),
            })
    scatter = {
        "points": points,
        "corr": _pearson([p["sentiment"] for p in points], [p["ret_1d"] for p in points]),
        "n": len(points),
    }
    return {
        "companies": result,
        "align": align,
        "aligned_from": aligned_from,
        "aligned_to": aligned_to,
        "market": scatter,
    }


@app.get("/api/market")
def market(ticker: str = Query(...)):
    from src.market_reaction import attach_events
    ticker = ticker.upper()
    transcripts, _ = _load_analyzed_for_ticker(ticker)
    if not transcripts:
        raise HTTPException(status_code=404, detail=f"No hay análisis guardado para {ticker}.")
    events = []
    for t in transcripts:
        meta = t.get("metadata") or {}
        pr = t.get("prepared_remarks") or {}
        events.append({
            "date": meta.get("date"),
            "quarter": meta.get("quarter"),
            "year": meta.get("year"),
            "sentiment": pr.get("sentiment_score", 0),
        })
    return attach_events(ticker, events)


@app.get("/api/report")
def report(ticker: str = Query(...), year: int = Query(...), quarter: str = Query(...)):
    ticker = ticker.upper()
    q = str(quarter).replace("Q", "")
    path = os.path.join("data", "analyzed", f"{ticker}_{year}_Q{q}_analyzed.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No se encontró ese reporting analizado.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    from src.company_index import company_name
    data["company_name"] = company_name(ticker) or ticker
    return data


@app.get("/api/cached")
def list_cached():
    """Lista los tickers que ya tienen datos en caché local."""
    from src.company_index import company_name
    cache_dir = "data/transcripts_cache"
    analyzed_dir = "data/analyzed"
    tickers = set()
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.endswith("_transcripts.json"):
                tickers.add(f.replace("_transcripts.json", ""))
    if os.path.exists(analyzed_dir):
        for f in os.listdir(analyzed_dir):
            if f.endswith("_analyzed.json"):
                tickers.add(f.split("_")[0])
    items = [
        {"ticker": t, "company": company_name(t) or t}
        for t in sorted(tickers)
    ]
    return {"cached_tickers": sorted(tickers), "cached": items}


@app.get("/health")
def health():
    return {"ok": True}


app.mount("/static", StaticFiles(directory="public"), name="static")


@app.get("/")
def read_root():
    return FileResponse("public/index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8085"))
    reload = not os.environ.get("RENDER") and os.environ.get("ENV") != "production"
    print("=" * 50)
    print("  Earnings Call NLP Pipeline")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=reload)
