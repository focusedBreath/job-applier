# ── Stage 1: Build React UI ──────────────────────────────────────
FROM node:20-slim AS ui-builder
WORKDIR /ui
COPY ui/package.json ui/package-lock.json* ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# ── Stage 2: Python backend + Playwright + Xvfb ─────────────────
FROM python:3.12-slim

# Xvfb + Playwright system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xauth \
    x11-utils \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python deps (this layer is cached unless pyproject.toml/uv.lock changes)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Install Playwright browser
RUN uv run playwright install chromium --with-deps

# Copy backend source
COPY src/ ./src/

# Copy compiled frontend (served as static files by FastAPI)
COPY --from=ui-builder /ui/dist ./src/static/

# Create data directories (will be overridden by volume mounts)
RUN mkdir -p /app/data /app/reports

EXPOSE 8080

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
