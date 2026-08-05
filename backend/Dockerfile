FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build tools + git for GitHub pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    git \
    tesseract-ocr \
    tesseract-ocr-mal \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads && mkdir -p /app/backend/uploads

EXPOSE 8000

# Run from either /app or /app/backend depending on the build context
CMD ["sh", "-c", "if [ -f start.py ]; then python start.py; elif [ -f backend/start.py ]; then cd backend && python start.py; else echo 'Error: start.py not found'; exit 1; fi"]
