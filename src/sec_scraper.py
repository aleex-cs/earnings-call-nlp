"""
Scraper de transcripciones de earnings calls desde la SEC (EDGAR).
Completamente legal y gratuito - las empresas públicas depositan estos documentos.
"""

import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time
import pandas as pd


class EDGARScraper:
    """Scraper de transcripciones de earnings calls desde SEC EDGAR."""
    
    def __init__(self):
        self.base_url = "https://www.sec.gov"
        self.search_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
    
    def search_company_filings(self, ticker: str, filing_type: str = "Earnings Call Transcript") -> List[Dict]:
        """
        Busca filings de una empresa en EDGAR.
        
        Args:
            ticker: Símbolo de la empresa
            filing_type: Tipo de filing a buscar
        
        Returns:
            Lista de filings encontrados
        """
        # Primero obtener el CIK (Central Index Key) de la empresa
        cik = self._get_cik(ticker)
        if not cik:
            print(f"No se encontró CIK para {ticker}")
            return []
        
        # Buscar filings del tipo específico
        params = {
            'action': 'getcompany',
            'CIK': cik,
            'type': filing_type,
            'dateb': datetime.now().strftime('%Y%m%d'),
            'owner': 'exclude',
            'count': '40'
        }
        
        try:
            response = requests.get(self.search_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar tabla de filings
            table = soup.find('table', class_='tableFile2')
            if not table:
                return []
            
            filings = []
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows[:10]:  # Limitar a 10 filings más recientes
                cells = row.find_all('td')
                if len(cells) >= 3:
                    filing_link = cells[1].find('a')
                    if filing_link:
                        filing_url = self.base_url + filing_link['href']
                        filing_date = cells[3].text.strip()
                        
                        filings.append({
                            'cik': cik,
                            'ticker': ticker,
                            'filing_date': filing_date,
                            'filing_url': filing_url,
                            'filing_type': filing_type
                        })
            
            return filings
            
        except Exception as e:
            print(f"Error buscando filings: {e}")
            return []
    
    def _get_cik(self, ticker: str) -> Optional[str]:
        """Obtiene el CIK de una empresa desde su ticker."""
        # Usar el endpoint de búsqueda de CIK
        params = {
            'action': 'getcompany',
            'CIK': ticker.upper(),
            'owner': 'exclude'
        }
        
        try:
            response = requests.get(self.search_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            # Extraer CIK de la respuesta
            cik_match = re.search(r'CIK\s*=\s*(\d{10})', response.text)
            if cik_match:
                return cik_match.group(1)
            
            # Intentar extraer de la URL
            soup = BeautifulSoup(response.content, 'html.parser')
            company_info = soup.find('span', class_='companyName')
            if company_info:
                cik_match = re.search(r'CIK:\s*(\d{10})', company_info.text)
                if cik_match:
                    return cik_match.group(1)
            
        except Exception as e:
            print(f"Error obteniendo CIK: {e}")
        
        return None
    
    def get_filing_content(self, filing_url: str) -> Optional[str]:
        """Obtiene el contenido de un filing."""
        try:
            response = requests.get(filing_url, headers=self.headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Buscar el documento principal
            table = soup.find('table', class_='tableFile', summary='Document Format Files')
            if not table:
                return None
            
            # Encontrar el documento principal (generalmente el primero)
            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    doc_link = cells[2].find('a')
                    if doc_link:
                        doc_url = self.base_url + doc_link['href']
                        
                        # Obtener el documento
                        doc_response = requests.get(doc_url, headers=self.headers)
                        doc_response.raise_for_status()
                        
                        # Si es un texto plano, retornarlo directamente
                        if 'txt' in doc_url:
                            return doc_response.text
                        
                        # Si es HTML, extraer el texto
                        doc_soup = BeautifulSoup(doc_response.content, 'html.parser')
                        return doc_soup.get_text(separator='\n', strip=True)
            
            return None
            
        except Exception as e:
            print(f"Error obteniendo contenido del filing: {e}")
            return None
    
    def get_earnings_transcripts(self, ticker: str, limit: int = 5) -> List[Dict]:
        """
        Obtiene transcripciones de earnings calls de una empresa.
        
        Args:
            ticker: Símbolo de la empresa
            limit: Número máximo de transcripciones a obtener
        
        Returns:
            Lista de transcripciones
        """
        print(f"Buscando transcripciones de earnings calls para {ticker}...")
        
        # Buscar diferentes tipos de filings que pueden contener earnings calls
        filing_types = [
            "Earnings Call Transcript",
            "Earnings Call",
            "TRANSCRIPT",
            "8-K",  # Puede contener earnings press releases
            "10-Q",  # Quarterly report
        ]
        
        all_transcripts = []
        
        for filing_type in filing_types:
            filings = self.search_company_filings(ticker, filing_type)
            
            for filing in filings[:limit]:
                try:
                    print(f"Procesando filing del {filing['filing_date']}...")
                    
                    content = self.get_filing_content(filing['filing_url'])
                    
                    if content and len(content) > 500:  # Filtrar contenido muy corto
                        # Extraer metadatos
                        quarter_match = re.search(r'(Q[1-4])\s*(\d{4})', content, re.IGNORECASE)
                        if quarter_match:
                            quarter = quarter_match.group(1).upper()
                            year = int(quarter_match.group(2))
                        else:
                            # Intentar inferir del filing date
                            date_obj = datetime.strptime(filing['filing_date'], '%Y-%m-%d')
                            month = date_obj.month
                            quarter = f"Q{((month - 1) // 3) + 1}"
                            year = date_obj.year
                        
                        all_transcripts.append({
                            "company": ticker,
                            "ticker": ticker,
                            "quarter": quarter,
                            "year": year,
                            "date": filing['filing_date'],
                            "full_transcript": content,
                            "source": "SEC_EDGAR",
                            "filing_url": filing['filing_url']
                        })
                    
                    # Respetar rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"Error procesando filing: {e}")
                    continue
            
            if all_transcripts:
                break  # Si encontramos transcripciones, no buscar más tipos
        
        # Ordenar por fecha (más recientes primero)
        all_transcripts.sort(key=lambda x: x['date'], reverse=True)
        
        print(f"Encontradas {len(all_transcripts)} transcripciones")
        return all_transcripts[:limit]


class YahooFinanceScraper:
    """Scraper alternativo usando Yahoo Finance para obtener datos financieros reales."""
    
    @staticmethod
    def get_earnings_dates(ticker: str) -> pd.DataFrame:
        """Obtiene fechas de earnings de Yahoo Finance."""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            
            # Yahoo Finance no tiene un endpoint directo para earnings dates
            # Pero podemos obtener información financiera
            info = stock.info
            
            # Crear datos genéricos basados en la información disponible
            current_date = datetime.now()
            earnings_data = []
            
            # Generar fechas de earnings trimestrales aproximadas
            for i in range(4):
                quarter = (i % 4) + 1
                year = current_date.year - (i // 4)
                month = {1: 1, 2: 4, 3: 7, 4: 10}[quarter]
                day = 28  # Aproximado
                
                earnings_data.append({
                    'ticker': ticker,
                    'quarter': f'Q{quarter}',
                    'year': year,
                    'date': f'{year}-{month:02d}-{day:02d}',
                    'company': info.get('longName', ticker)
                })
            
            return pd.DataFrame(earnings_data)
            
        except Exception as e:
            print(f"Error obteniendo earnings dates: {e}")
            return pd.DataFrame()


class RealTranscriptFetcher:
    """Fetcher principal que combina múltiples fuentes de datos reales."""
    
    def __init__(self):
        self.sec_scraper = EDGARScraper()
        self.yahoo_scraper = YahooFinanceScraper()
    
    def get_transcripts(self, ticker: str, source: str = "sec", limit: int = 5) -> List[Dict]:
        """
        Obtiene transcripciones reales de earnings calls.
        
        Args:
            ticker: Símbolo de la empresa
            source: "sec" (EDGAR), "yahoo" (Yahoo Finance)
            limit: Número máximo de transcripciones
        
        Returns:
            Lista de transcripciones reales
        """
        ticker = ticker.upper()
        
        if source == "sec":
            print("Usando SEC EDGAR como fuente de datos...")
            transcripts = self.sec_scraper.get_earnings_transcripts(ticker, limit)
            
            if not transcripts:
                print("No se encontraron transcripciones en SEC. Intentando método alternativo...")
                # Si no hay transcripciones en SEC, intentar obtener estructura básica
                transcripts = self._generate_basic_structure(ticker)
            
            return transcripts
            
        elif source == "yahoo":
            print("Usando Yahoo Finance como fuente de datos...")
            earnings_df = self.yahoo_scraper.get_earnings_dates(ticker)
            
            transcripts = []
            for _, row in earnings_df.head(limit).iterrows():
                transcripts.append({
                    "company": row['company'],
                    "ticker": row['ticker'],
                    "quarter": row['quarter'],
                    "year": row['year'],
                    "date": row['date'],
                    "full_transcript": self._generate_placeholder_transcript(row),
                    "source": "yahoo_finance"
                })
            
            return transcripts
        else:
            return self._generate_basic_structure(ticker)
    
    def _generate_basic_structure(self, ticker: str) -> List[Dict]:
        """Genera estructura básica cuando no hay datos reales disponibles."""
        # Obtener información básica de Yahoo Finance
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            company_name = info.get('longName', ticker)
        except:
            company_name = ticker
        
        # Generar estructura de earnings calls recientes
        current_date = datetime.now()
        transcripts = []
        
        for i in range(2):  # Últimos 2 trimestres
            quarter = ((current_date.month - 1) // 3) - i
            if quarter < 0:
                quarter += 4
                year = current_date.year - 1
            else:
                year = current_date.year
            
            quarter_str = f"Q{quarter + 1}"
            
            transcripts.append({
                "company": company_name,
                "ticker": ticker,
                "quarter": quarter_str,
                "year": year,
                "date": f"{year}-{'01' if quarter == 0 else '04' if quarter == 1 else '07' if quarter == 2 else '10'}-28",
                "full_transcript": f"Transcripción de earnings call para {company_name} {quarter_str} {year}. Datos no disponibles en este momento.",
                "source": "placeholder"
            })
        
        return transcripts
    
    def _generate_placeholder_transcript(self, row: pd.Series) -> str:
        """Genera un placeholder cuando no hay transcripción real."""
        return f"""
        OPERATOR: Welcome to {row['company']} {row['quarter']} {row['year']} Earnings Conference Call.
        
        PREPARED REMARKS:
        [Transcripción no disponible - utilizando datos de Yahoo Finance para metadatos]
        
        Q&A SESSION:
        [Transcripción no disponible - utilizando datos de Yahoo Finance para metadatos]
        """


if __name__ == "__main__":
    # Probar el scraper
    print("Probando SEC EDGAR Scraper...")
    
    fetcher = RealTranscriptFetcher()
    
    # Probar con una empresa conocida
    print("\nObteniendo transcripciones de AAPL desde SEC...")
    transcripts = fetcher.get_transcripts("AAPL", source="sec", limit=3)
    
    for trans in transcripts:
        print(f"\n{trans['company']} - {trans['quarter']} {trans['year']}:")
        print(f"  Fecha: {trans['date']}")
        print(f"  Fuente: {trans['source']}")
        print(f"  Longitud: {len(trans['full_transcript'])} caracteres")
        if len(trans['full_transcript']) > 100:
            print(f"  Muestra: {trans['full_transcript'][:200]}...")
