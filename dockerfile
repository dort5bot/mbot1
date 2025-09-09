FROM python:3.11-slim AS builder

WORKDIR /app

# Sistem bağımlılıklarını kur (güncellenmiş)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    libffi-dev \
    libssl-dev \
    python3-dev \
    libgomp1 \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve global olarak kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime sistem bağımlılıklarını kur
RUN apt-get update && apt-get install -y \
    curl \
    libgomp1 \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user oluştur
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Environment variables for optimization
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp

# Builder stage'den Python paketlerini ve uygulama kodunu kopyala
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=appuser:appgroup . .

# Port bilgisi
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# Non-root user ile çalıştır
USER appuser

# Container başlatıldığında çalışacak komut
CMD ["python", "main.py"]
