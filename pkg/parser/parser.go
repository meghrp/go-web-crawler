package parser

import (
	"net/url"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"golang.org/x/net/html"
)

// Represents the parsed data from a webpage
type Result struct {
	Title       string
	Description string
	Content     string
	Links       []string
}

func Parse(htmlContent string, baseURL string, extractNewsContent bool) (*Result, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return nil, err
	}

	result := &Result{
		Links: make([]string, 0),
	}

	result.Title = doc.Find("title").Text()

	doc.Find("meta[name='description']").Each(func(i int, s *goquery.Selection) {
		if content, exists := s.Attr("content"); exists {
			result.Description = content
		}
	})

	if result.Description == "" {
		doc.Find("meta[property='og:description']").Each(func(i int, s *goquery.Selection) {
			if content, exists := s.Attr("content"); exists {
				result.Description = content
			}
		})
	}

	if extractNewsContent {
		articleBody := doc.Find("[itemprop='articleBody']").Text()
		if articleBody != "" {
			result.Content = articleBody
		} else {
			article := doc.Find("article").First()
			if article.Length() > 0 {
				result.Content = article.Text()
			} else {
				selectors := []string{
					".article-content", ".post-content", ".entry-content",
					"#article-body", "#story-body", ".story-body",
					"main p", ".content p",
				}

				for _, selector := range selectors {
					content := ""
					doc.Find(selector).Each(func(i int, s *goquery.Selection) {
						content += s.Text() + "\n"
					})

					if content != "" {
						result.Content = strings.TrimSpace(content)
						break
					}
				}
			}
		}
	} else {
		var mainContent strings.Builder
		doc.Find("p").Each(func(i int, s *goquery.Selection) {
			text := strings.TrimSpace(s.Text())
			if text != "" {
				mainContent.WriteString(text)
				mainContent.WriteString("\n")
			}
		})
		result.Content = mainContent.String()
	}

	doc.Find("a[href]").Each(func(i int, s *goquery.Selection) {
		href, exists := s.Attr("href")
		if !exists || href == "" || strings.HasPrefix(href, "#") {
			return
		}

		absoluteURL, err := resolveURL(baseURL, href)
		if err != nil {
			return
		}

		if !strings.HasPrefix(absoluteURL, "http://") && !strings.HasPrefix(absoluteURL, "https://") {
			return
		}

		if shouldSkipURL(absoluteURL) {
			return
		}

		result.Links = append(result.Links, absoluteURL)
	})

	return result, nil
}

func resolveURL(baseURL, href string) (string, error) {
	base, err := url.Parse(baseURL)
	if err != nil {
		return "", err
	}

	relative, err := url.Parse(href)
	if err != nil {
		return "", err
	}

	resolvedURL := base.ResolveReference(relative)
	return resolvedURL.String(), nil
}

func shouldSkipURL(rawURL string) bool {
	skipExtensions := []string{
		".pdf", ".jpg", ".jpeg", ".png", ".gif", ".css", ".js",
		".ico", ".svg", ".xml", ".json", ".mp3", ".mp4", ".avi",
		".mov", ".mpg", ".mpeg", ".zip", ".tar", ".gz", ".rar",
	}

	lowercaseURL := strings.ToLower(rawURL)

	for _, ext := range skipExtensions {
		if strings.HasSuffix(lowercaseURL, ext) {
			return true
		}
	}

	skipPatterns := []string{
		"/cdn-cgi/", "/wp-admin/", "/wp-includes/",
		"javascript:", "mailto:", "tel:", "sms:",
		"/feed/", "/rss/", "/print/", "/search?",
		"login", "logout", "signin", "signup", "register",
	}

	for _, pattern := range skipPatterns {
		if strings.Contains(lowercaseURL, pattern) {
			return true
		}
	}

	return false
}

func StripTags(html string) string {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
	if err != nil {
		return html
	}
	return strings.TrimSpace(doc.Text())
}

func ExtractText(n *html.Node) string {
	if n.Type == html.TextNode {
		return n.Data
	}
	if n.Type != html.ElementNode {
		return ""
	}

	var result string
	for c := n.FirstChild; c != nil; c = c.NextSibling {
		result += ExtractText(c)
	}
	return result
}
