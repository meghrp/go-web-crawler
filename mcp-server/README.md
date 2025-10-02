# MCP Server

## Local (STDIO)
```bash
go build -o gocrawler .
cd mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

## Local (HTTP/SSE)
```bash
cd mcp-server
source .venv/bin/activate  # reuse from above or create one
pip install -r requirements-http.txt
export CRAWLER_API_URL=http://localhost:8080
python server_http.py
```

## Docker
```bash
docker compose up mcp-server
```

## Cloud Run
```bash
./deploy.sh PROJECT_ID REGION
```

## Generic container
```bash
docker build -t mcp-server mcp-server/
docker run -p 8080:8080 -e CRAWLER_API_URL=https://YOUR_API_URL mcp-server
```
