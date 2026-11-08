package codal

import (
	"context"
	"crypto/rand"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	defaultMaxConcurrency = 2
	defaultMaxRetries     = 3
	defaultBaseDelay      = 500 * time.Millisecond
	defaultMaxDelay       = 60 * time.Second
	defaultMinRequestGap  = 500 * time.Millisecond
	defaultBaseURL        = "https://search.codal.ir"
)

// PoliteClientConfig تنظیمات کلاینت مؤدب کدال.
type PoliteClientConfig struct {
	MaxConcurrency int
	MaxRetries     int
	BaseDelay      time.Duration
	MaxDelay       time.Duration
	MinRequestGap  time.Duration
	HTTPClient     *http.Client
	BaseURL        string
}

// PoliteClient کلاینت HTTP با پشتیبانی از Retry-After، سقف هم‌زمانی ۲ و بک‌آف نمایی با Jitter.
type PoliteClient struct {
	client        *http.Client
	baseURL       string
	sem           chan struct{}
	maxRetries    int
	baseDelay     time.Duration
	maxDelay      time.Duration
	minRequestGap time.Duration

	mu          sync.Mutex
	lastReqTime time.Time
}

// NewPoliteClient یک نمونه جدید از PoliteClient می‌سازد.
func NewPoliteClient(configs ...PoliteClientConfig) *PoliteClient {
	cfg := PoliteClientConfig{}
	if len(configs) > 0 {
		cfg = configs[0]
	}

	maxConc := cfg.MaxConcurrency
	if maxConc <= 0 {
		maxConc = defaultMaxConcurrency
	}

	maxRetries := cfg.MaxRetries
	if maxRetries <= 0 {
		maxRetries = defaultMaxRetries
	}

	baseDelay := cfg.BaseDelay
	if baseDelay <= 0 {
		baseDelay = defaultBaseDelay
	}

	maxDelay := cfg.MaxDelay
	if maxDelay <= 0 {
		maxDelay = defaultMaxDelay
	}

	minGap := cfg.MinRequestGap
	if minGap <= 0 {
		minGap = defaultMinRequestGap
	}

	httpClient := cfg.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{
			Timeout: 60 * time.Second,
		}
	}

	bURL := cfg.BaseURL
	if bURL == "" {
		bURL = os.Getenv("CODAL_BASE_URL")
	}
	if bURL == "" {
		bURL = defaultBaseURL
	}
	bURL = strings.TrimRight(bURL, "/")

	return &PoliteClient{
		client:        httpClient,
		baseURL:       bURL,
		sem:           make(chan struct{}, maxConc),
		maxRetries:    maxRetries,
		baseDelay:     baseDelay,
		maxDelay:      maxDelay,
		minRequestGap: minGap,
	}
}

// BaseURL آدرس پایه فعلی کلاینت را برمی‌گرداند.
func (c *PoliteClient) BaseURL() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.baseURL
}

// SetBaseURL آدرس پایه را تغییر می‌دهد (مخصوصاً برای تست‌ها).
func (c *PoliteClient) SetBaseURL(u string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.baseURL = strings.TrimRight(u, "/")
}

// Get ارسال درخواست HTTP GET مؤدب با مدیریت هم‌زمانی، فاصله درخواست‌ها، Retry-After و بک‌آف.
func (c *PoliteClient) Get(ctx context.Context, targetURL string) ([]byte, int, error) {
	// ۱. رعایت سقف هم‌زمانی با semaphore
	select {
	case c.sem <- struct{}{}:
		defer func() { <-c.sem }()
	case <-ctx.Done():
		return nil, 0, ctx.Err()
	}

	var lastBody []byte
	var lastStatus int
	var lastErr error

	for attempt := 0; attempt <= c.maxRetries; attempt++ {
		// ۲. بررسی لغو Context قبل از اقدام
		if err := ctx.Err(); err != nil {
			return nil, 0, err
		}

		// ۳. اعمال حداقل فاصله بین درخواست‌ها (Rate Limiting)
		c.throttle(ctx)
		if err := ctx.Err(); err != nil {
			return nil, 0, err
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodGet, targetURL, nil)
		if err != nil {
			return nil, 0, fmt.Errorf("create request: %w", err)
		}

		// سرفصل‌های استاندارد مرورگر دسکتاپ
		req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
		req.Header.Set("Accept", "application/json, text/plain, */*")
		req.Header.Set("Accept-Language", "fa-IR,fa;q=0.9,en-US;q=0.8")
		req.Header.Set("Referer", "https://codal.ir/")

		resp, err := c.client.Do(req)
		if err != nil {
			lastErr = err
			if attempt == c.maxRetries {
				return nil, 0, lastErr
			}
			c.sleepBackoff(ctx, attempt, 0)
			continue
		}

		body, readErr := io.ReadAll(resp.Body)
		_ = resp.Body.Close()
		if readErr != nil {
			lastErr = readErr
			if attempt == c.maxRetries {
				return nil, resp.StatusCode, lastErr
			}
			c.sleepBackoff(ctx, attempt, 0)
			continue
		}

		lastStatus = resp.StatusCode
		lastBody = body

		// پاسخ موفق (۲۰۰ تا ۲۹۹)
		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return body, resp.StatusCode, nil
		}

		// در صورت دریافت ۴۲۹: اولویت قطعی هدر Retry-After
		if resp.StatusCode == http.StatusTooManyRequests {
			if attempt == c.maxRetries {
				return body, resp.StatusCode, nil
			}
			retryAfter := parseRetryAfter(resp.Header.Get("Retry-After"))
			if retryAfter > 0 {
				select {
				case <-time.After(retryAfter):
					continue
				case <-ctx.Done():
					return nil, resp.StatusCode, ctx.Err()
				}
			}
			// اگر سرفصل Retry-After ارسال نشده بود، از بک‌آف نمایی استفاده می‌شود
			c.sleepBackoff(ctx, attempt, 0)
			continue
		}

		// خطاهای گذرا سرور (5xx)
		if resp.StatusCode >= 500 && resp.StatusCode <= 599 {
			if attempt == c.maxRetries {
				return body, resp.StatusCode, nil
			}
			c.sleepBackoff(ctx, attempt, 0)
			continue
		}

		// سایر خطاهای کلاینت (مانند ۴۰۰، ۴۰۱، ۴۰۳، ۴۰۴) بدون تکرار بازگردانده می‌شوند
		return body, resp.StatusCode, nil
	}

	return lastBody, lastStatus, lastErr
}

// throttle ایجاد وقفه لازم برای حفظ سقف ۲ درخواست در ثانیه.
func (c *PoliteClient) throttle(ctx context.Context) {
	c.mu.Lock()
	now := time.Now()
	gap := now.Sub(c.lastReqTime)
	var wait time.Duration
	if gap < c.minRequestGap {
		wait = c.minRequestGap - gap
	}
	c.lastReqTime = now.Add(wait)
	c.mu.Unlock()

	if wait > 0 {
		select {
		case <-time.After(wait):
		case <-ctx.Done():
		}
	}
}

// sleepBackoff محاسبه زمان بک‌آف نمایی همراه با Jitter تصادفی.
func (c *PoliteClient) sleepBackoff(ctx context.Context, attempt int, explicitDuration time.Duration) {
	if explicitDuration > 0 {
		select {
		case <-time.After(explicitDuration):
		case <-ctx.Done():
		}
		return
	}

	// T = min(maxDelay, baseDelay * 2^attempt)
	delay := c.baseDelay * (1 << attempt)
	if delay > c.maxDelay {
		delay = c.maxDelay
	}

	// Jitter: افزودن صفر تا ۲۵٪ تاخیر به عنوان انحراف تصادفی
	jitter := time.Duration(0)
	if delay > 0 {
		maxJitter := delay / 4
		if maxJitter > 0 {
			if n, err := rand.Int(rand.Reader, big.NewInt(int64(maxJitter))); err == nil {
				jitter = time.Duration(n.Int64())
			}
		}
	}

	total := delay + jitter
	select {
	case <-time.After(total):
	case <-ctx.Done():
	}
}

// parseRetryAfter استخراج زمان انتظار از سرفصل Retry-After (به ثانیه یا تاریخ HTTP).
func parseRetryAfter(headerVal string) time.Duration {
	val := strings.TrimSpace(headerVal)
	if val == "" {
		return 0
	}

	// ۱. تلاش برای خواندن عدد صحیح (ثانیه)
	if sec, err := strconv.Atoi(val); err == nil {
		if sec > 0 {
			return time.Duration(sec) * time.Second
		}
		return 0
	}

	// ۲. تلاش برای خواندن تاریخ استاندارد HTTP
	if t, err := http.ParseTime(val); err == nil {
		d := time.Until(t)
		if d > 0 {
			return d
		}
	}

	return 0
}
