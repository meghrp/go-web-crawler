package frontier

import (
	"net/url"
	"sync"
)

type URLItem struct {
	URL   string
	Depth int
}

// Manages the queue of URLs to crawl
type URLFrontier struct {
	queue      []URLItem
	visited    map[string]bool
	mutex      sync.Mutex
	normalized map[string]bool
}

func NewURLFrontier() *URLFrontier {
	return &URLFrontier{
		queue:      make([]URLItem, 0),
		visited:    make(map[string]bool),
		normalized: make(map[string]bool),
	}
}

func (f *URLFrontier) Add(rawURL string, depth int) bool {
	f.mutex.Lock()
	defer f.mutex.Unlock()

	if f.visited[rawURL] {
		return false
	}

	parsedURL, err := url.Parse(rawURL)
	if err != nil {
		return false
	}

	normalized := parsedURL.Scheme + "://" + parsedURL.Host + parsedURL.Path

	if f.normalized[normalized] {
		return false
	}

	f.visited[rawURL] = true
	f.normalized[normalized] = true

	f.queue = append(f.queue, URLItem{URL: rawURL, Depth: depth})
	return true
}

func (f *URLFrontier) Next() (string, int, bool) {
	f.mutex.Lock()
	defer f.mutex.Unlock()

	if len(f.queue) == 0 {
		return "", 0, false
	}

	item := f.queue[0]
	f.queue = f.queue[1:]
	return item.URL, item.Depth, true
}

func (f *URLFrontier) HasNext() bool {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	return len(f.queue) > 0
}

func (f *URLFrontier) Size() int {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	return len(f.queue)
}

func (f *URLFrontier) VisitedCount() int {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	return len(f.visited)
}

func (f *URLFrontier) Visited(rawURL string) bool {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	return f.visited[rawURL]
}

func (f *URLFrontier) Clear() {
	f.mutex.Lock()
	defer f.mutex.Unlock()
	f.queue = make([]URLItem, 0)
	f.visited = make(map[string]bool)
	f.normalized = make(map[string]bool)
}
