package crawler

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/user/gocrawler/pkg/frontier"
	"github.com/user/gocrawler/pkg/parser"
	"github.com/user/gocrawler/pkg/robotstxt"
	"github.com/user/gocrawler/pkg/storage"
)

type Config struct {
	MaxDepth      int
	WorkerCount   int
	Delay         time.Duration
	Timeout       time.Duration
	MaxPages      int
	RespectRobots bool
	UserAgent     string
	NewsOnly      bool
	Verbose       bool
	StayOnDomain  bool
	URLFilter     string
	SeedOnly      bool
	ExtractLinks  bool
}

type Statistics struct {
	PagesCrawled    int
	LinksDiscovered int
	StartTime       time.Time
	EndTime         time.Time
}

type Crawler struct {
	config     Config
	frontier   *frontier.URLFrontier
	storage    storage.Storage
	robots     *robotstxt.RobotsCache
	httpClient *http.Client
	done       chan struct{}
	stats      Statistics
	wg         sync.WaitGroup
	ctx        context.Context
	cancel     context.CancelFunc
	mutex      sync.Mutex
}

func New(config Config, frontier *frontier.URLFrontier, storage storage.Storage) *Crawler {
	ctx, cancel := context.WithCancel(context.Background())

	httpClient := &http.Client{
		Timeout: config.Timeout,
		Transport: &http.Transport{
			MaxIdleConns:        100,
			MaxIdleConnsPerHost: 10,
			IdleConnTimeout:     30 * time.Second,
		},
	}

	return &Crawler{
		config:     config,
		frontier:   frontier,
		storage:    storage,
		robots:     robotstxt.NewRobotsCache(24 * time.Hour),
		httpClient: httpClient,
		done:       make(chan struct{}),
		stats: Statistics{
			StartTime: time.Now(),
		},
		ctx:    ctx,
		cancel: cancel,
	}
}

func (c *Crawler) Start() error {
	if c.config.Verbose {
		fmt.Println("Starting crawler with", c.config.WorkerCount, "workers")
	}

	rateLimiter := make(chan struct{}, c.config.WorkerCount)

	hostLimiters := make(map[string]chan time.Time)
	hostLimitersMutex := sync.Mutex{}

	for i := 0; i < c.config.WorkerCount; i++ {
		c.wg.Add(1)
		go c.worker(i, rateLimiter, hostLimiters, &hostLimitersMutex)
	}

	c.wg.Wait()

	c.stats.EndTime = time.Now()

	close(c.done)

	if c.config.Verbose {
		fmt.Println("Crawling completed. Crawled", c.stats.PagesCrawled, "pages")
	}

	return nil
}

func (c *Crawler) Stop() {
	c.cancel()
}

func (c *Crawler) Done() <-chan struct{} {
	return c.done
}

func (c *Crawler) Stats() Statistics {
	c.mutex.Lock()
	defer c.mutex.Unlock()
	return c.stats
}

func (c *Crawler) worker(id int, rateLimiter chan struct{}, hostLimiters map[string]chan time.Time, hostLimitersMutex *sync.Mutex) {
	defer c.wg.Done()

	for {
		select {
		case <-c.ctx.Done():
			return
		default:
		}

		c.mutex.Lock()
		if c.config.MaxPages > 0 && c.stats.PagesCrawled >= c.config.MaxPages {
			c.mutex.Unlock()
			return
		}
		c.mutex.Unlock()

		urlStr, depth, ok := c.frontier.Next()
		if !ok {
			return
		}

		if depth > c.config.MaxDepth {
			continue
		}

		rateLimiter <- struct{}{}

		parsedURL, err := url.Parse(urlStr)
		if err == nil {
			host := parsedURL.Host
			hostLimitersMutex.Lock()
			limiter, exists := hostLimiters[host]
			if !exists {
				limiter = make(chan time.Time, 1)
				hostLimiters[host] = limiter
				limiter <- time.Now()
			}
			hostLimitersMutex.Unlock()

			lastTime := <-limiter
			sleepTime := c.config.Delay - time.Since(lastTime)
			if sleepTime > 0 {
				time.Sleep(sleepTime)
			}

			limiter <- time.Now()
		}

		c.processURL(urlStr, depth)

		<-rateLimiter
	}
}

func (c *Crawler) processURL(urlStr string, depth int) {
	if c.config.RespectRobots {
		allowed, delay, err := c.robots.IsAllowed(urlStr, c.config.UserAgent)
		if err != nil && c.config.Verbose {
			fmt.Printf("Warning: Robots.txt error for %s: %v\n", urlStr, err)
		}

		if !allowed {
			if c.config.Verbose {
				fmt.Printf("Skipping %s - disallowed by robots.txt\n", urlStr)
			}
			return
		}

		if delay > c.config.Delay {
			time.Sleep(delay - c.config.Delay)
		}
	}

	if c.config.Verbose {
		fmt.Printf("Crawling [depth:%d] %s\n", depth, urlStr)
	}

	html, err := c.fetchURL(urlStr)
	if err != nil {
		if c.config.Verbose {
			fmt.Printf("Error fetching %s: %v\n", urlStr, err)
		}
		return
	}

	result, err := parser.Parse(html, urlStr, c.config.NewsOnly, c.config.ExtractLinks)
	if err != nil {
		if c.config.Verbose {
			fmt.Printf("Error parsing %s: %v\n", urlStr, err)
		}
		return
	}

	c.mutex.Lock()
	c.stats.PagesCrawled++
	c.stats.LinksDiscovered += len(result.Links)
	c.mutex.Unlock()

	err = c.storage.Save(storage.PageData{
		URL:         urlStr,
		Title:       result.Title,
		Description: result.Description,
		Content:     result.Content,
		Links:       result.Links,
		CrawledAt:   time.Now(),
		Depth:       depth,
	})

	if err != nil && c.config.Verbose {
		fmt.Printf("Error saving data for %s: %v\n", urlStr, err)
	}

	if c.config.SeedOnly {
		return
	}

	var seedDomain string
	if c.config.StayOnDomain {
		parsedURL, err := url.Parse(urlStr)
		if err == nil {
			seedDomain = parsedURL.Host
		}
	}

	for _, link := range result.Links {
		if c.config.StayOnDomain {
			parsedLink, err := url.Parse(link)
			if err != nil || parsedLink.Host != seedDomain {
				continue
			}
		}

		if c.config.URLFilter != "" && !strings.Contains(link, c.config.URLFilter) {
			continue
		}

		c.frontier.Add(link, depth+1)
	}
}

func (c *Crawler) fetchURL(url string) (string, error) {
	req, err := http.NewRequestWithContext(c.ctx, "GET", url, nil)
	if err != nil {
		return "", err
	}

	req.Header.Set("User-Agent", c.config.UserAgent)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("unexpected status code: %d", resp.StatusCode)
	}

	contentType := resp.Header.Get("Content-Type")
	if !strings.Contains(contentType, "text/html") && !strings.Contains(contentType, "application/xhtml+xml") {
		return "", fmt.Errorf("non-HTML content type: %s", contentType)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	return string(body), nil
}
