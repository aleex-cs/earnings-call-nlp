# Installation Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Virtual environment (recommended)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/earnings-call-nlp.git
cd earnings-call-nlp
```

### 2. Create Virtual Environment

```bash
# Using venv (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# For development, install dev dependencies
pip install -r requirements-dev.txt
```

### 4. Verify Installation

```bash
# Test imports
python -c "import torch; import transformers; print('Installation successful')"

# Run tests
pytest tests/ -v
```

### 5. Run the Dashboard

```bash
streamlit run app.py
```

The dashboard will be available at `http://localhost:8501`

## GPU Support (Optional)

For GPU acceleration with CUDA:

```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Update requirements.txt accordingly
```

## Docker Installation (Optional)

```bash
# Build Docker image
docker build -t earnings-call-nlp .

# Run container
docker run -p 8501:8501 earnings-call-nlp
```

## Troubleshooting

### Common Issues

**Issue**: PyTorch CUDA not available
- **Solution**: Use CPU version or install CUDA-compatible PyTorch

**Issue**: Missing dependencies
- **Solution**: Ensure you're using Python 3.10+ and reinstall requirements

**Issue**: Streamlit not launching
- **Solution**: Check firewall settings and ensure port 8501 is available

## Development Setup

For contributing to the project:

```bash
# Install in development mode
pip install -e .

# Install pre-commit hooks
pre-commit install

# Run code formatting
black src/ tests/
```