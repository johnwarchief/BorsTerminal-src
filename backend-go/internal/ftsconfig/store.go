package ftsconfig

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strings"
	"time"
)

const ddl = `
CREATE TABLE IF NOT EXISTS fts_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    config_json TEXT,
    updated_at TEXT
);
`

type Store struct {
	db *sql.DB
}

func NewStore(db *sql.DB) (*Store, error) {
	if db != nil {
		if _, err := db.Exec(ddl); err != nil {
			errStr := strings.ToLower(err.Error())
			if !strings.Contains(errStr, "readonly") && !strings.Contains(errStr, "read-only") {
				return nil, fmt.Errorf("ensure fts_config table: %w", err)
			}
		}
	}
	return &Store{db: db}, nil
}

// Defaults returns the canonical FTS threshold defaults matching FTS_BASIC_DEFAULTS in useFtsConfig.ts.
func Defaults() map[string]any {
	return map[string]any{
		"growth_min":                   40.0,
		"eps_years":                    3,
		"margin_min":                   20.0,
		"margin_optimal":               30.0,
		"sales_to_mcap_min":            0.33,
		"profit_potential_min":         40.0,
		"industry_mode":                "Exclude_Mandatory_Pricing",
		"watchlist_max":                50,
		"mcap_min_hmt":                 0.0,
		"suspended_max_stale_sessions": 3,
		"filter_m141":                  false,
		"min_trade_val":                0.0,
		"mandatory_sectors": []string{
			"خودرو", "نیروگاه", "لاستیک",
		},
		"free_sectors": []string{
			"سیمان", "پتروشیمی", "شیمیایی", "فلزات", "کانی", "کاشی",
			"سرامیک", "شیشه", "کانه", "معادن", "نفت", "محصولات فلزی",
		},
		"reject_insurance":            true,
		"include_industries":          []string{},
		"exclude_industries":          []string{},
		"v10_monetary_growth_min":     60.0,
		"v10_volume_growth_min":       0.0,
		"v10_volume_breadth_min":      0.6,
		"v10_eps_years":               3,
		"v10_margin_min":              20.0,
		"v10_margin_ideal":            30.0,
		"v10_sales_to_mcap_min":       0.33,
		"v10_potential_min":           40.0,
		"v10_inflation_basis":         60.0,
		"hourglass_rsi_period":        7,
		"hourglass_rsi_oversold":      30.0,
		"hourglass_ma52_position":     "below",
		"holdings_sales_na":           true,
		"pharma_margin_exempt_min":    0.0,
		"exclude_base_market":         true,
		"exclude_rejected_indicators": []string{},
	}
}

func (s *Store) Get(ctx context.Context) (map[string]any, error) {
	defs := Defaults()
	if s.db == nil {
		return defs, nil
	}

	var jsonStr string
	err := s.db.QueryRowContext(ctx, "SELECT config_json FROM fts_config WHERE id = 1").Scan(&jsonStr)
	if errors.Is(err, sql.ErrNoRows) {
		return defs, nil
	}
	if err != nil {
		errStr := strings.ToLower(err.Error())
		if strings.Contains(errStr, "no such table") {
			return defs, nil
		}
		return nil, fmt.Errorf("query fts_config: %w", err)
	}

	var stored map[string]any
	if err := json.Unmarshal([]byte(jsonStr), &stored); err != nil {
		return defs, nil
	}

	return cleanAndMerge(defs, stored), nil
}

func (s *Store) Save(ctx context.Context, payload map[string]any) (map[string]any, error) {
	if s.db == nil {
		return nil, errors.New("user database handle is nil")
	}

	current, err := s.Get(ctx)
	if err != nil {
		return nil, err
	}

	if nested, ok := payload["config"].(map[string]any); ok {
		payload = nested
	}

	merged := cleanAndMerge(current, payload)
	raw, err := json.Marshal(merged)
	if err != nil {
		return nil, fmt.Errorf("marshal fts_config: %w", err)
	}

	updatedAt := time.Now().UTC().Format(time.RFC3339)
	query := `
INSERT INTO fts_config (id, config_json, updated_at)
VALUES (1, ?, ?)
ON CONFLICT(id) DO UPDATE SET config_json = excluded.config_json, updated_at = excluded.updated_at;
`
	if _, err := s.db.ExecContext(ctx, query, string(raw), updatedAt); err != nil {
		return nil, fmt.Errorf("persist fts_config: %w", err)
	}

	return merged, nil
}

func cleanAndMerge(base, incoming map[string]any) map[string]any {
	out := make(map[string]any, len(base))
	for k, v := range base {
		out[k] = v
	}

	aliases := map[string]string{
		"bad_sectors":  "mandatory_sectors",
		"good_sectors": "free_sectors",
	}

	for rawK, v := range incoming {
		k := rawK
		if target, ok := aliases[k]; ok {
			k = target
		}
		if _, exists := base[k]; !exists {
			continue
		}

		switch k {
		case "industry_mode", "hourglass_ma52_position":
			if strVal, ok := v.(string); ok && strVal != "" {
				out[k] = strVal
			}
		case "filter_m141", "reject_insurance", "holdings_sales_na", "exclude_base_market":
			if b, ok := v.(bool); ok {
				out[k] = b
			}
		case "mandatory_sectors", "free_sectors", "include_industries", "exclude_industries", "exclude_rejected_indicators":
			switch list := v.(type) {
			case []string:
				out[k] = list
			case []any:
				items := make([]string, 0, len(list))
				for _, item := range list {
					if s, ok := item.(string); ok && strings.TrimSpace(s) != "" {
						items = append(items, strings.TrimSpace(s))
					}
				}
				out[k] = items
			case string:
				parts := strings.Split(strings.ReplaceAll(list, "،", ","), ",")
				items := make([]string, 0, len(parts))
				for _, part := range parts {
					if s := strings.TrimSpace(part); s != "" {
						items = append(items, s)
					}
				}
				out[k] = items
			}
		case "eps_years", "watchlist_max", "suspended_max_stale_sessions", "v10_eps_years", "hourglass_rsi_period":
			if f, ok := asFloat(v); ok {
				out[k] = int(math.Trunc(f))
			}
		default:
			if f, ok := asFloat(v); ok {
				out[k] = f
			}
		}
	}
	return out
}

func asFloat(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	case json.Number:
		f, err := x.Float64()
		return f, err == nil
	case string:
		var f float64
		_, err := fmt.Sscanf(strings.TrimSpace(x), "%f", &f)
		return f, err == nil
	}
	return 0, false
}
