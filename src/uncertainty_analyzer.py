"""
Módulo para análisis de incertidumbre en transcripciones.
Identifica lenguaje evasivo y de duda.
"""

from typing import Dict, List
import re
from collections import Counter


class UncertaintyAnalyzer:
    """Analiza la incertidumbre en el lenguaje de ejecutivos."""
    
    def __init__(self):
        """Inicializa el analizador con diccionarios de palabras de incertidumbre."""
        
        # Diccionario de palabras de incertidumbre/duda
        self.uncertainty_words = {
            # Palabras de duda directa
            "uncertain", "uncertainty", "unclear", "unsure", "uncertainly",
            "doubt", "doubtful", "doubts", "questionable", "questionably",
            "speculate", "speculation", "speculative", "hypothetical",
            
            # Palabras de cautela
            "cautious", "cautiously", "careful", "carefully", "conservative",
            "wary", "hesitant", "hesitate", "hesitation", "reluctant",
            
            # Palabras de indefinición temporal
            "eventually", "ultimately", "potentially", "possibly", "perhaps",
            "maybe", "might", "could", "may", "should", "would",
            "sometime", "someday", "in the future", "down the road",
            
            # Palabras de probabilidad baja
            "unlikely", "improbable", "rarely", "seldom", "hardly",
            
            # Palabras de evasión
            "decline", "declined", "cannot comment", "no comment", 
            "not appropriate", "not at liberty", "premature",
            "speculate", "speculation", "guide", "guidance",
            
            # Palabras de mitigación
            "approximately", "roughly", "about", "around", "estimated",
            "projected", "forecast", "expectation", "anticipate",
            
            # Palabras de riesgo
            "risk", "risky", "challenge", "challenging", "headwind",
            "headwinds", "concern", "concerning", "concerns", "issue",
            "issues", "problem", "problems", "difficulty", "difficulties",
            
            # Palabras de volatilidad
            "volatile", "volatility", "fluctuate", "fluctuation", "variable",
            "unpredictable", "uncertain", "uncertainty"
        }
        
        # Patrones de frases evasivas
        self.evasive_patterns = [
            r"we (can't|cannot) (say|comment|speculate|provide)",
            r"it's (too early|premature) to",
            r"we (don't|do not) have (enough|sufficient) (data|information|visibility)",
            r"(we|i) (remain|are) (cautious|conservative)",
            r"it's (difficult|hard|challenging) to (predict|forecast|say)",
            r"visibility is (limited|unclear|poor)",
            r"we're (not|unable to) (provide|give) (guidance|details)",
            r"(it's|that's) (not|not yet) (clear|certain|determined)",
            r"we (will|would) not (comment|speculate)",
            r"premature to (speculate|comment|judge)"
        ]
        
        # Compilación de patrones regex
        self.evasive_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.evasive_patterns]
    
    def analyze_uncertainty(self, text: str) -> Dict:
        """
        Analiza la incertidumbre en un texto.
        
        Args:
            text: Texto a analizar
        
        Returns:
            Diccionario con métricas de incertidumbre
        """
        text_lower = text.lower()
        words = text_lower.split()

        sentences = re.split(r'(?<=[.!?])(?:\s+|(?=[A-Z"“]))', text)
        if len(sentences) < 4:
            sentences = re.split(r'[\n;]+', text)

        extracted_cautions = []
        uncertainty_word_count = 0
        evasive_pattern_count = 0

        for sentence in sentences:
            s_lower = sentence.lower()
            s_words = s_lower.split()
            u_count = sum(1 for w in s_words if w.strip(".,;:()") in self.uncertainty_words)
            uncertainty_word_count += u_count
            e_count = sum(1 for pattern in self.evasive_regex if pattern.search(sentence))
            evasive_pattern_count += e_count

            clean_sentence = " ".join(sentence.split())
            if self._is_junk_quote(clean_sentence):
                continue
            if 8 <= len(s_words) <= 70 and (e_count > 0 or u_count >= 2):
                extracted_cautions.append((u_count + e_count * 2, clean_sentence))

        extracted_cautions.sort(key=lambda x: x[0], reverse=True)
        seen = set()
        top_cautions = []
        for _, quote in extracted_cautions:
            key = quote[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            top_cautions.append(quote)
            if len(top_cautions) >= 8:
                break
        
        # Calcular ratios
        total_words = len(words)
        uncertainty_ratio = uncertainty_word_count / total_words if total_words > 0 else 0
        evasive_ratio = evasive_pattern_count / total_words if total_words > 0 else 0
        
        # Calcular score de incertidumbre (0-1)
        uncertainty_score = self._calculate_uncertainty_score(
            uncertainty_ratio, evasive_ratio, total_words
        )
        
        # Identificar palabras de incertidumbre más frecuentes
        frequent_uncertainty_words = self._get_frequent_uncertainty_words(words)

        return {
            "uncertainty_word_count": uncertainty_word_count,
            "evasive_pattern_count": evasive_pattern_count,
            "total_words": total_words,
            "uncertainty_ratio": uncertainty_ratio,
            "evasive_ratio": evasive_ratio,
            "uncertainty_score": uncertainty_score,
            "uncertainty_level": self._interpret_uncertainty_level(uncertainty_score),
            "frequent_uncertainty_words": frequent_uncertainty_words,
            "interpretation": self._interpret_uncertainty(uncertainty_score, uncertainty_ratio, evasive_ratio),
            "extracted_cautions": top_cautions
        }

    @staticmethod
    def _is_junk_quote(text: str) -> bool:
        if not text or len(text) < 40:
            return True
        if re.search(r"(?i)ex-99|exhibit 99|unaudited|financial summary|highlights \d", text):
            return True
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return True
        if sum(1 for c in letters if c.islower()) / len(letters) < 0.4:
            return True
        digits = sum(1 for c in text if c.isdigit())
        if digits / max(len(text), 1) > 0.22:
            return True
        return False
    
    def _calculate_uncertainty_score(self, uncertainty_ratio: float, 
                                     evasive_ratio: float, total_words: int) -> float:
        """
        Calcula un score compuesto de incertidumbre (0-1).
        
        Fórmula: 0.6 * uncertainty_ratio + 0.4 * evasive_ratio
        (Pesos: palabras de incertidumbre tienen más peso que patrones)
        """
        # Normalizar ratios (asumiendo que ratios > 0.1 son altos)
        normalized_uncertainty = min(uncertainty_ratio / 0.1, 1.0)
        normalized_evasive = min(evasive_ratio / 0.05, 1.0)  # Patrones son más raros
        
        score = 0.6 * normalized_uncertainty + 0.4 * normalized_evasive
        return score
    
    def _interpret_uncertainty_level(self, score: float) -> str:
        """Interpreta el nivel de incertidumbre."""
        if score < 0.2:
            return "Baja"
        elif score < 0.4:
            return "Moderada"
        elif score < 0.6:
            return "Media-Alta"
        elif score < 0.8:
            return "Alta"
        else:
            return "Muy Alta"
    
    def _interpret_uncertainty(self, score: float, uncertainty_ratio: float, 
                               evasive_ratio: float) -> str:
        """Genera una interpretación textual de la incertidumbre."""
        if score < 0.2:
            return "Lenguaje muy confiado y directo. Poca evidencia de duda o evasión."
        elif score < 0.4:
            return "Lenguaje generalmente confiado con algunos matices de cautela."
        elif score < 0.6:
            return "Nivel moderado de incertidumbre. Presencia notable de lenguaje cauteloso."
        elif score < 0.8:
            return "Alta incertidumbre. Uso frecuente de lenguaje evasivo y de duda."
        else:
            return "Incertidumbre muy alta. Lenguaje predominantemente evasivo y cauteloso."
    
    def _get_frequent_uncertainty_words(self, words: List[str]) -> List[Dict]:
        """Identifica las palabras de incertidumbre más frecuentes."""
        uncertainty_words_found = [word for word in words if word in self.uncertainty_words]
        word_counts = Counter(uncertainty_words_found)
        
        # Retornar top 5
        top_words = word_counts.most_common(5)
        
        return [
            {"word": word, "count": count}
            for word, count in top_words
        ]
    
    def analyze_qa_uncertainty(self, qa_session: Dict) -> Dict:
        """
        Analiza la incertidumbre específicamente en la sesión Q&A.
        Esta es la sección más importante para detectar evasión.
        
        Args:
            qa_session: Datos de la sesión Q&A
        
        Returns:
            Análisis de incertidumbre del Q&A
        """
        qa_text = qa_session.get("text", "")
        
        # Análisis general
        uncertainty_analysis = self.analyze_uncertainty(qa_text)
        
        # Análisis por segmentos de hablante (si están disponibles)
        speaker_segments = qa_session.get("speaker_segments", [])
        speaker_uncertainty = {}
        
        for segment in speaker_segments:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")
            
            if text and speaker not in ["OPERATOR", "MODERATOR", "HOST"]:
                speaker_analysis = self.analyze_uncertainty(text)
                speaker_uncertainty[speaker] = speaker_analysis
        
        # Identificar ejecutivos vs analistas
        executive_uncertainty = {}
        analyst_questions = 0
        
        for speaker, analysis in speaker_uncertainty.items():
            if any(role in speaker.upper() for role in ["CEO", "CFO", "CTO", "PRESIDENT", "DIRECTOR"]):
                executive_uncertainty[speaker] = analysis
            elif "ANALYST" in speaker.upper():
                analyst_questions += 1
        
        return {
            "overall_uncertainty": uncertainty_analysis,
            "speaker_uncertainty": speaker_uncertainty,
            "executive_uncertainty": executive_uncertainty,
            "analyst_question_count": analyst_questions,
            "executive_uncertainty_avg": self._average_executive_uncertainty(executive_uncertainty),
            "interpretation": self._interpret_qa_uncertainty(uncertainty_analysis, executive_uncertainty)
        }
    
    def _average_executive_uncertainty(self, executive_uncertainty: Dict) -> Dict:
        """Calcula el promedio de incertidumbre de ejecutivos."""
        if not executive_uncertainty:
            return {
                "uncertainty_score": 0.0,
                "uncertainty_level": "N/A",
                "executives_analyzed": 0
            }
        
        total_score = sum(analysis["uncertainty_score"] for analysis in executive_uncertainty.values())
        avg_score = total_score / len(executive_uncertainty)
        
        return {
            "uncertainty_score": avg_score,
            "uncertainty_level": self._interpret_uncertainty_level(avg_score),
            "executives_analyzed": len(executive_uncertainty)
        }
    
    def _interpret_qa_uncertainty(self, overall: Dict, executive: Dict) -> str:
        """Interpreta la incertidumbre en el contexto del Q&A."""
        overall_score = overall["uncertainty_score"]
        
        if not executive:
            return f"Nivel general de incertidumbre: {overall['uncertainty_level']}. No se pudo analizar por ejecutivos."
        
        exec_score = executive.get("uncertainty_score", 0)
        
        if overall_score > 0.6 and exec_score > 0.6:
            return "ALERTA: Ejecutivos muestran alta incertidumbre en el Q&A. Posibles problemas operativos no revelados."
        elif overall_score > 0.4 and exec_score > 0.4:
            return "Incertidumbre moderada en respuestas de ejecutivos. Requiere monitoreo."
        elif overall_score < 0.3 and exec_score < 0.3:
            return "Ejecutivos responden con confianza. Baja evasión detectada."
        else:
            return f"Incertidumbre mixta. General: {overall['uncertainty_level']}, Ejecutivos: {self._interpret_uncertainty_level(exec_score)}"
    
    def analyze_transcript_uncertainty(self, analyzed_transcript: Dict) -> Dict:
        """
        Analiza la incertidumbre de una transcripción completa.
        
        Args:
            analyzed_transcript: Transcripción con análisis de sentimiento
        
        Returns:
            Transcripción con análisis de incertidumbre añadido
        """
        result = analyzed_transcript.copy()
        
        # Analizar incertidumbre en Q&A (sección crítica)
        qa_uncertainty = self.analyze_qa_uncertainty(result["qa_session"])
        result["qa_session"]["uncertainty"] = qa_uncertainty
        
        # Analizar incertidumbre en Prepared Remarks (para comparación)
        prepared_text = result["prepared_remarks"]["text"]
        prepared_uncertainty = self.analyze_uncertainty(prepared_text)
        result["prepared_remarks"]["uncertainty"] = prepared_uncertainty
        
        # Calcular diferencial de incertidumbre
        uncertainty_gap = qa_uncertainty["overall_uncertainty"]["uncertainty_score"] - prepared_uncertainty["uncertainty_score"]
        
        result["uncertainty_analysis"] = {
            "prepared_uncertainty_score": prepared_uncertainty["uncertainty_score"],
            "qa_uncertainty_score": qa_uncertainty["overall_uncertainty"]["uncertainty_score"],
            "uncertainty_gap": uncertainty_gap,
            "gap_interpretation": self._interpret_uncertainty_gap(uncertainty_gap),
            "executive_uncertainty": qa_uncertainty.get("executive_uncertainty_avg", {})
        }
        
        return result
    
    def _interpret_uncertainty_gap(self, gap: float) -> str:
        """Interpreta el diferencial de incertidumbre entre secciones."""
        if gap > 0.3:
            return "Q&A significativamente más evasivo que Prepared Remarks (ALERTA)"
        elif gap > 0.1:
            return "Q&A ligeramente más evasivo que Prepared Remarks"
        elif gap > -0.1:
            return "Nivel de incertidumbre similar entre secciones"
        elif gap > -0.3:
            return "Prepared Remarks ligeramente más evasivo que Q&A"
        else:
            return "Prepared Remarks significativamente más evasivo que Q&A (inusual)"


if __name__ == "__main__":
    # Ejemplo de uso
    print("Probando UncertaintyAnalyzer...")
    
    # Cargar transcripción analizada
    import json
    with open("data/segmented/AAPL_2024_Q1_analyzed.json", "r", encoding="utf-8") as f:
        analyzed = json.load(f)
    
    # Crear analizador
    uncertainty_analyzer = UncertaintyAnalyzer()
    
    # Analizar incertidumbre
    print("\nAnalizando incertidumbre en transcripción...")
    with_uncertainty = uncertainty_analyzer.analyze_transcript_uncertainty(analyzed)
    
    # Mostrar resultados
    print(f"\n--- Resultados de Análisis de Incertidumbre ---")
    print(f"Empresa: {with_uncertainty['metadata']['company']}")
    
    print(f"\nPrepared Remarks:")
    print(f"  Score incertidumbre: {with_uncertainty['prepared_remarks']['uncertainty']['uncertainty_score']:.3f}")
    print(f"  Nivel: {with_uncertainty['prepared_remarks']['uncertainty']['uncertainty_level']}")
    print(f"  Palabras de incertidumbre: {with_uncertainty['prepared_remarks']['uncertainty']['uncertainty_word_count']}")
    
    print(f"\nQ&A Session:")
    print(f"  Score incertidumbre: {with_uncertainty['qa_session']['uncertainty']['overall_uncertainty']['uncertainty_score']:.3f}")
    print(f"  Nivel: {with_uncertainty['qa_session']['uncertainty']['overall_uncertainty']['uncertainty_level']}")
    print(f"  Palabras de incertidumbre: {with_uncertainty['qa_session']['uncertainty']['overall_uncertainty']['uncertainty_word_count']}")
    
    print(f"\nAnálisis Comparativo:")
    print(f"  Gap: {with_uncertainty['uncertainty_analysis']['uncertainty_gap']:.3f}")
    print(f"  Interpretación: {with_uncertainty['uncertainty_analysis']['gap_interpretation']}")
    
    print(f"\nIncertidumbre de Ejecutivos:")
    exec_unc = with_uncertainty['uncertainty_analysis']['executive_uncertainty']
    print(f"  Score promedio: {exec_unc.get('uncertainty_score', 0):.3f}")
    print(f"  Nivel: {exec_unc.get('uncertainty_level', 'N/A')}")
    print(f"  Ejecutivos analizados: {exec_unc.get('executives_analyzed', 0)}")
    
    # Mostrar palabras frecuentes
    print(f"\nPalabras de incertidumbre más frecuentes (Q&A):")
    for word_info in with_uncertainty['qa_session']['uncertainty']['overall_uncertainty']['frequent_uncertainty_words']:
        print(f"  - {word_info['word']}: {word_info['count']} veces")
    
    # Guardar resultado
    with open("data/segmented/AAPL_2024_Q1_final.json", "w", encoding="utf-8") as f:
        json.dump(with_uncertainty, f, ensure_ascii=False, indent=2)
    
    print(f"\nTranscripción completa guardada en: data/segmented/AAPL_2024_Q1_final.json")
