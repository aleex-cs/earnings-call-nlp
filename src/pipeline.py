"""
Pipeline principal de NLP para Earnings Calls.
Integra todos los componentes en un flujo unificado.
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime

from src.data_fetcher import create_transcript_fetcher
from src.real_data_fetcher import RealDataFetcher
from src.real_financial_data import RealDataFetcher as RealFinancialDataFetcher
from src.fmp_fetcher import FMPAutoFetcher
from src.segmenter import TranscriptSegmenter
from src.chunker import TextChunker
from src.sentiment_analyzer import FinBERTAnalyzer
from src.uncertainty_analyzer import UncertaintyAnalyzer
from src.temporal_analyzer import TemporalAnalyzer


class EarningsCallPipeline:
    """Pipeline completo para análisis de earnings calls."""
    
    def __init__(self, source_type: str = "real_financial", device: str = "cpu") -> None:
        """
        Inicializa el pipeline.
        
        Args:
            source_type: Tipo de fuente de datos ("real_financial", "realistic", "generic", "mock", "fmp")
            device: Dispositivo para FinBERT ("cpu", "cuda")
        """
        print("Inicializando Earnings Call Pipeline...")
        
        # Inicializar componentes según el tipo de fuente
        if source_type == "real_financial":
            # Usar FMP para transcripciones REALES descargadas automáticamente
            self.fetcher: Union[FMPAutoFetcher, RealDataFetcher, object] = FMPAutoFetcher()
            self.source_type: str = source_type
        elif source_type in ["realistic", "generic"]:
            self.fetcher = RealDataFetcher()
            self.source_type = source_type
        else:
            self.fetcher = create_transcript_fetcher(source_type)
            self.source_type = source_type
            
        self.segmenter = TranscriptSegmenter()
        self.chunker = TextChunker()
        self.sentiment_analyzer = FinBERTAnalyzer(device=device)
        self.uncertainty_analyzer = UncertaintyAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        
        print("Pipeline inicializado exitosamente.")
    
    def analyze_single_transcript(self, ticker: str, quarter: str, year: int) -> Dict:
        """
        Analiza una transcripción individual completa.
        
        Args:
            ticker: Símbolo de la empresa
            quarter: Trimestre (Q1, Q2, Q3, Q4)
            year: Año
        
        Returns:
            Transcripción completamente analizada
        """
        print(f"\nAnalizando {ticker} {year} {quarter}...")
        
        # 1. Obtener transcripción
        transcript: Dict = self.fetcher.get_transcript(ticker, quarter, year)
        if not transcript:
            raise ValueError(f"No se encontró transcripción para {ticker} {year} {quarter}")
        
        # 2. Segmentar
        segmented: Dict = self.segmenter.segment_transcript(transcript)
        self._reclean_prepared(segmented)
        
        # 3. Chunking
        chunked: Dict = self.chunker.chunk_transcript(segmented)
        
        # 4. Análisis de sentimiento
        with_sentiment: Dict = self.sentiment_analyzer.analyze_transcript(chunked)
        
        # 5. Análisis de incertidumbre
        final: Dict = self.uncertainty_analyzer.analyze_transcript_uncertainty(with_sentiment)
        
        # 6. Análisis de confianza del documento
        confidence = self.temporal_analyzer.analyze_document_confidence(final)
        final['executive_confidence'] = confidence
        
        return final
        print(f"\nAnalizando {ticker} {year} {quarter}...")
        
        # 1. Obtener transcripción
        transcript = self.fetcher.get_transcript(ticker, quarter, year)
        if not transcript:
            raise ValueError(f"No se encontró transcripción para {ticker} {year} {quarter}")
        
        # 2. Segmentar
        segmented = self.segmenter.segment_transcript(transcript)
        self._reclean_prepared(segmented)
        
        # 3. Chunking
        chunked = self.chunker.chunk_transcript(segmented)
        
        # 4. Análisis de sentimiento
        with_sentiment = self.sentiment_analyzer.analyze_transcript(chunked)
        
        # 5. Análisis de incertidumbre
        final = self.uncertainty_analyzer.analyze_transcript_uncertainty(with_sentiment)
        
        # 6. Análisis de confianza del documento
        confidence = self.temporal_analyzer.analyze_document_confidence(final)
        final['executive_confidence'] = confidence
        
        return final

    @staticmethod
    def _reclean_prepared(segmented: Dict) -> None:
        from src.exhibit_cleaner import clean_exhibit_text
        pr = segmented.get("prepared_remarks") or {}
        raw = pr.get("text") or ""
        cleaned = clean_exhibit_text(raw)
        if cleaned and len(cleaned.split()) >= 40:
            pr["text"] = cleaned
            pr["word_count"] = len(cleaned.split())
            segmented["prepared_remarks"] = pr
    
    def _analyze_transcript_dict(self, transcript: Dict) -> Dict:
        """
        Analiza una transcripción directamente desde un diccionario.
        
        Args:
            transcript: Diccionario con la transcripción completa
        
        Returns:
            Transcripción completamente analizada
        """
        ticker = transcript.get('ticker', 'UNKNOWN')
        quarter = transcript.get('quarter', 'Q1')
        year = transcript.get('year', 2024)
        
        print(f"Analizando {ticker} {year} {quarter}...")
        
        # 2. Segmentar
        segmented = self.segmenter.segment_transcript(transcript)
        self._reclean_prepared(segmented)
        
        # 3. Chunking
        chunked = self.chunker.chunk_transcript(segmented)
        
        # 4. Análisis de sentimiento
        with_sentiment = self.sentiment_analyzer.analyze_transcript(chunked)
        
        # 5. Análisis de incertidumbre
        final = self.uncertainty_analyzer.analyze_transcript_uncertainty(with_sentiment)
        
        # 6. Análisis de confianza del documento
        confidence = self.temporal_analyzer.analyze_document_confidence(final)
        final['executive_confidence'] = confidence
        
        return final
    
    def analyze_company(self, ticker: str, limit: int = 4, save: bool = True) -> Tuple[List[Dict], Optional[Dict]]:
        """
        Analiza todas las transcripciones disponibles de una empresa.
        
        Args:
            ticker: Símbolo de la empresa
            limit: Número de transcripciones a analizar (default: 4)
            save: Si guardar los resultados en disco
        
        Returns:
            Tupla (transcripciones_analizadas, análisis_temporal)
        """
        print(f"\nAnalizando las últimas {limit} transcripciones de {ticker}...")
        
        # Obtener transcripciones según el tipo de fuente
        if self.source_type == "real_financial":
            # Descargar transcripciones REALES desde FMP (con caché automático)
            transcripts = self.fetcher.fetch_transcripts(
                ticker, limit=limit, force_refresh=getattr(self.fetcher, "force_refresh", False)
            )
            
            if not transcripts:
                print(f"No hay transcripciones disponibles para {ticker}")
                return [], None
            
            print(f"Encontradas {len(transcripts)} transcripciones")
            transcripts = self._unique_by_quarter(transcripts)
            
            # Analizar cada transcripción (reutiliza JSON analizado si existe)
            analyzed_transcripts = []
            force = getattr(self.fetcher, "force_refresh", False)
            rerun_nlp = force
            for trans in transcripts:
                try:
                    cached_analyzed = None if rerun_nlp else self._load_analyzed_transcript(trans)
                    analyzed = cached_analyzed or self._analyze_transcript_dict(trans)
                    analyzed_transcripts.append(analyzed)
                    
                    if save and cached_analyzed is None:
                        self._save_transcript(analyzed)
                        
                except Exception as e:
                    print(f"Error analizando transcripción: {e}")
                    continue
            analyzed_transcripts = self._unique_by_quarter(analyzed_transcripts)
            self._refresh_cautions(analyzed_transcripts)
        elif self.source_type in ["realistic", "generic"]:
            # Usar el fetcher de datos realistas
            transcripts = self.fetcher.get_transcripts(ticker, source=self.source_type)
            
            if not transcripts:
                print(f"No hay transcripciones disponibles para {ticker}")
                return [], None
            
            print(f"Encontradas {len(transcripts)} transcripciones")
            
            # Analizar cada transcripción
            analyzed_transcripts = []
            for trans in transcripts:
                try:
                    analyzed = self._analyze_transcript_dict(trans)
                    analyzed_transcripts.append(analyzed)
                    
                    # Guardar individualmente
                    if save:
                        self._save_transcript(analyzed)
                        
                except Exception as e:
                    print(f"Error analizando transcripción: {e}")
                    continue
        else:
            # Usar el fetcher original (mock/fmp)
            available = self.fetcher.list_available(ticker)
            if not available:
                print(f"No hay transcripciones disponibles para {ticker}")
                return [], None
            
            print(f"Encontradas {len(available)} transcripciones")
            
            # Analizar cada transcripción
            analyzed_transcripts = []
            for trans_info in available:
                try:
                    analyzed = self.analyze_single_transcript(
                        ticker,
                        trans_info['quarter'],
                        trans_info['year']
                    )
                    analyzed_transcripts.append(analyzed)
                    
                    # Guardar individualmente
                    if save:
                        self._save_transcript(analyzed)
                        
                except Exception as e:
                    print(f"Error analizando {trans_info}: {e}")
                    continue
        
        # Análisis temporal + señal + topics
        trading_signal = self.temporal_analyzer.generate_trading_signal(analyzed_transcripts)
        topics = self._extract_trending_topics(analyzed_transcripts)
        
        if len(analyzed_transcripts) > 1:
            print(f"\nRealizando análisis temporal...")
            df = self.temporal_analyzer.create_temporal_dataframe(analyzed_transcripts)
            temporal_analysis = self.temporal_analyzer.analyze_temporal_trends(df)
            temporal_analysis['trading_signal'] = trading_signal
            temporal_analysis['trending_topics'] = topics
            temporal_analysis['alerts'] = self.temporal_analyzer.generate_alerts(
                analyzed_transcripts, temporal_analysis
            )
            
            # Guardar análisis temporal
            if save:
                self._save_temporal_analysis(ticker, temporal_analysis, df)
            
            return analyzed_transcripts, temporal_analysis
        
        alerts = self.temporal_analyzer.generate_alerts(analyzed_transcripts, {
            "quarterly_deltas": [],
            "trending_topics": topics
        })
        return analyzed_transcripts, {
            "trading_signal": trading_signal,
            "trending_topics": topics,
            "alerts": alerts
        }

    
    @staticmethod
    def _unique_by_quarter(transcripts: List[Dict]) -> List[Dict]:
        best = {}
        for t in transcripts:
            meta = t.get("metadata") or t
            key = (str(meta.get("year")), str(meta.get("quarter")))
            date = (meta.get("date") or t.get("date") or "")
            prev = best.get(key)
            prev_date = ""
            if prev:
                prev_meta = prev.get("metadata") or prev
                prev_date = prev_meta.get("date") or prev.get("date") or ""
            if prev is None or date >= prev_date:
                best[key] = t
        return sorted(
            best.values(),
            key=lambda t: ((t.get("metadata") or t).get("date") or t.get("date") or ""),
        )

    @staticmethod
    def _refresh_cautions(transcripts: List[Dict]) -> None:
        from src.uncertainty_analyzer import UncertaintyAnalyzer
        ua = UncertaintyAnalyzer()
        for t in transcripts:
            prepared = t.get("prepared_remarks") or {}
            text = prepared.get("text") or ""
            if not text:
                continue
            fresh = ua.analyze_uncertainty(text)
            if "uncertainty" not in prepared or not isinstance(prepared["uncertainty"], dict):
                prepared["uncertainty"] = {}
            prepared["uncertainty"]["extracted_cautions"] = fresh.get("extracted_cautions") or []
            t["prepared_remarks"] = prepared

    def _analyzed_path(self, ticker: str, year, quarter: str) -> str:
        q = str(quarter).replace("Q", "")
        return os.path.join("data", "analyzed", f"{ticker.upper()}_{year}_Q{q}_analyzed.json")

    def _load_analyzed_transcript(self, trans: Dict) -> Optional[Dict]:
        ticker = (trans.get("ticker") or trans.get("metadata", {}).get("ticker") or "").upper()
        year = trans.get("year") or trans.get("metadata", {}).get("year")
        quarter = trans.get("quarter") or trans.get("metadata", {}).get("quarter")
        if not ticker or year is None or not quarter:
            return None
        path = self._analyzed_path(ticker, year, quarter)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                print(f"  Cargando análisis previo {ticker} {year} {quarter}")
                analyzed = json.load(f)
        except Exception:
            return None
        old_text = (analyzed.get("prepared_remarks") or {}).get("text") or ""
        if re.search(r"(?:[A-Z]\s){4,}[A-Z]", old_text) or old_text.lstrip().startswith("EX-99"):
            print("  Análisis previo sucio (TOC/tablas); se reejecuta NLP.")
            return None
        new_text = trans.get("full_transcript") or ""
        if new_text and old_text and abs(len(new_text) - len(old_text)) > max(500, 0.3 * max(len(new_text), len(old_text))):
            print("  El texto limpio cambió respecto al análisis guardado; se reejecuta NLP.")
            return None
        return analyzed

    def _save_transcript(self, transcript: Dict):
        """Guarda una transcripción analizada en disco."""
        output_dir = "data/analyzed"
        os.makedirs(output_dir, exist_ok=True)
        
        ticker = transcript['metadata']['ticker']
        year = transcript['metadata']['year']
        quarter = transcript['metadata']['quarter']
        
        filename = f"{ticker}_{year}_Q{quarter.replace('Q', '')}_analyzed.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def _extract_trending_topics(transcripts: List[Dict]) -> List[Dict]:
        """
        Extrae los topics financieros más mencionados en las transcripciones.
        Compara la frecuencia del último trimestre vs. el promedio histórico.
        """
        # Temas financieros clave con sus palabras clave
        topic_keywords = {
            "AI & Technology":    ["ai", "artificial intelligence", "machine learning", "cloud", "automation", "digital"],
            "Margins & Costs":    ["margin", "margins", "cost", "costs", "expenses", "efficiency", "profitability"],
            "Revenue Growth":     ["revenue", "growth", "sales", "demand", "record", "expansion"],
            "Macroeconomic":      ["inflation", "interest rate", "recession", "macro", "economy", "gdp", "fed"],
            "Supply Chain":       ["supply chain", "inventory", "shortage", "logistics", "disruption"],
            "Layoffs & Workforce":["layoff", "layoffs", "headcount", "restructuring", "workforce", "employees"],
            "China & Geopolitics":["china", "geopolitical", "tariff", "trade", "sanctions", "export"],
            "Guidance & Outlook": ["guidance", "outlook", "forecast", "expect", "anticipate", "next quarter"],
            "Competition":        ["competitive", "competition", "competitor", "market share"],
            "Capital Returns":    ["buyback", "dividend", "repurchase", "shareholder", "capital return"],
        }

        def count_topic(text: str, keywords: list) -> int:
            text_lower = text.lower()
            return sum(text_lower.count(kw) for kw in keywords)

        def transcript_text(t: Dict) -> str:
            prepared = t.get('prepared_remarks') or {}
            return (
                prepared.get('text')
                or prepared.get('full_text')
                or t.get('full_transcript')
                or ""
            )

        results = []

        for topic, keywords in topic_keywords.items():
            counts = []
            for t in transcripts:
                counts.append(count_topic(transcript_text(t), keywords))

            if not counts:
                continue

            latest_count = counts[-1]
            historical_avg = sum(counts[:-1]) / max(len(counts) - 1, 1)

            if latest_count == 0 and historical_avg == 0:
                continue

            # Calcular el cambio relativo respecto a la media histórica
            if historical_avg > 0:
                change_pct = (latest_count - historical_avg) / historical_avg * 100
            elif latest_count > 0:
                change_pct = 100.0
            else:
                change_pct = 0.0

            results.append({
                "topic": topic,
                "latest_count": latest_count,
                "historical_avg": round(historical_avg, 1),
                "change_pct": round(change_pct, 1),
                "series": [
                    {
                        "date": (transcripts[i].get("metadata") or transcripts[i]).get("date"),
                        "year": (transcripts[i].get("metadata") or transcripts[i]).get("year"),
                        "quarter": (transcripts[i].get("metadata") or transcripts[i]).get("quarter"),
                        "count": counts[i],
                    }
                    for i in range(len(transcripts))
                ],
            })

        # Ordenar por menciones recientes (más mencionado primero)
        results.sort(key=lambda x: x['latest_count'], reverse=True)
        return results

    def _save_temporal_analysis(self, ticker: str, analysis: Dict, df):
        """Guarda el análisis temporal."""
        import pandas as pd
        
        output_dir = "data/analyzed"
        os.makedirs(output_dir, exist_ok=True)
        
        # Guardar análisis JSON
        analysis_file = os.path.join(output_dir, f"{ticker}_temporal_analysis.json")
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        # Guardar DataFrame CSV
        csv_file = os.path.join(output_dir, f"{ticker}_temporal_data.csv")
        df.to_csv(csv_file, index=False)
    
    def get_executive_confidence_score(self, transcript: Dict) -> float:
        """
        Obtiene el score de confianza ejecutiva (0-1).
        
        Args:
            transcript: Transcripción analizada
        
        Returns:
            Score de confianza (0 = baja, 1 = alta)
        """
        discrepancy = transcript.get('section_discrepancy', {})
        confidence_indicator = discrepancy.get('executive_confidence_indicator', {})
        
        return confidence_indicator.get('confidence_score', 0.5)
    
    def get_sentiment_color(self, score: float) -> str:
        """Devuelve un color basado en el score de sentimiento."""
        if score > 0.3:
            return "green"  # Positivo
        elif score > -0.3:
            return "yellow"  # Neutral
        else:
            return "red"  # Negativo


if __name__ == "__main__":
    # Ejemplo de uso rápido
    print("Ejecutando pipeline de ejemplo...")
    
    # Crear pipeline
    pipeline = EarningsCallPipeline(source_type="mock", device="cpu")
    
    # Analizar una empresa
    transcripts, temporal = pipeline.analyze_company("AAPL")
    
    print(f"\n✓ Análisis completado para {len(transcripts)} transcripciones")
    
    if temporal:
        print(f"\nEvaluación temporal: {temporal['overall_assessment']}")
    
    # Mostrar resumen
    print(f"\n--- Resumen Ejecutivo ---")
    for trans in transcripts:
        metadata = trans['metadata']
        discrepancy = trans.get('section_discrepancy', {})
        
        confidence = pipeline.get_executive_confidence_score(trans)
        print(f"{metadata['date']} - {metadata['quarter']}: "
              f"Confianza: {confidence:.2f}, "
              f"Descalce: {discrepancy.get('discrepancy_level', 'N/A')}")
