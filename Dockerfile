# ===== Frontend build =====
FROM node:20-alpine AS fe
WORKDIR /fe

# Install deps and build
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build


# ===== Backend runtime =====
FROM python:3.11-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps (use backend requirements for API)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt

# App code
COPY backend ./backend
COPY modules ./modules

# Frontend build artifacts served by FastAPI
COPY --from=fe /fe/dist ./frontend/dist

EXPOSE 8080

# Run the app (serves both API and built frontend)
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]


