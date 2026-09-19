"""
Test de la API de Financial Modeling Prep
"""

import os
from dotenv import load_dotenv
import requests

# Cargar variables de entorno
load_dotenv()

api_key = os.getenv("FMP_API_KEY")
print(f"API Key encontrada: {api_key[:10]}...{api_key[-4:] if api_key else 'None'}")

if not api_key:
    print("ERROR: No se encontró FMP_API_KEY en el archivo .env")
else:
    # Probar endpoint específico de transcripts
    url = f"https://financialmodelingprep.com/api/v4/earning_call_transcript/AAPL?apikey={api_key}&year=2024&quarter=1"
    
    try:
        print(f"Probando endpoint v4 de transcripts...")
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("EXITO: API funcionando")
            print(f"Datos: {data[:2] if isinstance(data, list) else data}")
        else:
            print(f"Error: {response.text[:300]}")
            
    except Exception as e:
        print(f"Error de conexion: {e}")
