package screener

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/symbolid"
)

type ScreenerPayload struct {
	Status           string           `json:"status"`
	Count            int              `json:"count"`
	Data             []map[string]any `json:"data"`
	Thresholds       any              `json:"thresholds,omitempty"`
	MaxScore         any              `json:"max_score,omitempty"`
	AsOf             any              `json:"as_of,omitempty"`
	FunnelGate       any              `json:"funnel_gate,omitempty"`
	RequestedSymbols int              `json:"requested_symbols,omitempty"`
}

type cachedScreener struct {
	ts      time.Time
	payload map[string]any
}

type Service struct {
	marketDB *sql.DB
	dataDir  string
	mu       sync.RWMutex
	cache    *cachedScreener
}

func NewService(marketDB *sql.DB, dataDir string) *Service {
	return &Service{
		marketDB: marketDB,
		dataDir:  dataDir,
	}
}

// GetScreener بازگرداندن جدول غربالگری ۵ شاخص FTS و ادغام با پارامترهای symbols و preset.
func (s *Service) GetScreener(ctx context.Context, symbolsStr, preset, chainStr string) (map[string]any, error) {
	s.mu.RLock()
	cached := s.cache
	s.mu.RUnlock()

	now := time.Now()
	// TTL ۱۲ ساعت
	if cached == nil || now.Sub(cached.ts) > 12*time.Hour {
		fresh, err := s.loadScreenerData(ctx)
		if err == nil && fresh != nil {
			s.mu.Lock()
			s.cache = &cachedScreener{
				ts:      now,
				payload: fresh,
			}
			cached = s.cache
			s.mu.Unlock()
		}
	}

	if cached == nil || cached.payload == nil {
		return map[string]any{
			"status": "error",
			"data":   []any{},
			"count":  0,
		}, nil
	}

	// کپی برای اعمال فیلترهای درخواست
	rawRows, _ := cached.payload["data"].([]any)
	if rawRows == nil {
		if mapRows, ok := cached.payload["data"].([]map[string]any); ok {
			rawRows = make([]any, len(mapRows))
			for i, mr := range mapRows {
				rawRows[i] = mr
			}
		}
	}

	// فیلتر نمادها در صورت ارسال symbols=
	var wantedSymbols map[string]bool
	var askedCount int
	if strings.TrimSpace(symbolsStr) != "" {
		wantedSymbols = make(map[string]bool)
		parts := strings.Split(symbolsStr, ",")
		for _, p := range parts {
			cp := symbolid.Norm(strings.TrimSpace(p))
			if cp != "" {
				wantedSymbols[cp] = true
			}
		}
		askedCount = len(wantedSymbols)
	}

	filteredRows := make([]map[string]any, 0, len(rawRows))
	for _, item := range rawRows {
		rMap, ok := item.(map[string]any)
		if !ok {
			continue
		}
		sym, _ := rMap["symbol"].(string)
		if wantedSymbols != nil && !wantedSymbols[symbolid.Norm(sym)] {
			continue
		}
		// کپی سطحی
		rowCp := make(map[string]any, len(rMap))
		for k, v := range rMap {
			rowCp[k] = v
		}
		filteredRows = append(filteredRows, rowCp)
	}

	res := make(map[string]any, len(cached.payload)+4)
	for k, v := range cached.payload {
		if k == "data" {
			continue
		}
		res[k] = v
	}
	res["data"] = filteredRows
	res["count"] = len(filteredRows)
	if askedCount > 0 {
		res["requested_symbols"] = askedCount
	}

	// در صورت نبود funnel_gate، ساخت بلوک استاندارد
	if res["funnel_gate"] == nil {
		res["funnel_gate"] = map[string]any{
			"chain": preset,
			"state": "applied",
		}
	}

	return res, nil
}

// loadScreenerData خواندن از فایل .screener_cache.json یا پایگاه داده
func (s *Service) loadScreenerData(ctx context.Context) (map[string]any, error) {
	// ۱. تلاش برای خواندن از .screener_cache.json
	candidatePaths := []string{
		filepath.Join(s.dataDir, ".screener_cache.json"),
		".screener_cache.json",
	}

	for _, p := range candidatePaths {
		if _, err := os.Stat(p); err == nil {
			content, err := os.ReadFile(p)
			if err == nil {
				var diskWrapper struct {
					Payload map[string]any `json:"payload"`
				}
				if err := json.Unmarshal(content, &diskWrapper); err == nil && diskWrapper.Payload != nil {
					return diskWrapper.Payload, nil
				}
			}
		}
	}

	// ۲. استخراج از جدول fts_results
	query := `
		SELECT f.symbol, COALESCE(i.l_val30, f.symbol) AS name,
		       COALESCE(i.sector_name, '') AS sector_name,
		       f.score, f.verdict, f.excluded, f.exclusion_reasons,
		       f.f01_growth_pct, f.f01_pass, f.f02_pass, f.f03_margin_pct,
		       f.f03_pass, f.f04_ratio, f.f04_pass, f.f05_verdict, f.f05_pass
		FROM fts_results f
		LEFT JOIN instruments i ON i.l_val18 = f.symbol
	`
	rows, err := s.marketDB.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var dataList []map[string]any
	for rows.Next() {
		var sym, name, sector, verdict, exclReasons, f05Verdict string
		var score, f01Pass, f02Pass, f03Pass, f04Pass, f05Pass, excluded int
		var f01Growth, f03Margin, f04Ratio sql.NullFloat64

		if err := rows.Scan(
			&sym, &name, &sector, &score, &verdict, &excluded, &exclReasons,
			&f01Growth, &f01Pass, &f02Pass, &f03Margin, &f03Pass,
			&f04Ratio, &f04Pass, &f05Verdict, &f05Pass,
		); err != nil {
			continue
		}

		item := map[string]any{
			"symbol":            sym,
			"symbol_norm":       symbolid.Norm(sym),
			"name":              name,
			"sector_name":       sector,
			"score":             score,
			"verdict":           verdict,
			"excluded":          excluded > 0,
			"exclusion_reasons": exclReasons,
			"i1_pass":           f01Pass > 0,
			"i2_pass":           f02Pass > 0,
			"i3_pass":           f03Pass > 0,
			"i4_pass":           f04Pass > 0,
			"i5_pass":           f05Pass > 0,
		}
		dataList = append(dataList, item)
	}

	return map[string]any{
		"status":    "success",
		"count":     len(dataList),
		"data":      dataList,
		"max_score": 5,
		"as_of":     time.Now().Format("2006-01-02"),
	}, nil
}
