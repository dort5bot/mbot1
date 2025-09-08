#dockerfile
# 🐍 Python 3.11 slim base image
FROM python:3.11-slim AS builder

WORKDIR /app

# Sistem bağımlılıklarını kur
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve kur
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 🔒 Runtime stage - daha güvenli
FROM python:3.11-slim AS runtime

WORKDIR /app

# Non-root user oluştur (güvenlik için)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Builder stage'den Python paketlerini kopyala
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
COPY --chown=appuser:appgroup . .

# PATH'e user Python paketlerini ekle
ENV PATH="/home/appuser/.local/bin:${PATH}" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1"

# Port bilgisi
EXPOSE 3000

# Health check (main.py'de health endpoint olmalı)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# Non-root user ile çalıştır
USER appuser

# Container başlatıldığında çalışacak komut
CMD ["python", "main.py"]
