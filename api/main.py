"""
Web Crawler REST API

A FastAPI-based REST API for the Go web crawler.
Provides endpoints for crawling websites, scraping pages, and extracting links.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List, Dict, Any
import subprocess
import tempfile
import json
import os
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Web Crawler API",
    description="A powerful web crawling API that extracts content, links, and metadata from websites",
    version="1.0.0",
    docs_url="/",  # Swagger UI at root
    redoc_url="/redoc"
)

# Enable CORS for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to the Go crawler binary
CRAWLER_BINARY = Path(__file__).parent / "gocrawler"

# Validate binary exists
if not CRAWLER_BINARY.exists():
    logger.warning(
        f"Crawler binary not found at {CRAWLER_BINARY}. "
        "It should be copied during Docker build."
    )


# ============================================================================
# Pydantic Models (Request/Response schemas)
# ============================================================================

class CrawlRequest(BaseModel):
    """Request model for full website crawling"""
    url: str = Field(..., description="The URL to start crawling from")
    extract_links: bool = Field(False, description="Extract links from pages")
    depth: int = Field(1, ge=0, le=5, description="Maximum crawl depth (0-5)")
    max_pages: int = Field(20, ge=1, le=100, description="Maximum pages to crawl (1-100)")
    workers: int = Field(2, ge=1, le=10, description="Number of concurrent workers (1-10)")
    stay_domain: bool = Field(True, description="Stay on the same domain")
    filter: Optional[str] = Field(None, description="Only crawl URLs containing this string")
    seed_only: bool = Field(False, description="Crawl only the seed URL")
    news: bool = Field(False, description="Extract news article content")
    delay: int = Field(1, ge=0, le=10, description="Delay between requests in seconds (0-10)")
    timeout: int = Field(10, ge=5, le=60, description="Request timeout in seconds (5-60)")
    verbose: bool = Field(False, description="Enable verbose output")

    @validator('url')
    def validate_url(cls, v):
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com",
                "extract_links": True,
                "depth": 2,
                "max_pages": 20,
                "workers": 2
            }
        }


class ScrapeRequest(BaseModel):
    """Request model for quick single-page scraping"""
    url: str = Field(..., description="The URL to scrape")
    extract_links: bool = Field(False, description="Also extract links from the page")

    @validator('url')
    def validate_url(cls, v):
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com",
                "extract_links": False
            }
        }


class LinksRequest(BaseModel):
    """Request model for extracting links only"""
    url: str = Field(..., description="The URL to extract links from")

    @validator('url')
    def validate_url(cls, v):
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com"
            }
        }


class PageData(BaseModel):
    """Model for a crawled page"""
    url: str
    title: str
    description: str
    content: Optional[str] = None
    links: Optional[List[str]] = None
    crawled_at: str
    depth: int


class CrawlResponse(BaseModel):
    """Response model for crawl endpoint"""
    pages_crawled: int
    pages: List[PageData]
    execution_time_seconds: float


class ScrapeResponse(PageData):
    """Response model for scrape endpoint"""
    pass


class LinksResponse(BaseModel):
    """Response model for links endpoint"""
    url: str
    links_found: int
    links: List[str]


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    crawler_available: bool


# ============================================================================
# Helper Functions
# ============================================================================

async def run_crawler(args: List[str], timeout: int = 60) -> Dict[str, Any]:
    """
    Run the Go crawler binary with the specified arguments.
    
    Args:
        args: Command-line arguments to pass to the crawler
        timeout: Maximum execution time in seconds
        
    Returns:
        Parsed JSON output from the crawler
        
    Raises:
        HTTPException: If the crawler fails or times out
    """
    # Create a temporary file for the output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        output_file = tmp.name
    
    try:
        # Build the command
        cmd = [str(CRAWLER_BINARY), "-output", output_file] + args
        
        logger.info(f"Running crawler: {' '.join(cmd)}")
        
        # Run the crawler
        start_time = datetime.now()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Check if the process succeeded
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else "Unknown error"
            logger.error(f"Crawler failed: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Crawler failed: {error_msg}"
            )
        
        # Read and parse the output
        with open(output_file, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Crawler completed in {execution_time:.2f}s")
        
        return {
            "data": data,
            "execution_time": execution_time
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"Crawler timed out after {timeout} seconds")
        raise HTTPException(
            status_code=504,
            detail=f"Crawler timed out after {timeout} seconds"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse crawler output: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to parse crawler output"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        # Clean up the temporary file
        try:
            os.unlink(output_file)
        except Exception:
            pass


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the API status and whether the crawler binary is available.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        crawler_available=CRAWLER_BINARY.exists()
    )


@app.post(
    "/crawl",
    response_model=CrawlResponse,
    responses={
        200: {"description": "Successful crawl"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Crawler error"},
        504: {"model": ErrorResponse, "description": "Timeout"}
    },
    tags=["Crawling"]
)
async def crawl_website(request: CrawlRequest):
    """
    Crawl a website with full control over all crawling parameters.
    
    This endpoint performs multi-page crawling with configurable depth,
    link extraction, filtering, and more. Perfect for comprehensive
    website scraping tasks.
    
    **Parameters:**
    - **url**: Starting URL (required)
    - **extract_links**: Extract links from pages (default: false)
    - **depth**: Maximum crawl depth, 0-5 (default: 1)
    - **max_pages**: Maximum pages to crawl, 1-100 (default: 20)
    - **workers**: Concurrent workers, 1-10 (default: 2)
    - **stay_domain**: Stay on same domain (default: true)
    - **filter**: Only crawl URLs containing this string
    - **seed_only**: Crawl only the seed URL (default: false)
    - **news**: Extract news article content (default: false)
    - **delay**: Delay between requests in seconds, 0-10 (default: 1)
    - **timeout**: Request timeout in seconds, 5-60 (default: 10)
    - **verbose**: Enable verbose output (default: false)
    """
    # Build crawler arguments
    crawler_args = ["-seed", request.url]
    
    if request.extract_links:
        crawler_args.append("-extract-links")
    
    crawler_args.extend(["-depth", str(request.depth)])
    crawler_args.extend(["-max", str(request.max_pages)])
    crawler_args.extend(["-workers", str(request.workers)])
    
    if not request.stay_domain:
        crawler_args.append("-stay-domain=false")
    
    if request.filter:
        crawler_args.extend(["-filter", request.filter])
    
    if request.seed_only:
        crawler_args.append("-seed-only")
    
    if request.news:
        crawler_args.append("-news")
    
    crawler_args.extend(["-delay", str(request.delay)])
    crawler_args.extend(["-timeout", str(request.timeout)])
    
    if request.verbose:
        crawler_args.append("-verbose")
    
    # Calculate timeout (give extra time for the subprocess)
    execution_timeout = request.timeout * request.max_pages + 30
    
    # Run the crawler
    result = await run_crawler(crawler_args, timeout=execution_timeout)
    
    return CrawlResponse(
        pages_crawled=len(result["data"]),
        pages=result["data"],
        execution_time_seconds=result["execution_time"]
    )


@app.post(
    "/scrape",
    response_model=ScrapeResponse,
    responses={
        200: {"description": "Successful scrape"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Scraper error"},
        504: {"model": ErrorResponse, "description": "Timeout"}
    },
    tags=["Scraping"]
)
async def scrape_page(request: ScrapeRequest):
    """
    Quickly scrape a single page and extract its content.
    
    This is a simplified endpoint for when you just need to get the
    title, description, and text content from one page. Optionally
    extract links as well.
    
    **Parameters:**
    - **url**: The URL to scrape (required)
    - **extract_links**: Also extract links (default: false)
    """
    # Use seed-only mode for quick scraping
    crawler_args = ["-seed", request.url, "-seed-only"]
    
    if request.extract_links:
        crawler_args.append("-extract-links")
    
    # Run the crawler with a shorter timeout
    result = await run_crawler(crawler_args, timeout=30)
    
    if not result["data"]:
        raise HTTPException(
            status_code=404,
            detail="No data returned from the page"
        )
    
    # Return the first (and only) page
    page = result["data"][0]
    
    return ScrapeResponse(**page)


@app.post(
    "/links",
    response_model=LinksResponse,
    responses={
        200: {"description": "Successfully extracted links"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Extraction error"},
        504: {"model": ErrorResponse, "description": "Timeout"}
    },
    tags=["Link Extraction"]
)
async def extract_links(request: LinksRequest):
    """
    Extract all links from a single page.
    
    Use this when you only need to discover what pages link from a
    given URL, without extracting the page content.
    
    **Parameters:**
    - **url**: The URL to extract links from (required)
    """
    # Use seed-only mode with link extraction
    crawler_args = ["-seed", request.url, "-seed-only", "-extract-links"]
    
    # Run the crawler
    result = await run_crawler(crawler_args, timeout=30)
    
    if not result["data"]:
        raise HTTPException(
            status_code=404,
            detail="No data returned from the page"
        )
    
    # Extract just the links
    page = result["data"][0]
    links = page.get("links", [])
    
    return LinksResponse(
        url=request.url,
        links_found=len(links),
        links=links
    )


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors"""
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# ============================================================================
# Startup/Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("Web Crawler API starting up")
    logger.info(f"Crawler binary: {CRAWLER_BINARY}")
    logger.info(f"Binary exists: {CRAWLER_BINARY.exists()}")


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information"""
    logger.info("Web Crawler API shutting down")


# ============================================================================
# Main (for local development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")

