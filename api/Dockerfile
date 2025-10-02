# Multi-stage Dockerfile for Web Crawler API
# Stage 1: Build Go binary
# Stage 2: Python FastAPI application

# ============================================================================
# Stage 1: Build the Go crawler
# ============================================================================
FROM golang:1.21-alpine AS go-builder

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY main.go ./
COPY pkg/ ./pkg/

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o gocrawler .

# ============================================================================
# Stage 2: Python FastAPI application
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=go-builder /build/gocrawler /app/gocrawler

RUN chmod +x /app/gocrawler

COPY api/main.py .

RUN useradd -m -u 1000 crawler && chown -R crawler:crawler /app
USER crawler

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
