FROM python:3.11-slim

WORKDIR /app

# System deps for matplotlib + bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
# consejo_ia/ is the main codebase
COPY . /app/consejo_ia/

# Copy Layout platform code into /app/layout/
# (In Railway, mount Layout/ as volume or copy at build)
RUN mkdir -p /app/layout/output

# Environment
ENV GREYBARK_LAYOUT_DIR=/app/layout
ENV GREYBARK_OUTPUT=/app/layout/output
ENV GREYBARK_PASSWORDS=/app/layout/passwords.json
ENV GREYBARK_DB=/app/layout/greybark.db
ENV PYTHONPATH=/app/consejo_ia:/app/layout
ENV PYTHONIOENCODING=utf-8

# Port (Railway auto-assigns via $PORT)
EXPOSE 8000

# Startup: init layout (seeds DB if volume empty) then run uvicorn
CMD ["sh", "-c", "cd /app/consejo_ia && python deploy/init_layout.py && python -m uvicorn deploy.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
