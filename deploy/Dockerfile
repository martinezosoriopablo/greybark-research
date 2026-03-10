FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the 3 project directories
COPY consejo_ia/ /app/consejo_ia/
COPY layout/ /app/layout/
COPY proyectos/ /app/proyectos/

# PYTHONPATH so imports resolve across all 3 dirs
ENV PYTHONPATH=/app/consejo_ia:/app/layout:/app/proyectos

# Runtime config
ENV GREYBARK_DB=/data/greybark.db
ENV GREYBARK_OUTPUT=/data/output
ENV GREYBARK_LAYOUT_DIR=/app/layout
ENV GREYBARK_PASSWORDS=/data/passwords.json

# Data volume for persistence
VOLUME ["/data"]

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/login || exit 1

# Run from consejo_ia/ so relative imports work
WORKDIR /app/consejo_ia
CMD ["uvicorn", "deploy.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
