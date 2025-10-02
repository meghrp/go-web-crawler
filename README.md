# Go Web Crawler

A high-performance web crawler written in Go

## Features

- Concurrent crawling using Go's goroutines and channels
- Polite crawling with rate limiting and robots.txt compliance
- HTML parsing to extract links and specific content (news article extraction)
- URL frontier management with duplicate detection
- Command-line interface with configurable options
- Data storage in JSON or CSV format

## Installation

```bash
# Clone repo
git clone https://github.com/your-username/gocrawler.git
cd gocrawler

# Install dependencies
go mod download

# Build the application
go build -o gocrawler
```

## Usage

### Available Flags

```
-seed         Required. Starting URL for crawling
-depth        Maximum link depth to crawl (default: 1)
-workers      Number of concurrent crawlers (default: 2)
-max          Maximum pages to crawl (default: 20)
-delay        Seconds between requests (default: 1)
-timeout      Request timeout in seconds (default: 10)
-format       Output format: json or csv (default: json)
-output       Output filename (default: results.json)
-agent        Custom User-Agent string (default: GoCrawler/1.0)
-robots       Respect robots.txt rules (default: true)
-news         Extract news article content (default: false)
-verbose      Show detailed output (default: false)
-stay-domain  Stay on the same domain (default: true)
-filter       Only crawl URLs containing this string
-seed-only    Crawl only the seed URL (default: false)
-extract-links Extract links from crawled pages (default: false)
```

### Examples

```bash
# Basic usage with a seed URL
./gocrawler -seed https://example.com

# Crawl ONLY the seed URL without following any links
./gocrawler -seed https://example.com -seed-only

# Crawl with more workers (default is 2)
./gocrawler -seed https://example.com -workers 10

# Increase crawl depth (default is 1)
./gocrawler -seed https://example.com -depth 3

# Set maximum pages to crawl (default is 20)
./gocrawler -seed https://example.com -max 50

# Allow crawling across different domains (default is to stay on the same domain)
./gocrawler -seed https://example.com -stay-domain=false

# Only crawl URLs containing a specific string (great for focusing on specific sections)
./gocrawler -seed https://en.wikipedia.org/wiki/Go_(programming_language) -filter "/wiki/"

# Output to CSV instead of JSON (default is JSON)
./gocrawler -seed https://example.com -format csv -output results.csv

# Focus on extracting news article content
./gocrawler -seed https://news-website.com -news -output news.json

# Show verbose output
./gocrawler -seed https://example.com -verbose

# Custom delay between requests (in seconds)
./gocrawler -seed https://example.com -delay 2

# Disable robots.txt compliance (not recommended)
./gocrawler -seed https://example.com -robots=false

# Custom user agent
./gocrawler -seed https://example.com -agent "MyCustomBot/1.0"
```

## Default Behavior

By default, the crawler:

- Crawls only to a depth of 1 (the seed URL and direct links from it)
- Stays within the same domain as the seed URL
- Limits to a maximum of 20 pages
- Uses 2 concurrent workers
- Respects robots.txt rules
- Has a 1-second delay between requests to the same domain

You can make the crawler even more focused by using the `-filter` option to only crawl URLs containing a specific string, or use `-seed-only` to crawl just the single URL you provide.

## MCP Server Integration

An **MCP (Model Context Protocol) server** is available that allows LLMs to use this web crawler directly! This enables natural language interaction with the crawler through tools like Cursor.

**Features:**

- Three tools for LLMs: `crawl_website`, `quick_scrape`, and `get_page_links`
- Seamless integration with all crawler flags and options
- Easy setup with Cursor and other MCP-compatible clients

**Quick Start:**

```bash
# Install Python dependencies
cd mcp-server
pip install -r requirements.txt

# See the MCP server README for Cursor configuration
cat mcp-server/README.md
```

**Usage Example in Cursor:**

```
"Scrape example.com and extract all the links"
"Crawl wikipedia.org starting from the Go page, only following /wiki/ links"
```

For complete setup instructions and usage examples, see [`mcp-server/README.md`](mcp-server/README.md).

## REST API & Cloud Deployment

The crawler is also available as a **public REST API** that can be deployed to the cloud with auto-scaling!

**Features:**

- FastAPI-based HTTP endpoints
- Full Swagger/OpenAPI documentation
- Containerized with Docker
- Deployable to Google Cloud Run
- Auto-scales from 0 to 1000s of instances
- Both REST API and remote MCP server

**Quick Deploy:**

```bash
# Deploy to Google Cloud Run
./deploy.sh YOUR_PROJECT_ID us-central1
```

**Local Testing:**

```bash
# Run with Docker Compose
docker-compose up
```

**REST API Endpoints:**

- `POST /crawl` - Full website crawling
- `POST /scrape` - Quick single-page scrape
- `POST /links` - Extract links only
- `GET /health` - Health check
- `GET /` - Interactive API docs

**Usage Example:**

```bash
curl -X POST https://your-api-url/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**Complete deployment guide:** See [`DEPLOYMENT.md`](DEPLOYMENT.md)  
**API documentation:** See [`api/README.md`](api/README.md)

## Project Structure

- `main.go`: Entry point and command-line interface
- `pkg/crawler`: Core crawler implementation
- `pkg/frontier`: URL frontier for managing crawl queue and detecting duplicates
- `pkg/parser`: HTML parsing and content extraction
- `pkg/robotstxt`: Robots.txt parser and cache
- `pkg/storage`: Data storage implementations (JSON and CSV)
- `api/`: FastAPI REST API server
- `mcp-server/`: MCP server for LLM integration (local and remote)
- `docker-compose.yml`: Local development environment
- `deploy.sh`: Cloud deployment automation
- `DEPLOYMENT.md`: Complete deployment guide

## Performance Considerations

- The crawler uses concurrent goroutines to maximize throughput
- Domain-specific rate limiting prevents overloading any single domain
- Memory-efficient URL frontier with duplicate detection
- Timeout handling for unresponsive servers

## Limitations

### JavaScript-Rendered Sites

This crawler fetches and parses **static HTML only**. It does not execute JavaScript, which means:

- **Single Page Applications (SPAs)** built with React, Vue, Angular, or similar frameworks will return minimal or no content
- Sites built with tools like Vite, Create React App, Next.js (in client-side rendering mode), Gatsby (in CSR mode), etc. will appear mostly empty
- Dynamic content loaded after page load via AJAX/fetch will not be captured

**Example:** A React SPA might return only:

```html
<body>
  <div id="root"></div>
  <script src="/app.js"></script>
</body>
```

The crawler will see the empty `<div id="root">` but won't execute the JavaScript that populates it with content.
