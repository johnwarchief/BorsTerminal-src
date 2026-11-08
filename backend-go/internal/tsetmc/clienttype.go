package tsetmc

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
)

const (
	// DefaultClientTypeValueSource is the canonical provenance identifier for client_type_value rows.
	DefaultClientTypeValueSource = "tsetmc_clienttype_history"
)

// ClientTypePoint represents a single symbol point in the client_type table (live volumes and order counts).
type ClientTypePoint struct {
	InsCode     string  `json:"ins_code"`
	DEven       int     `json:"d_even"`
	BuyIVol     float64 `json:"buy_i_vol"`
	BuyNVol     float64 `json:"buy_n_vol"`
	BuyDDDVol   float64 `json:"buy_ddd_vol"`
	BuyCountI   int64   `json:"buy_count_i"`
	BuyCountN   int64   `json:"buy_count_n"`
	BuyCountDDD int64   `json:"buy_count_ddd"`
	SellIVol    float64 `json:"sell_i_vol"`
	SellNVol    float64 `json:"sell_n_vol"`
	SellCountI  int64   `json:"sell_count_i"`
	SellCountN  int64   `json:"sell_count_n"`
	FetchedAt   string  `json:"fetched_at"`
}

// ClientTypeValuePoint represents a single symbol point in the client_type_value table (historical rial values).
type ClientTypeValuePoint struct {
	InsCode   string  `json:"ins_code"`
	DEven     int     `json:"d_even"`
	BuyIVal   float64 `json:"buy_i_val"`
	BuyNVal   float64 `json:"buy_n_val"`
	SellIVal  float64 `json:"sell_i_val"`
	SellNVal  float64 `json:"sell_n_val"`
	BuyDDDVal float64 `json:"buy_ddd_val"`
	Kind      string  `json:"kind"`
	FetchedAt string  `json:"fetched_at"`
	Source    string  `json:"source"`
}

type rawClientTypeItem struct {
	InsCode     any `json:"insCode"`
	DEven       any `json:"dEven"`
	RecDate     any `json:"recDate"`
	BuyIVolume  any `json:"buy_I_Volume"`
	BuyNVolume  any `json:"buy_N_Volume"`
	BuyDDDVol   any `json:"buy_DDD_Volume"`
	BuyCountI   any `json:"buy_CountI"`
	BuyCountN   any `json:"buy_CountN"`
	BuyCountDDD any `json:"buy_CountDDD"`
	SellIVolume any `json:"sell_I_Volume"`
	SellNVolume any `json:"sell_N_Volume"`
	SellCountI  any `json:"sell_CountI"`
	SellCountN  any `json:"sell_CountN"`
}

type rawClientTypeAllResponse struct {
	ClientTypeAllDto []rawClientTypeItem `json:"clientTypeAllDto"`
	ClientTypeAll    []rawClientTypeItem `json:"clientTypeAll"`
	Direct           []rawClientTypeItem
}

func (r *rawClientTypeAllResponse) UnmarshalJSON(data []byte) error {
	var arr []rawClientTypeItem
	if err := json.Unmarshal(data, &arr); err == nil {
		r.Direct = arr
		return nil
	}
	type Alias rawClientTypeAllResponse
	var alias Alias
	if err := json.Unmarshal(data, &alias); err != nil {
		return err
	}
	r.ClientTypeAllDto = alias.ClientTypeAllDto
	r.ClientTypeAll = alias.ClientTypeAll
	return nil
}

func (r *rawClientTypeAllResponse) Items() []rawClientTypeItem {
	if len(r.Direct) > 0 {
		return r.Direct
	}
	if len(r.ClientTypeAllDto) > 0 {
		return r.ClientTypeAllDto
	}
	return r.ClientTypeAll
}

// FetchClientTypeAll fetches the live client type volume/count board from /ClientType/GetClientTypeAll.
func (c *Client) FetchClientTypeAll(ctx context.Context) ([]ClientTypePoint, error) {
	var resp rawClientTypeAllResponse
	if err := c.GetJSON(ctx, "/ClientType/GetClientTypeAll", &resp); err != nil {
		return nil, fmt.Errorf("fetch client type all: %w", err)
	}

	items := resp.Items()
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	todayDate, _ := strconv.Atoi(time.Now().Format("20060102"))

	points := make([]ClientTypePoint, 0, len(items))
	for _, it := range items {
		insCode := strings.TrimSpace(toString(it.InsCode))
		if insCode == "" {
			continue
		}

		dEven := toInt(it.DEven)
		if dEven == 0 {
			dEven = toInt(it.RecDate)
		}
		if dEven == 0 {
			dEven = todayDate
		}

		points = append(points, ClientTypePoint{
			InsCode:     insCode,
			DEven:       dEven,
			BuyIVol:     toFloat(it.BuyIVolume),
			BuyNVol:     toFloat(it.BuyNVolume),
			BuyDDDVol:   toFloat(it.BuyDDDVol),
			BuyCountI:   int64(toInt(it.BuyCountI)),
			BuyCountN:   int64(toInt(it.BuyCountN)),
			BuyCountDDD: int64(toInt(it.BuyCountDDD)),
			SellIVol:    toFloat(it.SellIVolume),
			SellNVol:    toFloat(it.SellNVolume),
			SellCountI:  int64(toInt(it.SellCountI)),
			SellCountN:  int64(toInt(it.SellCountN)),
			FetchedAt:   nowStr,
		})
	}

	return points, nil
}

// FetchClientTypeHistory fetches client type historical values for an instrument and date.
// It parses buy_I_Value, buy_N_Value, sell_I_Value, sell_N_Value, buy_DDD_Value.
// It marks kind as "native" if all 4 values are present, else "mixed".
func (c *Client) FetchClientTypeHistory(ctx context.Context, insCode string, dEven int) (*ClientTypeValuePoint, error) {
	insCode = strings.TrimSpace(insCode)
	if insCode == "" {
		return nil, fmt.Errorf("insCode is required")
	}

	endpoint := fmt.Sprintf("/ClientType/GetClientTypeHistory/%s/%d", insCode, dEven)
	var rawData json.RawMessage
	if err := c.GetJSON(ctx, endpoint, &rawData); err != nil {
		return nil, fmt.Errorf("fetch client type history: %w", err)
	}

	// Unwrap payload: could be {"clientType": {...}}, [{...}], or {...}
	var rawMap map[string]any
	if err := json.Unmarshal(rawData, &rawMap); err != nil {
		// Try array of objects
		var rawArr []map[string]any
		if arrErr := json.Unmarshal(rawData, &rawArr); arrErr == nil && len(rawArr) > 0 {
			rawMap = rawArr[0]
		} else {
			return nil, fmt.Errorf("unmarshal history response: %w", err)
		}
	}

	// Check if wrapped in "clientType"
	targetMap := rawMap
	if ctVal, exists := rawMap["clientType"]; exists {
		if ctObj, ok := ctVal.(map[string]any); ok {
			targetMap = ctObj
		} else if ctArr, ok := ctVal.([]any); ok && len(ctArr) > 0 {
			if firstObj, ok := ctArr[0].(map[string]any); ok {
				targetMap = firstObj
			}
		}
	}

	// Case-insensitive lookup for fields
	getVal := func(keys ...string) (any, bool) {
		for _, want := range keys {
			wantLower := strings.ToLower(want)
			for k, v := range targetMap {
				if strings.ToLower(k) == wantLower && v != nil {
					return v, true
				}
			}
		}
		return nil, false
	}

	rawBuyI, haveBuyI := getVal("buy_I_Value", "buy_i_val", "buyIValue")
	rawBuyN, haveBuyN := getVal("buy_N_Value", "buy_n_val", "buyNValue")
	rawSellI, haveSellI := getVal("sell_I_Value", "sell_i_val", "sellIValue")
	rawSellN, haveSellN := getVal("sell_N_Value", "sell_n_val", "sellNValue")
	rawBuyDDD, _ := getVal("buy_DDD_Value", "buy_ddd_val", "buyDDDValue")
	rawRecDate, haveRecDate := getVal("recDate", "dEven", "deven")

	// Determine kind: "native" if all 4 values are present, else "mixed"
	kind := "mixed"
	if haveBuyI && haveBuyN && haveSellI && haveSellN {
		kind = "native"
	}

	finalDEven := dEven
	if haveRecDate {
		if parsedDate := toInt(rawRecDate); parsedDate > 0 {
			finalDEven = parsedDate
		}
	}

	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")

	return &ClientTypeValuePoint{
		InsCode:   insCode,
		DEven:     finalDEven,
		BuyIVal:   toFloat(rawBuyI),
		BuyNVal:   toFloat(rawBuyN),
		SellIVal:  toFloat(rawSellI),
		SellNVal:  toFloat(rawSellN),
		BuyDDDVal: toFloat(rawBuyDDD),
		Kind:      kind,
		FetchedAt: nowStr,
		Source:    DefaultClientTypeValueSource,
	}, nil
}

// EnsureClientTypeSchema creates the client_type and client_type_value tables and indexes.
func EnsureClientTypeSchema(db *sql.DB) error {
	ddls := []string{
		`CREATE TABLE IF NOT EXISTS client_type (
			ins_code TEXT,
			d_even INTEGER,
			buy_i_vol REAL,
			buy_n_vol REAL,
			buy_ddd_vol REAL,
			buy_count_i INTEGER,
			buy_count_n INTEGER,
			buy_count_ddd INTEGER,
			sell_i_vol REAL,
			sell_n_vol REAL,
			sell_count_i INTEGER,
			sell_count_n INTEGER,
			fetched_at TEXT,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE INDEX IF NOT EXISTS ix_client_type_ins ON client_type(ins_code);`,
		`CREATE TABLE IF NOT EXISTS client_type_value (
			ins_code TEXT,
			d_even INTEGER,
			buy_i_val REAL,
			buy_n_val REAL,
			sell_i_val REAL,
			sell_n_val REAL,
			buy_ddd_val REAL,
			kind TEXT,
			fetched_at TEXT,
			source TEXT,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE INDEX IF NOT EXISTS ix_client_type_value_ins ON client_type_value(ins_code);`,
	}

	for _, ddl := range ddls {
		if _, err := db.Exec(ddl); err != nil {
			return fmt.Errorf("ensure client type schema exec: %w", err)
		}
	}

	// Idempotent column check for client_type_value
	if err := ensureColumnsExist(db, "client_type_value", map[string]string{
		"kind":   "TEXT",
		"source": "TEXT",
	}); err != nil {
		return err
	}

	return nil
}

// IngestClientType inserts or updates live client type data into client_type table.
func IngestClientType(ctx context.Context, db *sql.DB, points []ClientTypePoint) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO client_type (
			ins_code, d_even, buy_i_vol, buy_n_vol, buy_ddd_vol,
			buy_count_i, buy_count_n, buy_count_ddd, sell_i_vol,
			sell_n_vol, sell_count_i, sell_count_n, fetched_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(ins_code, d_even) DO UPDATE SET
			buy_i_vol = excluded.buy_i_vol,
			buy_n_vol = excluded.buy_n_vol,
			buy_ddd_vol = excluded.buy_ddd_vol,
			buy_count_i = excluded.buy_count_i,
			buy_count_n = excluded.buy_count_n,
			buy_count_ddd = excluded.buy_count_ddd,
			sell_i_vol = excluded.sell_i_vol,
			sell_n_vol = excluded.sell_n_vol,
			sell_count_i = excluded.sell_count_i,
			sell_count_n = excluded.sell_count_n,
			fetched_at = excluded.fetched_at
	`)
	if err != nil {
		return fmt.Errorf("prepare client_type stmt: %w", err)
	}
	defer stmt.Close()

	for _, pt := range points {
		if pt.InsCode == "" {
			continue
		}
		_, err := stmt.ExecContext(ctx,
			pt.InsCode, pt.DEven, pt.BuyIVol, pt.BuyNVol, pt.BuyDDDVol,
			pt.BuyCountI, pt.BuyCountN, pt.BuyCountDDD, pt.SellIVol,
			pt.SellNVol, pt.SellCountI, pt.SellCountN, pt.FetchedAt,
		)
		if err != nil {
			return fmt.Errorf("exec client_type %s/%d: %w", pt.InsCode, pt.DEven, err)
		}
	}

	return tx.Commit()
}

// IngestClientTypeValue inserts or updates historical client type value data into client_type_value table.
func IngestClientTypeValue(ctx context.Context, db *sql.DB, points []ClientTypeValuePoint) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO client_type_value (
			ins_code, d_even, buy_i_val, buy_n_val, sell_i_val, sell_n_val,
			buy_ddd_val, kind, fetched_at, source
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(ins_code, d_even) DO UPDATE SET
			buy_i_val = excluded.buy_i_val,
			buy_n_val = excluded.buy_n_val,
			sell_i_val = excluded.sell_i_val,
			sell_n_val = excluded.sell_n_val,
			buy_ddd_val = excluded.buy_ddd_val,
			kind = excluded.kind,
			fetched_at = excluded.fetched_at,
			source = excluded.source
	`)
	if err != nil {
		return fmt.Errorf("prepare client_type_value stmt: %w", err)
	}
	defer stmt.Close()

	for _, pt := range points {
		if pt.InsCode == "" {
			continue
		}
		_, err := stmt.ExecContext(ctx,
			pt.InsCode, pt.DEven, pt.BuyIVal, pt.BuyNVal, pt.SellIVal, pt.SellNVal,
			pt.BuyDDDVal, pt.Kind, pt.FetchedAt, pt.Source,
		)
		if err != nil {
			return fmt.Errorf("exec client_type_value %s/%d: %w", pt.InsCode, pt.DEven, err)
		}
	}

	return tx.Commit()
}
