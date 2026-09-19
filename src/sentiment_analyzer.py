"""
Módulo para análisis de sentimiento usando FinBERT.
Especializado en textos financieros.
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import Dict, List, Optional, Tuple
import numpy as np
from tqdm import tqdm


class FinBERTAnalyzer:
    """Analizador de sentimiento usando FinBERT."""
    
    def __init__(self, model_name: str = "ProsusAI/finbert", device: Optional[str] = None):
        """
        Inicializa el analizador FinBERT.
        
        Args:
            model_name: Nombre del modelo en HuggingFace
            device: 'cuda', 'cpu', o None (auto-detect)
        """
        self.model_name = model_name
        self.device = self._get_device(device)
        
        print(f"Cargando modelo FinBERT ({model_name}) en {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        self.use_fp16 = self.device == "cuda"
        self.batch_size = 32 if self.device == "cuda" else 8

        # ProsusAI/finbert id2label is {0: positive, 1: negative, 2: neutral}.
        # Hardcoding ["negative","neutral","positive"] inverted every score.
        id2label = getattr(self.model.config, "id2label", None) or {}
        n_labels = int(getattr(self.model.config, "num_labels", 3) or 3)
        labels = []
        for i in range(n_labels):
            raw = id2label.get(i, id2label.get(str(i), ["positive", "negative", "neutral"][i]))
            labels.append(str(raw).lower())
        self.labels = labels
        print(f"FinBERT labels (logit order): {self.labels}")
        
        print(f"Modelo cargado exitosamente en {self.device}"
              + (f" ({torch.cuda.get_device_name(0)})" if self.device == "cuda" else "")
              + f", batch_size={self.batch_size}.")
    
    def _get_device(self, device: Optional[str]) -> str:
        """Detecta el dispositivo disponible."""
        if device:
            # Si el usuario pide CUDA pero no está disponible, usar CPU
            if device == "cuda" and not torch.cuda.is_available():
                print("CUDA solicitado pero no disponible. Usando CPU.")
                return "cpu"
            return device
        
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
        else:
            return "cpu"
    
    def _empty_result(self) -> Dict:
        return {
            "label": "neutral",
            "confidence": 0.0,
            "probabilities": {
                "negative": 0.0,
                "neutral": 1.0,
                "positive": 0.0
            }
        }

    def _probs_to_result(self, predictions) -> Dict:
        return {
            "label": self.labels[int(np.argmax(predictions))],
            "confidence": float(np.max(predictions)),
            "probabilities": {
                self.labels[i]: float(predictions[i])
                for i in range(len(self.labels))
            }
        }

    def analyze_text(self, text: str) -> Dict:
        """
        Analiza el sentimiento de un texto.
        
        Args:
            text: Texto a analizar
        
        Returns:
            Diccionario con probabilidades y etiqueta predicha
        """
        return self.analyze_chunks([text], show_progress=False)[0]
    
    def analyze_chunks(self, chunks: List[str], show_progress: bool = True) -> List[Dict]:
        """
        Analiza el sentimiento de múltiples chunks (por lotes en GPU).
        """
        if not chunks:
            return []

        results: List[Optional[Dict]] = [None] * len(chunks)
        pending_idx = [i for i, c in enumerate(chunks) if c and c.strip()]
        for i, c in enumerate(chunks):
            if not c or not c.strip():
                results[i] = self._empty_result()

        if not pending_idx:
            return results

        iterator = range(0, len(pending_idx), self.batch_size)
        if show_progress:
            iterator = tqdm(iterator, desc=f"Analizando chunks ({self.device})",
                            total=(len(pending_idx) + self.batch_size - 1) // self.batch_size)

        for start in iterator:
            batch_ids = pending_idx[start:start + self.batch_size]
            batch_texts = [chunks[i] for i in batch_ids]
            inputs = self.tokenizer(
                batch_texts,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            inputs = {k: v.to(self.device, non_blocking=True) for k, v in inputs.items()}

            with torch.inference_mode():
                if self.use_fp16:
                    with torch.autocast(device_type="cuda", dtype=torch.float16):
                        outputs = self.model(**inputs)
                else:
                    outputs = self.model(**inputs)
                preds = torch.nn.functional.softmax(outputs.logits, dim=-1).detach().cpu().numpy()

            for row, idx in enumerate(batch_ids):
                results[idx] = self._probs_to_result(preds[row])

        return results
    
    def aggregate_sentiment(self, chunk_results: List[Dict]) -> Dict:
        """
        Agrega los resultados de múltiples chunks en un sentimiento global.
        
        Args:
            chunk_results: Resultados de análisis por chunk
        
        Returns:
            Sentimiento agregado
        """
        if not chunk_results:
            return {
                "label": "neutral",
                "confidence": 0.0,
                "probabilities": {
                    "negative": 0.0,
                    "neutral": 1.0,
                    "positive": 0.0
                },
                "method": "no_data"
            }
        
        # Promediar probabilidades
        avg_probabilities = {
            "negative": np.mean([r["probabilities"]["negative"] for r in chunk_results]),
            "neutral": np.mean([r["probabilities"]["neutral"] for r in chunk_results]),
            "positive": np.mean([r["probabilities"]["positive"] for r in chunk_results])
        }
        
        # Etiqueta basada en la probabilidad promedio más alta
        label = max(avg_probabilities, key=avg_probabilities.get)
        confidence = avg_probabilities[label]
        
        return {
            "label": label,
            "confidence": float(confidence),
            "probabilities": avg_probabilities,
            "method": "average_probability",
            "chunk_count": len(chunk_results)
        }
    
    def calculate_sentiment_score(self, sentiment_result: Dict) -> float:
        """
        Calcula un score numérico de sentimiento (-1 a 1).
        
        Args:
            sentiment_result: Resultado del análisis de sentimiento
        
        Returns:
            Score entre -1 (muy negativo) y 1 (muy positivo)
        """
        probs = sentiment_result["probabilities"]
        
        # Ponderar: positive = +1, neutral = 0, negative = -1
        score = (
            probs["positive"] * 1.0 +
            probs["neutral"] * 0.0 +
            probs["negative"] * -1.0
        )
        
        return score
    
    def analyze_transcript(self, chunked_transcript: Dict) -> Dict:
        """
        Analiza el sentimiento de una transcripción completa chunked.
        
        Args:
            chunked_transcript: Transcripción con chunks
        
        Returns:
            Transcripción con análisis de sentimiento añadido
        """
        result = chunked_transcript.copy()
        
        # Analizar Prepared Remarks
        prepared_chunks = chunked_transcript["prepared_remarks"]["chunks"]
        prepared_results = self.analyze_chunks(prepared_chunks)
        prepared_aggregated = self.aggregate_sentiment(prepared_results)
        prepared_score = self.calculate_sentiment_score(prepared_aggregated)
        
        result["prepared_remarks"]["sentiment"] = prepared_aggregated
        result["prepared_remarks"]["sentiment_score"] = prepared_score
        result["prepared_remarks"]["sentiment_by_chunk"] = prepared_results
        
        # Analizar Q&A Session
        qa_chunks = chunked_transcript["qa_session"]["chunks"]
        qa_results = self.analyze_chunks(qa_chunks)
        qa_aggregated = self.aggregate_sentiment(qa_results)
        qa_score = self.calculate_sentiment_score(qa_aggregated)
        
        result["qa_session"]["sentiment"] = qa_aggregated
        result["qa_session"]["sentiment_score"] = qa_score
        result["qa_session"]["sentiment_by_chunk"] = qa_results
        
        # Calcular diferencial entre secciones
        sentiment_gap = prepared_score - qa_score
        result["sentiment_analysis"] = {
            "prepared_remarks_score": prepared_score,
            "qa_session_score": qa_score,
            "sentiment_gap": sentiment_gap,
            "gap_interpretation": self._interpret_gap(sentiment_gap)
        }
        
        return result
    
    def _interpret_gap(self, gap: float) -> str:
        """Interpreta el diferencial de sentimiento entre secciones."""
        if gap > 0.3:
            return "Prepared remarks significativamente más optimistas que Q&A"
        elif gap > 0.1:
            return "Prepared remarks ligeramente más optimistas que Q&A"
        elif gap > -0.1:
            return "Tono similar entre secciones"
        elif gap > -0.3:
            return "Q&A ligeramente más optimista que Prepared remarks"
        else:
            return "Q&A significativamente más optimista que Prepared remarks"


class FallbackSentimentAnalyzer:
    """Analizador de sentimiento fallback usando VADER (más rápido pero menos preciso)."""
    
    def __init__(self):
        """Inicializa VADER."""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.analyzer = SentimentIntensityAnalyzer()
            self.available = True
        except ImportError:
            print("VADER no disponible. Instala con: pip install vaderSentiment")
            self.available = False
    
    def analyze_text(self, text: str) -> Dict:
        """Analiza sentimiento usando VADER."""
        if not self.available:
            return {
                "label": "neutral",
                "confidence": 0.0,
                "probabilities": {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
            }
        
        scores = self.analyzer.polarity_scores(text)
        
        # Convertir scores de VADER a formato compatible
        compound = scores["compound"]
        
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        
        # Convertir a probabilidades aproximadas
        if label == "positive":
            pos_prob = 0.5 + abs(compound) * 0.5
            neg_prob = (1 - pos_prob) * 0.3
            neu_prob = (1 - pos_prob) * 0.7
        elif label == "negative":
            neg_prob = 0.5 + abs(compound) * 0.5
            pos_prob = (1 - neg_prob) * 0.3
            neu_prob = (1 - neg_prob) * 0.7
        else:
            neu_prob = 0.7 + abs(compound) * 0.3
            pos_prob = (1 - neu_prob) * 0.5
            neg_prob = (1 - neu_prob) * 0.5
        
        return {
            "label": label,
            "confidence": abs(compound),
            "probabilities": {
                "positive": pos_prob,
                "neutral": neu_prob,
                "negative": neg_prob
            }
        }


if __name__ == "__main__":
    # Ejemplo de uso
    print("Probando FinBERTAnalyzer...")
    
    # Cargar transcripción chunked
    import json
    with open("data/segmented/AAPL_2024_Q1_chunked.json", "r", encoding="utf-8") as f:
        chunked = json.load(f)
    
    # Crear analizador (esto descargará el modelo la primera vez)
    try:
        analyzer = FinBERTAnalyzer()
        
        # Analizar transcripción
        print("\nAnalizando transcripción completa...")
        analyzed = analyzer.analyze_transcript(chunked)
        
        # Mostrar resultados
        print(f"\n--- Resultados de Análisis de Sentimiento ---")
        print(f"Empresa: {analyzed['metadata']['company']}")
        print(f"Fecha: {analyzed['metadata']['date']}")
        
        print(f"\nPrepared Remarks:")
        print(f"  Sentimiento: {analyzed['prepared_remarks']['sentiment']['label']}")
        print(f"  Confianza: {analyzed['prepared_remarks']['sentiment']['confidence']:.3f}")
        print(f"  Score: {analyzed['prepared_remarks']['sentiment_score']:.3f}")
        
        print(f"\nQ&A Session:")
        print(f"  Sentimiento: {analyzed['qa_session']['sentiment']['label']}")
        print(f"  Confianza: {analyzed['qa_session']['sentiment']['confidence']:.3f}")
        print(f"  Score: {analyzed['qa_session']['sentiment_score']:.3f}")
        
        print(f"\nAnálisis Comparativo:")
        print(f"  Gap: {analyzed['sentiment_analysis']['sentiment_gap']:.3f}")
        print(f"  Interpretación: {analyzed['sentiment_analysis']['gap_interpretation']}")
        
        # Guardar resultado
        with open("data/segmented/AAPL_2024_Q1_analyzed.json", "w", encoding="utf-8") as f:
            json.dump(analyzed, f, ensure_ascii=False, indent=2)
        
        print(f"\nTranscripción analizada guardada en: data/segmented/AAPL_2024_Q1_analyzed.json")
        
    except Exception as e:
        print(f"\nError al cargar FinBERT: {e}")
        print("Usando fallback analyzer...")
        
        fallback = FallbackSentimentAnalyzer()
        if fallback.available:
            # Probar con un texto simple
            test_text = "The company had excellent results this quarter with strong growth."
            result = fallback.analyze_text(test_text)
            print(f"\nResultado fallback: {result}")
