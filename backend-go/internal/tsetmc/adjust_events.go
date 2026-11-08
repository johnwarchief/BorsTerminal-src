package tsetmc

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"
)

const (
	// DefaultPriceAdjustSource is the canonical provenance identifier for price_adjust_events.
	DefaultPriceAdjustSource = "tsetmc_price_adjust_by_flow"
	// DefaultShareChangeSource is the canonical provenance identifier for share_change_events.
	DefaultShareChangeSource = "tsetmc_share_change_by_flow"
	// DefaultCorpSize is the default batch limit for price adjustments per flow.
	DefaultCorpSize = 500
	// DefaultCorpDays is the default lookback window in days for share changes.
	DefaultCorpDays = 14
)

// PriceAdjustEvent represents a single price adjustment event from TSETMC.
type PriceAdjustEvent struct {
	InsCode             string  `json:"ins_code"`
	DEven               int     `json:"d_even"`
	Symbol              string  `json:"symbol"`
	PClosing            float64 `json:"p_closing"`
	PClosingNotAdjusted float64 `json:"p_closing_not_adjusted"`
	CorporateTypeCode   *int    `json:"corporate_type_code"` // raw integer, not decoded
	Ratio               float64 `json:"ratio"`               // round(pClosing / pClosingNotAdjusted, 8)
	Source              string  `json:"source"`
	FetchedAt           string  `json:"fetched_at"`
}

// ShareChangeEvent represents a single capital increase / share change event from TSETMC.
type ShareChangeEvent struct {
	InsCode   string  `json:"ins_code"`
	DEven     int     `json:"d_even"`
	Symbol    string  `json:"symbol"`
	SharesOld float64 `json:"shares_old"`
	SharesNew float64 `json:"shares_new"`
	Ratio     float64 `json:"ratio"` // round(sharesOld / sharesNew, 8)
	Source    string  `json:"source"`
	FetchedAt string  `json:"fetched_at"`
}

type rawPriceAdjustPayload struct {
	PriceAdjust     []rawPriceAdjustItem `json:"priceAdjust"`
	PriceAdjustList []rawPriceAdjustItem `json:"priceAdjustList"`
	Direct          []rawPriceAdjustItem
}

func (p *rawPriceAdjustPayload) UnmarshalJSON(data []byte) error {
	var direct []rawPriceAdjustItem
	if err := json.Unmarshal(data, &direct); err == nil {
		p.Direct = direct
		return nil
	}
	type Alias rawPriceAdjustPayload
	var alias Alias
	if err := json.Unmarshal(data, &alias); err != nil {
		return err
	}
	p.PriceAdjust = alias.PriceAdjust
	p.PriceAdjustList = alias.PriceAdjustList
	return nil
}

func (p *rawPriceAdjustPayload) Items() []rawPriceAdjustItem {
	if len(p.Direct) > 0 {
		return p.Direct
	}
	if len(p.PriceAdjust) > 0 {
		return p.PriceAdjust
	}
	return p.PriceAdjustList
}

type rawShareChangePayload struct {
	InstrumentShareChange []rawShareChangeItem `json:"instrumentShareChange"`
	ShareChange           []rawShareChangeItem `json:"shareChange"`
	Direct                []rawShareChangeItem
}

func (p *rawShareChangePayload) UnmarshalJSON(data []byte) error {
	var direct []rawShareChangeItem
	if err := json.Unmarshal(data, &direct); err == nil {
		p.Direct = direct
		return nil
	}
	type Alias rawShareChangePayload
	var alias Alias
	if err := json.Unmarshal(data, &alias); err != nil {
		return err
	}
	p.InstrumentShareChange = alias.InstrumentShareChange
	p.ShareChange = alias.ShareChange
	return nil
}

func (p *rawShareChangePayload) Items() []rawShareChangeItem {
	if len(p.Direct) > 0 {
		return p.Direct
	}
	if len(p.InstrumentShareChange) > 0 {
		return p.InstrumentShareChange
	}
	return p.ShareChange
}

type rawPriceAdjustItem struct {
	InsCode             any                     `json:"insCode"`
	DEven               any                     `json:"dEven"`
	PClosing            any                     `json:"pClosing"`
	PClosingNotAdjusted any                     `json:"pClosingNotAdjusted"`
	CorporateTypeCode   any                     `json:"corporateTypeCode"`
	LVal18AFC           any                     `json:"lVal18AFC"`
	LVal18              any                     `json:"lVal18"`
	Instrument          *rawInstrumentSubObject `json:"instrument"`
}

type rawShareChangeItem struct {
	InsCode          any                     `json:"insCode"`
	DEven            any                     `json:"dEven"`
	LVal18AFC        any                     `json:"lVal18AFC"`
	LVal18           any                     `json:"lVal18"`
	NumberOfShareOld any                     `json:"numberOfShareOld"`
	NumberOfShareNew any                     `json:"numberOfShareNew"`
	Instrument       *rawInstrumentSubObject `json:"instrument"`
}

type rawInstrumentSubObject struct {
	InsCode   any `json:"insCode"`
	LVal18AFC any `json:"lVal18AFC"`
	LVal18    any `json:"lVal18"`
	LVal30    any `json:"lVal30"`
}

func toNullableInt(v any) *int {
	if v == nil {
		return nil
	}
	switch val := v.(type) {
	case float64:
		i := int(val)
		return &i
	case float32:
		i := int(val)
		return &i
	case int:
		return &val
	case int64:
		i := int(val)
		return &i
	case string:
		s := strings.TrimSpace(val)
		if s == "" || strings.EqualFold(s, "null") {
			return nil
		}
		if i, err := strconv.Atoi(s); err == nil {
			return &i
		}
	case json.Number:
		if i, err := val.Int64(); err == nil {
			intVal := int(i)
			return &intVal
		}
	}
	return nil
}

func parsePriceAdjustItems(items []rawPriceAdjustItem, fallbackInsCode, source, nowStr string) []PriceAdjustEvent {
	if nowStr == "" {
		nowStr = time.Now().UTC().Format("2006-01-02 15:04:05")
	}
	if source == "" {
		source = DefaultPriceAdjustSource
	}

	out := make([]PriceAdjustEvent, 0, len(items))
	for _, it := range items {
		ins := strings.TrimSpace(toString(it.InsCode))
		if ins == "" || ins == "0" {
			if it.Instrument != nil {
				ins = strings.TrimSpace(toString(it.Instrument.InsCode))
			}
		}
		if ins == "" || ins == "0" {
			ins = strings.TrimSpace(fallbackInsCode)
		}

		dEven := toInt(it.DEven)
		if ins == "" || ins == "0" || dEven == 0 {
			continue
		}

		adj := toFloat(it.PClosing)
		raw := toFloat(it.PClosingNotAdjusted)
		var ratio float64
		if adj > 0 && raw > 0 {
			ratio = math.Round((adj/raw)*1e8) / 1e8
		}

		var sym string
		if it.Instrument != nil {
			sym = strings.TrimSpace(toString(it.Instrument.LVal18AFC))
			if sym == "" {
				sym = strings.TrimSpace(toString(it.Instrument.LVal18))
			}
		}
		if sym == "" {
			sym = strings.TrimSpace(toString(it.LVal18AFC))
		}
		if sym == "" {
			sym = strings.TrimSpace(toString(it.LVal18))
		}

		corpCode := toNullableInt(it.CorporateTypeCode)

		out = append(out, PriceAdjustEvent{
			InsCode:             ins,
			DEven:               dEven,
			Symbol:              sym,
			PClosing:            adj,
			PClosingNotAdjusted: raw,
			CorporateTypeCode:   corpCode,
			Ratio:               ratio,
			Source:              source,
			FetchedAt:           nowStr,
		})
	}
	return out
}

func parseShareChangeItems(items []rawShareChangeItem, fallbackInsCode, source, nowStr string) []ShareChangeEvent {
	if nowStr == "" {
		nowStr = time.Now().UTC().Format("2006-01-02 15:04:05")
	}
	if source == "" {
		source = DefaultShareChangeSource
	}

	out := make([]ShareChangeEvent, 0, len(items))
	for _, it := range items {
		ins := strings.TrimSpace(toString(it.InsCode))
		if ins == "" || ins == "0" {
			if it.Instrument != nil {
				ins = strings.TrimSpace(toString(it.Instrument.InsCode))
			}
		}
		if ins == "" || ins == "0" {
			ins = strings.TrimSpace(fallbackInsCode)
		}

		dEven := toInt(it.DEven)
		if ins == "" || ins == "0" || dEven == 0 {
			continue
		}

		oldShares := toFloat(it.NumberOfShareOld)
		newShares := toFloat(it.NumberOfShareNew)
		var ratio float64
		if oldShares > 0 && newShares > 0 {
			ratio = math.Round((oldShares/newShares)*1e8) / 1e8
		}

		var sym string
		if it.Instrument != nil {
			sym = strings.TrimSpace(toString(it.Instrument.LVal18AFC))
			if sym == "" {
				sym = strings.TrimSpace(toString(it.Instrument.LVal18))
			}
		}
		if sym == "" {
			sym = strings.TrimSpace(toString(it.LVal18AFC))
		}
		if sym == "" {
			sym = strings.TrimSpace(toString(it.LVal18))
		}

		out = append(out, ShareChangeEvent{
			InsCode:   ins,
			DEven:     dEven,
			Symbol:    sym,
			SharesOld: oldShares,
			SharesNew: newShares,
			Ratio:     ratio,
			Source:    source,
			FetchedAt: nowStr,
		})
	}
	return out
}

// EnsureCorporateSchema creates price_adjust_events and share_change_events tables and indexes.
func EnsureCorporateSchema(ctx context.Context, db *sql.DB) error {
	ddls := []string{
		`CREATE TABLE IF NOT EXISTS price_adjust_events (
			ins_code TEXT,
			d_even INTEGER,
			symbol TEXT,
			p_closing REAL,
			p_closing_not_adjusted REAL,
			corporate_type_code INTEGER,
			ratio REAL,
			source TEXT,
			fetched_at TEXT,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE INDEX IF NOT EXISTS ix_price_adjust_events_ins ON price_adjust_events(ins_code);`,
		`CREATE TABLE IF NOT EXISTS share_change_events (
			ins_code TEXT,
			d_even INTEGER,
			symbol TEXT,
			shares_old REAL,
			shares_new REAL,
			ratio REAL,
			source TEXT,
			fetched_at TEXT,
			PRIMARY KEY (ins_code, d_even)
		);`,
		`CREATE INDEX IF NOT EXISTS ix_share_change_events_ins ON share_change_events(ins_code);`,
	}

	for _, ddl := range ddls {
		if _, err := db.ExecContext(ctx, ddl); err != nil {
			return fmt.Errorf("ensure corporate schema: %w", err)
		}
	}
	return nil
}

// FetchPriceAdjustByFlow fetches corporate price adjust events for a specific flow and size.
func FetchPriceAdjustByFlow(ctx context.Context, client *Client, flow int, size int) ([]PriceAdjustEvent, error) {
	if client == nil {
		client = NewClient("", nil)
	}
	if size <= 0 {
		size = DefaultCorpSize
	}
	endpoint := fmt.Sprintf("/ClosingPrice/GetPriceAdjustByFlow/%d/%d", flow, size)
	var payload rawPriceAdjustPayload
	if err := client.GetJSON(ctx, endpoint, &payload); err != nil {
		return nil, fmt.Errorf("fetch price adjust by flow %d: %w", flow, err)
	}
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	return parsePriceAdjustItems(payload.Items(), "", DefaultPriceAdjustSource, nowStr), nil
}

// FetchInstrumentShareChangeByFlow fetches corporate share change events for a specific flow and lookback days.
func FetchInstrumentShareChangeByFlow(ctx context.Context, client *Client, flow int, days int) ([]ShareChangeEvent, error) {
	if client == nil {
		client = NewClient("", nil)
	}
	if days <= 0 {
		days = DefaultCorpDays
	}
	endpoint := fmt.Sprintf("/Instrument/GetInstrumentShareChangeByFlow/%d/%d", flow, days)
	var payload rawShareChangePayload
	if err := client.GetJSON(ctx, endpoint, &payload); err != nil {
		return nil, fmt.Errorf("fetch share change by flow %d: %w", flow, err)
	}
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	return parseShareChangeItems(payload.Items(), "", DefaultShareChangeSource, nowStr), nil
}

// FetchInstrumentShareChange fetches corporate share change events for a specific instrument insCode.
func FetchInstrumentShareChange(ctx context.Context, client *Client, insCode string) ([]ShareChangeEvent, error) {
	if client == nil {
		client = NewClient("", nil)
	}
	insCode = strings.TrimSpace(insCode)
	if insCode == "" {
		return nil, fmt.Errorf("insCode is required")
	}
	endpoint := fmt.Sprintf("/Instrument/GetInstrumentShareChange/%s", insCode)
	var payload rawShareChangePayload
	if err := client.GetJSON(ctx, endpoint, &payload); err != nil {
		return nil, fmt.Errorf("fetch share change for %s: %w", insCode, err)
	}
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	return parseShareChangeItems(payload.Items(), insCode, DefaultShareChangeSource, nowStr), nil
}

// FetchPriceAdjustList fetches corporate price adjust events for a specific instrument insCode.
func FetchPriceAdjustList(ctx context.Context, client *Client, insCode string) ([]PriceAdjustEvent, error) {
	if client == nil {
		client = NewClient("", nil)
	}
	insCode = strings.TrimSpace(insCode)
	if insCode == "" {
		return nil, fmt.Errorf("insCode is required")
	}
	endpoint := fmt.Sprintf("/ClosingPrice/GetPriceAdjustList/%s", insCode)
	var payload rawPriceAdjustPayload
	if err := client.GetJSON(ctx, endpoint, &payload); err != nil {
		return nil, fmt.Errorf("fetch price adjust list for %s: %w", insCode, err)
	}
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	return parsePriceAdjustItems(payload.Items(), insCode, DefaultPriceAdjustSource, nowStr), nil
}

// IngestPriceAdjustEvents deduplicates events by (ins_code, d_even) and upserts them into price_adjust_events table.
func IngestPriceAdjustEvents(ctx context.Context, db *sql.DB, events []PriceAdjustEvent) error {
	if len(events) == 0 {
		return nil
	}

	dedupMap := make(map[string]PriceAdjustEvent)
	var keys []string
	for _, ev := range events {
		if ev.InsCode == "" || ev.DEven == 0 {
			continue
		}
		k := fmt.Sprintf("%s:%d", ev.InsCode, ev.DEven)
		if _, exists := dedupMap[k]; !exists {
			keys = append(keys, k)
		}
		dedupMap[k] = ev
	}
	if len(keys) == 0 {
		return nil
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO price_adjust_events (
			ins_code, d_even, symbol, p_closing, p_closing_not_adjusted,
			corporate_type_code, ratio, source, fetched_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(ins_code, d_even) DO UPDATE SET
			symbol = excluded.symbol,
			p_closing = excluded.p_closing,
			p_closing_not_adjusted = excluded.p_closing_not_adjusted,
			corporate_type_code = excluded.corporate_type_code,
			ratio = excluded.ratio,
			source = excluded.source,
			fetched_at = excluded.fetched_at
	`)
	if err != nil {
		return fmt.Errorf("prepare stmt: %w", err)
	}
	defer stmt.Close()

	for _, k := range keys {
		ev := dedupMap[k]
		var corpCode any
		if ev.CorporateTypeCode != nil {
			corpCode = *ev.CorporateTypeCode
		}
		_, err := stmt.ExecContext(ctx,
			ev.InsCode, ev.DEven, ev.Symbol, ev.PClosing, ev.PClosingNotAdjusted,
			corpCode, ev.Ratio, ev.Source, ev.FetchedAt,
		)
		if err != nil {
			return fmt.Errorf("exec price_adjust_events %s/%d: %w", ev.InsCode, ev.DEven, err)
		}
	}

	return tx.Commit()
}

// IngestShareChangeEvents deduplicates events by (ins_code, d_even) and upserts them into share_change_events table.
func IngestShareChangeEvents(ctx context.Context, db *sql.DB, events []ShareChangeEvent) error {
	if len(events) == 0 {
		return nil
	}

	dedupMap := make(map[string]ShareChangeEvent)
	var keys []string
	for _, ev := range events {
		if ev.InsCode == "" || ev.DEven == 0 {
			continue
		}
		k := fmt.Sprintf("%s:%d", ev.InsCode, ev.DEven)
		if _, exists := dedupMap[k]; !exists {
			keys = append(keys, k)
		}
		dedupMap[k] = ev
	}
	if len(keys) == 0 {
		return nil
	}

	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	stmt, err := tx.PrepareContext(ctx, `
		INSERT INTO share_change_events (
			ins_code, d_even, symbol, shares_old, shares_new,
			ratio, source, fetched_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(ins_code, d_even) DO UPDATE SET
			symbol = excluded.symbol,
			shares_old = excluded.shares_old,
			shares_new = excluded.shares_new,
			ratio = excluded.ratio,
			source = excluded.source,
			fetched_at = excluded.fetched_at
	`)
	if err != nil {
		return fmt.Errorf("prepare stmt: %w", err)
	}
	defer stmt.Close()

	for _, k := range keys {
		ev := dedupMap[k]
		_, err := stmt.ExecContext(ctx,
			ev.InsCode, ev.DEven, ev.Symbol, ev.SharesOld, ev.SharesNew,
			ev.Ratio, ev.Source, ev.FetchedAt,
		)
		if err != nil {
			return fmt.Errorf("exec share_change_events %s/%d: %w", ev.InsCode, ev.DEven, err)
		}
	}

	return tx.Commit()
}

// DetectPriceAdjustAmendments compares incoming events against the database and returns:
// - amendments: count of existing (ins_code, d_even) rows where ratio has changed (|old - new| > 1e-12)
// - lateRows: count of incoming events that do not yet exist in the database
func DetectPriceAdjustAmendments(ctx context.Context, db *sql.DB, events []PriceAdjustEvent) (amendments int, lateRows int, err error) {
	dedupMap := make(map[string]PriceAdjustEvent)
	for _, ev := range events {
		if ev.InsCode == "" || ev.DEven == 0 {
			continue
		}
		k := fmt.Sprintf("%s:%d", ev.InsCode, ev.DEven)
		dedupMap[k] = ev
	}
	if len(dedupMap) == 0 {
		return 0, 0, nil
	}

	stmt, err := db.PrepareContext(ctx, "SELECT ratio FROM price_adjust_events WHERE ins_code = ? AND d_even = ?")
	if err != nil {
		return 0, 0, fmt.Errorf("prepare query: %w", err)
	}
	defer stmt.Close()

	for _, ev := range dedupMap {
		var existingRatio sql.NullFloat64
		err := stmt.QueryRowContext(ctx, ev.InsCode, ev.DEven).Scan(&existingRatio)
		if errors.Is(err, sql.ErrNoRows) {
			lateRows++
			continue
		}
		if err != nil {
			return 0, 0, fmt.Errorf("query %s/%d: %w", ev.InsCode, ev.DEven, err)
		}
		if !existingRatio.Valid {
			if ev.Ratio != 0 {
				amendments++
			}
		} else if math.Abs(existingRatio.Float64-ev.Ratio) > 1e-12 {
			amendments++
		}
	}
	return amendments, lateRows, nil
}

// DetectShareChangeAmendments compares incoming events against the database and returns:
// - amendments: count of existing (ins_code, d_even) rows where ratio has changed (|old - new| > 1e-12)
// - lateRows: count of incoming events that do not yet exist in the database
func DetectShareChangeAmendments(ctx context.Context, db *sql.DB, events []ShareChangeEvent) (amendments int, lateRows int, err error) {
	dedupMap := make(map[string]ShareChangeEvent)
	for _, ev := range events {
		if ev.InsCode == "" || ev.DEven == 0 {
			continue
		}
		k := fmt.Sprintf("%s:%d", ev.InsCode, ev.DEven)
		dedupMap[k] = ev
	}
	if len(dedupMap) == 0 {
		return 0, 0, nil
	}

	stmt, err := db.PrepareContext(ctx, "SELECT ratio FROM share_change_events WHERE ins_code = ? AND d_even = ?")
	if err != nil {
		return 0, 0, fmt.Errorf("prepare query: %w", err)
	}
	defer stmt.Close()

	for _, ev := range dedupMap {
		var existingRatio sql.NullFloat64
		err := stmt.QueryRowContext(ctx, ev.InsCode, ev.DEven).Scan(&existingRatio)
		if errors.Is(err, sql.ErrNoRows) {
			lateRows++
			continue
		}
		if err != nil {
			return 0, 0, fmt.Errorf("query %s/%d: %w", ev.InsCode, ev.DEven, err)
		}
		if !existingRatio.Valid {
			if ev.Ratio != 0 {
				amendments++
			}
		} else if math.Abs(existingRatio.Float64-ev.Ratio) > 1e-12 {
			amendments++
		}
	}
	return amendments, lateRows, nil
}

// SyncCorporateEvents orchestrates corporate actions ingestion.
// When insCode is provided, it fetches specific instrument events via FetchPriceAdjustList and FetchInstrumentShareChange.
// When insCode is empty, it queries flow 1 (Bourse) and flow 2 (Fara Bourse) for both price adjustments and share changes.
func SyncCorporateEvents(ctx context.Context, client *http.Client, db *sql.DB, insCode string) error {
	tClient := NewClient("", client)
	if err := EnsureCorporateSchema(ctx, db); err != nil {
		return fmt.Errorf("ensure corporate schema: %w", err)
	}

	insCode = strings.TrimSpace(insCode)
	if insCode != "" {
		var errs []error
		paEvents, err := FetchPriceAdjustList(ctx, tClient, insCode)
		if err != nil {
			errs = append(errs, fmt.Errorf("fetch price adjust list: %w", err))
		} else if len(paEvents) > 0 {
			if err := IngestPriceAdjustEvents(ctx, db, paEvents); err != nil {
				return fmt.Errorf("ingest price adjust: %w", err)
			}
		}

		scEvents, err := FetchInstrumentShareChange(ctx, tClient, insCode)
		if err != nil {
			errs = append(errs, fmt.Errorf("fetch share change: %w", err))
		} else if len(scEvents) > 0 {
			if err := IngestShareChangeEvents(ctx, db, scEvents); err != nil {
				return fmt.Errorf("ingest share change: %w", err)
			}
		}

		if len(errs) == 2 {
			return errors.Join(errs...)
		}
		return nil
	}

	var allPA []PriceAdjustEvent
	var allSC []ShareChangeEvent
	var fetchErrs []error

	for _, flow := range []int{1, 2} {
		pa, err := FetchPriceAdjustByFlow(ctx, tClient, flow, DefaultCorpSize)
		if err != nil {
			fetchErrs = append(fetchErrs, fmt.Errorf("flow %d price adjust: %w", flow, err))
		} else {
			allPA = append(allPA, pa...)
		}

		sc, err := FetchInstrumentShareChangeByFlow(ctx, tClient, flow, DefaultCorpDays)
		if err != nil {
			fetchErrs = append(fetchErrs, fmt.Errorf("flow %d share change: %w", flow, err))
		} else {
			allSC = append(allSC, sc...)
		}
	}

	if len(fetchErrs) == 4 {
		return fmt.Errorf("all corporate event flows failed: %w", errors.Join(fetchErrs...))
	}

	if len(allPA) > 0 {
		if err := IngestPriceAdjustEvents(ctx, db, allPA); err != nil {
			return fmt.Errorf("ingest price adjust: %w", err)
		}
	}
	if len(allSC) > 0 {
		if err := IngestShareChangeEvents(ctx, db, allSC); err != nil {
			return fmt.Errorf("ingest share change: %w", err)
		}
	}

	return nil
}
