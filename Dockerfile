# ==============================================================================
# Dockerfile para SandyCore en DigitalOcean (Optimizado para bajo consumo de RAM)
# ==============================================================================
FROM python:3.12-slim-bookworm AS base

# Variables de entorno esenciales de Python y optimización de memoria
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    # Optimización clave de RAM para servidores multicore en DigitalOcean:
    # Limita las arenas de glibc para prevenir fragmentación del heap y sobreconsumo
    MALLOC_ARENA_MAX=2

WORKDIR /app

# Instalar dependencias mínimas de sistema (curl para el healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar el código fuente de la aplicación
COPY app/ ./app/

# Crear y usar un usuario sin privilegios por seguridad
RUN useradd -m -u 10001 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Verificación de salud interna que comprueba el endpoint de telemetría y memoria
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/memory || exit 1

# Comando de inicio con uvicorn respetando el puerto configurado
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
