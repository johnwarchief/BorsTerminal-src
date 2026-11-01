package marketindex

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"sort"
	"strconv"
	"sync"
	"time"

	"borsterminal/backend/internal/candle"
	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/pyround"
)

const (
	TedpixInsCode     = "32097828799138957"
	TedpixSymbol      = "شاخص کل"
	IndexCDNTmpl      = "https://cdn.tsetmc.com/api/Index/GetIndexB2History/%s"
	IndexSource       = "tsetmc:cdn/Index/GetIndexB2History"
	IndexCacheTTL     = 600 * time.Second
	IndexHTTPTimeout  = 25 * time.Second
)

type rawIndexItem struct {
	InsCode          any     `json:"insCode"`
	DEven            any     `json:"dEven"`
	XNivInuClMresIbs float64 `json:"xNivInuClMresIbs"` // شاخص کل پایانی
	XNivInuPhMresIbs float64 `json:"xNivInuPhMresIbs"` // بیشترین
	XNivInuPbMresIbs float64 `json:"xNivInuPbMresIbs"` // کمترین
}

type rawResponse struct {
	IndexB2 []rawIndexItem `json:"indexB2"`
}

type cacheEntry struct {
	fetchedAt time.Time
	payload   map[string]any
}

type Service struct {
	dataDir    string
	httpClient *http.Client
	baseURL    string // در تست‌ها می‌تواند آدرس سرور آزمایشی باشد
	mu         sync.RWMutex
	cache      map[string]cacheEntry
}

func NewService(dataDir string, client *http.Client) *Service {
	if client == nil {
		client = &http.Client{Timeout: IndexHTTPTimeout}
	}
	return &Service{
		dataDir:    dataDir,
		httpClient: client,
		cache:      make(map[string]cacheEntry),
	}
}

func (s *Service) SetBaseURL(u string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.baseURL = u
}

func safeFloat(v float64) float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) || v < 0 {
		return 0.0
	}
	return v
}

func dEvenToISO(dEven any) string {
	var num int64
	switch v := dEven.(type) {
	case float64:
		num = int64(v)
	case int64:
		num = v
	case int:
		num = int64(v)
	case string:
		n, err := strconv.ParseInt(v, 10, 64)
		if err != nil {
			return ""
		}
		num = n
	default:
		return ""
	}
	s := strconv.FormatInt(num, 10)
	if len(s) != 8 {
		return ""
	}
	return fmt.Sprintf("%s-%s-%s", s[:4], s[4:6], s[6:])
}

func (s *Service) fetchTedpixSeries(ctx context.Context, insCode string) ([]rawIndexItem, error) {
	url := fmt.Sprintf(IndexCDNTmpl, insCode)
	s.mu.RLock()
	if s.baseURL != "" {
		url = fmt.Sprintf("%s/%s", s.baseURL, insCode)
	}
	s.mu.RUnlock()

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("TSETMC unreachable: %w", err)
	}
	req.Header.Set("User-Agent", "Mozilla/5.0")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Referer", "https://tsetmc.com/")
	req.Header.Set("Origin", "https://tsetmc.com")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("TSETMC unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("TSETMC HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("TSETMC bad JSON: %w", err)
	}

	var parsed rawResponse
	if err := json.Unmarshal(body, &parsed); err != nil {
		return nil, fmt.Errorf("TSETMC bad JSON: %w", err)
	}

	if len(parsed.IndexB2) == 0 {
		return nil, fmt.Errorf("TSETMC payload empty (indexB2 missing/empty)")
	}

	return parsed.IndexB2, nil
}

type dayRow struct {
	time  string
	close float64
	high  float64
	low   float64
}

// BuildTedpixPayload ساخت payload سری زمانی شاخص کل مطابق با api/market_index.py در پایتون.
func (s *Service) BuildTedpixPayload(ctx context.Context, insCode string, limit int, force bool) (map[string]any, int, error) {
	if insCode == "" {
		insCode = TedpixInsCode
	}

	now := time.Now()
	s.mu.RLock()
	hit, exists := s.cache[insCode]
	s.mu.RUnlock()

	if !force && exists && now.Sub(hit.fetchedAt) < IndexCacheTTL {
		cached := copyMap(hit.payload)
		cached["cached"] = true
		cached["cache_age_sec"] = pyround.Round(now.Sub(hit.fetchedAt).Seconds(), 1)

		candles, _ := cached["candles"].([]map[string]any)
		if limit > 0 && len(candles) > limit {
			candles = candles[len(candles)-limit:]
			cached["candles"] = candles
			cached["count"] = len(candles)
		}
		resolved := pricebasis.ResolvePayload(cached, "candles", [2]string{"#089981", "#f23645"}, pricebasis.Default)
		return resolved, http.StatusOK, nil
	}

	raw, err := s.fetchTedpixSeries(ctx, insCode)
	if err != nil {
		return nil, http.StatusBadGateway, err
	}

	var rows []dayRow
	for _, x := range raw {
		iso := dEvenToISO(x.DEven)
		if iso == "" {
			continue
		}
		c := safeFloat(x.XNivInuClMresIbs)
		if c <= 0 {
			continue
		}
		rows = append(rows, dayRow{
			time:  iso,
			close: c,
			high:  safeFloat(x.XNivInuPhMresIbs),
			low:   safeFloat(x.XNivInuPbMresIbs),
		})
	}

	if len(rows) == 0 {
		return nil, http.StatusBadGateway, fmt.Errorf("TSETMC returned rows but none usable (all close<=0)")
	}

	sort.Slice(rows, func(i, j int) bool {
		return rows[i].time < rows[j].time
	})

	candles := make([]map[string]any, 0, len(rows))
	var prevClose float64

	for _, r := range rows {
		c := r.close
		h := r.high
		if h <= 0 {
			h = c
		}
		l := r.low
		if l <= 0 {
			l = c
		}
		if h < c {
			h = c
		}
		if l > c {
			l = c
		}

		o := c
		if prevClose > 0 {
			o = prevClose
		}
		h, l = candle.Widen(o, h, l, c)

		candles = append(candles, map[string]any{
			"time":  r.time,
			"open":  pyround.Round(o, 2),
			"high":  pyround.Round(h, 2),
			"low":   pyround.Round(l, 2),
			"close": pyround.Round(c, 2),
			"last":  nil,
		})
		prevClose = c
	}

	firstDate := any(nil)
	lastDate := any(nil)
	if len(candles) > 0 {
		firstDate = candles[0]["time"]
		lastDate = candles[len(candles)-1]["time"]
	}

	payload := map[string]any{
		"status":        "success",
		"symbol":        TedpixSymbol,
		"ins_code":      insCode,
		"source":        IndexSource,
		"unit":          "index_point",
		"has_volume":    false,
		"open_basis":    "prev_close_clamped_to_range",
		"candles":       candles,
		"volumes":       []map[string]any{},
		"count":         len(candles),
		"first_date":    firstDate,
		"last_date":     lastDate,
		"fetched_at":    now.Format("2006-01-02T15:04:05"),
		"cache_ttl_sec": IndexCacheTTL.Seconds(),
		"cached":        false,
	}

	// ذخیره در کش
	s.mu.Lock()
	s.cache[insCode] = cacheEntry{
		fetchedAt: now,
		payload:   copyMap(payload),
	}
	s.mu.Unlock()

	resp := copyMap(payload)
	cands, _ := resp["candles"].([]map[string]any)
	if limit > 0 && len(cands) > limit {
		cands = cands[len(cands)-limit:]
		resp["candles"] = cands
		resp["count"] = len(cands)
	}

	resolved := pricebasis.ResolvePayload(resp, "candles", [2]string{"#089981", "#f23645"}, pricebasis.Default)
	return resolved, http.StatusOK, nil
}

func copyMap(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		if k == "candles" {
			if list, ok := v.([]map[string]any); ok {
				cList := make([]map[string]any, len(list))
				for i, item := range list {
					cItem := make(map[string]any, len(item))
					for ik, iv := range item {
						cItem[ik] = iv
					}
					cList[i] = cItem
				}
				out[k] = cList
				continue
			}
		}
		out[k] = v
	}
	return out
}
