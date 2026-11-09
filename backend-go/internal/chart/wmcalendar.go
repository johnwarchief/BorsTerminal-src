package chart

import (
	"bufio"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// پورتِ wm_calendar.py — پلِ تاریخیِ سبدهایِ هفتگی/ماهانه.
//
// برایِ کلیدهایی که تقویم/دادهٔ روزانهٔ محصول با مرجع یکی نیست (Round 32D)،
// نوارِ مرجعِ ذخیره‌شده جای تجمیعِ ناقص می‌نشیند؛ سایر کلیدها دست‌نخورده‌اند و
// در نبودِ بسته رفتارِ قبلی برمی‌گردد. بسته فقط W/M دارد (نه سریِ روزانه) و
// هیچ شبکه‌ای نمی‌زند.
const wmCalendarVersion = "ra365-r32d"

type wmKey struct {
	symbol    string
	timeframe string
	key       int
}

type wmBar struct {
	time                   string
	open, high, low, close float64
	volume                 *float64
}

type calendarPack struct {
	rows map[wmKey]wmBar
}

func normSymbol(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "\u064A", "\u06CC") // ي عربی → ی فارسی
	s = strings.ReplaceAll(s, "\u0643", "\u06A9") // ك عربی → ک فارسی
	return s
}

func wmCalendarDisabled() bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv("BORS_WM_CALENDAR_DISABLE"))) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

func wmPackCandidates(dataDir string) []string {
	out := []string{}
	if d := strings.TrimSpace(os.Getenv("BORS_WM_CALENDAR_DIR")); d != "" {
		out = append(out, d)
	}
	if dataDir != "" {
		out = append(out,
			filepath.Join(dataDir, "data", "ra365_calendar", wmCalendarVersion),
			filepath.Join(dataDir, "ra365_calendar", wmCalendarVersion))
	}
	// در بستهٔ onedir، data/ کنارِ EXE می‌نشیند و DataDir ممکن است پوشهٔ
	// دادهٔ کاربر باشد؛ هر دو مسیر بررسی می‌شوند.
	if exe, err := os.Executable(); err == nil {
		out = append(out, filepath.Join(filepath.Dir(exe), "data",
			"ra365_calendar", wmCalendarVersion))
	}
	return out
}

// loadCalendarPack همان قراردادِ get_pack() پایتون: نبودِ manifest یا بستهٔ
// خراب ⇒ nil (رفتارِ قبلی)، نه خطا و نه دادهٔ نیمه‌معتبر.
func loadCalendarPack(dataDir string) *calendarPack {
	if wmCalendarDisabled() {
		return nil
	}
	for _, dir := range wmPackCandidates(dataDir) {
		manifestPath := filepath.Join(dir, "manifest.json")
		if _, err := os.Stat(manifestPath); err != nil {
			continue
		}
		if p := loadPackDir(dir, manifestPath); p != nil {
			return p
		}
	}
	return nil
}

type wmManifest struct {
	Files map[string]string `json:"files"`
	SHA   map[string]string `json:"file_sha256"`
}

func loadPackDir(dir, manifestPath string) *calendarPack {
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil
	}
	var man wmManifest
	if err := json.Unmarshal(raw, &man); err != nil {
		return nil
	}
	name := man.Files["bars"]
	if name == "" {
		name = "wm_calendar_bars.ndjson.gz"
	}
	barsPath := name
	if !filepath.IsAbs(barsPath) {
		barsPath = filepath.Join(dir, name)
	}
	// همان بررسیِ SHAِ پایتون: بستهٔ دست‌کاری‌شده پذیرفته نمی‌شود.
	if want := man.SHA["bars"]; want != "" {
		if got := fileSHA256(barsPath); got != want {
			return nil
		}
	}
	f, err := os.Open(barsPath)
	if err != nil {
		return nil
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return nil
	}
	defer gz.Close()
	rows := map[wmKey]wmBar{}
	sc := bufio.NewScanner(gz)
	sc.Buffer(make([]byte, 0, 1<<20), 1<<20)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var r struct {
			Symbol    string   `json:"symbol"`
			Timeframe string   `json:"timeframe"`
			Key       int      `json:"key"`
			DateTo    string   `json:"date_to"`
			Open      *float64 `json:"open"`
			High      *float64 `json:"high"`
			Low       *float64 `json:"low"`
			Close     *float64 `json:"close"`
			Volume    *float64 `json:"volume"`
			// در بسته `unavailable` فهرست است (خالی = در دسترس)؛ bool گرفتنش
			// همهٔ ردیف‌ها را دور می‌ریخت.
			Unavailable any `json:"unavailable"`
		}
		if err := json.Unmarshal([]byte(line), &r); err != nil {
			continue
		}
		unavailable := false
		switch v := r.Unavailable.(type) {
		case nil:
		case bool:
			unavailable = v
		case []any:
			unavailable = len(v) > 0
		case string:
			unavailable = v != ""
		default:
			unavailable = true
		}
		if unavailable || r.Symbol == "" || r.Timeframe == "" {
			continue
		}
		if r.Open == nil || r.High == nil || r.Low == nil || r.Close == nil {
			continue
		}
		rows[wmKey{normSymbol(r.Symbol), r.Timeframe, r.Key}] = wmBar{
			time: r.DateTo, open: *r.Open, high: *r.High, low: *r.Low,
			close: *r.Close, volume: r.Volume,
		}
	}
	if err := sc.Err(); err != nil {
		return nil
	}
	return &calendarPack{rows: rows}
}

func fileSHA256(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return ""
	}
	return hex.EncodeToString(h.Sum(nil))
}

func (p *calendarPack) bar(symbol, timeframe string, key int) (wmBar, bool) {
	if p == nil {
		return wmBar{}, false
	}
	b, ok := p.rows[wmKey{normSymbol(symbol), timeframe, key}]
	return b, ok
}

// wmWeekKey معادلِ WMC.week_key: شنبهٔ ۱۹۷۰-۰۱-۰۳ لنگرِ صفر است.
func wmWeekKey(date string) (int, bool) {
	d, err := time.Parse("2006-01-02", date)
	if err != nil {
		return 0, false
	}
	epoch := time.Date(1970, 1, 1, 0, 0, 0, 0, time.UTC)
	day := int(d.Sub(epoch).Hours() / 24)
	return (day - 2) / 7, true
}

// applyPackRefs معادلِ حلقهٔ `if symbol:` در _fts_resample: نوارِ مرجع رویِ
// سبدِ تجمیعی می‌نشیند و open/high/low/close/time را جایگزین می‌کند؛ حجم فقط
// وقتی مرجع حجم دارد.
func (p *calendarPack) applyPackRefs(rows []candle, bucket, symbol string) {
	if p == nil || symbol == "" || len(rows) == 0 {
		return
	}
	for i := range rows {
		var key int
		if bucket == "W" {
			k, ok := wmWeekKey(trim10(rows[i].Time))
			if !ok {
				continue
			}
			key = k
		} else {
			d, err := time.Parse("2006-01-02", trim10(rows[i].Time))
			if err != nil {
				continue
			}
			jy, jm, _ := g2j(d.Year(), int(d.Month()), d.Day())
			key = jy*12 + jm - 1
		}
		ref, ok := p.bar(symbol, bucket, key)
		if !ok {
			continue
		}
		rows[i].Open = ref.open
		rows[i].High = ref.high
		rows[i].Low = ref.low
		rows[i].Close = ref.close
		if ref.time != "" {
			rows[i].Time = trim10(ref.time)
		}
		if ref.volume != nil {
			rows[i].Volume = *ref.volume
		}
	}
}
