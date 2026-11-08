package tsetmc

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	// DefaultBaseURL is the official TSETMC CDN API endpoint.
	DefaultBaseURL = "https://cdn.tsetmc.com/api"
	// DefaultUserAgent mimics a modern desktop Chrome browser.
	DefaultUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
	// DefaultMaxRetries is the default number of retry attempts for 429/5xx.
	DefaultMaxRetries = 3
	// DefaultBackoffBase is the base duration for exponential backoff.
	DefaultBackoffBase = 100 * time.Millisecond
	// DefaultMaxBackoff is the upper limit for backoff delay.
	DefaultMaxBackoff = 30 * time.Second
)

// Client handles HTTP communication with TSETMC API endpoints.
type Client struct {
	HTTPClient  *http.Client
	BaseURL     string
	UserAgent   string
	MaxRetries  int
	BackoffBase time.Duration
	MaxBackoff  time.Duration
}

// NewClient creates a new TSETMC API client.
func NewClient(baseURL string, httpClient *http.Client) *Client {
	if baseURL == "" {
		baseURL = os.Getenv("TSETMC_BASE_URL")
	}
	if baseURL == "" {
		baseURL = DefaultBaseURL
	}
	baseURL = strings.TrimRight(baseURL, "/")

	if httpClient == nil {
		httpClient = &http.Client{
			Timeout: 30 * time.Second,
		}
	}

	return &Client{
		HTTPClient:  httpClient,
		BaseURL:     baseURL,
		UserAgent:   DefaultUserAgent,
		MaxRetries:  DefaultMaxRetries,
		BackoffBase: DefaultBackoffBase,
		MaxBackoff:  DefaultMaxBackoff,
	}
}

// GetJSON performs an HTTP GET request to the specified endpoint with retry,
// backoff for 429/5xx errors, standard headers, and JSON decoding into target.
func (c *Client) GetJSON(ctx context.Context, endpoint string, target any) error {
	httpClient := c.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 30 * time.Second}
	}

	baseURL := c.BaseURL
	if baseURL == "" {
		baseURL = DefaultBaseURL
	}
	baseURL = strings.TrimRight(baseURL, "/")

	ua := c.UserAgent
	if ua == "" {
		ua = DefaultUserAgent
	}

	maxRetries := c.MaxRetries
	if maxRetries <= 0 {
		maxRetries = DefaultMaxRetries
	}

	backoffBase := c.BackoffBase
	if backoffBase <= 0 {
		backoffBase = DefaultBackoffBase
	}

	maxBackoff := c.MaxBackoff
	if maxBackoff <= 0 {
		maxBackoff = DefaultMaxBackoff
	}

	// Resolve full URL
	var fullURL string
	if strings.HasPrefix(endpoint, "http://") || strings.HasPrefix(endpoint, "https://") {
		fullURL = endpoint
	} else {
		fullURL = baseURL + "/" + strings.TrimPrefix(endpoint, "/")
	}

	var lastErr error

	for attempt := 0; attempt <= maxRetries; attempt++ {
		// Context check before request
		if err := ctx.Err(); err != nil {
			return err
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, fullURL, nil)
		if err != nil {
			return fmt.Errorf("create request: %w", err)
		}

		// Standard TSETMC headers
		req.Header.Set("User-Agent", ua)
		req.Header.Set("Accept", "application/json, text/plain, */*")
		req.Header.Set("Referer", "https://tsetmc.com/")
		req.Header.Set("Origin", "https://tsetmc.com")

		resp, err := httpClient.Do(req)
		if err != nil {
			lastErr = err
			if attempt == maxRetries {
				return fmt.Errorf("request failed: %w", lastErr)
			}
			if sleepErr := sleepWithBackoff(ctx, backoffBase, maxBackoff, attempt); sleepErr != nil {
				return sleepErr
			}
			continue
		}

		body, readErr := io.ReadAll(resp.Body)
		_ = resp.Body.Close()
		if readErr != nil {
			lastErr = readErr
			if attempt == maxRetries {
				return fmt.Errorf("read body: %w", lastErr)
			}
			if sleepErr := sleepWithBackoff(ctx, backoffBase, maxBackoff, attempt); sleepErr != nil {
				return sleepErr
			}
			continue
		}

		// Success status codes
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			if target != nil {
				if err := json.Unmarshal(body, target); err != nil {
					return fmt.Errorf("decode json from %s: %w", fullURL, err)
				}
			}
			return nil
		}

		// 429 Too Many Requests
		if resp.StatusCode == http.StatusTooManyRequests {
			lastErr = fmt.Errorf("HTTP 429: %s", http.StatusText(resp.StatusCode))
			if attempt == maxRetries {
				return lastErr
			}

			retryAfter := parseRetryAfter(resp.Header.Get("Retry-After"))
			if retryAfter > 0 {
				select {
				case <-time.After(retryAfter):
					continue
				case <-ctx.Done():
					return ctx.Err()
				}
			}

			if sleepErr := sleepWithBackoff(ctx, backoffBase, maxBackoff, attempt); sleepErr != nil {
				return sleepErr
			}
			continue
		}

		// 5xx Server Errors
		if resp.StatusCode >= 500 && resp.StatusCode <= 599 {
			lastErr = fmt.Errorf("HTTP %d: %s", resp.StatusCode, http.StatusText(resp.StatusCode))
			if attempt == maxRetries {
				return lastErr
			}
			if sleepErr := sleepWithBackoff(ctx, backoffBase, maxBackoff, attempt); sleepErr != nil {
				return sleepErr
			}
			continue
		}

		// Other HTTP errors (4xx non-429, 3xx)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, http.StatusText(resp.StatusCode))
	}

	if lastErr != nil {
		return lastErr
	}
	return errors.New("request exhausted retries without response")
}

func parseRetryAfter(val string) time.Duration {
	val = strings.TrimSpace(val)
	if val == "" {
		return 0
	}
	if secs, err := strconv.Atoi(val); err == nil && secs > 0 {
		return time.Duration(secs) * time.Second
	}
	if t, err := http.ParseTime(val); err == nil {
		diff := time.Until(t)
		if diff > 0 {
			return diff
		}
	}
	return 0
}

func sleepWithBackoff(ctx context.Context, base, max time.Duration, attempt int) error {
	shift := attempt
	if shift > 10 {
		shift = 10
	}
	delay := base * (1 << shift)
	if delay > max {
		delay = max
	}
	select {
	case <-time.After(delay):
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
