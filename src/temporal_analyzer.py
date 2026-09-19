"""
Módulo para análisis temporal de sentimiento.
Compara el sentimiento entre trimestres consecutivos.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np


class TemporalAnalyzer:
    """Analiza la evolución temporal del sentimiento e incertidumbre."""
    
    def __init__(self):
        """Inicializa el analizador temporal."""
        pass
    
    def load_multiple_transcripts(self, filepaths: List[str]) -> List[Dict]:
        """
        Carga múltiples transcripciones analizadas.
        
        Args:
            filepaths: Lista de rutas a archivos JSON de transcripciones
        
        Returns:
            Lista de transcripciones cargadas
        """
        transcripts = []
        
        for filepath in filepaths:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)
                    transcripts.append(transcript)
            except Exception as e:
                print(f"Error cargando {filepath}: {e}")
        
        # Ordenar por fecha
        transcripts.sort(key=lambda x: x['metadata'].get('date', ''))
        
        return transcripts
    
    def create_temporal_dataframe(self, transcripts: List[Dict]) -> pd.DataFrame:
        """
        Crea un DataFrame con los datos temporales de las transcripciones.
        
        Args:
            transcripts: Lista de transcripciones analizadas
        
        Returns:
            DataFrame con métricas temporales
        """
        data = []
        
        for transcript in transcripts:
            metadata = transcript['metadata']
            prepared = transcript['prepared_remarks']
            sentiment = transcript.get('sentiment_analysis', {})
            uncertainty = transcript.get('uncertainty_analysis', {})
            
            row = {
                'ticker': metadata.get('ticker', ''),
                'company': metadata.get('company', ''),
                'date': metadata.get('date', ''),
                'quarter': metadata.get('quarter', ''),
                'year': metadata.get('year', ''),
                
                # Sentimiento Documento (almacenado en prepared_remarks)
                'document_sentiment': prepared.get('sentiment', {}).get('label', ''),
                'document_sentiment_score': prepared.get('sentiment_score', 0.0),
                'document_confidence': prepared.get('sentiment', {}).get('confidence', 0.0),
                
                # Incertidumbre
                'document_uncertainty_score': prepared.get('uncertainty', {}).get('uncertainty_score', 0.0),
                
                # Contadores
                'word_count': prepared.get('word_count', 0),
            }
            
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Convertir fecha a datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        return df
    
    def calculate_sentiment_delta(self, current_score: float, previous_score: float) -> Dict:
        """
        Calcula el diferencial de sentimiento (Δ Sentiment).
        
        Args:
            current_score: Score de sentimiento del trimestre actual (Q_t)
            previous_score: Score de sentimiento del trimestre anterior (Q_{t-1})
        
        Returns:
            Diccionario con el delta y su interpretación
        """
        delta = current_score - previous_score
        
        # Interpretación del delta
        if delta > 0.5:
            interpretation = "Mejora significativa en el tono"
            severity = "positive_major"
        elif delta > 0.2:
            interpretation = "Mejora moderada en el tono"
            severity = "positive_moderate"
        elif delta > -0.2:
            interpretation = "Tono estable"
            severity = "stable"
        elif delta > -0.5:
            interpretation = "Deterioro moderado en el tono"
            severity = "negative_moderate"
        else:
            interpretation = "Deterioro significativo en el tono (ALERTA)"
            severity = "negative_major"
        
        return {
            "delta": delta,
            "current_score": current_score,
            "previous_score": previous_score,
            "interpretation": interpretation,
            "severity": severity,
            "percentage_change": self._calculate_percentage_change(previous_score, current_score)
        }
    
    def _calculate_percentage_change(self, old_value: float, new_value: float) -> float:
        """Calcula el cambio porcentual."""
        if old_value == 0:
            return 0.0
        return ((new_value - old_value) / abs(old_value)) * 100
    
    def analyze_temporal_trends(self, df: pd.DataFrame) -> Dict:
        """
        Analiza tendencias temporales en el DataFrame.
        
        Args:
            df: DataFrame con datos temporales
        
        Returns:
            Diccionario con análisis de tendencias
        """
        if len(df) < 2:
            return {
                "error": "Se necesitan al menos 2 transcripciones para análisis temporal",
                "trend_analysis": None
            }
        
        # Análisis por sección
        trends = {}
        
        # Tendencia Documento
        document_trend = self._analyze_series_trend(df['document_sentiment_score'].tolist())
        trends['document'] = document_trend
        
        # Tendencia Incertidumbre
        uncertainty_trend = self._analyze_series_trend(df['document_uncertainty_score'].tolist())
        trends['uncertainty'] = uncertainty_trend
        
        # Calcular deltas entre trimestres consecutivos
        deltas = []
        for i in range(1, len(df)):
            current = df.iloc[i]
            previous = df.iloc[i-1]
            
            # Delta Documento
            document_delta = self.calculate_sentiment_delta(
                current['document_sentiment_score'],
                previous['document_sentiment_score']
            )
            
            # Delta Incertidumbre
            uncertainty_delta = current['document_uncertainty_score'] - previous['document_uncertainty_score']
            
            deltas.append({
                'from_quarter': f"{previous['year']} {previous['quarter']}",
                'to_quarter': f"{current['year']} {current['quarter']}",
                'document_sentiment_delta': document_delta,
                'uncertainty_delta': uncertainty_delta,
                'alert_level': self._calculate_alert_level(document_delta, uncertainty_delta)
            })
        
        return {
            "trend_analysis": trends,
            "quarterly_deltas": deltas,
            "overall_assessment": self._generate_overall_assessment(trends, deltas)
        }
    
    def _analyze_series_trend(self, series: List[float]) -> Dict:
        """Analiza la tendencia de una serie de valores."""
        if len(series) < 2:
            return {"trend": "insufficient_data", "slope": 0, "correlation": 0}
        
        # Calcular pendiente (regresión lineal simple)
        x = np.arange(len(series))
        y = np.array(series)
        
        slope = np.polyfit(x, y, 1)[0]
        
        # Calcular correlación con tiempo
        correlation = np.corrcoef(x, y)[0, 1] if len(series) > 1 else 0
        
        # Interpretar tendencia
        if slope > 0.1:
            trend = "increasing"
        elif slope < -0.1:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "slope": float(slope),
            "correlation": float(correlation),
            "start_value": float(series[0]),
            "end_value": float(series[-1]),
            "total_change": float(series[-1] - series[0])
        }
    
    def _calculate_alert_level(self, sentiment_delta: Dict, uncertainty_delta: float) -> str:
        """
        Calcula el nivel de alerta basado en cambios en sentimiento e incertidumbre.
        
        Alto alerta: Sentimiento cae significativamente O incertidumbre sube significativamente
        """
        sentiment_change = sentiment_delta['delta']
        sentiment_severity = sentiment_delta['severity']
        
        # Si el sentimiento cae significativamente
        if sentiment_severity == 'negative_major':
            return 'HIGH'
        
        # Si la incertidumbre sube significativamente (>0.3)
        if uncertainty_delta > 0.3:
            return 'HIGH'
        
        # Si hay deterioro moderado en ambos
        if sentiment_severity == 'negative_moderate' and uncertainty_delta > 0.1:
            return 'MEDIUM'
        
        # Si hay mejora significativa
        if sentiment_severity == 'positive_major':
            return 'LOW_POSITIVE'
        
        return 'LOW'
    
    def _generate_overall_assessment(self, trends: Dict, deltas: List[Dict]) -> str:
        """Genera una evaluación general de la situación."""
        if not deltas:
            return "Insuficientes datos para evaluación temporal"
        
        # Contar alertas
        high_alerts = sum(1 for d in deltas if d['alert_level'] == 'HIGH')
        medium_alerts = sum(1 for d in deltas if d['alert_level'] == 'MEDIUM')
        
        # Evaluar tendencias
        doc_trend = trends.get('document', {}).get('trend', 'unknown')
        uncertainty_trend = trends.get('uncertainty', {}).get('trend', 'unknown')
        
        if high_alerts > 0:
            return (f"ALERT CRITICAL: {high_alerts} significant negative changes detected. "
                   f"Document Trend: {doc_trend}, Uncertainty: {uncertainty_trend}. "
                   "Detailed investigation recommended.")
        elif medium_alerts > 0:
            return (f"ALERT MODERATE: {medium_alerts} moderate negative changes. "
                   f"Document Trend: {doc_trend}, Uncertainty: {uncertainty_trend}. "
                   "Monitoring recommended.")
        elif doc_trend == 'increasing' and uncertainty_trend == 'decreasing':
            return "STABLE: Improvement in sentiment and reduction in uncertainty."
        elif doc_trend == 'decreasing':
            return "CAUTION: Negative trend in document sentiment."
        else:
            return "STABLE: No significant changes detected."
    
    def analyze_document_confidence(self, transcript: Dict) -> Dict:
        """
        Analiza la confianza global basada en el texto del documento.
        Reemplaza a analyze_section_discrepancy ya que ahora no tenemos Q&A.
        
        Args:
            transcript: Transcripción individual analizada
        
        Returns:
            Análisis de confianza del documento
        """
        # Segmenter pone todo el texto en prepared_remarks para EDGAR 8-K
        doc = transcript['prepared_remarks']
        
        sentiment_score = doc.get('sentiment_score', 0.0)
        
        try:
            uncertainty_score = doc['uncertainty']['uncertainty_score']
        except (KeyError, TypeError):
            uncertainty_score = 0.0
            
        return {
            "executive_confidence_indicator": self._calculate_executive_confidence(
                sentiment_score, uncertainty_score
            )
        }
    
    def _calculate_executive_confidence(self, sentiment_score: float, uncertainty_score: float) -> Dict:
        """
        Calcula un indicador de confianza ejecutiva (0-1).
        
        Alta confianza: Sentimiento positivo, baja incertidumbre.
        Baja confianza: Sentimiento negativo, alta incertidumbre.
        """
        # Convertir sentimiento (-1 a 1) a escala (0 a 1)
        normalized_sentiment = (sentiment_score + 1) / 2
        # La "confianza" no debe ser un clon del sentimiento: prioriza claridad
        # (poca evasión) y solo usa el tono como ajuste menor.
        confidence = ((1.0 - uncertainty_score) * 0.75) + (normalized_sentiment * 0.25)
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "confidence_score": confidence,
            "confidence_level": self._interpret_confidence_level(confidence),
            "factors": {
                "sentiment_factor": normalized_sentiment,
                "uncertainty_factor": 1.0 - uncertainty_score
            }
        }
    
    def _interpret_confidence_level(self, score: float) -> str:
        """Interpreta el nivel de confianza."""
        if score > 0.8:
            return "HIGH"
        elif score > 0.6:
            return "MODERATE-HIGH"
        elif score > 0.4:
            return "MODERATE"
        elif score > 0.2:
            return "LOW-MODERATE"
        else:
            return "LOW"

    def generate_trading_signal(self, transcripts: List[Dict]) -> Dict:
        """
        Genera una señal de trading NLP basada en las métricas del documento.
        Combina: sentimiento actual, incertidumbre actual y momentum (delta vs trimestre anterior).

        Returns:
            Diccionario con signal, score, y rationale
        """
        if not transcripts:
            return {"signal": "NEUTRAL", "score": 0.0, "rationale": "No data available."}

        # Tomar el trimestre más reciente
        latest = transcripts[-1]
        doc = latest.get('prepared_remarks', {})

        sentiment = doc.get('sentiment_score', 0.0)
        uncertainty = doc.get('uncertainty', {}).get('uncertainty_score', 0.0)
        confidence = latest.get('executive_confidence', {}).get('executive_confidence_indicator', {}).get('confidence_score', 0.5)

        # Calcular momentum si hay al menos 2 trimestres
        momentum = 0.0
        if len(transcripts) >= 2:
            prev = transcripts[-2].get('prepared_remarks', {})
            prev_sentiment = prev.get('sentiment_score', 0.0)
            prev_uncertainty = prev.get('uncertainty', {}).get('uncertainty_score', 0.0)
            # Momentum positivo si sentimiento mejora y/o incertidumbre baja
            sentiment_momentum = sentiment - prev_sentiment  # [-2, +2]
            uncertainty_momentum = prev_uncertainty - uncertainty  # positivo = mejora
            momentum = (sentiment_momentum * 0.6 + uncertainty_momentum * 0.4)  # [-2, +2], normalize below

        # Construir score compuesto [-1, 1]:
        # Sentimiento: -1 a +1
        # Confianza: 0 a 1, convertido a -0.5 a +0.5
        # Momentum: raw, clampado
        composite = (
            sentiment * 0.4 +
            (confidence - 0.5) * 2 * 0.3 +
            max(-1.0, min(1.0, momentum)) * 0.3
        )
        composite = max(-1.0, min(1.0, composite))

        # Convertir a señal discreta
        if composite >= 0.4:
            signal = "STRONG BUY"
            color = "#10b981"
        elif composite >= 0.15:
            signal = "BUY"
            color = "#34d399"
        elif composite <= -0.4:
            signal = "STRONG SELL"
            color = "#ef4444"
        elif composite <= -0.15:
            signal = "SELL"
            color = "#f87171"
        else:
            signal = "NEUTRAL"
            color = "#f59e0b"

        # Generar rationale legible
        sentiment_desc = "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral"
        uncert_desc = "high" if uncertainty > 0.4 else "moderate" if uncertainty > 0.2 else "low"
        momentum_desc = "improving" if momentum > 0.05 else "deteriorating" if momentum < -0.05 else "stable"

        rationale = (
            f"Latest earnings release shows {sentiment_desc} sentiment (score: {sentiment:.2f}), "
            f"{uncert_desc} uncertainty ({uncertainty*100:.0f}%), "
            f"and {momentum_desc} momentum vs prior quarter."
        )

        return {
            "signal": signal,
            "score": round(composite, 3),
            "color": color,
            "rationale": rationale,
            "factors": {
                "sentiment": round(sentiment, 3),
                "uncertainty": round(uncertainty, 3),
                "confidence": round(confidence, 3),
                "momentum": round(momentum, 3)
            }
        }

    def generate_alerts(self, transcripts: List[Dict], temporal: Optional[Dict] = None) -> List[Dict]:
        """
        Alertas relativas al propio histórico de la empresa.
        Los umbrales absolutos (confianza < 40%, incertidumbre > 60%) casi nunca
        se cumplen en press releases, así que se usan z-scores y deltas trimestrales.
        """
        alerts: List[Dict] = []
        if not transcripts:
            return alerts

        temporal = temporal or {}
        sents = [t.get("prepared_remarks", {}).get("sentiment_score", 0.0) for t in transcripts]
        uncerts = [
            t.get("prepared_remarks", {}).get("uncertainty", {}).get("uncertainty_score", 0.0)
            for t in transcripts
        ]
        confs = [
            t.get("executive_confidence", {})
            .get("executive_confidence_indicator", {})
            .get("confidence_score", 0.5)
            for t in transcripts
        ]

        latest = transcripts[-1]
        meta = latest.get("metadata") or {}
        latest_label = f"{meta.get('year', '')} {meta.get('quarter', '')}".strip() or meta.get("date", "latest")

        if len(sents) >= 3:
            hist_s, hist_u, hist_c = sents[:-1], uncerts[:-1], confs[:-1]
            sent_std = max(float(np.std(hist_s)), 0.03)
            uncert_std = max(float(np.std(hist_u)), 0.002)
            conf_std = max(float(np.std(hist_c)), 0.01)
            z_s = (sents[-1] - float(np.mean(hist_s))) / sent_std
            z_u = (uncerts[-1] - float(np.mean(hist_u))) / uncert_std
            z_c = (confs[-1] - float(np.mean(hist_c))) / conf_std

            if z_s <= -1.5:
                alerts.append({
                    "type": "critical",
                    "date": meta.get("date"),
                    "msg": f"Sentiment in {latest_label} is well below this company's history (z={z_s:.2f}, score {sents[-1]:.3f} vs avg {np.mean(hist_s):.3f})."
                })
            elif z_s <= -0.8:
                alerts.append({
                    "type": "moderate",
                    "date": meta.get("date"),
                    "msg": f"Sentiment softened vs this company's history in {latest_label} (z={z_s:.2f})."
                })
            elif z_s >= 1.2:
                alerts.append({
                    "type": "positive",
                    "date": meta.get("date"),
                    "msg": f"Sentiment in {latest_label} is unusually strong vs this company's history (z={z_s:.2f})."
                })

            if z_u >= 1.5:
                alerts.append({
                    "type": "critical",
                    "date": meta.get("date"),
                    "msg": f"Uncertainty spiked vs history in {latest_label} ({uncerts[-1]*100:.2f}% vs avg {np.mean(hist_u)*100:.2f}%)."
                })
            elif z_u >= 0.8:
                alerts.append({
                    "type": "moderate",
                    "date": meta.get("date"),
                    "msg": f"Uncertainty is elevated vs this company's baseline in {latest_label} ({uncerts[-1]*100:.2f}% vs {np.mean(hist_u)*100:.2f}%)."
                })
            elif z_u <= -1.0:
                alerts.append({
                    "type": "positive",
                    "date": meta.get("date"),
                    "msg": f"Language is clearer than usual in {latest_label} (uncertainty {uncerts[-1]*100:.2f}% vs avg {np.mean(hist_u)*100:.2f}%)."
                })

            if z_c <= -1.2:
                alerts.append({
                    "type": "moderate",
                    "date": meta.get("date"),
                    "msg": f"Executive confidence dipped vs history in {latest_label} ({confs[-1]*100:.1f}% vs avg {np.mean(hist_c)*100:.1f}%)."
                })

        if len(sents) >= 3 and sents[-1] < sents[-2] < sents[-3]:
            alerts.append({
                "type": "moderate",
                "date": meta.get("date"),
                "msg": f"Sentiment declined for three consecutive filings ending {latest_label}."
            })

        for d in temporal.get("quarterly_deltas") or []:
            delta = (d.get("document_sentiment_delta") or {}).get("delta", 0)
            u_delta = d.get("uncertainty_delta") or 0
            label = f"{d.get('from_quarter')} → {d.get('to_quarter')}"
            if d.get("alert_level") == "HIGH" or delta <= -0.2:
                alerts.append({
                    "type": "critical",
                    "date": d.get("to_quarter"),
                    "msg": f"Sharp tone deterioration {label} (Δ sentiment {delta:+.3f})."
                })
            elif d.get("alert_level") == "MEDIUM" or delta <= -0.1:
                alerts.append({
                    "type": "moderate",
                    "date": d.get("to_quarter"),
                    "msg": f"Moderate tone deterioration {label} (Δ sentiment {delta:+.3f})."
                })
            elif delta >= 0.15:
                alerts.append({
                    "type": "positive",
                    "date": d.get("to_quarter"),
                    "msg": f"Tone improved {label} (Δ sentiment {delta:+.3f})."
                })
            if u_delta >= 0.01:
                alerts.append({
                    "type": "moderate",
                    "date": d.get("to_quarter"),
                    "msg": f"Uncertainty rose {label} (Δ {u_delta*100:+.2f} pp)."
                })

        for topic in temporal.get("trending_topics") or []:
            change = topic.get("change_pct", 0)
            if topic.get("latest_count", 0) >= 3 and change >= 80:
                alerts.append({
                    "type": "moderate",
                    "date": meta.get("date"),
                    "msg": f"Topic spike: “{topic['topic']}” is {change:.0f}% above the historical average ({topic['latest_count']} mentions)."
                })
            elif topic.get("historical_avg", 0) >= 3 and change <= -50:
                alerts.append({
                    "type": "moderate",
                    "date": meta.get("date"),
                    "msg": f"Topic drop: “{topic['topic']}” is {abs(change):.0f}% below the historical average."
                })

        seen = set()
        unique = []
        for a in alerts:
            key = (a.get("type"), a.get("msg"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(a)

        unique.sort(key=lambda a: {"critical": 0, "moderate": 1, "positive": 2}.get(a["type"], 3))

        if not unique:
            unique.append({
                "type": "info",
                "date": meta.get("date"),
                "msg": (
                    f"No relative anomalies vs this company's own history. "
                    f"Latest sentiment {sents[-1]:.3f}, uncertainty {uncerts[-1]*100:.2f}%, "
                    f"confidence {confs[-1]*100:.1f}%."
                )
            })
        return unique


if __name__ == "__main__":
    # Ejemplo de uso
    print("Probando TemporalAnalyzer...")
    
    # Cargar transcripciones existentes (primero generar más datos)
    print("\nGenerando transcripciones adicionales para análisis temporal...")
    
    # Usar el data_fetcher para obtener más transcripciones
    import sys
    sys.path.append('.')
    from src.data_fetcher import create_transcript_fetcher
    from src.segmenter import TranscriptSegmenter
    from src.chunker import TextChunker
    from src.sentiment_analyzer import FinBERTAnalyzer
    from src.uncertainty_analyzer import UncertaintyAnalyzer
    
    fetcher = create_transcript_fetcher("mock")
    segmenter = TranscriptSegmenter()
    chunker = TextChunker()
    
    # Obtener transcripciones disponibles
    transcripts = fetcher.list_available("AAPL")
    print(f"Transcripciones disponibles: {len(transcripts)}")
    
    # Procesar todas las transcripciones
    all_analyzed = []
    
    # Cargar la que ya tenemos
    with open("data/segmented/AAPL_2024_Q1_final.json", "r", encoding="utf-8") as f:
        all_analyzed.append(json.load(f))
    
    # Procesar las demás
    for trans_info in transcripts:
        ticker = trans_info['ticker']
        quarter = trans_info['quarter']
        year = trans_info['year']
        
        # Saltar la que ya tenemos
        if year == 2024 and quarter == "Q1":
            continue
        
        print(f"Procesando {ticker} {year} {quarter}...")
        
        # Obtener transcripción
        transcript = fetcher.get_transcript(ticker, quarter, year)
        if not transcript:
            continue
        
        # Segmentar
        segmented = segmenter.segment_transcript(transcript)
        
        # Chunking
        chunked = chunker.chunk_transcript(segmented)
        
        # Análisis de sentimiento
        analyzer = FinBERTAnalyzer()
        analyzed = analyzer.analyze_transcript(chunked)
        
        # Análisis de incertidumbre
        uncertainty_analyzer = UncertaintyAnalyzer()
        final = uncertainty_analyzer.analyze_transcript_uncertainty(analyzed)
        
        # Guardar
        filename = f"data/segmented/{ticker}_{year}_Q{quarter.replace('Q', '')}_final.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)
        
        all_analyzed.append(final)
    
    # Análisis temporal
    print(f"\n--- Análisis Temporal ---")
    temporal_analyzer = TemporalAnalyzer()
    
    # Crear DataFrame
    df = temporal_analyzer.create_temporal_dataframe(all_analyzed)
    print(f"\nDataFrame creado con {len(df)} transcripciones")
    print(df[['date', 'quarter', 'qa_sentiment_score', 'prepared_sentiment_score', 
              'qa_uncertainty_score']].to_string())
    
    # Análisis de tendencias
    trends = temporal_analyzer.analyze_temporal_trends(df)
    print(f"\n{trends['overall_assessment']}")
    
    # Análisis de descalce por sección
    print(f"\n--- Análisis de Descalce por Sección ---")
    for analyzed in all_analyzed:
        metadata = analyzed['metadata']
        discrepancy = temporal_analyzer.analyze_section_discrepancy(analyzed)
        
        print(f"\n{metadata['company']} - {metadata['date']}:")
        print(f"  Nivel descalce: {discrepancy['discrepancy_level']}")
        print(f"  Confianza ejecutiva: {discrepancy['executive_confidence_indicator']['confidence_level']}")
        print(f"  {discrepancy['interpretation']}")
