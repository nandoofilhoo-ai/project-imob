FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for compiling psycopg2 if required, though psycopg2-binary is used)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and tests
COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini* ./

EXPOSE 8000

# Start FastAPI application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
