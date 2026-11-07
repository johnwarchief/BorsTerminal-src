// Package live feeds the TSE market watch into the board's live overlay.
//
// One poller, one TSE request per tick. The DB remains the durable snapshot;
// this package only overrides the volatile columns in memory so /api/market
// can be as fresh as the source without a 60s cache wait.
package live

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/store"

	_ "modernc.org/sqlite"
)

const DefaultURL = "https://cdn.tsetmc.ir/api/ClosingPrice/GetMarketWatch" +
	"?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3" +
	"&paperTypes[3]=4&paperTypes[4]=5&paperTypes[5]=6&paperTypes[6]=7" +
	"&paperTypes[7]=8&paperTypes[8]=9&showTraded=false" +
	"&withBestLimits=true&hEven=0"

const failureBackoff = 30 * time.Second

// bookPersistEvery keeps the five-level depth table fresh without rewriting
// ~3k rows on every 5s market_watch persist. The drawer polls every 30s.
const bookPersistEvery = 30 * time.Second

type Book struct {
	Txt      string
	BuyVol   float64
	BuyVal   float64
	BuyCnt   float64
	SellVol  float64
	SellVal  float64
	SellCnt  float64
	Buy1Vol  float64
	Buy1Px   float64
	Sell1Vol float64
	Sell1Px  float64
	Buy1Cnt  float64
	OK       bool
}

type Row struct {
	Symbol  string
	Closing float64
	Last    float64
	Change  float64
	Prev    float64
	Max     float64
	Min     float64
	First   float64
	Volume  float64
	Value   float64
	Trades  float64
	PE      float64
	DEven   int64
	HEven   int64
	Book    Book
}

type Snapshot struct {
	Rows    map[string]Row
	HEven   int64
	Updated time.Time
	Err     string
}

type Feed struct {
	mu       sync.RWMutex
	snap     Snapshot
	gen      int64
	failTill time.Time
	interval time.Duration
	url      string
	client   *http.Client

	// persistence is optional; when a DB path is set, every persistEvery the
	// live snapshot updates today's market_watch rows and market_sync.json.
	dbPath       string
	persistEvery time.Duration
	lastPersist  time.Time
	persistErr   string
	db           *sql.DB
	insCodes     map[string]string
	dEven        int64
	lastBook     time.Time
	started      time.Time
}

func New(interval time.Duration) *Feed {
	if interval < 500*time.Millisecond {
		interval = 500 * time.Millisecond
	}
	return &Feed{
		interval: interval,
		url:      DefaultURL,
		client:   &http.Client{Timeout: 15 * time.Second},
		snap:     Snapshot{Rows: map[string]Row{}},
		started:  time.Now(),
	}
}

// SetURL/SetClient are for the offline feed tests; production keeps defaults.
func (f *Feed) SetURL(url string)        { f.url = url }
func (f *Feed) SetClient(c *http.Client) { f.client = c }

// EnablePersistence makes the live snapshot durable at every persistEvery.
// The DB is opened lazily on the first successful tick.
func (f *Feed) EnablePersistence(dbPath string, every time.Duration) {
	if every < time.Second {
		every = 5 * time.Second
	}
	f.mu.Lock()
	f.dbPath = dbPath
	f.persistEvery = every
	f.mu.Unlock()
}

// Close releases the persistence handle. The in-memory feed keeps working.
func (f *Feed) Close() error {
	f.mu.Lock()
	db := f.db
	f.db = nil
	f.mu.Unlock()
	if db != nil {
		return db.Close()
	}
	return nil
}

func (f *Feed) Start(ctx context.Context) {
	go func() {
		f.FetchOnce(ctx)
		t := time.NewTicker(f.interval)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				f.FetchOnce(ctx)
			}
		}
	}()
}

// FetchOnce performs exactly one TSE request. Failures keep the last snapshot
// and back off for 30s; they never write a fabricated row or zero the board.
func (f *Feed) FetchOnce(ctx context.Context) {
	f.mu.RLock()
	failTill := f.failTill
	f.mu.RUnlock()
	if time.Now().Before(failTill) {
		return
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, f.url, nil)
	if err != nil {
		f.fail(err)
		return
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "BorsTerminal-Go/1.0")
	resp, err := f.client.Do(req)
	if err != nil {
		f.fail(err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusForbidden || resp.StatusCode == http.StatusTooManyRequests {
		f.fail(fmt.Errorf("TSE HTTP %d", resp.StatusCode))
		return
	}
	if resp.StatusCode != http.StatusOK {
		f.fail(fmt.Errorf("TSE HTTP %d", resp.StatusCode))
		return
	}
	var doc struct {
		Marketwatch []map[string]any `json:"marketwatch"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&doc); err != nil {
		f.fail(err)
		return
	}
	rows, hEven := parseRows(doc.Marketwatch)
	if len(rows) == 0 {
		f.fail(fmt.Errorf("TSE returned no marketwatch rows"))
		return
	}
	now := time.Now()
	f.mu.Lock()
	f.snap = Snapshot{Rows: rows, HEven: hEven, Updated: now}
	f.gen++
	f.failTill = time.Time{}
	f.mu.Unlock()
	f.maybePersist(ctx, rows)
}

func (f *Feed) maybePersist(ctx context.Context, rows map[string]Row) {
	f.mu.RLock()
	dbPath, every, last := f.dbPath, f.persistEvery, f.lastPersist
	f.mu.RUnlock()
	if dbPath == "" || time.Since(last) < every {
		return
	}
	f.mu.Lock()
	f.lastPersist = time.Now()
	f.mu.Unlock()
	if err := f.persist(ctx, rows); err != nil {
		log.Printf("[live] persist failed: %v", err)
		f.mu.Lock()
		f.persistErr = err.Error()
		f.mu.Unlock()
	}
}

// persist updates today's market_watch rows from the live snapshot. It only
// updates instruments already known to the DB; new listings still need the
// normal sync path (instruments/boards). Prices never regress to zero: a zero
// live value preserves the stored value, while volume/value/trades are direct.
func (f *Feed) persist(ctx context.Context, rows map[string]Row) error {
	f.mu.Lock()
	db, dbPath, insCodes, dEven := f.db, f.dbPath, f.insCodes, f.dEven
	f.mu.Unlock()
	if db == nil {
		opened, err := sql.Open("sqlite", dbPath)
		if err != nil {
			return err
		}
		opened.SetMaxOpenConns(1)
		if _, err := opened.Exec("PRAGMA busy_timeout=5000"); err != nil {
			opened.Close()
			return err
		}
		db = opened
		f.mu.Lock()
		f.db = db
		f.mu.Unlock()
	}
	if insCodes == nil {
		m := map[string]string{}
		rs, err := db.Query("SELECT ins_code, l_val18 FROM instruments" +
			" WHERE l_val18 IS NOT NULL AND l_val18 <> ''")
		if err != nil {
			return err
		}
		for rs.Next() {
			var code, sym string
			if err := rs.Scan(&code, &sym); err == nil && code != "" && sym != "" {
				m[norm(sym)] = code
			}
		}
		rs.Close()
		insCodes = m
		f.mu.Lock()
		f.insCodes = m
		f.mu.Unlock()
	}
	if dEven == 0 {
		if err := db.QueryRow("SELECT COALESCE(MAX(d_even),0) FROM market_watch").Scan(&dEven); err != nil {
			return err
		}
		if dEven == 0 {
			return nil
		}
		f.mu.Lock()
		f.dEven = dEven
		f.mu.Unlock()
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	stmt, err := tx.PrepareContext(ctx, `UPDATE market_watch SET
		d_even=?,
		h_even=CASE WHEN ? > 0 THEN ? ELSE h_even END,
		p_closing=COALESCE(NULLIF(?,0), p_closing),
		p_last=COALESCE(NULLIF(?,0), p_last),
		price_min=COALESCE(NULLIF(?,0), price_min),
		price_max=COALESCE(NULLIF(?,0), price_max),
		price_yesterday=COALESCE(NULLIF(?,0), price_yesterday),
		price_first=COALESCE(NULLIF(?,0), price_first),
		q_tot_tran=?, q_tot_cap=?, z_tot_tran=?, price_change=?,
		pe=COALESCE(NULLIF(?,0), pe),
		buy_q_vol=COALESCE(NULLIF(?,0), buy_q_vol),
		buy_q_val=COALESCE(NULLIF(?,0), buy_q_val),
		buy_q_cnt=COALESCE(NULLIF(?,0), buy_q_cnt),
		sell_q_vol=COALESCE(NULLIF(?,0), sell_q_vol),
		sell_q_val=COALESCE(NULLIF(?,0), sell_q_val),
		sell_q_cnt=COALESCE(NULLIF(?,0), sell_q_cnt),
		buy_q1_vol=COALESCE(NULLIF(?,0), buy_q1_vol),
		buy_q1_px=COALESCE(NULLIF(?,0), buy_q1_px),
		sell_q1_vol=COALESCE(NULLIF(?,0), sell_q1_vol),
		sell_q1_px=COALESCE(NULLIF(?,0), sell_q1_px),
		buy_q1_cnt=COALESCE(NULLIF(?,0), buy_q1_cnt),
		fetched_at=?
		WHERE ins_code=?`)
	if err != nil {
		tx.Rollback()
		return err
	}
	defer stmt.Close()

	f.mu.Lock()
	writeBook := time.Since(f.lastBook) >= bookPersistEvery
	f.mu.Unlock()
	var bookStmt *sql.Stmt
	if writeBook {
		if _, err := tx.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS order_book (
			ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
			book_txt TEXT, updated_at TEXT)`); err != nil {
			tx.Rollback()
			return err
		}
		bookStmt, err = tx.PrepareContext(ctx, `INSERT OR REPLACE INTO order_book
			(ins_code, d_even, h_even, book_txt, updated_at) VALUES (?,?,?,?,?)`)
		if err != nil {
			tx.Rollback()
			return err
		}
		defer bookStmt.Close()
	}

	now := time.Now().Format("2006-01-02 15:04:05")
	n, books := 0, 0
	for sym, row := range rows {
		code := insCodes[norm(sym)]
		if code == "" {
			continue
		}
		de := row.DEven
		if de == 0 {
			de = dEven
		}
		if _, err := stmt.ExecContext(ctx, de, row.HEven, row.HEven,
			row.Closing, row.Last, row.Min, row.Max, row.Prev, row.First,
			row.Volume, row.Value, row.Trades, row.Change, row.PE,
			row.Book.BuyVol, row.Book.BuyVal, row.Book.BuyCnt,
			row.Book.SellVol, row.Book.SellVal, row.Book.SellCnt,
			row.Book.Buy1Vol, row.Book.Buy1Px, row.Book.Sell1Vol,
			row.Book.Sell1Px, row.Book.Buy1Cnt, now, code); err != nil {
			tx.Rollback()
			return err
		}
		if writeBook && row.Book.OK {
			if _, err := bookStmt.ExecContext(ctx, code, de, row.HEven,
				row.Book.Txt, now); err != nil {
				tx.Rollback()
				return err
			}
			books++
		}
		n++
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	if writeBook {
		f.mu.Lock()
		f.lastBook = time.Now()
		f.mu.Unlock()
	}
	if books > 0 {
		log.Printf("[live] persisted %d market rows and %d depth books", n, books)
	}
	f.writeSyncStatus(n, time.Now())
	return nil
}

func (f *Feed) writeSyncStatus(n int, now time.Time) {
	f.mu.RLock()
	dbPath, started := f.dbPath, f.started
	f.mu.RUnlock()
	dir := filepath.Dir(dbPath)
	data := map[string]any{
		"stage": "tsetmc", "phase": "live",
		"detail": fmt.Sprintf("ذخیرهٔ %d نماد زنده در پایگاه محلی ...", n),
		"total":  n, "current": n, "symbol": "",
		"elapsed": math.Round(now.Sub(started).Seconds()*10) / 10,
		"percent": 100.0,
		"ts":      now.Format("2006-01-02T15:04:05"),
	}
	raw, err := json.Marshal(data)
	if err != nil {
		return
	}
	path := filepath.Join(dir, "market_sync.json")
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o644); err != nil {
		return
	}
	_ = os.Rename(tmp, path)
}

func (f *Feed) fail(err error) {
	log.Printf("[live] TSE poll failed: %v (backoff %s)", err, failureBackoff)
	f.mu.Lock()
	f.failTill = time.Now().Add(failureBackoff)
	f.snap.Err = err.Error()
	f.mu.Unlock()
}

func (f *Feed) Latest() Snapshot {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.snap
}

func (f *Feed) Generation() int64 {
	f.mu.RLock()
	defer f.mu.RUnlock()
	return f.gen
}

// Apply overlays volatile columns on a copy of the frame. It never mutates the
// service's cached static frame; columns not present in the snapshot stay as
// they are in the DB frame.
func (f *Feed) Apply(fr *store.Frame) *store.Frame {
	snap := f.Latest()
	if fr == nil || len(snap.Rows) == 0 {
		return fr
	}
	symbols := fr.Cols["symbol"]
	if symbols == nil {
		return fr
	}
	idx := make(map[string]int, len(symbols))
	for i, v := range symbols {
		if s, ok := v.(string); ok && s != "" {
			idx[norm(s)] = i
		}
	}
	cols := make(map[string][]any, len(fr.Cols))
	for k, v := range fr.Cols {
		cols[k] = v
	}
	setNum := func(col string, pick func(Row) (float64, bool)) {
		src, ok := cols[col]
		if !ok {
			return
		}
		cp := append([]any(nil), src...)
		for key, row := range snap.Rows {
			i, ok := idx[key]
			if !ok || i >= len(cp) {
				continue
			}
			if v, ok := pick(row); ok {
				cp[i] = v
			}
		}
		cols[col] = cp
	}
	setNum("p_closing", func(r Row) (float64, bool) { return pos(r.Closing) })
	setNum("p_last", func(r Row) (float64, bool) { return pos(r.Last) })
	setNum("price_change", func(r Row) (float64, bool) { return r.Change, true })
	setNum("price_yesterday", func(r Row) (float64, bool) { return pos(r.Prev) })
	setNum("p_max", func(r Row) (float64, bool) { return pos(r.Max) })
	setNum("p_min", func(r Row) (float64, bool) { return pos(r.Min) })
	setNum("p_first", func(r Row) (float64, bool) { return pos(r.First) })
	setNum("q_tot_tran", func(r Row) (float64, bool) { return r.Volume, true })
	setNum("q_tot_cap", func(r Row) (float64, bool) { return r.Value, true })
	setNum("z_tot_tran", func(r Row) (float64, bool) { return r.Trades, true })
	setNum("pe", func(r Row) (float64, bool) { return r.PE, r.PE != 0 })
	if src, ok := cols["h_even"]; ok {
		cp := append([]any(nil), src...)
		for key, row := range snap.Rows {
			if i, ok := idx[key]; ok && i < len(cp) && row.HEven > 0 {
				cp[i] = row.HEven
			}
		}
		cols["h_even"] = cp
	}
	return &store.Frame{Codes: fr.Codes, Cols: cols}
}

func pos(v float64) (float64, bool) {
	if v > 0 {
		return v, true
	}
	return 0, false
}

func norm(s string) string {
	return strings.TrimSpace(strings.NewReplacer("ي", "ی", "ى", "ی", "ك", "ک").Replace(s))
}

// bookOf mirrors Python's queue_agg + book_lines: five compact [bpx,bvol,bcnt,
// spx,svol,scnt] lines plus the five-level aggregates used by the board filters.
func bookOf(v any) Book {
	arr, ok := v.([]any)
	if !ok || len(arr) == 0 {
		return Book{}
	}
	lines := make([][6]float64, 0, 5)
	var b Book
	for _, item := range arr {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		bpx, bvol, bcnt := num(m["pmd"]), num(m["qmd"]), num(m["zmd"])
		spx, svol, scnt := num(m["pmo"]), num(m["qmo"]), num(m["zmo"])
		if bpx == 0 && spx == 0 {
			continue
		}
		if len(lines) == 0 {
			b.Buy1Vol, b.Buy1Px, b.Buy1Cnt = bvol, bpx, bcnt
			b.Sell1Vol, b.Sell1Px = svol, spx
		}
		b.BuyVol += bvol
		b.BuyVal += bvol * bpx
		b.BuyCnt += bcnt
		b.SellVol += svol
		b.SellVal += svol * spx
		b.SellCnt += scnt
		lines = append(lines, [6]float64{bpx, bvol, bcnt, spx, svol, scnt})
		if len(lines) == 5 {
			break
		}
	}
	if len(lines) == 0 {
		return Book{}
	}
	raw, err := json.Marshal(lines)
	if err != nil {
		return Book{}
	}
	b.Txt = string(raw)
	b.OK = true
	return b
}

func parseRows(raw []map[string]any) (map[string]Row, int64) {
	rows := make(map[string]Row, len(raw))
	var maxHEven int64
	for _, m := range raw {
		sym := str(m["lva"])
		if sym == "" {
			continue
		}
		r := Row{
			Symbol: sym, Closing: num(m["pcl"]), Last: num(m["pdv"]),
			Change: num(m["pc"]), Prev: num(m["py"]), Max: num(m["pmx"]),
			Min: num(m["pmn"]), First: num(m["pf"]), Volume: num(m["qtj"]),
			Value: num(m["qtc"]), Trades: num(m["ztt"]), PE: num(m["pe"]),
			DEven: int64(num(m["dEven"])), HEven: int64(num(m["hEven"])),
			Book: bookOf(m["blDs"]),
		}
		rows[norm(sym)] = r
		if r.HEven > maxHEven {
			maxHEven = r.HEven
		}
	}
	return rows, maxHEven
}

func num(v any) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case json.Number:
		f, _ := x.Float64()
		return f
	case string:
		f, _ := strconv.ParseFloat(strings.TrimSpace(x), 64)
		return f
	default:
		return 0
	}
}

func str(v any) string {
	if s, ok := v.(string); ok {
		return strings.TrimSpace(s)
	}
	return ""
}
