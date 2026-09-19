"""
Tests para el módulo de segmentación de transcripciones.
"""

import pytest
import sys
import os

# Añadir el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.segmenter import TranscriptSegmenter


class TestTranscriptSegmenter:
    """Tests para TranscriptSegmenter."""
    
    @pytest.fixture
    def sample_transcript(self):
        """Transcripción de ejemplo para testing."""
        return {
            "company": "Test Company",
            "ticker": "TEST",
            "date": "2024-01-31",
            "quarter": "Q1",
            "year": 2024,
            "full_transcript": """
            OPERATOR: Welcome to the earnings call.
            
            PREPARED REMARKS:
            We had a great quarter with strong revenue growth.
            
            Q&A SESSION:
            Analyst: Can you elaborate on the growth?
            CEO: Yes, we saw strong demand across all segments.
            """
        }
    
    @pytest.fixture
    def segmenter(self):
        """Instancia del segmenter para testing."""
        return TranscriptSegmenter()
    
    def test_segment_transcript_basic(self, segmenter, sample_transcript):
        """Test básico de segmentación."""
        result = segmenter.segment_transcript(sample_transcript)
        
        assert "metadata" in result
        assert "prepared_remarks" in result
        assert "qa_session" in result
        assert result["metadata"]["company"] == "Test Company"
    
    def test_segmentation_confidence(self, segmenter, sample_transcript):
        """Test del cálculo de confianza de segmentación."""
        result = segmenter.segment_transcript(sample_transcript)
        
        assert "segmentation_confidence" in result
        assert 0 <= result["segmentation_confidence"] <= 1
    
    def test_speaker_extraction(self, segmenter, sample_transcript):
        """Test de extracción de hablantes."""
        result = segmenter.segment_transcript(sample_transcript)
        
        assert "speakers" in result
        assert isinstance(result["speakers"], list)
    
    def test_empty_transcript(self, segmenter):
        """Test con transcripción vacía."""
        empty_transcript = {
            "company": "Test",
            "ticker": "TEST",
            "date": "2024-01-31",
            "quarter": "Q1",
            "year": 2024,
            "full_transcript": ""
        }
        
        result = segmenter.segment_transcript(empty_transcript)
        
        # Debe manejar gracefully
        assert "prepared_remarks" in result
        assert "qa_session" in result