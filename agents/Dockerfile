FROM python:3.11-slim

WORKDIR /app

# Install build dependencies first for caching
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    iputils-ping \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command (overridden in docker-compose)
CMD ["python", "monitor_agent.py"]
