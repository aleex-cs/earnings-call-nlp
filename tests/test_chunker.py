"""
Tests para el módulo de chunking de texto.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.chunker import TextChunker


class TestTextChunker:
    """Tests para TextChunker."""
    
    @pytest.fixture
    def chunker(self):
        """Instancia del chunker para testing."""
        return TextChunker(max_chunk_length=512, overlap=50)
    
    def test_chunk_by_sentences_basic(self, chunker):
        """Test básico de chunking por oraciones."""
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = chunker.chunk_by_sentences(text)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
    
    def test_chunk_by_words(self, chunker):
        """Test de chunking por palabras."""
        text = "word " * 200  # 200 palabras
        chunks = chunker.chunk_by_words(text, chunk_size=50)
        
        assert len(chunks) > 0
        # Debe haber chunks divididos
        assert len(chunks) >= 4
    
    def test_chunk_by_paragraphs(self, chunker):
        """Test de chunking por párrafos."""
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunker.chunk_by_paragraphs(text)
        
        assert len(chunks) >= 3
    
    def test_empty_text(self, chunker):
        """Test con texto vacío."""
        chunks = chunker.chunk_by_sentences("")
        
        assert len(chunks) == 0
    
    def test_chunk_statistics(self, chunker):
        """Test de cálculo de estadísticas."""
        text = "This is a test. " * 10
        chunks = chunker.chunk_by_sentences(text)
        
        stats = chunker.get_chunk_statistics({"prepared_remarks": {"chunks": chunks}})
        
        assert "prepared_remarks" in stats
        assert "total_chunks" in stats["prepared_remarks"]
        assert "avg_chunk_length" in stats["prepared_remarks"]