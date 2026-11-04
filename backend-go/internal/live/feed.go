// Package live feeds the TSE market watch into the board's live overlay.
//
// One poller, one TSE request per tick. The DB remains the durable snapshot;
// this package only overrides the volatile columns in memory so /api/market
// can be as fresh as the source without a 60s cache wait.
package live

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/store"
)

const DefaultURL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch" +
	"?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3" +
	"&paperTypes[3]=4&paperTypes[4]=5&paperTypes[5]=6&paperTypes[6]=7" +
	"&paperTypes[7]=8&paperTypes[8]=9&showTraded=false" +
	"&withBestLimits=true&hEven=0"

const failureBackoff = 30 * time.Second

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
	HEven   int64
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
	}
}

// SetURL/SetClient are for the offline feed tests; production keeps defaults.
func (f *Feed) SetURL(url string)        { f.url = url }
func (f *Feed) SetClient(c *http.Client) { f.client = c }

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
			HEven: int64(num(m["hEven"])),
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
