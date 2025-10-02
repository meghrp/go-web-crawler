#!/usr/bin/env python3
"""
MCP Server for Go Web Crawler

This server exposes web crawling capabilities to LLMs via the Model Context Protocol.
It wraps the Go web crawler binary and provides structured tools for web scraping.
"""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import mcp.server.stdio


# Get the path to the gocrawler binary
CRAWLER_DIR = Path(__file__).parent.parent
CRAWLER_BINARY = CRAWLER_DIR / "gocrawler"

# Validate that the binary exists
if not CRAWLER_BINARY.exists():
    raise RuntimeError(
        f"Crawler binary not found at {CRAWLER_BINARY}. "
        "Please build the Go crawler first with: go build -o gocrawler"
    )


def validate_url(url: str) -> bool:
    """Validate that a URL is well-formed."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


async def run_crawler(args: list[str], timeout: int = 60) -> dict[str, Any]:
    """
    Run the Go crawler binary with the specified arguments.
    
    Args:
        args: Command-line arguments to pass to the crawler
        timeout: Maximum execution time in seconds
        
    Returns:
        Parsed JSON output from the crawler
        
    Raises:
        RuntimeError: If the crawler fails or times out
    """
    # Create a temporary file for the output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        output_file = tmp.name
    
    try:
        # Build the command
        cmd = [str(CRAWLER_BINARY), "-output", output_file] + args
        
        # Run the crawler
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise RuntimeError(f"Crawler timed out after {timeout} seconds")
        
        # Check if the process succeeded
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
            raise RuntimeError(f"Crawler failed: {error_msg}")
        
        # Read and parse the output
        with open(output_file, 'r') as f:
            result = json.load(f)
        
        return result
        
    finally:
        # Clean up the temporary file
        try:
            os.unlink(output_file)
        except Exception:
            pass


# Initialize the MCP server
app = Server("web-crawler")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available web crawling tools."""
    return [
        Tool(
            name="crawl_website",
            description=(
                "Crawl a website with full control over all crawling parameters. "
                "This tool can perform multi-page crawling with configurable depth, "
                "link extraction, filtering, and more. Use this for comprehensive "
                "website scraping tasks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to start crawling from (required)"
                    },
                    "extract_links": {
                        "type": "boolean",
                        "description": "Extract links from crawled pages (default: false)",
                        "default": False
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum crawl depth (default: 1)",
                        "default": 1,
                        "minimum": 0,
                        "maximum": 5
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum number of pages to crawl (default: 20)",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "workers": {
                        "type": "integer",
                        "description": "Number of concurrent workers (default: 2)",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "stay_domain": {
                        "type": "boolean",
                        "description": "Stay on the same domain as the seed URL (default: true)",
                        "default": True
                    },
                    "filter": {
                        "type": "string",
                        "description": "Only crawl URLs containing this string (e.g., '/wiki/')"
                    },
                    "seed_only": {
                        "type": "boolean",
                        "description": "Crawl only the seed URL, don't follow any links (default: false)",
                        "default": False
                    },
                    "news": {
                        "type": "boolean",
                        "description": "Extract news article content (default: false)",
                        "default": False
                    },
                    "delay": {
                        "type": "integer",
                        "description": "Delay between requests in seconds (default: 1)",
                        "default": 1,
                        "minimum": 0,
                        "maximum": 10
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout in seconds (default: 10)",
                        "default": 10,
                        "minimum": 5,
                        "maximum": 60
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Enable verbose output (default: false)",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="quick_scrape",
            description=(
                "Quickly scrape a single page and extract its content. "
                "This is a simplified tool for when you just need to get the "
                "title, description, and text content from one page. Optionally "
                "extract links as well."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scrape"
                    },
                    "extract_links": {
                        "type": "boolean",
                        "description": "Also extract links from the page (default: false)",
                        "default": False
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="get_page_links",
            description=(
                "Extract all links from a single page. Use this when you only "
                "need to discover what pages link from a given URL, without "
                "extracting the page content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to extract links from"
                    }
                },
                "required": ["url"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls from the LLM."""
    
    if name == "crawl_website":
        return await handle_crawl_website(arguments)
    elif name == "quick_scrape":
        return await handle_quick_scrape(arguments)
    elif name == "get_page_links":
        return await handle_get_page_links(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_crawl_website(args: dict[str, Any]) -> list[TextContent]:
    """Handle the crawl_website tool."""
    url = args.get("url")
    if not url:
        raise ValueError("URL is required")
    
    if not validate_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    # Build crawler arguments
    crawler_args = ["-seed", url]
    
    if args.get("extract_links", False):
        crawler_args.append("-extract-links")
    
    if "depth" in args:
        crawler_args.extend(["-depth", str(args["depth"])])
    
    if "max_pages" in args:
        crawler_args.extend(["-max", str(args["max_pages"])])
    
    if "workers" in args:
        crawler_args.extend(["-workers", str(args["workers"])])
    
    if args.get("stay_domain") is False:
        crawler_args.append("-stay-domain=false")
    
    if "filter" in args and args["filter"]:
        crawler_args.extend(["-filter", args["filter"]])
    
    if args.get("seed_only", False):
        crawler_args.append("-seed-only")
    
    if args.get("news", False):
        crawler_args.append("-news")
    
    if "delay" in args:
        crawler_args.extend(["-delay", str(args["delay"])])
    
    if "timeout" in args:
        crawler_args.extend(["-timeout", str(args["timeout"])])
    
    if args.get("verbose", False):
        crawler_args.append("-verbose")
    
    # Calculate timeout (give extra time for the subprocess)
    execution_timeout = args.get("timeout", 10) * args.get("max_pages", 20) + 30
    
    # Run the crawler
    try:
        result = await run_crawler(crawler_args, timeout=execution_timeout)
        
        # Format the response
        response = {
            "pages_crawled": len(result),
            "pages": result
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error crawling website: {str(e)}"
        )]


async def handle_quick_scrape(args: dict[str, Any]) -> list[TextContent]:
    """Handle the quick_scrape tool."""
    url = args.get("url")
    if not url:
        raise ValueError("URL is required")
    
    if not validate_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    # Use seed-only mode for quick scraping
    crawler_args = ["-seed", url, "-seed-only"]
    
    if args.get("extract_links", False):
        crawler_args.append("-extract-links")
    
    # Run the crawler with a shorter timeout
    try:
        result = await run_crawler(crawler_args, timeout=30)
        
        if not result:
            return [TextContent(
                type="text",
                text="No data returned from the page"
            )]
        
        # Return the first (and only) page
        page = result[0]
        
        return [TextContent(
            type="text",
            text=json.dumps(page, indent=2)
        )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error scraping page: {str(e)}"
        )]


async def handle_get_page_links(args: dict[str, Any]) -> list[TextContent]:
    """Handle the get_page_links tool."""
    url = args.get("url")
    if not url:
        raise ValueError("URL is required")
    
    if not validate_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    # Use seed-only mode with link extraction
    crawler_args = ["-seed", url, "-seed-only", "-extract-links"]
    
    # Run the crawler
    try:
        result = await run_crawler(crawler_args, timeout=30)
        
        if not result:
            return [TextContent(
                type="text",
                text="No data returned from the page"
            )]
        
        # Extract just the links
        page = result[0]
        links = page.get("links", [])
        
        response = {
            "url": url,
            "links_found": len(links),
            "links": links
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error extracting links: {str(e)}"
        )]


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

