# GoCrawler

A high-performance web crawler written in Go, demonstrating concurrent programming and modern Go practices.

## Features

- Concurrent crawling using Go's goroutines and channels
- Polite crawling with rate limiting and robots.txt compliance
- HTML parsing to extract links and specific content (news article extraction)
- URL frontier management with duplicate detection
- Command-line interface with configurable options
- Data storage in JSON or CSV format

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/gocrawler.git
cd gocrawler

# Install dependencies
go mod download

# Build the application
go build -o gocrawler
```

## Usage

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

## Example Use Cases

### Crawling a News Website

```bash
./gocrawler -seed https://news-website.com -news -depth 2 -max 50 -output news_articles.json -verbose
```

This command crawls a news website, extracting article content, limiting to depth 2 and maximum 50 pages, saving results in JSON format, and showing verbose output.

### Creating a Site Map

```bash
./gocrawler -seed https://example.com -depth 3 -max 1000 -format csv -output sitemap.csv
```

This command crawls a website to a depth of 3, collecting up to 1000 URLs, and outputs a CSV file that can be used as a sitemap.

### Archiving a Blog

```bash
./gocrawler -seed https://blog.example.com -depth 5 -max 500 -output blog_archive.json -delay 2
```

This command crawls a blog with a depth of 5, collecting up to 500 pages, with a 2-second delay between requests to be extra polite to the server.

## Project Structure

- `main.go`: Entry point and command-line interface
- `pkg/crawler`: Core crawler implementation
- `pkg/frontier`: URL frontier for managing crawl queue and detecting duplicates
- `pkg/parser`: HTML parsing and content extraction
- `pkg/robotstxt`: Robots.txt parser and cache
- `pkg/storage`: Data storage implementations (JSON and CSV)

## Performance Considerations

- The crawler uses concurrent goroutines to maximize throughput
- Domain-specific rate limiting prevents overloading any single domain
- Memory-efficient URL frontier with duplicate detection
- Timeout handling for unresponsive servers

## License

MIT License 