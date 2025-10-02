#!/usr/bin/env python3
"""
MCP Server for Go Web Crawler (HTTP/SSE Transport)

This server exposes web crawling capabilities to LLMs via the Model Context Protocol
using HTTP/SSE transport for remote access. It calls the Crawler REST API instead of
running the binary directly.
"""

import os
from typing import Optional
from urllib.parse import urlparse
import json

import httpx
from mcp.server.fastmcp import FastMCP

# Get the Crawler API URL from environment variable
CRAWLER_API_URL = os.getenv("CRAWLER_API_URL", "http://localhost:8080")

# Initialize FastMCP server
mcp = FastMCP("web-crawler")


def validate_url(url: str) -> bool:
    """Validate that a URL is well-formed."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


async def call_crawler_api(endpoint: str, data: dict) -> dict:
    """
    Call the Crawler REST API.
    
    Args:
        endpoint: API endpoint to call (e.g., '/crawl', '/scrape', '/links')
        data: Request data to send
        
    Returns:
        API response data
        
    Raises:
        Exception: If the API call fails
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                f"{CRAWLER_API_URL}{endpoint}",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            raise Exception(f"Crawler API error: {error_detail}")
        except Exception as e:
            raise Exception(f"Failed to call Crawler API: {str(e)}")


@mcp.tool()
async def crawl_website(
    url: str,
    extract_links: bool = False,
    depth: int = 1,
    max_pages: int = 20,
    workers: int = 2,
    stay_domain: bool = True,
    filter: Optional[str] = None,
    seed_only: bool = False,
    news: bool = False,
    delay: int = 1,
    timeout: int = 10,
    verbose: bool = False
) -> str:
    """
    Crawl a website with full control over all crawling parameters.
    
    This tool can perform multi-page crawling with configurable depth,
    link extraction, filtering, and more. Use this for comprehensive
    website scraping tasks.
    
    Args:
        url: The URL to start crawling from (required)
        extract_links: Extract links from crawled pages (default: false)
        depth: Maximum crawl depth, 0-5 (default: 1)
        max_pages: Maximum number of pages to crawl, 1-100 (default: 20)
        workers: Number of concurrent workers, 1-10 (default: 2)
        stay_domain: Stay on the same domain as the seed URL (default: true)
        filter: Only crawl URLs containing this string (e.g., '/wiki/')
        seed_only: Crawl only the seed URL, don't follow any links (default: false)
        news: Extract news article content (default: false)
        delay: Delay between requests in seconds, 0-10 (default: 1)
        timeout: Request timeout in seconds, 5-60 (default: 10)
        verbose: Enable verbose output (default: false)
    
    Returns:
        JSON string with crawl results
    """
    if not validate_url(url):
        return json.dumps({"error": f"Invalid URL: {url}"})
    
    # Prepare request data for the API
    request_data = {
        "url": url,
        "extract_links": extract_links,
        "depth": depth,
        "max_pages": max_pages,
        "workers": workers,
        "stay_domain": stay_domain,
        "seed_only": seed_only,
        "news": news,
        "delay": delay,
        "timeout": timeout,
        "verbose": verbose
    }
    
    # Add filter if provided
    if filter:
        request_data["filter"] = filter
    
    # Call the Crawler API
    try:
        result = await call_crawler_api("/crawl", request_data)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error crawling website: {str(e)}"})


@mcp.tool()
async def quick_scrape(
    url: str,
    extract_links: bool = False
) -> str:
    """
    Quickly scrape a single page and extract its content.
    
    This is a simplified tool for when you just need to get the
    title, description, and text content from one page. Optionally
    extract links as well.
    
    Args:
        url: The URL to scrape (required)
        extract_links: Also extract links from the page (default: false)
    
    Returns:
        JSON string with page data
    """
    if not validate_url(url):
        return json.dumps({"error": f"Invalid URL: {url}"})
    
    # Prepare request data
    request_data = {
        "url": url,
        "extract_links": extract_links
    }
    
    # Call the Crawler API
    try:
        result = await call_crawler_api("/scrape", request_data)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error scraping page: {str(e)}"})


@mcp.tool()
async def get_page_links(url: str) -> str:
    """
    Extract all links from a single page.
    
    Use this when you only need to discover what pages link from a
    given URL, without extracting the page content.
    
    Args:
        url: The URL to extract links from (required)
    
    Returns:
        JSON string with links data
    """
    if not validate_url(url):
        return json.dumps({"error": f"Invalid URL: {url}"})
    
    # Prepare request data
    request_data = {"url": url}
    
    # Call the Crawler API
    try:
        result = await call_crawler_api("/links", request_data)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Error extracting links: {str(e)}"})


def main():
    """Run the MCP server with SSE transport."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount
    
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting MCP server on port {port}")
    print(f"Crawler API URL: {CRAWLER_API_URL}")
    
    # Create Starlette app with MCP SSE server mounted
    app = Starlette(
        routes=[
            Mount("/", app=mcp.sse_app()),
        ]
    )
    
    # Run with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
