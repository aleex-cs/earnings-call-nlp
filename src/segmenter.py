"""
Módulo para segmentar transcripciones de earnings calls.
Divide el texto en Prepared Remarks y Q&A Session.
"""

import re
from typing import Dict, Tuple, Optional
import json


class TranscriptSegmenter:
    """Segmenta transcripciones en secciones clave."""
    
    def __init__(self):
        # Patrones comunes para identificar secciones
        self.prepared_remarks_patterns = [
            r"PREPARED REMARKS:",
            r"OPERATOR.*?PREPARED REMARKS:",
            r"PRESENTATION:",
            r"MANAGEMENT DISCUSSION:",
            r"CEO REMARKS:",
            r"OPENING REMARKS:"
        ]
        
        self.qa_patterns = [
            r"Q&A SESSION:",
            r"QUESTION AND ANSWER:",
            r"Q&A:",
            r"QUESTIONS AND ANSWERS:",
            r"ANALYST QUESTIONS:",
            r"CALL FOR QUESTIONS:"
        ]
        
        self.operator_patterns = [
            r"OPERATOR:",
            r"MODERATOR:",
            r"HOST:"
        ]
    
    def segment_transcript(self, transcript: Dict) -> Dict:
        """
        Segmenta una transcripción completa en secciones.
        
        Args:
            transcript: Diccionario con la transcripción completa
        
        Returns:
            Diccionario con las secciones segmentadas
        """
        full_text = transcript["full_transcript"]
        
        # Identificar secciones
        prepared_remarks, qa_session = self._split_sections(full_text)
        
        # Extraer metadatos adicionales
        speakers = self._extract_speakers(full_text)
        
        return {
            "metadata": {
                "company": transcript.get("company", ""),
                "ticker": transcript.get("ticker", ""),
                "date": transcript.get("date", ""),
                "quarter": transcript.get("quarter", ""),
                "year": transcript.get("year", "")
            },
            "prepared_remarks": {
                "text": prepared_remarks,
                "word_count": len(prepared_remarks.split()),
                "speaker_segments": self._extract_speaker_segments(prepared_remarks)
            },
            "qa_session": {
                "text": qa_session,
                "word_count": len(qa_session.split()),
                "speaker_segments": self._extract_speaker_segments(qa_session),
                "question_count": self._count_questions(qa_session)
            },
            "speakers": speakers,
            "segmentation_confidence": self._calculate_confidence(full_text, prepared_remarks, qa_session)
        }
    
    def _split_sections(self, text: str) -> Tuple[str, str]:
        """
        Divide el texto en Prepared Remarks y Q&A Session.
        
        Returns:
            Tuple (prepared_remarks, qa_session)
        """
        # Primero, intentar encontrar el patrón de Q&A
        qa_start = None
        for pattern in self.qa_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                qa_start = match.start()
                break
        
        if qa_start is None:
            # Si no se encuentra Q&A, intentar heurísticas
            return self._fallback_split(text)
        
        # El texto antes de Q&A son los Prepared Remarks
        prepared_remarks = text[:qa_start].strip()
        qa_session = text[qa_start:].strip()
        
        # Limpiar la etiqueta de Q&A del texto
        for pattern in self.qa_patterns:
            qa_session = re.sub(pattern, "", qa_session, flags=re.IGNORECASE).strip()
        
        # Limpiar etiquetas de Prepared Remarks si existen
        for pattern in self.prepared_remarks_patterns:
            prepared_remarks = re.sub(pattern, "", prepared_remarks, flags=re.IGNORECASE).strip()
        
        return prepared_remarks, qa_session
    
    def _fallback_split(self, text: str) -> Tuple[str, str]:
        """
        Método fallback cuando no se puede identificar Q&A claramente.
        Usa heurísticas para dividir el texto.
        """
        # Si no se puede segmentar, todo va a prepared_remarks
        # y qa_session queda vacío
        return text, ""
    
    def _extract_speakers(self, text: str) -> list:
        """Extrae los hablantes de la transcripción."""
        # Patrón para identificar líneas de hablante
        speaker_pattern = r"([A-Z][A-Z\s]+):"
        
        speakers = set()
        matches = re.finditer(speaker_pattern, text)
        
        for match in matches:
            speaker = match.group(1).strip()
            # Filtrar palabras comunes que no son hablantes
            if len(speaker) > 2 and speaker not in ["OPERATOR", "MODERATOR", "HOST"]:
                speakers.add(speaker)
        
        return sorted(list(speakers))
    
    def _extract_speaker_segments(self, text: str) -> list:
        """Extrae segmentos por hablante."""
        speaker_pattern = r"([A-Z][A-Z\s]+):"
        
        segments = []
        current_speaker = None
        current_text = []
        
        lines = text.split('\n')
        for line in lines:
            match = re.match(speaker_pattern, line)
            if match:
                # Guardar segmento anterior si existe
                if current_speaker and current_text:
                    segments.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_text).strip()
                    })
                
                # Iniciar nuevo segmento
                current_speaker = match.group(1).strip()
                current_text = [line.replace(match.group(0), "").strip()]
            else:
                if current_speaker:
                    current_text.append(line.strip())
        
        # Guardar último segmento
        if current_speaker and current_text:
            segments.append({
                "speaker": current_speaker,
                "text": " ".join(current_text).strip()
            })
        
        return segments
    
    def _count_questions(self, qa_text: str) -> int:
        """Cuenta el número de preguntas en la sesión Q&A."""
        # Contar signos de interrogación
        question_marks = qa_text.count("?")
        
        # Contar palabras que indican preguntas
        question_words = ["what", "how", "why", "when", "where", "which", "who", "can", "could", "would", "will"]
        question_word_count = sum(1 for word in qa_text.lower().split() if word in question_words)
        
        # Usar el máximo de ambos métodos
        return max(question_marks, question_word_count)
    
    def _calculate_confidence(self, full_text: str, prepared: str, qa: str) -> float:
        """
        Calcula la confianza en la segmentación.
        
        Returns:
            Float entre 0 y 1
        """
        confidence = 0.0
        
        # Si ambas secciones tienen contenido
        if prepared and qa:
            confidence += 0.5
        
        # Si el texto de Q&A tiene patrones de preguntas
        if qa and ("?" in qa or "question" in qa.lower()):
            confidence += 0.3
        
        # Si se encontraron patrones de Q&A explícitos
        for pattern in self.qa_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                confidence += 0.2
                break
        
        return min(confidence, 1.0)
    
    def save_segmented(self, segmented: Dict, output_dir: str = "data/segmented") -> str:
        """Guarda la transcripción segmentada."""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        ticker = segmented["metadata"]["ticker"]
        year = segmented["metadata"]["year"]
        quarter = segmented["metadata"]["quarter"]
        
        filename = f"{ticker}_{year}_Q{quarter.replace('Q', '')}_segmented.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(segmented, f, ensure_ascii=False, indent=2)
        
        return filepath


if __name__ == "__main__":
    # Ejemplo de uso
    print("Probando TranscriptSegmenter...")
    
    # Cargar una transcripción existente
    with open("data/transcripts/AAPL_2024_Q1.json", "r", encoding="utf-8") as f:
        transcript = json.load(f)
    
    # Segmentar
    segmenter = TranscriptSegmenter()
    segmented = segmenter.segment_transcript(transcript)
    
    # Mostrar resultados
    print(f"\nEmpresa: {segmented['metadata']['company']}")
    print(f"Fecha: {segmented['metadata']['date']}")
    print(f"\nPrepared Remarks: {segmented['prepared_remarks']['word_count']} palabras")
    print(f"Q&A Session: {segmented['qa_session']['word_count']} palabras")
    print(f"Número de preguntas: {segmented['qa_session']['question_count']}")
    print(f"Confianza de segmentación: {segmented['segmentation_confidence']:.2f}")
    
    print(f"\nHablantes identificados: {segmented['speakers']}")
    
    # Guardar resultado
    filepath = segmenter.save_segmented(segmented)
    print(f"\nTranscripción segmentada guardada en: {filepath}")
    
    # Mostrar muestra de cada sección
    print("\n--- Muestra de Prepared Remarks ---")
    print(segmented['prepared_remarks']['text'][:200] + "...")
    
    print("\n--- Muestra de Q&A Session ---")
    print(segmented['qa_session']['text'][:200] + "...")
