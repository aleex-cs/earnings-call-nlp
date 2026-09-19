# Contributing to Earnings Call NLP Pipeline

Thanks for wanting to contribute. This is how to do it without fighting the existing stack.

## Reporting bugs

1. Search [existing issues](https://github.com/aleex-cs/earnings-call-nlp/issues) first.
2. Open a new issue with:
   - A short, specific title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment (Python version, OS, CPU vs CUDA)

## Feature ideas

1. Check issues so we do not duplicate threads.
2. Describe the feature and a concrete use case.
3. Say why it belongs in this pipeline (EDGAR 8-Ks, FinBERT, compare, prices).

## Pull requests

1. Fork the repository.
2. Create a branch (`git checkout -b feature/short-name`).
3. Commit with a message that explains *why*.
4. Push and open a pull request against `main`.

## Code style

Format Python with **Black**:

```bash
black src/ tests/ server.py
```

Add type hints on new functions:

```python
def analyze_sentiment(text: str) -> dict[str, float]:
    """Return FinBERT-style probabilities."""
    return {"score": 0.5}
```

Document public functions with a short docstring (`Args` / `Returns` when it is not obvious).

## Tests

```bash
pytest
pytest --cov=src --cov-report=html
pytest tests/test_segmenter.py
```

Add tests next to the behavior you change. Do not require a GPU for unit tests.

## Project layout

```
earnings-call-nlp/
├── server.py             # FastAPI app
├── public/               # Vanilla JS dashboard
├── src/                  # Pipeline (EDGAR, FinBERT, market join)
├── tests/
├── data/analyzed/        # Cached scored filings (demo)
├── render.yaml           # Render Blueprint
└── requirements.txt
```

The UI is **FastAPI + `public/`**, not Streamlit.

## PR checklist

- [ ] `pytest` passes
- [ ] `black` / formatting is reasonable
- [ ] New code has type hints and docstrings where useful
- [ ] No extra heavy dependencies
- [ ] README updated if behavior or deploy steps changed

## Local setup

```bash
git clone https://github.com/aleex-cs/earnings-call-nlp.git
cd earnings-call-nlp
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python server.py
```

Open http://localhost:8085. Optional CUDA: install a CUDA PyTorch wheel, then use **Force Fresh Download** when you want to recompute.

## Communication

- **GitHub Issues** — bugs and features
- **GitHub Discussions** — questions

## Useful areas

1. Better Exhibit 99.1 extraction (PDFs, messy HTML)
2. Tests around FinBERT label mapping and cleaners
3. Dashboard / compare UX
4. Docs and Render deploy notes
