package robotstxt

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"
)

type RobotsCache struct {
	cache      map[string]*RobotsData
	mutex      sync.RWMutex
	expiration time.Duration
}

type RobotsData struct {
	rules      map[string][]Rule
	createdAt  time.Time
	crawlDelay time.Duration
}

type Rule struct {
	path      string
	allow     bool
	userAgent string
}

func NewRobotsCache(expiration time.Duration) *RobotsCache {
	return &RobotsCache{
		cache:      make(map[string]*RobotsData),
		expiration: expiration,
	}
}

func (rc *RobotsCache) IsAllowed(rawURL, userAgent string) (bool, time.Duration, error) {
	parsedURL, err := url.Parse(rawURL)
	if err != nil {
		return false, 0, fmt.Errorf("failed to parse URL: %w", err)
	}

	host := parsedURL.Scheme + "://" + parsedURL.Host

	rc.mutex.RLock()
	robotsData, exists := rc.cache[host]
	rc.mutex.RUnlock()

	if !exists || time.Since(robotsData.createdAt) > rc.expiration {
		robotsData, err = rc.fetchAndParse(host, userAgent)
		if err != nil {
			return true, 1 * time.Second, fmt.Errorf("failed to fetch robots.txt: %w", err)
		}

		rc.mutex.Lock()
		rc.cache[host] = robotsData
		rc.mutex.Unlock()
	}

	path := parsedURL.Path
	if path == "" {
		path = "/"
	}

	allowed := rc.checkRules(robotsData, path, userAgent)
	if allowed != nil {
		return *allowed, robotsData.crawlDelay, nil
	}

	allowed = rc.checkRules(robotsData, path, "*")
	if allowed != nil {
		return *allowed, robotsData.crawlDelay, nil
	}

	return true, robotsData.crawlDelay, nil
}

func (rc *RobotsCache) checkRules(data *RobotsData, path, userAgent string) *bool {
	rules, exists := data.rules[userAgent]
	if !exists {
		return nil
	}

	for _, rule := range rules {
		if strings.HasPrefix(path, rule.path) {
			return &rule.allow
		}
	}

	return nil
}

func (rc *RobotsCache) fetchAndParse(host, userAgent string) (*RobotsData, error) {
	robotsURL := host + "/robots.txt"

	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	req, err := http.NewRequest("GET", robotsURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", userAgent)

	resp, err := client.Do(req)
	if err != nil {
		return defaultRobotsData()
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return defaultRobotsData()
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return defaultRobotsData()
	}

	return parseRobotsTxt(string(body)), nil
}

func parseRobotsTxt(content string) *RobotsData {
	data := &RobotsData{
		rules:      make(map[string][]Rule),
		createdAt:  time.Now(),
		crawlDelay: 1 * time.Second,
	}

	lines := strings.Split(content, "\n")
	var currentUserAgent string

	for _, line := range lines {
		line = strings.TrimSpace(line)

		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}

		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}

		field := strings.TrimSpace(strings.ToLower(parts[0]))
		value := strings.TrimSpace(parts[1])

		switch field {
		case "user-agent":
			currentUserAgent = value
			if _, exists := data.rules[currentUserAgent]; !exists {
				data.rules[currentUserAgent] = make([]Rule, 0)
			}
		case "disallow":
			if currentUserAgent != "" && value != "" {
				rule := Rule{
					path:      value,
					allow:     false,
					userAgent: currentUserAgent,
				}
				data.rules[currentUserAgent] = append(data.rules[currentUserAgent], rule)
			}
		case "allow":
			if currentUserAgent != "" && value != "" {
				rule := Rule{
					path:      value,
					allow:     true,
					userAgent: currentUserAgent,
				}
				data.rules[currentUserAgent] = append(data.rules[currentUserAgent], rule)
			}
		case "crawl-delay":
			if delay, err := time.ParseDuration(value + "s"); err == nil && delay > 0 {
				data.crawlDelay = delay
			}
		}
	}

	return data
}

func defaultRobotsData() (*RobotsData, error) {
	return &RobotsData{
		rules:      make(map[string][]Rule),
		createdAt:  time.Now(),
		crawlDelay: 1 * time.Second,
	}, nil
}
