package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/user/gocrawler/pkg/crawler"
	"github.com/user/gocrawler/pkg/frontier"
	"github.com/user/gocrawler/pkg/storage"
)

func main() {
	seedURL := flag.String("seed", "", "Seed URL to start crawling from (required)")
	outputFile := flag.String("output", "results.json", "Output file name")
	outputFormat := flag.String("format", "json", "Output format: json or csv")
	workerCount := flag.Int("workers", 2, "Number of concurrent workers")
	depth := flag.Int("depth", 1, "Maximum crawl depth")
	delay := flag.Int("delay", 1, "Delay between requests in seconds")
	timeout := flag.Int("timeout", 10, "Request timeout in seconds")
	respectRobots := flag.Bool("robots", true, "Respect robots.txt")
	newsOnly := flag.Bool("news", false, "Extract only news article content")
	maxPages := flag.Int("max", 20, "Maximum number of pages to crawl")
	userAgent := flag.String("agent", "GoCrawler/1.0", "User-Agent string")
	verbose := flag.Bool("verbose", false, "Verbose output")
	stayOnDomain := flag.Bool("stay-domain", true, "Stay on the same domain as the seed URL")
	urlFilter := flag.String("filter", "", "Only crawl URLs containing this string (e.g., '/wiki/')")
	seedOnly := flag.Bool("seed-only", false, "Crawl only the seed URL, don't follow any links")

	flag.Parse()

	if *seedURL == "" {
		fmt.Println("Error: seed URL is required")
		flag.Usage()
		os.Exit(1)
	}

	var store storage.Storage
	var err error
	switch *outputFormat {
	case "json":
		store, err = storage.NewJSONStorage(*outputFile)
	case "csv":
		store, err = storage.NewCSVStorage(*outputFile)
	default:
		fmt.Printf("Unsupported output format: %s, defaulting to JSON\n", *outputFormat)
		store, err = storage.NewJSONStorage(*outputFile)
	}

	if err != nil {
		log.Fatalf("Failed to initialize storage: %v", err)
	}
	defer store.Close()

	urlFrontier := frontier.NewURLFrontier()
	urlFrontier.Add(*seedURL, 0)

	crawlerConfig := crawler.Config{
		MaxDepth:      *depth,
		WorkerCount:   *workerCount,
		Delay:         time.Duration(*delay) * time.Second,
		Timeout:       time.Duration(*timeout) * time.Second,
		MaxPages:      *maxPages,
		RespectRobots: *respectRobots,
		UserAgent:     *userAgent,
		NewsOnly:      *newsOnly,
		Verbose:       *verbose,
		StayOnDomain:  *stayOnDomain,
		URLFilter:     *urlFilter,
		SeedOnly:      *seedOnly,
	}

	c := crawler.New(crawlerConfig, urlFrontier, store)

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		if err := c.Start(); err != nil {
			log.Printf("Crawler error: %v", err)
		}
	}()

	select {
	case sig := <-sigChan:
		fmt.Printf("\nReceived signal %v, shutting down gracefully...\n", sig)
		c.Stop()
	case <-c.Done():
		fmt.Println("\nCrawling completed successfully!")
	}

	wg.Wait()
	fmt.Printf("Crawled %d pages. Results saved to %s\n", c.Stats().PagesCrawled, *outputFile)
}
