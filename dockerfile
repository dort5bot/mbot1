# Build aşaması
FROM python:3.11-slim AS builder

WORKDIR /app

# Build bağımlılıklarını kur
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve wheel olarak derle
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# Runtime aşaması
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime bağımlılıkları
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Uygulama kullanıcısı oluştur
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

# Python optimizasyonları
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/tmp \
    PIP_NO_CACHE_DIR=1

# Wheel'lardan paketleri kur
COPY --from=builder /app/wheels /wheels
RUN pip install --no-index --find-links=/wheels -r /wheels/requirements.txt \
    && rm -rf /wheels

# Uygulama kodunu kopyala
COPY --chown=appuser:appgroup . .

# Health check ve port ayarları
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

# Çalışma kullanıcısını ayarla
USER appuser

# Çalıştırma komutu
CMD ["python", "main.py"]


# Geliştirme aşaması (opsiyonel - sadece development için)
FROM runtime AS development

USER root

# Geliştirme araçlarını kur
RUN apt-get update && apt-get install -y \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Debug modunu etkinleştir
ENV PYTHONFAULTHANDLER=1

USER appuser
