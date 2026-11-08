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

// MarketWatchRow represents a single instrument record in the market_watch table.
type MarketWatchRow struct {
	InsCode        string  `json:"ins_code"`
	DEven          int     `json:"d_even"`
	HEven          int     `json:"h_even"`
	PClosing       float64 `json:"p_closing"`
	PLast          float64 `json:"p_last"`
	PriceMin       float64 `json:"price_min"`
	PriceMax       float64 `json:"price_max"`
	AllowedMin     float64 `json:"allowed_min"`
	AllowedMax     float64 `json:"allowed_max"`
	PriceYesterday float64 `json:"price_yesterday"`
	PriceFirst     float64 `json:"price_first"`
	QTotTran       float64 `json:"q_tot_tran"`
	QTotCap        float64 `json:"q_tot_cap"`
	ZTotTran       float64 `json:"z_tot_tran"`
	PriceChange    float64 `json:"price_change"`
	EPS            float64 `json:"eps"`
	PE             float64 `json:"pe"`
	TotalShares    float64 `json:"total_shares"`
	SectorCode     string  `json:"sector_code"`
	FetchedAt      string  `json:"fetched_at"`
	BuyQVol        float64 `json:"buy_q_vol"`
	BuyQVal        float64 `json:"buy_q_val"`
	BuyQCnt        float64 `json:"buy_q_cnt"`
	SellQVol       float64 `json:"sell_q_vol"`
	SellQVal       float64 `json:"sell_q_val"`
	SellQCnt       float64 `json:"sell_q_cnt"`
	BuyQ1Vol       float64 `json:"buy_q1_vol"`
	BuyQ1Px        float64 `json:"buy_q1_px"`
	SellQ1Vol      float64 `json:"sell_q1_vol"`
	SellQ1Px       float64 `json:"sell_q1_px"`
	BuyQ1Cnt       float64 `json:"buy_q1_cnt"`
	MarketCap      float64 `json:"market_cap"`
	MarketCapSrc   string  `json:"market_cap_src"`
	Flow           int     `json:"flow"`
	PRedTran       float64 `json:"p_red_tran"`
	BuyOP          float64 `json:"buy_op"`
}

// InstrumentRow represents an instrument's master metadata in the instruments table.
type InstrumentRow struct {
	InsCode     string  `json:"ins_code"`
	LVal18      string  `json:"l_val18"`
	LVal30      string  `json:"l_val30"`
	SectorCode  string  `json:"sector_code"`
	SectorName  string  `json:"sector_name"`
	TotalShares float64 `json:"total_shares"`
	EPS         float64 `json:"eps"`
	PE          float64 `json:"pe"`
	BaseVol     float64 `json:"base_vol"`
	UpdatedAt   string  `json:"updated_at"`
	ISIN        string  `json:"isin"`
	CGrValCot   string  `json:"c_gr_val_cot"`
	PaperType   int     `json:"paper_type"`
}

// rawBestLimit represents an order line in blDs.
type rawBestLimit struct {
	Qmd any `json:"qmd"` // buy volume
	Pmd any `json:"pmd"` // buy price
	Zmd any `json:"zmd"` // buy count
	Qmo any `json:"qmo"` // sell volume
	Pmo any `json:"pmo"` // sell price
	Zmo any `json:"zmo"` // sell count
}

// rawMarketWatchItem represents a raw symbol item from GetMarketWatch.
type rawMarketWatchItem struct {
	InsCode     any            `json:"insCode"`
	DEven       any            `json:"dEven"`
	HEven       any            `json:"hEven"`
	Pcl         any            `json:"pcl"`      // closing price
	Pdv         any            `json:"pdv"`      // last price
	Pmn         any            `json:"pmn"`      // price min
	Pmx         any            `json:"pmx"`      // price max
	PMin        any            `json:"pMin"`     // allowed min
	PMax        any            `json:"pMax"`     // allowed max
	Py          any            `json:"py"`       // yesterday price
	Pf          any            `json:"pf"`       // first price
	Qtj         any            `json:"qtj"`      // total volume
	Qtc         any            `json:"qtc"`      // total value
	Ztt         any            `json:"ztt"`      // total trades
	Pc          any            `json:"pc"`       // price change
	EPS         any            `json:"eps"`
	PE          any            `json:"pe"`
	Ztd         any            `json:"ztd"`      // total shares
	CSV         any            `json:"csv"`      // sector code
	Lva         any            `json:"lva"`      // l_val18 (symbol)
	Lvc         any            `json:"lvc"`      // l_val30 (company name)
	Bv          any            `json:"bv"`       // base volume
	InsID       any            `json:"insID"`    // isin
	CGrValCot   any            `json:"cGrValCot"`
	Flow        any            `json:"flow"`
	PRedTran    any            `json:"pRedTran"`
	BuyOP       any            `json:"buyOP"`
	PaperType   any            `json:"paperType"`
	MarketValue any            `json:"marketValue"`
	BlDs        []rawBestLimit `json:"blDs"`
}

type rawMarketWatchResponse struct {
	MarketWatch  []rawMarketWatchItem `json:"marketwatch"`
	MarketWatch2 []rawMarketWatchItem `json:"marketWatch"`
	Direct       []rawMarketWatchItem
}

func (r *rawMarketWatchResponse) UnmarshalJSON(data []byte) error {
	var arr []rawMarketWatchItem
	if err := json.Unmarshal(data, &arr); err == nil {
		r.Direct = arr
		return nil
	}
	type Alias rawMarketWatchResponse
	var alias Alias
	if err := json.Unmarshal(data, &alias); err != nil {
		return err
	}
	r.MarketWatch = alias.MarketWatch
	r.MarketWatch2 = alias.MarketWatch2
	return nil
}

func (r *rawMarketWatchResponse) Items() []rawMarketWatchItem {
	if len(r.Direct) > 0 {
		return r.Direct
	}
	if len(r.MarketWatch) > 0 {
		return r.MarketWatch
	}
	return r.MarketWatch2
}

type rawStaticDataItem struct {
	Type string `json:"type"`
	Code any    `json:"code"`
	Name string `json:"name"`
}

type rawStaticDataResponse struct {
	StaticData  []rawStaticDataItem `json:"staticData"`
	StaticData2 []rawStaticDataItem `json:"StaticData"`
	Direct      []rawStaticDataItem
}

func (r *rawStaticDataResponse) UnmarshalJSON(data []byte) error {
	var arr []rawStaticDataItem
	if err := json.Unmarshal(data, &arr); err == nil {
		r.Direct = arr
		return nil
	}
	type Alias rawStaticDataResponse
	var alias Alias
	if err := json.Unmarshal(data, &alias); err != nil {
		return err
	}
	r.StaticData = alias.StaticData
	r.StaticData2 = alias.StaticData2
	return nil
}

func (r *rawStaticDataResponse) Items() []rawStaticDataItem {
	if len(r.Direct) > 0 {
		return r.Direct
	}
	if len(r.StaticData) > 0 {
		return r.StaticData
	}
	return r.StaticData2
}

// FetchMarketWatch fetches the live market watch snapshot and static industry group data,
// calculates market caps, extracts 5-limit order depths, and returns rows for market_watch and instruments.
func (c *Client) FetchMarketWatch(ctx context.Context) ([]MarketWatchRow, []InstrumentRow, error) {
	// 1. Fetch industry groups mapping
	sectorMap := make(map[string]string)
	var staticResp rawStaticDataResponse
	if err := c.GetJSON(ctx, "/StaticData/GetStaticData", &staticResp); err != nil {
		// Log / continue on non-fatal static data error unless context is cancelled
		if ctx.Err() != nil {
			return nil, nil, ctx.Err()
		}
	} else {
		for _, item := range staticResp.Items() {
			if strings.EqualFold(item.Type, "IndustrialGroup") {
				code := strings.TrimSpace(toString(item.Code))
				if code != "" {
					sectorMap[code] = strings.TrimSpace(item.Name)
				}
			}
		}
	}

	// 2. Fetch live market watch
	// TSETMC standard query with paperTypes 1..9
	endpoint := "/ClosingPrice/GetMarketWatch?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3&paperTypes[3]=4&paperTypes[4]=5&paperTypes[5]=6&paperTypes[7]=8&paperTypes[8]=9&showTraded=false&withBestLimits=true&hEven=0"
	var mwResp rawMarketWatchResponse
	if err := c.GetJSON(ctx, endpoint, &mwResp); err != nil {
		return nil, nil, fmt.Errorf("fetch market watch: %w", err)
	}

	rawItems := mwResp.Items()
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")

	mwRows := make([]MarketWatchRow, 0, len(rawItems))
	instRows := make([]InstrumentRow, 0, len(rawItems))

	for _, item := range rawItems {
		insCode := strings.TrimSpace(toString(item.InsCode))
		if insCode == "" {
			continue
		}

		secCode := strings.TrimSpace(toString(item.CSV))
		secName := sectorMap[secCode]

		pcl := toFloat(item.Pcl)
		pdv := toFloat(item.Pdv)
		pLast := pdv
		if pLast == 0 {
			pLast = pcl
		}

		totalShares := toFloat(item.Ztd)
		rawMcap := toFloat(item.MarketValue)

		var marketCap float64
		var marketCapSrc string
		if rawMcap > 0 {
			marketCap = rawMcap
			marketCapSrc = "tse_raw"
		} else if pcl > 0 && totalShares > 0 {
			marketCap = pcl * totalShares
			marketCapSrc = "tse_board_calc"
		}

		// Depth aggregation from blDs
		var (
			buyQVol, buyQVal, buyQCnt   float64
			sellQVol, sellQVal, sellQCnt float64
			buyQ1Vol, buyQ1Px, buyQ1Cnt  float64
			sellQ1Vol, sellQ1Px          float64
		)
		for i, bl := range item.BlDs {
			qmd := toFloat(bl.Qmd)
			pmd := toFloat(bl.Pmd)
			zmd := toFloat(bl.Zmd)
			qmo := toFloat(bl.Qmo)
			pmo := toFloat(bl.Pmo)
			zmo := toFloat(bl.Zmo)

			buyQVol += qmd
			buyQVal += qmd * pmd
			buyQCnt += zmd

			sellQVol += qmo
			sellQVal += qmo * pmo
			sellQCnt += zmo

			if i == 0 {
				buyQ1Vol = qmd
				buyQ1Px = pmd
				buyQ1Cnt = zmd
				sellQ1Vol = qmo
				sellQ1Px = pmo
			}
		}

		mwRows = append(mwRows, MarketWatchRow{
			InsCode:        insCode,
			DEven:          toInt(item.DEven),
			HEven:          toInt(item.HEven),
			PClosing:       pcl,
			PLast:          pLast,
			PriceMin:       toFloat(item.Pmn),
			PriceMax:       toFloat(item.Pmx),
			AllowedMin:     toFloat(item.PMin),
			AllowedMax:     toFloat(item.PMax),
			PriceYesterday: toFloat(item.Py),
			PriceFirst:     toFloat(item.Pf),
			QTotTran:       toFloat(item.Qtj),
			QTotCap:        toFloat(item.Qtc),
			ZTotTran:       toFloat(item.Ztt),
			PriceChange:    toFloat(item.Pc),
			EPS:            toFloat(item.EPS),
			PE:             toFloat(item.PE),
			TotalShares:    totalShares,
			SectorCode:     secCode,
			FetchedAt:      nowStr,
			BuyQVol:        buyQVol,
			BuyQVal:        buyQVal,
			BuyQCnt:        buyQCnt,
			SellQVol:       sellQVol,
			SellQVal:       sellQVal,
			SellQCnt:       sellQCnt,
			BuyQ1Vol:       buyQ1Vol,
			BuyQ1Px:        buyQ1Px,
			SellQ1Vol:      sellQ1Vol,
			SellQ1Px:       sellQ1Px,
			BuyQ1Cnt:       buyQ1Cnt,
			MarketCap:      marketCap,
			MarketCapSrc:   marketCapSrc,
			Flow:           toInt(item.Flow),
			PRedTran:       toFloat(item.PRedTran),
			BuyOP:          toFloat(item.BuyOP),
		})

		instRows = append(instRows, InstrumentRow{
			InsCode:     insCode,
			LVal18:      strings.TrimSpace(toString(item.Lva)),
			LVal30:      strings.TrimSpace(toString(item.Lvc)),
			SectorCode:  secCode,
			SectorName:  secName,
			TotalShares: totalShares,
			EPS:         toFloat(item.EPS),
			PE:          toFloat(item.PE),
			BaseVol:     toFloat(item.Bv),
			UpdatedAt:   nowStr,
			ISIN:        strings.TrimSpace(toString(item.InsID)),
			CGrValCot:   strings.TrimSpace(toString(item.CGrValCot)),
			PaperType:   toInt(item.PaperType),
		})
	}

	return mwRows, instRows, nil
}

// EnsureMarketWatchSchema creates tables market_watch and instruments if they do not exist,
// and ensures required indexes and columns exist idempotently.
func EnsureMarketWatchSchema(db *sql.DB) error {
	ddls := []string{
		`CREATE TABLE IF NOT EXISTS instruments (
			ins_code TEXT PRIMARY KEY,
			l_val18 TEXT,
			l_val30 TEXT,
			sector_code TEXT,
			sector_name TEXT,
			total_shares REAL,
			eps REAL,
			pe REAL,
			base_vol REAL,
			updated_at TEXT,
			isin TEXT,
			c_gr_val_cot TEXT,
			paper_type INTEGER
		);`,
		`CREATE INDEX IF NOT EXISTS ix_instruments_lval18 ON instruments(l_val18);`,
		`CREATE INDEX IF NOT EXISTS ix_instruments_lval30 ON instruments(l_val30);`,
		`CREATE TABLE IF NOT EXISTS market_watch (
			ins_code TEXT PRIMARY KEY,
			d_even INTEGER,
			h_even INTEGER,
			p_closing REAL,
			p_last REAL,
			price_min REAL,
			price_max REAL,
			allowed_min REAL,
			allowed_max REAL,
			price_yesterday REAL,
			price_first REAL,
			q_tot_tran REAL,
			q_tot_cap REAL,
			z_tot_tran REAL,
			price_change REAL,
			eps REAL,
			pe REAL,
			total_shares REAL,
			sector_code TEXT,
			fetched_at TEXT,
			buy_q_vol REAL,
			buy_q_val REAL,
			buy_q_cnt REAL,
			sell_q_vol REAL,
			sell_q_val REAL,
			sell_q_cnt REAL,
			buy_q1_vol REAL,
			buy_q1_px REAL,
			sell_q1_vol REAL,
			sell_q1_px REAL,
			buy_q1_cnt REAL,
			market_cap REAL,
			market_cap_src TEXT,
			flow INTEGER,
			p_red_tran REAL,
			buy_op REAL
		);`,
	}

	for _, ddl := range ddls {
		if _, err := db.Exec(ddl); err != nil {
			return fmt.Errorf("ensure schema exec: %w", err)
		}
	}

	// Idempotent column check for older database versions
	if err := ensureColumnsExist(db, "instruments", map[string]string{
		"isin":         "TEXT",
		"c_gr_val_cot": "TEXT",
		"paper_type":   "INTEGER",
	}); err != nil {
		return err
	}

	if err := ensureColumnsExist(db, "market_watch", map[string]string{
		"market_cap":     "REAL",
		"market_cap_src": "TEXT",
		"flow":           "INTEGER",
		"p_red_tran":     "REAL",
		"buy_op":         "REAL",
		"buy_q_vol":      "REAL",
		"buy_q_val":      "REAL",
		"buy_q_cnt":      "REAL",
		"sell_q_vol":     "REAL",
		"sell_q_val":     "REAL",
		"sell_q_cnt":     "REAL",
		"buy_q1_vol":     "REAL",
		"buy_q1_px":      "REAL",
		"sell_q1_vol":    "REAL",
		"sell_q1_px":     "REAL",
		"buy_q1_cnt":     "REAL",
	}); err != nil {
		return err
	}

	return nil
}

// IngestMarketWatch upserts rows into instruments and market_watch in a single transaction.
func IngestMarketWatch(ctx context.Context, db *sql.DB, rows []MarketWatchRow, insts []InstrumentRow) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback()

	// 1. Upsert instruments
	instStmt, err := tx.PrepareContext(ctx, `
		INSERT INTO instruments (
			ins_code, l_val18, l_val30, sector_code, sector_name, total_shares,
			eps, pe, base_vol, updated_at, isin, c_gr_val_cot, paper_type
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(ins_code) DO UPDATE SET
			l_val18 = excluded.l_val18,
			l_val30 = excluded.l_val30,
			sector_code = excluded.sector_code,
			sector_name = excluded.sector_name,
			total_shares = excluded.total_shares,
			eps = excluded.eps,
			pe = excluded.pe,
			base_vol = excluded.base_vol,
			updated_at = excluded.updated_at,
			isin = COALESCE(NULLIF(excluded.isin, ''), instruments.isin),
			c_gr_val_cot = COALESCE(NULLIF(excluded.c_gr_val_cot, ''), instruments.c_gr_val_cot),
			paper_type = excluded.paper_type
	`)
	if err != nil {
		return fmt.Errorf("prepare inst stmt: %w", err)
	}
	defer instStmt.Close()

	for _, inst := range insts {
		if inst.InsCode == "" {
			continue
		}
		_, err := instStmt.ExecContext(ctx,
			inst.InsCode, inst.LVal18, inst.LVal30, inst.SectorCode, inst.SectorName,
			inst.TotalShares, inst.EPS, inst.PE, inst.BaseVol, inst.UpdatedAt,
			inst.ISIN, inst.CGrValCot, inst.PaperType,
		)
		if err != nil {
			return fmt.Errorf("exec inst %s: %w", inst.InsCode, err)
		}
	}

	// 2. Upsert market_watch
	mwStmt, err := tx.PrepareContext(ctx, `
		INSERT INTO market_watch (
			ins_code, d_even, h_even, p_closing, p_last, price_min, price_max,
			allowed_min, allowed_max, price_yesterday, price_first, q_tot_tran,
			q_tot_cap, z_tot_tran, price_change, eps, pe, total_shares,
			sector_code, fetched_at, buy_q_vol, buy_q_val, buy_q_cnt,
			sell_q_vol, sell_q_val, sell_q_cnt, buy_q1_vol, buy_q1_px,
			sell_q1_vol, sell_q1_px, buy_q1_cnt, market_cap, market_cap_src,
			flow, p_red_tran, buy_op
		) VALUES (
			?, ?, ?, ?, ?, ?, ?,
			?, ?, ?, ?, ?,
			?, ?, ?, ?, ?, ?,
			?, ?, ?, ?, ?,
			?, ?, ?, ?, ?,
			?, ?, ?, ?, ?,
			?, ?, ?
		)
		ON CONFLICT(ins_code) DO UPDATE SET
			d_even = excluded.d_even,
			h_even = excluded.h_even,
			p_closing = excluded.p_closing,
			p_last = excluded.p_last,
			price_min = excluded.price_min,
			price_max = excluded.price_max,
			allowed_min = excluded.allowed_min,
			allowed_max = excluded.allowed_max,
			price_yesterday = excluded.price_yesterday,
			price_first = excluded.price_first,
			q_tot_tran = excluded.q_tot_tran,
			q_tot_cap = excluded.q_tot_cap,
			z_tot_tran = excluded.z_tot_tran,
			price_change = excluded.price_change,
			eps = excluded.eps,
			pe = excluded.pe,
			total_shares = excluded.total_shares,
			sector_code = excluded.sector_code,
			fetched_at = excluded.fetched_at,
			buy_q_vol = excluded.buy_q_vol,
			buy_q_val = excluded.buy_q_val,
			buy_q_cnt = excluded.buy_q_cnt,
			sell_q_vol = excluded.sell_q_vol,
			sell_q_val = excluded.sell_q_val,
			sell_q_cnt = excluded.sell_q_cnt,
			buy_q1_vol = excluded.buy_q1_vol,
			buy_q1_px = excluded.buy_q1_px,
			sell_q1_vol = excluded.sell_q1_vol,
			sell_q1_px = excluded.sell_q1_px,
			buy_q1_cnt = excluded.buy_q1_cnt,
			market_cap = excluded.market_cap,
			market_cap_src = excluded.market_cap_src,
			flow = CASE WHEN excluded.flow != 0 THEN excluded.flow ELSE market_watch.flow END,
			p_red_tran = excluded.p_red_tran,
			buy_op = excluded.buy_op
	`)
	if err != nil {
		return fmt.Errorf("prepare mw stmt: %w", err)
	}
	defer mwStmt.Close()

	for _, row := range rows {
		if row.InsCode == "" {
			continue
		}
		_, err := mwStmt.ExecContext(ctx,
			row.InsCode, row.DEven, row.HEven, row.PClosing, row.PLast, row.PriceMin, row.PriceMax,
			row.AllowedMin, row.AllowedMax, row.PriceYesterday, row.PriceFirst, row.QTotTran,
			row.QTotCap, row.ZTotTran, row.PriceChange, row.EPS, row.PE, row.TotalShares,
			row.SectorCode, row.FetchedAt, row.BuyQVol, row.BuyQVal, row.BuyQCnt,
			row.SellQVol, row.SellQVal, row.SellQCnt, row.BuyQ1Vol, row.BuyQ1Px,
			row.SellQ1Vol, row.SellQ1Px, row.BuyQ1Cnt, row.MarketCap, row.MarketCapSrc,
			row.Flow, row.PRedTran, row.BuyOP,
		)
		if err != nil {
			return fmt.Errorf("exec mw %s: %w", row.InsCode, err)
		}
	}

	return tx.Commit()
}

func ensureColumnsExist(db *sql.DB, table string, cols map[string]string) error {
	rows, err := db.Query(fmt.Sprintf("PRAGMA table_info(%s)", table))
	if err != nil {
		return nil
	}
	defer rows.Close()

	existing := make(map[string]bool)
	for rows.Next() {
		var cid int
		var name, ctype string
		var notnull, pk int
		var dfltValue any
		if err := rows.Scan(&cid, &name, &ctype, &notnull, &dfltValue, &pk); err == nil {
			existing[strings.ToLower(name)] = true
		}
	}

	for col, colType := range cols {
		if !existing[strings.ToLower(col)] {
			alter := fmt.Sprintf("ALTER TABLE %s ADD COLUMN %s %s", table, col, colType)
			_, _ = db.Exec(alter)
		}
	}
	return nil
}

// Helper conversion routines
func toFloat(v any) float64 {
	if v == nil {
		return 0
	}
	switch val := v.(type) {
	case float64:
		return val
	case float32:
		return float64(val)
	case int:
		return float64(val)
	case int64:
		return float64(val)
	case string:
		f, _ := strconv.ParseFloat(strings.TrimSpace(val), 64)
		return f
	case json.Number:
		f, _ := val.Float64()
		return f
	}
	return 0
}

func toInt(v any) int {
	if v == nil {
		return 0
	}
	switch val := v.(type) {
	case float64:
		return int(val)
	case int:
		return val
	case int64:
		return int(val)
	case string:
		i, _ := strconv.Atoi(strings.TrimSpace(val))
		return i
	case json.Number:
		i, _ := val.Int64()
		return int(i)
	}
	return 0
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	switch val := v.(type) {
	case string:
		return strings.TrimSpace(val)
	case float64:
		return strconv.FormatInt(int64(val), 10)
	case int:
		return strconv.Itoa(val)
	case int64:
		return strconv.FormatInt(val, 10)
	case fmt.Stringer:
		return val.String()
	default:
		return fmt.Sprintf("%v", v)
	}
}
