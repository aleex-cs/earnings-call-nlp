# Contributing to Earnings Call NLP Pipeline

¡Gracias por tu interés en contribuir a este proyecto! Aquí tienes algunas guías para hacerlo de manera efectiva.

## 🤝 Cómo Contribuir

### Reporting Bugs

Antes de reportar un bug, por favor:

1. Busca en los [issues existentes](https://github.com/yourusername/earnings-call-nlp/issues) para ver si ya fue reportado.
2. Si es un nuevo bug, crea un issue con:
   - Título descriptivo
   - Pasos para reproducir el problema
   - Comportamiento esperado vs actual
   - Tu entorno (Python version, OS, etc.)

### Sugerencias de Features

Para sugerir nuevas funcionalidades:

1. Busca en issues existentes para evitar duplicados.
2. Describe claramente la feature propuesta y su caso de uso.
3. Explica por qué sería útil para el proyecto.

### Pull Requests

1. **Fork** el repositorio
2. Crea una **rama** para tu feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. **Push** a la rama (`git push origin feature/AmazingFeature`)
5. Abre un **Pull Request**

## 📝 Estándares de Código

### Code Style

Usamos **Black** para formatear el código:

```bash
black src/ tests/
```

### Type Hints

Añade type hints a las funciones nuevas:

```python
def analyze_sentiment(text: str) -> Dict[str, float]:
    """Analyze sentiment of text."""
    return {"score": 0.5}
```

### Documentation

Documenta las funciones con docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    """
    return True
```

## 🧪 Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests con cobertura
pytest --cov=src --cov-report=html

# Tests específicos
pytest tests/test_segmenter.py
```

### Escribir Tests

Añade tests para nuevas funcionalidades:

```python
def test_new_feature():
    """Test new feature."""
    result = new_function()
    assert result == expected_value
```

## 🏗️ Estructura del Proyecto

```
earnings-call-nlp/
├── src/              # Código fuente
├── tests/            # Tests
├── data/             # Datos y resultados
├── docs/             # Documentación
├── app.py            # Dashboard
└── pyproject.toml   # Configuración
```

## 📋 Checklist para PRs

Antes de abrir un PR, verifica:

- [ ] Tests pasan (`pytest`)
- [ ] Código formateado (`black`)
- [ ] Type hints añadidos
- [ ] Docstrings completos
- [ ] No dependencies innecesarias
- [ ] README actualizado si es necesario
- [ ] Commits descriptivos

## 🚀 Desarrollo Local

### Setup

```bash
# Clonar repo
git clone https://github.com/yourusername/earnings-call-nlp.git
cd earnings-call-nlp

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements-dev.txt

# Instalar en modo desarrollo
pip install -e .
```

### Ejecutar el Dashboard

```bash
streamlit run app.py
```

## 📖 Recursos

- [Python Style Guide](https://peps.python.org/pep-0008/)
- [Black Documentation](https://black.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)

## 💬 Communication

- **GitHub Issues**: Para bugs y features
- **GitHub Discussions**: Para preguntas y debates
- **Email**: Para asuntos privados

## 🎯 Áreas de Contribución Prioritarias

1. **Más APIs financieras**: Integración con Alpha Vantage, IEX Cloud
2. **Multi-idioma**: Soporte para earnings calls en otros idiomas
3. **Visualizaciones**: Mejoras al dashboard
4. **Tests**: Mayor cobertura de tests
5. **Documentación**: Mejoras a docs y tutoriales

¡Gracias por contribuir! 🙏