FROM python:3.11-slim

WORKDIR /app

# System deps for matplotlib, bcrypt, QuantLib
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libboost-all-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY . /app/consejo_ia/

# Seed Layout: platform module, DB, passwords
RUN mkdir -p /app/layout/output
COPY deploy/layout_seed/greybark_platform.py /app/layout/greybark_platform.py
COPY deploy/layout_seed/greybark.db /app/layout/greybark.db
COPY deploy/layout_seed/passwords.json /app/layout/passwords.json

# Environment
ENV GREYBARK_LAYOUT_DIR=/app/layout
ENV GREYBARK_OUTPUT=/app/layout/output
ENV GREYBARK_PASSWORDS=/app/layout/passwords.json
ENV GREYBARK_DB=/app/layout/greybark.db
ENV PYTHONPATH=/app/consejo_ia:/app/layout
ENV PYTHONIOENCODING=utf-8

# Port (Railway auto-assigns via $PORT)
EXPOSE 8000

# Start uvicorn directly
CMD ["sh", "-c", "cd /app/consejo_ia && python -m uvicorn deploy.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
