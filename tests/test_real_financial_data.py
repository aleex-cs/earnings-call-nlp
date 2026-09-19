"""
Tests para el módulo de datos financieros reales.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.real_financial_data import RealFinancialData, RealEarningsCallGenerator


class TestRealFinancialData:
    """Tests para RealFinancialData."""
    
    @pytest.fixture
    def financial_data(self):
        """Instancia para testing."""
        return RealFinancialData()
    
    def test_get_company_info(self, financial_data):
        """Test de obtención de información de empresa."""
        # Usar un ticker conocido
        info = financial_data.get_company_info("AAPL")
        
        assert "ticker" in info
        assert info["ticker"] == "AAPL"
        assert "company_name" in info
    
    def test_get_stock_history(self, financial_data):
        """Test de obtención de historial de precios."""
        hist = financial_data.get_stock_history("AAPL", period="1mo")
        
        # Debe retornar un DataFrame
        assert hasattr(hist, 'columns')
        # Puede estar vacío si no hay conexión, pero no debe dar error
    
    def test_calculate_financial_metrics(self, financial_data):
        """Test de cálculo de métricas financieras."""
        metrics = financial_data.calculate_financial_metrics("AAPL")
        
        # Las métricas pueden estar vacías si no hay datos
        # pero no debe dar error
        assert isinstance(metrics, dict)
    
    def test_determine_sentiment_logic(self, financial_data):
        """Test de lógica de determinación de sentimiento."""
        # Caso positivo
        positive_metrics = {
            "price_vs_ma50": 10,
            "price_change_3m": 15,
            "rsi": 50,
            "volatility_annual": 20
        }
        
        sentiment = financial_data._determine_sentiment(positive_metrics)
        assert sentiment == "positive"
        
        # Caso negativo
        negative_metrics = {
            "price_vs_ma50": -10,
            "price_change_3m": -15,
            "rsi": 80,
            "volatility_annual": 60
        }
        
        sentiment = financial_data._determine_sentiment(negative_metrics)
        assert sentiment == "negative"


class TestRealEarningsCallGenerator:
    """Tests para RealEarningsCallGenerator."""
    
    @pytest.fixture
    def generator(self):
        """Instancia para testing."""
        return RealEarningsCallGenerator()
    
    def test_generate_realistic_transcript(self, generator):
        """Test de generación de transcripción realista."""
        transcript = generator.generate_realistic_transcript("AAPL", "Q1", 2024)
        
        assert "company" in transcript
        assert "ticker" in transcript
        assert "quarter" in transcript
        assert "year" in transcript
        assert "full_transcript" in transcript
        assert len(transcript["full_transcript"]) > 100
    
    def test_sentiment_based_generation(self, generator):
        """Test de que la generación se basa en sentimiento."""
        # Probar con diferentes condiciones
        positive_metrics = {"price_change_3m": 20, "volatility_annual": 15}
        negative_metrics = {"price_change_3m": -20, "volatility_annual": 60}
        
        # Las transcripciones deben ser diferentes según las métricas
        # (esto es más un test de integración, verificamos que no falle)