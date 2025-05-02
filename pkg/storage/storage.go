package storage

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"
)

type PageData struct {
	URL         string    `json:"url"`
	Title       string    `json:"title"`
	Description string    `json:"description"`
	Content     string    `json:"content,omitempty"`
	Links       []string  `json:"links,omitempty"`
	CrawledAt   time.Time `json:"crawled_at"`
	Depth       int       `json:"depth"`
}

type Storage interface {
	Save(data PageData) error
	Close() error
}

type JSONStorage struct {
	file      *os.File
	encoder   *json.Encoder
	mutex     sync.Mutex
	dataItems []PageData
}

func NewJSONStorage(filename string) (*JSONStorage, error) {
	file, err := os.Create(filename)
	if err != nil {
		return nil, fmt.Errorf("failed to create JSON file: %w", err)
	}

	return &JSONStorage{
		file:      file,
		encoder:   json.NewEncoder(file),
		dataItems: make([]PageData, 0),
	}, nil
}

func (j *JSONStorage) Save(data PageData) error {
	j.mutex.Lock()
	defer j.mutex.Unlock()
	j.dataItems = append(j.dataItems, data)
	return nil
}

func (j *JSONStorage) Close() error {
	j.mutex.Lock()
	defer j.mutex.Unlock()

	if _, err := j.file.Seek(0, 0); err != nil {
		return fmt.Errorf("failed to reset file position: %w", err)
	}

	if err := j.file.Truncate(0); err != nil {
		return fmt.Errorf("failed to truncate file: %w", err)
	}

	if err := json.NewEncoder(j.file).Encode(j.dataItems); err != nil {
		return fmt.Errorf("failed to encode JSON data: %w", err)
	}

	return j.file.Close()
}

type CSVStorage struct {
	file    *os.File
	writer  *csv.Writer
	mutex   sync.Mutex
	headers []string
}

func NewCSVStorage(filename string) (*CSVStorage, error) {
	file, err := os.Create(filename)
	if err != nil {
		return nil, fmt.Errorf("failed to create CSV file: %w", err)
	}

	writer := csv.NewWriter(file)
	headers := []string{"URL", "Title", "Description", "Content", "Links", "CrawledAt", "Depth"}

	if err := writer.Write(headers); err != nil {
		file.Close()
		return nil, fmt.Errorf("failed to write CSV headers: %w", err)
	}
	writer.Flush()

	return &CSVStorage{
		file:    file,
		writer:  writer,
		headers: headers,
	}, nil
}

func (c *CSVStorage) Save(data PageData) error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	linksStr := ""
	for i, link := range data.Links {
		if i > 0 {
			linksStr += ","
		}
		linksStr += link
	}

	record := []string{
		data.URL,
		data.Title,
		data.Description,
		data.Content,
		linksStr,
		data.CrawledAt.Format(time.RFC3339),
		fmt.Sprintf("%d", data.Depth),
	}

	if err := c.writer.Write(record); err != nil {
		return fmt.Errorf("failed to write CSV record: %w", err)
	}

	c.writer.Flush()
	return c.writer.Error()
}

func (c *CSVStorage) Close() error {
	c.mutex.Lock()
	defer c.mutex.Unlock()
	c.writer.Flush()
	return c.file.Close()
}
