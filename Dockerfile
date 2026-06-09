FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including WeasyPrint requirements)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
# Add the new dependencies we need for the API
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set Python path
ENV PYTHONPATH=/app

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
