"""
Descarga automática de datos reales de Earnings Calls desde SEC EDGAR.
Completamente gratuito y legal. Descarga las press releases de resultados
(8-K Exhibit 99.1) de cada empresa y las usa como base de análisis NLP.
Incluye caché local para evitar descargas repetidas.
"""

import requests
import json
import os
import re
import time
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

CACHE_DIR = "data/transcripts_cache"
EDGAR_DATA_URL = "https://data.sec.gov"
EDGAR_WWW_URL = "https://www.sec.gov"

HEADERS = {
    "User-Agent": "earnings-call-nlp research@example.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}
WWW_HEADERS = {
    "User-Agent": "earnings-call-nlp research@example.com",
}


class FMPAutoFetcher:
    """
    Descarga automáticamente press releases y datos reales de Earnings Calls
    desde SEC EDGAR (completamente gratuito y legal).
    Incluye caché local para no repetir descargas.

    Nota: el nombre de clase se mantiene como FMPAutoFetcher para compatibilidad
    con el pipeline existente, aunque la fuente real es SEC EDGAR.
    """

    def __init__(self, api_key: Optional[str] = None):
        # api_key ignorada — usamos EDGAR que es gratuito
        self.force_refresh = False
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _cache_path(self, ticker: str) -> str:
        return os.path.join(CACHE_DIR, f"{ticker.upper()}_transcripts.json")

    def _load_cache(self, ticker: str) -> Optional[List[Dict]]:
        path = self._cache_path(ticker)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def _save_cache(self, ticker: str, data: List[Dict]) -> None:
        path = self._cache_path(ticker)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_cik(self, ticker: str) -> Optional[str]:
        """Obtiene el CIK de la empresa desde el buscador de EDGAR."""
        url = f"{EDGAR_DATA_URL}/submissions/CIK"
        # Buscar en el índice de tickers
        try:
            r = requests.get(
                "https://efts.sec.gov/LATEST/search-index?q=%22" + ticker + "%22&dateRange=custom&startdt=2020-01-01&forms=8-K",
                headers={"User-Agent": "earnings-call-nlp research@example.com"},
                timeout=10,
            )
        except Exception:
            pass

        # Usar el endpoint de company_tickers.json de EDGAR
        try:
            r = requests.get(
                f"{EDGAR_DATA_URL}/submissions/",
                headers={"User-Agent": "earnings-call-nlp research@example.com"},
                timeout=10,
            )
        except Exception:
            pass

        try:
            r = requests.get(
                "https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=" + ticker +
                "&type=8-K&dateb=&owner=include&count=10&search_text=&action=getcompany",
                headers=WWW_HEADERS,
                timeout=10,
            )
            # Extraer CIK de la URL de redirección o del HTML
            cik_match = re.search(r"CIK=(\d{10})", r.url)
            if cik_match:
                return cik_match.group(1)
            cik_match = re.search(r"CIK=(\d+)", r.text)
            if cik_match:
                return cik_match.group(1).zfill(10)
        except Exception:
            pass

        # Último recurso: company_tickers.json
        try:
            r = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=WWW_HEADERS,
                timeout=15,
            )
            data = r.json()
            for entry in data.values():
                if entry["ticker"].upper() == ticker.upper():
                    return str(entry["cik_str"]).zfill(10)
        except Exception as e:
            print(f"  [EDGAR] Error buscando CIK: {e}")

        return None

    def _get_8k_filings(self, cik: str, limit: int = 8) -> List[Dict]:
        """Obtiene los 8-K filings más recientes de la empresa."""
        url = f"{EDGAR_DATA_URL}/submissions/CIK{cik}.json"
        try:
            r = requests.get(url, headers={"User-Agent": "earnings-call-nlp research@example.com"}, timeout=15)
            r.raise_for_status()
            data = r.json()

            filings = data["filings"]["recent"]
            forms = filings["form"]
            dates = filings["filingDate"]
            acc_nums = filings["accessionNumber"]
            items = filings.get("items") or [""] * len(forms)

            results = []
            for i in range(len(forms)):
                if forms[i] != "8-K":
                    continue
                results.append({
                    "date": dates[i],
                    "accessionNumber": acc_nums[i],
                    "cik": cik,
                    "items": items[i] if i < len(items) else "",
                })
                if len(results) >= limit:
                    break

            earnings = [f for f in results if "2.02" in str(f.get("items") or "")]
            other = [f for f in results if f not in earnings]
            return earnings + other
        except Exception as e:
            print(f"  [EDGAR] Error obteniendo filings: {e}")
            return []

    def _absolute_sec_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return "https://www.sec.gov" + href
        return "https://www.sec.gov/" + href.lstrip("/")

    def _pdf_to_text(self, content: bytes) -> str:
        from io import BytesIO
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages[:30]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)

    def _get_exhibit_99_1(self, cik: str, acc_num: str) -> Optional[str]:
        """Obtiene el contenido del Exhibit 99.1 (HTML o PDF)."""
        acc_path = acc_num.replace("-", "")
        index_url = f"{EDGAR_WWW_URL}/Archives/edgar/data/{int(cik)}/{acc_path}/{acc_num}-index.htm"

        try:
            r = requests.get(index_url, headers=WWW_HEADERS, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, "html.parser")

            candidates = []
            secondary = []
            for tr in soup.find_all("tr"):
                cells = [c.get_text(" ", strip=True).lower() for c in tr.find_all(["td", "th"])]
                row = " ".join(cells)
                link = tr.find("a", href=True)
                if not link:
                    continue
                href = link["href"]
                if href.startswith("/ix?"):
                    continue
                low = href.lower()
                if any(low.endswith(ext) for ext in (".xsd", ".xml", ".jpg", ".png", ".gif")):
                    continue
                url = self._absolute_sec_url(href)
                if "ex-99.1" in row or "ex99.1" in row or "exhibit 99.1" in row:
                    if url not in candidates:
                        candidates.append(url)
                elif "ex-99" in row or "exhibit 99" in row or re.search(r"ex-99|ex99|press.?release|_pr\.htm|fy\d+pr", low):
                    if url not in secondary:
                        secondary.append(url)
            for url in secondary:
                if url not in candidates:
                    candidates.append(url)

            from src.exhibit_cleaner import clean_exhibit_text

            for exhibit_url in candidates:
                try:
                    r2 = requests.get(exhibit_url, headers=WWW_HEADERS, timeout=20)
                    r2.raise_for_status()
                except Exception:
                    continue
                ctype = (r2.headers.get("Content-Type") or "").lower()
                raw = ""
                if "pdf" in ctype or exhibit_url.lower().endswith(".pdf"):
                    try:
                        raw = self._pdf_to_text(r2.content)
                    except Exception as e:
                        print(f"    PDF no legible ({e})")
                        continue
                else:
                    soup2 = BeautifulSoup(r2.content, "html.parser")
                    raw = soup2.get_text(separator="\n", strip=True)
                text = clean_exhibit_text(raw)
                if len(text) >= 400:
                    return text
            return None

        except Exception as e:
            print(f"  [EDGAR] Error obteniendo Exhibit 99.1: {e}")
            return None

    @staticmethod
    def _infer_quarter(date_str: str, content: str) -> tuple:
        from src.exhibit_cleaner import infer_quarter_from_text
        return infer_quarter_from_text(date_str, content)

    @staticmethod
    def _normalize_transcripts(transcripts: List[Dict], limit: int) -> List[Dict]:
        from src.exhibit_cleaner import (
            clean_exhibit_text,
            infer_quarter_from_text,
            is_earnings_narrative,
            narrative_quality,
        )

        cleaned = []
        for t in transcripts:
            raw = t.get("full_transcript") or ""
            text = clean_exhibit_text(raw)
            if not is_earnings_narrative(text):
                continue
            quarter, year = infer_quarter_from_text(t.get("date", ""), raw or text)
            rec = dict(t)
            rec["full_transcript"] = text
            rec["quarter"] = quarter
            rec["year"] = year
            rec["quality"] = narrative_quality(text)
            cleaned.append(rec)

        best = {}
        for rec in cleaned:
            key = (rec["year"], rec["quarter"])
            prev = best.get(key)
            if prev is None or rec["quality"] > prev.get("quality", 0):
                best[key] = rec

        unique = sorted(best.values(), key=lambda x: x.get("date") or "")
        if limit and limit > 0:
            unique = unique[-limit:]
        for rec in unique:
            rec.pop("quality", None)
        return unique

    def fetch_transcripts(self, ticker: str, limit: int = 4, force_refresh: bool = False) -> List[Dict]:
        """
        Descarga automáticamente los datos reales de Earnings Calls de SEC EDGAR.
        Usa caché local si ya se descargaron previamente.

        Args:
            ticker: Símbolo bursátil (ej: AAPL)
            limit: Número máximo de trimestres a descargar
            force_refresh: Si True, ignora caché y descarga de nuevo

        Returns:
            Lista de transcripciones/press releases con datos reales
        """
        ticker = ticker.upper()

        if not force_refresh:
            cached = self._load_cache(ticker)
            if cached:
                normalized = self._normalize_transcripts(cached, limit=0)
                if len(normalized) >= limit:
                    print(f"[EDGAR] Cargando {limit} trimestres únicos de caché para {ticker}")
                    return normalized[-limit:]
                print(f"[EDGAR] Caché de {ticker} tiene {len(normalized)} trimestres de resultados, se piden {limit}.")

        print(f"[EDGAR] Descargando datos reales de {ticker} desde SEC EDGAR...")

        # 1. Obtener CIK
        cik = self._get_cik(ticker)
        if not cik:
            raise RuntimeError(
                f"No se encontró el CIK de '{ticker}' en SEC EDGAR. "
                "Verifica que el ticker es correcto (ej: AAPL, MSFT, GOOGL)."
            )
        print(f"  CIK encontrado: {cik}")

        # 2. Obtener 8-K filings
        filings = self._get_8k_filings(cik, limit=500)  # pedir bastantes por si algunos no tienen Exhibit 99.1
        if not filings:
            raise RuntimeError(f"No se encontraron 8-K filings para {ticker} en SEC EDGAR.")

        # 3. Descargar Exhibit 99.1 de cada filing de resultados
        transcripts = []
        seen_quarters = set()
        for filing in filings:
            if len(seen_quarters) >= limit:
                break
            acc = filing["accessionNumber"]
            date = filing["date"]

            print(f"  Procesando 8-K del {date} (items={filing.get('items') or 'n/a'})...")
            content = self._get_exhibit_99_1(cik, acc)

            if content:
                from src.exhibit_cleaner import is_earnings_narrative
                if not is_earnings_narrative(content):
                    print("    Omitido: no parece un release de resultados.")
                    time.sleep(0.35)
                    continue
                quarter, year = self._infer_quarter(date, content)
                key = (year, quarter)
                try:
                    from src.company_index import company_name
                    company = company_name(ticker) or ticker
                except Exception:
                    company = ticker
                transcripts.append({
                    "company": company,
                    "ticker": ticker,
                    "quarter": quarter,
                    "year": year,
                    "date": date,
                    "full_transcript": content,
                    "source": "sec_edgar_8k",
                    "accessionNumber": acc,
                })
                seen_quarters.add(key)
                print(f"    OK: {quarter} {year} — {len(content):,} caracteres")
            else:
                print("    Sin Exhibit 99.1 narrativo, saltando...")

            time.sleep(0.35)

        transcripts = self._normalize_transcripts(transcripts, limit)
        if not transcripts:
            raise RuntimeError(
                f"Se encontraron 8-K filings para {ticker} pero ninguno contenía "
                "una press release de resultados (Exhibit 99.1). "
                "Prueba con otro ticker (ej: AAPL, MSFT, AMZN)."
            )

        self._save_cache(ticker, transcripts)
        print(f"[EDGAR] {len(transcripts)} trimestres únicos guardados en caché.")

        return transcripts
