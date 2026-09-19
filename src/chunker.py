"""
Módulo para tokenización y chunking de texto.
Prepara el texto para el análisis con FinBERT.
"""

import nltk
from typing import List, Dict, Optional
import re


class TextChunker:
    """Divide el texto en chunks apropiados para el modelo."""
    
    def __init__(self, max_chunk_length: int = 512, overlap: int = 50):
        """
        Inicializa el chunker.
        
        Args:
            max_chunk_length: Longitud máxima en tokens
            overlap: Número de tokens de solapamiento entre chunks
        """
        self.max_chunk_length = max_chunk_length
        self.overlap = overlap
        
        # Descargar recursos de NLTK si no están disponibles
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            print("Descargando recursos de NLTK...")
            nltk.download('punkt')
            nltk.download('punkt_tab')
    
    def chunk_by_sentences(self, text: str) -> List[str]:
        """
        Divide el texto en oraciones y agrupa en chunks.
        
        Este es el método recomendado para análisis de sentimiento
        porque preserva el contexto semántico.
        """
        # Dividir en oraciones
        sentences = nltk.sent_tokenize(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            # Estimar longitud en tokens (aproximación: 1 token ≈ 0.75 palabras)
            sentence_tokens = len(sentence.split()) * 4 // 3
            
            # Si la oración es más larga que el máximo, dividirla
            if sentence_tokens > self.max_chunk_length:
                # Guardar chunk actual si existe
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Dividir oración larga
                sub_chunks = self._split_long_sentence(sentence)
                chunks.extend(sub_chunks)
                continue
            
            # Si agregar la oración excede el límite
            if current_length + sentence_tokens > self.max_chunk_length:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                
                # Crear nuevo chunk con overlap
                current_chunk = self._create_overlap_chunk(current_chunk, sentence)
                current_length = sum(len(s.split()) * 4 // 3 for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_length += sentence_tokens
        
        # Agregar último chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def chunk_by_words(self, text: str, chunk_size: int = 128) -> List[str]:
        """
        Divide el texto en chunks de tamaño fijo de palabras.
        
        Útil cuando necesitas control exacto del tamaño,
        pero puede perder contexto semántico.
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - self.overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def chunk_by_paragraphs(self, text: str) -> List[str]:
        """
        Divide el texto por párrafos.
        
        Preserva unidades de pensamiento completas,
        pero los párrafos pueden tener tamaños muy variables.
        """
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                # Si el párrafo es muy largo, dividirlo
                if len(paragraph.split()) > self.max_chunk_length * 3 // 4:
                    sub_chunks = self.chunk_by_sentences(paragraph)
                    chunks.extend(sub_chunks)
                else:
                    chunks.append(paragraph)
        
        return chunks
    
    def _split_long_sentence(self, sentence: str) -> List[str]:
        """Divide una oración muy larga en partes más pequeñas."""
        words = sentence.split()
        chunks = []
        
        chunk_size = self.max_chunk_length * 3 // 4  # Aproximación de tokens a palabras
        
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def _create_overlap_chunk(self, previous_chunk: List[str], new_sentence: str) -> List[str]:
        """Crea un nuevo chunk con overlap del anterior."""
        if not previous_chunk:
            return [new_sentence]
        
        # Calcular cuántas oraciones mantener del chunk anterior
        overlap_tokens = self.overlap
        kept_sentences = []
        kept_length = 0
        
        # Tomar oraciones del final del chunk anterior hasta llenar el overlap
        for sentence in reversed(previous_chunk):
            sentence_tokens = len(sentence.split()) * 4 // 3
            if kept_length + sentence_tokens <= overlap_tokens:
                kept_sentences.insert(0, sentence)
                kept_length += sentence_tokens
            else:
                break
        
        kept_sentences.append(new_sentence)
        return kept_sentences

    @staticmethod
    def _keep_chunk(chunk: str) -> bool:
        try:
            from src.exhibit_cleaner import is_analyzable_chunk
            return is_analyzable_chunk(chunk)
        except Exception:
            return bool(chunk and chunk.strip())
    
    def chunk_transcript(self, segmented_transcript: Dict) -> Dict:
        """
        Aplica chunking a una transcripción segmentada completa.
        
        Args:
            segmented_transcript: Transcripción ya segmentada en Prepared Remarks y Q&A
        
        Returns:
            Transcripción con chunks añadidos
        """
        result = segmented_transcript.copy()
        
        # Chunk de Prepared Remarks
        prepared_text = segmented_transcript["prepared_remarks"]["text"]
        raw_prepared = self.chunk_by_sentences(prepared_text)
        prepared_chunks = [c for c in raw_prepared if self._keep_chunk(c)]
        if not prepared_chunks and raw_prepared:
            prepared_chunks = raw_prepared
        
        result["prepared_remarks"]["chunks"] = prepared_chunks
        result["prepared_remarks"]["chunk_count"] = len(prepared_chunks)
        
        # Chunk de Q&A Session
        qa_text = segmented_transcript["qa_session"]["text"]
        qa_chunks = self.chunk_by_sentences(qa_text)
        
        result["qa_session"]["chunks"] = qa_chunks
        result["qa_session"]["chunk_count"] = len(qa_chunks)
        
        return result
    
    def get_chunk_statistics(self, chunked_transcript: Dict) -> Dict:
        """Obtiene estadísticas sobre los chunks generados."""
        prepared_chunks = chunked_transcript["prepared_remarks"]["chunks"]
        qa_chunks = chunked_transcript["qa_session"]["chunks"]
        
        stats = {
            "prepared_remarks": {
                "total_chunks": len(prepared_chunks),
                "avg_chunk_length": sum(len(c.split()) for c in prepared_chunks) / len(prepared_chunks) if prepared_chunks else 0,
                "min_chunk_length": min(len(c.split()) for c in prepared_chunks) if prepared_chunks else 0,
                "max_chunk_length": max(len(c.split()) for c in prepared_chunks) if prepared_chunks else 0,
            },
            "qa_session": {
                "total_chunks": len(qa_chunks),
                "avg_chunk_length": sum(len(c.split()) for c in qa_chunks) / len(qa_chunks) if qa_chunks else 0,
                "min_chunk_length": min(len(c.split()) for c in qa_chunks) if qa_chunks else 0,
                "max_chunk_length": max(len(c.split()) for c in qa_chunks) if qa_chunks else 0,
            }
        }
        
        return stats


class Tokenizer:
    """Tokenizador básico para estimar conteo de tokens."""
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estima el número de tokens en un texto.
        
        Nota: Esta es una aproximación. Para un conteo exacto,
        usar el tokenizador del modelo específico.
        """
        # Aproximación conservadora: 1 token ≈ 0.75 palabras en inglés
        words = len(text.split())
        return int(words * 4 / 3)
    
    @staticmethod
    def estimate_chars_per_token() -> float:
        """Promedio de caracteres por token (aproximado)."""
        return 4.0  # Aproximadamente 4 caracteres por token


if __name__ == "__main__":
    # Ejemplo de uso
    print("Probando TextChunker...")
    
    # Cargar transcripción segmentada
    import json
    with open("data/segmented/AAPL_2024_Q1_segmented.json", "r", encoding="utf-8") as f:
        segmented = json.load(f)
    
    # Crear chunker
    chunker = TextChunker(max_chunk_length=512, overlap=50)
    
    # Aplicar chunking
    chunked = chunker.chunk_transcript(segmented)
    
    # Mostrar estadísticas
    stats = chunker.get_chunk_statistics(chunked)
    
    print(f"\n--- Estadísticas de Chunking ---")
    print(f"Prepared Remarks:")
    print(f"  Total chunks: {stats['prepared_remarks']['total_chunks']}")
    print(f"  Longitud promedio: {stats['prepared_remarks']['avg_chunk_length']:.1f} palabras")
    print(f"  Rango: {stats['prepared_remarks']['min_chunk_length']} - {stats['prepared_remarks']['max_chunk_length']} palabras")
    
    print(f"\nQ&A Session:")
    print(f"  Total chunks: {stats['qa_session']['total_chunks']}")
    print(f"  Longitud promedio: {stats['qa_session']['avg_chunk_length']:.1f} palabras")
    print(f"  Rango: {stats['qa_session']['min_chunk_length']} - {stats['qa_session']['max_chunk_length']} palabras")
    
    # Mostrar ejemplos de chunks
    print(f"\n--- Ejemplo de Chunk (Prepared Remarks #1) ---")
    if chunked["prepared_remarks"]["chunks"]:
        print(chunked["prepared_remarks"]["chunks"][0][:200] + "...")
    
    print(f"\n--- Ejemplo de Chunk (Q&A Session #1) ---")
    if chunked["qa_session"]["chunks"]:
        print(chunked["qa_session"]["chunks"][0][:200] + "...")
    
    # Guardar resultado
    with open("data/segmented/AAPL_2024_Q1_chunked.json", "w", encoding="utf-8") as f:
        json.dump(chunked, f, ensure_ascii=False, indent=2)
    
    print(f"\nTranscripción con chunks guardada en: data/segmented/AAPL_2024_Q1_chunked.json")
