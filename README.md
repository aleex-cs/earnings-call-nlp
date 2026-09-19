# Earnings Call NLP Pipeline

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)
![FinBERT](https://img.shields.io/badge/Model-ProsusAI%2Ffinbert-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Dashboard that scores **SEC 8-K Exhibit 99.1** earnings releases with FinBERT, tracks uncertainty language over time, compares issuers, and overlays **next-session stock returns**.

Not investment advice. NLP tone is not a trading system.

## What it does

- Pulls earnings press releases from **SEC EDGAR** (HTML Exhibit 99.1; PDFs are skipped).
- Cleans EDGAR boilerplate, chunks narrative, scores **sentiment** with [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert) (`positive / negative / neutral` in the model’s own label order).
- Measures **uncertainty / evasive phrasing** with lexicons (independent of FinBERT).
- Builds a per-issuer timeline, alerts vs that company’s own history, and a **compare** view with a shared time window.
- Joins each filing date to Yahoo Finance prices: close after the 8-K vs last close on/before it (typical after-hours reaction), plus excess vs SPY.

Precomputed analyses for AAPL, GOOGL, MSFT, NVDA, and TSLA ship in `data/analyzed/` so the UI works immediately. Force-fresh re-runs EDGAR + FinBERT.

## Quick start (local)

Python 3.10+ (3.11 recommended). GPU optional.

```bash
git clone https://github.com/aleex-cs/earnings-call-nlp.git
cd earnings-call-nlp
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open [http://localhost:8085](http://localhost:8085). Search a company by name, or click a cached ticker.

### NVIDIA GPU (optional)

The PyPI `torch` wheel is CPU. To use CUDA locally:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

Pick **CUDA** in the sidebar and check **Force Fresh Download** only when you want to recompute (cached JSON does not use the GPU).

## Deploy on Render

The repo includes `render.yaml`. FinBERT + PyTorch need **more RAM than the free instance** — use at least **Starter (2 GB)**; 4 GB is safer the first time the model downloads.

1. Push this repo to GitHub (already the intended source).
2. In [Render](https://render.com): **New → Blueprint** and select the repo, **or** **New Web Service** → this repo.
3. If you create the service manually:
   - **Runtime:** Python 3.11
   - **Build:** `pip install -r requirements.txt && python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"`
   - **Start:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Health check:** `/health`
4. First boot may take several minutes while Hugging Face downloads FinBERT. Cached tickers load without that download until someone runs a fresh analysis.
5. Optional persistent disk on `/opt/render/project/src/.hf_cache` so the model is not re-fetched on every deploy.

Railway / Fly.io work the same way: bind `0.0.0.0` and `$PORT`.

## Dashboard

| Tab | Contents |
| --- | --- |
| Executive Summary | NLP signal, sentiment, uncertainty, confidence, quarter profile |
| Temporal | Sentiment / uncertainty / QoQ delta; click a point to open the filing; price reaction |
| Risk Factors | Sentences with evasive language |
| Topics | Keyword counts vs that issuer’s own history |
| Alerts | Anomalies vs own history |
| Compare | Overlay issuers; common window; tone vs next-session return |

## API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/api/companies?q=` | Name / ticker search |
| GET | `/api/cached` | Tickers with local analyses |
| GET | `/api/analyze?ticker=&device=&limit=&force_refresh=` | EDGAR + NLP (slow if not cached) |
| GET | `/api/load?ticker=` | Disk cache only |
| GET | `/api/compare?tickers=AAPL,MSFT&align=true` | Overlay + market join |
| GET | `/api/market?ticker=` | Event returns for one issuer |
| GET | `/api/report?ticker=&year=&quarter=` | Full filing + chunk scores |
| GET | `/api/gpu` | CUDA / nvidia-smi snapshot |

## Metrics

**Sentiment** (−1 … +1): FinBERT `P(positive) − P(negative)`, averaged over narrative chunks.

**Uncertainty** (0 … 1): share of hedge / evasion cues in the cleaned release.

**Executive confidence** (0 … 1): mostly *lack of uncertainty*, with a small weight on tone (not a clone of sentiment).

**Next-session return**: first close *after* the filing date ÷ last close *on or before* it − 1.

## Layout

```
server.py                 FastAPI + static UI
public/                   Vanilla JS + Plotly
src/
  fmp_fetcher.py          SEC EDGAR (class name is historical)
  exhibit_cleaner.py      Strip TOC / tables / exhibit headers
  chunker.py
  sentiment_analyzer.py   FinBERT (labels from model.config.id2label)
  uncertainty_analyzer.py
  temporal_analyzer.py
  market_reaction.py      yfinance event windows
  pipeline.py
  rescore.py              Re-score data/analyzed after model/cleaner changes
data/analyzed/            Cached JSON (committed for the demo)
render.yaml               Render Blueprint
```

## License

MIT — see [LICENSE](LICENSE).
