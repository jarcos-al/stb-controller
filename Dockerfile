# ── Stage 1: Build Frontend ──
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Runtime ──
FROM python:3.12-slim AS runtime
WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy built frontend into backend static dir
COPY --from=frontend-builder /app/frontend/dist ./backend/static/

# Create non-root user and dirs
RUN useradd -r -u 1000 -U appuser && \
    mkdir -p /data /config /logs && \
    chown -R appuser:appuser /app /data /config /logs

USER appuser

ENV PYTHONPATH=/app
ENV CONFIG_DIR=/config
ENV DATA_DIR=/data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8080/api/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
