"""
Limpia exhibits 99.1 de EDGAR: quita TOC, tablas, pies de foto y
encabezados tipo "F I N A N C I A L   S U M M A R Y" para dejar
solo narrativa usable por FinBERT.
"""
import re
from typing import List, Tuple


SPACED_CAPS = re.compile(r"(?:\b[A-Z]\s){2,}[A-Z]\b")
EXHIBIT_HEADER = re.compile(
    r"^EX[- ]?99.*$|Exhibit\s+99\.1.*$|^\d+\s+tsla-ex.*$",
    re.IGNORECASE | re.MULTILINE,
)
STOP_HEADINGS = re.compile(
    r"(?i)("
    r"forward[- ]looking statements|"
    r"non[- ]gaap financial information|"
    r"webcast information|"
    r"photos\s*&\s*charts|"
    r"condensed consolidated statements|"
    r"consolidated statements of operations|"
    r"consolidated balance sheets|"
    r"statement of operations|"
    r"statement of cash flows|"
    r"balance sheet|"
    r"reconciliation of gaap|"
    r"additional information"
    r")"
)
JUNK_LINE = re.compile(
    r"(?i)("
    r"unaudited|"
    r"gigafactory|"
    r"photos?\s*&\s*charts|"
    r"key metrics|"
    r"financial statements|"
    r"highlights\s+\d|"
    r"source:\s|"
    r"ttm\s*=|"
    r"exhibit 99"
    r")"
)
EARNINGS_HINTS = (
    "revenue", "net income", "operating income", "earnings", "gaap",
    "gross margin", "operating margin", "eps", "quarter", "deliveries",
    "free cash flow", "outlook", "guidance",
)


def unsqueeze_spaced_caps(text: str) -> str:
    return SPACED_CAPS.sub(lambda m: m.group().replace(" ", ""), text)


def _is_narrative_line(line: str) -> bool:
    line = line.strip()
    if len(line) < 35:
        return False
    words = line.split()
    if len(words) < 6:
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 25:
        return False
    lower = sum(1 for c in letters if c.islower())
    if lower / len(letters) < 0.42:
        return False
    digits = sum(1 for c in line if c.isdigit())
    if digits / max(len(line), 1) > 0.28:
        return False
    if re.fullmatch(r"[\d\s\$.,%()A-Z/–—-]+", line):
        return False
    caps_words = sum(1 for w in words if w.isupper() and len(w) > 2)
    if caps_words / len(words) > 0.55:
        return False
    return True


def clean_exhibit_text(raw: str) -> str:
    """Devuelve solo oraciones narrativas de un exhibit 99.1."""
    if not raw:
        return ""

    text = raw.replace("\xa0", " ").replace("\r", "\n")
    text = unsqueeze_spaced_caps(text)
    text = re.sub(
        r"(?i)EX[- ]?99\.\d\s+\d+\s+\S+\.(?:htm|html|txt)\s+(?:EX[- ]?99\.\d\s+)?Document\s*",
        " ",
        text,
    )
    text = re.sub(r"(?i)EX-99\.\d\s+\S+\.htm", " ", text)
    text = re.sub(r"(?i)\bEX[- ]?99\.\d\b", " ", text)
    text = re.sub(r"(?i)\b\d+\s+[A-Za-z0-9._-]+\.(?:htm|html)\b", " ", text)
    text = re.sub(r"(?i)Exhibit\s+99\.1", " ", text)
    text = re.sub(r"(?i)^\s*Document\s+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)

    stop = STOP_HEADINGS.search(text)
    if stop and stop.start() > 400:
        text = text[: stop.start()]

    blob = re.sub(r"\s+", " ", text).strip()
    toc_hit = re.search(r"(?i)Highlights\s+\d+|Financial Summary\s+\d+", blob[:1200])
    if toc_hit:
        start = re.search(
            r"(20\d{2} was |Today, |The Company |[A-Z][\w.&']{2,40} (?:today announced|reports?))",
            blob,
        )
        if start:
            blob = blob[start.start():]

    sentences = re.split(r"(?<=[.!?])\s+", blob)
    kept: List[str] = []
    seen = set()
    for sent in sentences:
        sent = unsqueeze_spaced_caps(sent)
        sent = re.sub(r"\s+", " ", sent).strip()
        if not _is_narrative_line(sent):
            continue
        if JUNK_LINE.search(sent) and sum(c.islower() for c in sent) < 40:
            continue
        key = re.sub(r"\W+", "", sent.lower())[:180]
        if key in seen:
            continue
        seen.add(key)
        kept.append(sent)

    return "\n\n".join(kept).strip()


def is_earnings_narrative(text: str) -> bool:
    if not text or len(text.split()) < 80:
        return False
    lower = text.lower()
    strong = ("revenue", "net income", "operating income", "gaap", "gross margin", "operating margin", "eps")
    if sum(1 for k in strong if k in lower) < 2:
        return False
    hits = sum(1 for k in EARNINGS_HINTS if k in lower)
    return hits >= 3


def is_analyzable_chunk(chunk: str) -> bool:
    """False para tablas, pies de foto y TOC que FinBERT no debe puntuar."""
    if not chunk or not chunk.strip():
        return False
    if _is_narrative_line(chunk):
        return True
    words = chunk.split()
    if len(words) < 40:
        return False
    letters = [c for c in chunk if c.isalpha()]
    if not letters:
        return False
    return (sum(1 for c in letters if c.islower()) / len(letters) >= 0.5)


def infer_quarter_from_text(date_str: str, content: str) -> Tuple[str, int]:
    """
    Prioriza el trimestre declarado al inicio del documento.
    Fallback: 8-K de resultados suele publicarse el mes siguiente al cierre.
    Ene-Mar → Q4 año anterior; Abr-Jun → Q1; Jul-Sep → Q2; Oct-Dic → Q3.
    """
    from datetime import datetime

    head = (content or "")[:900]
    mapping = {
        "FIRST": "Q1", "1": "Q1",
        "SECOND": "Q2", "2": "Q2",
        "THIRD": "Q3", "3": "Q3",
        "FOURTH": "Q4", "4": "Q4",
    }

    patterns = [
        r"Q([1-4])\s+and\s+FY\s*(\d{4})",
        r"FY\s*(\d{4})\s+Q([1-4])",
        r"(first|second|third|fourth)\s+quarter(?:\s+of)?\s+(?:fiscal\s+)?(\d{4})",
        r"(?:fiscal\s+)?(\d{4})\s+(first|second|third|fourth)\s+quarter",
        r"reports?\s+(?:fiscal\s+)?(\d{4})\s+(first|second|third|fourth)",
        r"Q([1-4])\s+(?:FY)?\s*(\d{4})\s+Update",
        r"Q([1-4])\s+(?:FY)?\s*(\d{4})\s+(?:results|letter|shareholder)",
    ]
    for pat in patterns:
        m = re.search(pat, head, re.IGNORECASE)
        if not m:
            continue
        g1, g2 = m.group(1), m.group(2)
        if g1.isdigit() and len(g1) == 4:
            year, qkey = int(g1), g2.upper()
        elif g2.isdigit() and len(g2) == 4:
            year, qkey = int(g2), g1.upper()
        else:
            continue
        quarter = mapping.get(qkey, qkey if qkey.startswith("Q") else f"Q{qkey}")
        if quarter in {"Q1", "Q2", "Q3", "Q4"} and 1995 < year < 2100:
            return quarter, year

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return "Q1", datetime.now().year

    if dt.month <= 3:
        return "Q4", dt.year - 1
    if dt.month <= 6:
        return "Q1", dt.year
    if dt.month <= 9:
        return "Q2", dt.year
    return "Q3", dt.year


def narrative_quality(text: str) -> int:
    if not text:
        return 0
    words = len(text.split())
    hints = sum(1 for k in EARNINGS_HINTS if k in text.lower())
    return words + hints * 40
