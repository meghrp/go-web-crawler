# Dockerfile for MCP Server (HTTP/SSE Transport)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-http.txt .
RUN pip install --no-cache-dir -r requirements-http.txt

# Copy the MCP server application
COPY server_http.py .

# Create a non-root user
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run the application
CMD ["python", "server_http.py"]

