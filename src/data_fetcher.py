"""
Módulo para obtener transcripciones de earnings calls.
Soporta múltiples fuentes de datos.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from typing import Dict, List, Optional
from abc import ABC, abstractmethod
import pandas as pd


class TranscriptSource(ABC):
    """Clase base abstracta para fuentes de transcripciones."""
    
    @abstractmethod
    def get_transcript(self, ticker: str, quarter: str, year: int) -> Optional[Dict]:
        """Obtiene una transcripción específica."""
        pass
    
    @abstractmethod
    def list_available_transcripts(self, ticker: str) -> List[Dict]:
        """Lista transcripciones disponibles para un ticker."""
        pass


class MockTranscriptSource(TranscriptSource):
    """Fuente de datos mock para desarrollo y pruebas."""
    
    def __init__(self):
        self.mock_data = self._generate_mock_data()
    
    def _generate_mock_data(self) -> Dict:
        """Genera datos de ejemplo para testing."""
        return {
            "AAPL": {
                "2024-Q1": {
                    "company": "Apple Inc.",
                    "date": "2024-01-31",
                    "ticker": "AAPL",
                    "quarter": "Q1",
                    "year": 2024,
                    "full_transcript": """
                    OPERATOR: Good day, ladies and gentlemen, and welcome to the Apple Inc. First Quarter Fiscal Year 2024 Earnings Conference Call. At this time, all participants are in a listen-only mode. After the presentation, we will conduct a question-and-answer session.
                    
                    PREPARED REMARKS:
                    Thank you for joining us today. We had a fantastic quarter with revenue of $119.6 billion, up 2% year over year. Our active device installed base reached over 2.2 billion, hitting an all-time high. Services revenue reached an all-time high of $23.3 billion, up 11% year over year.
                    
                    Our iPhone business performed exceptionally well with revenue of $69.7 billion. We continue to see strong customer satisfaction and loyalty. The iPhone 15 lineup has been incredibly popular with customers around the world.
                    
                    Looking ahead, we remain confident in our ability to drive growth through innovation and customer experience. We are excited about our product pipeline and the opportunities ahead.
                    
                    Q&A SESSION:
                    Analyst: Can you talk about the outlook for iPhone demand in the current quarter?
                    
                    CEO: We're seeing strong demand across all regions. However, we are cautious about the macroeconomic environment in certain markets. It's difficult to predict exactly how this will impact consumer spending, but we remain optimistic about our product portfolio.
                    
                    Analyst: What about the supply chain situation?
                    
                    CFO: We have made significant progress in resolving supply chain constraints. While there are still some challenges, we believe the worst is behind us. We expect supply to improve throughout the year, though we remain cautious about potential disruptions.
                    
                    Analyst: Can you provide more color on Services growth?
                    
                    CEO: Services continues to be a key growth driver. We're seeing strong adoption across our subscription offerings. The ecosystem is becoming more powerful, and customers are engaging more deeply with our services. We expect this trend to continue.
                    """
                },
                "2024-Q2": {
                    "company": "Apple Inc.",
                    "date": "2024-04-30",
                    "ticker": "AAPL",
                    "quarter": "Q2",
                    "year": 2024,
                    "full_transcript": """
                    OPERATOR: Welcome to Apple's Second Quarter Fiscal Year 2024 Earnings Conference Call.
                    
                    PREPARED REMARKS:
                    We reported revenue of $90.8 billion, down 4% year over year. Despite the challenging macroeconomic environment, our business remains resilient. Services revenue grew to $22.3 billion, up 8% year over year, reaching a new all-time high.
                    
                    iPhone revenue was $45.9 billion, down 10% year over year. We continue to believe in the long-term strength of our business and our ability to innovate through cycles.
                    
                    Our ecosystem continues to grow, with over 2.2 billion active devices. Customer satisfaction remains incredibly high across all our product categories.
                    
                    Q&A SESSION:
                    Analyst: The iPhone decline seems steeper than expected. What's driving this?
                    
                    CEO: We're seeing softer demand in certain emerging markets and some macroeconomic headwinds. While we're disappointed with the decline, we remain confident in our product strategy. The new features we're introducing should drive upgrades in the coming quarters.
                    
                    Analyst: Are you seeing any impact from competition?
                    
                    CFO: Competition has always been intense in our industry. We focus on innovation and customer experience rather than competitor moves. Our customer loyalty metrics remain strong, and we continue to win market share in premium segments.
                    
                    Analyst: What's your view on the economic outlook?
                    
                    CEO: The macroeconomic environment remains uncertain. We're seeing varying conditions across different regions. It's hard to make precise predictions, but we're prepared to navigate through the volatility. Our strong balance sheet gives us flexibility.
                    """
                }
            },
            "MSFT": {
                "2024-Q1": {
                    "company": "Microsoft Corporation",
                    "date": "2024-01-30",
                    "ticker": "MSFT",
                    "quarter": "Q1",
                    "year": 2024,
                    "full_transcript": """
                    OPERATOR: Welcome to Microsoft's First Quarter Fiscal Year 2024 Earnings Conference Call.
                    
                    PREPARED REMARKS:
                    We had an outstanding start to the fiscal year with revenue of $62.0 billion, up 18% year over year. Cloud revenue was $35.1 billion, up 24% year over year, reaching $33.4 billion in Azure revenue.
                    
                    Our AI investments are driving growth across our business. Copilot has been adopted by over 40% of the Fortune 500. We're seeing strong momentum in our AI-powered offerings.
                    
                    LinkedIn revenue grew 9% year over year. Gaming revenue increased, driven by Xbox Game Pass growth and content acquisitions.
                    
                    Q&A SESSION:
                    Analyst: How sustainable is the current Azure growth rate?
                    
                    CEO: We believe the growth is sustainable given the secular shift to cloud and AI adoption. While we expect some normalization, the long-term trend remains strong. Our differentiation in AI infrastructure is a significant competitive advantage.
                    
                    Analyst: What about the ROI on AI investments?
                    
                    CFO: We're seeing strong returns on our AI investments. Copilot adoption is exceeding expectations, and we're monetizing effectively. The payback period is reasonable, and we expect continued improvement as we scale.
                    
                    Analyst: Any concerns about AI infrastructure costs?
                    
                    CEO: AI infrastructure costs are significant, but we're managing them efficiently. We're investing in both internal capacity and partnerships. The economics are working well, and we expect continued optimization as technology advances.
                    """
                }
            }
        }
    
    def get_transcript(self, ticker: str, quarter: str, year: int) -> Optional[Dict]:
        """Obtiene una transcripción mock."""
        key = f"{year}-{quarter}"
        if ticker in self.mock_data and key in self.mock_data[ticker]:
            return self.mock_data[ticker][key]
        return None
    
    def list_available_transcripts(self, ticker: str) -> List[Dict]:
        """Lista transcripciones mock disponibles."""
        if ticker not in self.mock_data:
            return []
        
        transcripts = []
        for key, data in self.mock_data[ticker].items():
            transcripts.append({
                "ticker": ticker,
                "quarter": data["quarter"],
                "year": data["year"],
                "date": data["date"],
                "company": data["company"]
            })
        return transcripts


class FMPTranscriptSource(TranscriptSource):
    """Fuente de datos usando Financial Modeling Prep API."""
    
    def __init__(self, api_key: Optional[str] = None):
        # Cargar variables de entorno desde .env
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = api_key or os.getenv("FMP_API_KEY")
        self.base_url = "https://financialmodelingprep.com/api/v3"
        
        if not self.api_key:
            print("ADVERTENCIA: No se encontró FMP_API_KEY. Se usará modo mock.")
    
    def get_transcript(self, ticker: str, quarter: str, year: int) -> Optional[Dict]:
        """Obtiene transcripción de FMP API."""
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        # Usar el nuevo endpoint de FMP para earnings call transcripts
        url = f"{self.base_url}/earning_call_transcript/{ticker}"
        params = {
            "apikey": self.api_key,
            "year": year,
            "quarter": quarter.replace("Q", "")
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                return {
                    "company": data[0].get("company", ticker),
                    "date": data[0].get("date", ""),
                    "ticker": ticker,
                    "quarter": quarter,
                    "year": year,
                    "full_transcript": data[0].get("content", "")
                }
        except requests.RequestException as e:
            print(f"Error fetching transcript from FMP: {e}")
        
        return None
    
    def list_available_transcripts(self, ticker: str) -> List[Dict]:
        """Lista transcripciones disponibles en FMP."""
        if not self.api_key:
            raise ValueError("FMP API key is required")
        
        url = f"{self.base_url}/earning_call_transcript/{ticker}"
        params = {"apikey": self.api_key}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            transcripts = []
            for item in data:
                transcripts.append({
                    "ticker": ticker,
                    "quarter": f"Q{item.get('quarter', 1)}",
                    "year": item.get("year", 2024),
                    "date": item.get("date", ""),
                    "company": item.get("company", ticker)
                })
            return transcripts
        except requests.RequestException as e:
            print(f"Error listing transcripts from FMP: {e}")
            return []


class TranscriptFetcher:
    """Clase principal para obtener transcripciones."""
    
    def __init__(self, source: TranscriptSource):
        self.source = source
    
    def get_transcript(self, ticker: str, quarter: str, year: int) -> Optional[Dict]:
        """Obtiene una transcripción específica."""
        return self.source.get_transcript(ticker, quarter, year)
    
    def list_available(self, ticker: str) -> List[Dict]:
        """Lista transcripciones disponibles."""
        return self.source.list_available_transcripts(ticker)
    
    def save_transcript(self, transcript: Dict, output_dir: str = "data/transcripts") -> str:
        """Guarda una transcripción en disco."""
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{transcript['ticker']}_{transcript['year']}_Q{transcript['quarter'].replace('Q', '')}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def load_transcript(self, filepath: str) -> Dict:
        """Carga una transcripción desde disco."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


# Factory function para crear la fuente adecuada
def create_transcript_fetcher(source_type: str = "mock", **kwargs) -> TranscriptFetcher:
    """
    Crea un TranscriptFetcher con la fuente especificada.
    
    Args:
        source_type: "mock", "fmp", o futuras fuentes
        **kwargs: Argumentos específicos de la fuente (ej: api_key)
    
    Returns:
        TranscriptFetcher configurado
    """
    if source_type == "mock":
        source = MockTranscriptSource()
    elif source_type == "fmp":
        source = FMPTranscriptSource(api_key=kwargs.get("api_key"))
    else:
        raise ValueError(f"Unknown source type: {source_type}")
    
    return TranscriptFetcher(source)


if __name__ == "__main__":
    # Ejemplo de uso
    print("Probando TranscriptFetcher con datos mock...")
    
    # Crear fetcher con datos mock
    fetcher = create_transcript_fetcher("mock")
    
    # Listar transcripciones disponibles
    print("\nTranscripciones disponibles para AAPL:")
    transcripts = fetcher.list_available("AAPL")
    for t in transcripts:
        print(f"  - {t['year']} {t['quarter']}: {t['date']}")
    
    # Obtener una transcripción específica
    print("\nObteniendo transcripción AAPL 2024-Q1...")
    transcript = fetcher.get_transcript("AAPL", "Q1", 2024)
    
    if transcript:
        print(f"Empresa: {transcript['company']}")
        print(f"Fecha: {transcript['date']}")
        print(f"Longitud transcripción: {len(transcript['full_transcript'])} caracteres")
        
        # Guardar en disco
        filepath = fetcher.save_transcript(transcript)
        print(f"\nTranscripción guardada en: {filepath}")
    else:
        print("No se encontró la transcripción")
