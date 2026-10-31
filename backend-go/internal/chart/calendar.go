package chart

import (
	"encoding/json"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// pySpace همان مجموعه‌ای است که `\s`ِ پایتون رویِ str می‌پذیرد.
const pySpaceClass = `[\t\n\v\f\r \x{1c}-\x{1f}\x{85}\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}\x{3000}]`

var (
	assemblyChangeRe = regexp.MustCompile("لغو|عدم برگزاری|به تعویق|تغییر زمان|انتقال مجمع|موافقت با تغییر")
	capitalClassRe   = regexp.MustCompile("افزایش" + pySpaceClass + "*سرمایه")
	ipoRe            = regexp.MustCompile("عرضه" + pySpaceClass + "*اولیه|عرضه" + pySpaceClass + "*در" +
		pySpaceClass + "*بازار")
	bondRe = regexp.MustCompile("سررسید|اخزا|صکوک|اوراق")
	capRe  = regexp.MustCompile("افزايش" + pySpaceClass + "*سرمايه|افزایش" + pySpaceClass + "*سرمایه|" +
		"افزایشسرمايه|افزايشسرمايه")
	titleDateRe = regexp.MustCompile("(?:مورخ|مؤرخ|تاریخ)" + pySpaceClass + `*[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}`)
	calNorm     = strings.NewReplacer("\u064a", "\u06cc", "\u0643", "\u06a9", "\u0649", "\u06cc")
)

// توابعِ کمکیِ عدد/رشته، معادلِ int(x or 0) و str(x or "").

func intOf(v any) int {
	switch x := v.(type) {
	case nil:
		return 0
	case int:
		return x
	case int64:
		return int(x)
	case float64:
		return int(x)
	case json.Number:
		if n, err := x.Int64(); err == nil {
			return int(n)
		}
	case string:
		if n, err := strconv.Atoi(strings.TrimSpace(x)); err == nil {
			return n
		}
	case bool:
		if x {
			return 1
		}
	}
	return 0
}

func strOf(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

func truncateRunes(s string, n int) string {
	rs := []rune(s)
	if len(rs) <= n {
		return s
	}
	return string(rs[:n])
}

func foldDigits(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		switch {
		case r >= '۰' && r <= '۹':
			b.WriteRune('0' + (r - '۰'))
		case r >= '٠' && r <= '٩':
			b.WriteRune('0' + (r - '٠'))
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func calSymbol(s string) string { return strings.TrimSpace(calNorm.Replace(s)) }

func calClassify(title string, tid int) string {
	t := strings.ReplaceAll(title, "\u200c", "")
	t = calNorm.Replace(t)
	switch {
	case assemblyChangeRe.MatchString(t):
		return "assemblyChange"
	case tid == 1:
		return "assembly"
	case capitalClassRe.MatchString(t):
		return "capitalIncrease"
	case ipoRe.MatchString(t):
		return "ipo"
	case bondRe.MatchString(t):
		return "bondMaturity"
	}
	return "other"
}

func eventDateSource(ev map[string]any) string {
	src := strings.TrimSpace(strOf(ev["date_source"]))
	if src == "title" || src == "publication_fallback" {
		return src
	}
	title := foldDigits(firstNonEmpty(strOf(ev["event_title"]), strOf(ev["description"])))
	if titleDateRe.MatchString(title) {
		return "title"
	}
	return "publication_fallback"
}

var dateLayouts = []string{
	time.RFC3339Nano,
	"2006-01-02T15:04:05.999999999",
	"2006-01-02 15:04:05.999999999",
	"2006-01-02",
}

func parseEventDate(s string) (time.Time, bool) {
	for _, layout := range dateLayouts {
		if t, err := time.Parse(layout, s); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

type calendarCache struct {
	mu     sync.Mutex
	sig    string
	events []map[string]any
}

// events کشِ بی‌عکس‌سازیِ mtime، مثلِ _cal_cache_events.
func (c *calendarCache) eventsFrom(path string) []map[string]any {
	st, err := os.Stat(path)
	if err != nil {
		return nil
	}
	sig := path + "|" + strconv.FormatInt(st.ModTime().UnixNano(), 10) + "|" +
		strconv.FormatInt(st.Size(), 10)
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.sig == sig && c.events != nil {
		return c.events
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var doc struct {
		Events []map[string]any `json:"events"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil
	}
	if doc.Events == nil {
		doc.Events = []map[string]any{}
	}
	c.sig, c.events = sig, doc.Events
	return c.events
}

func (s *Service) calEventsFor(symbol string) []map[string]any {
	want := calSymbol(symbol)
	out := []map[string]any{}
	seen := map[string]bool{}
	for _, ev := range s.cal.eventsFrom(s.calendarPath) {
		if calSymbol(strOf(ev["asset_symbol_trade"])) != want {
			continue
		}
		dt, ok := parseEventDate(strOf(ev["date_time"]))
		if !ok {
			continue
		}
		title := truncateRunes(strOf(ev["event_title"]), 140)
		day := dt.Format("2006-01-02")
		key := day + "|" + title
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, map[string]any{
			"date":         day,
			"ts":           time.Date(dt.Year(), dt.Month(), dt.Day(), 12, 0, 0, 0, time.UTC).Unix() * 1000,
			"title":        title,
			"cat":          calClassify(title, intOf(ev["event_type_id"])),
			"date_source":  eventDateSource(ev),
			"published_at": ev["published_at"],
		})
	}
	sort.SliceStable(out, func(i, j int) bool {
		return out[i]["ts"].(int64) < out[j]["ts"].(int64)
	})
	return out
}

func clampDays(days int) int {
	if days < 1 {
		return 1
	}
	if days > 90 {
		return 90
	}
	return days
}

func (s *Service) dateToday() time.Time {
	t := s.now()
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC)
}

// upcomingBy همان _upcoming_by: نزدیک‌ترین رویدادِ پیش‌روی هر نماد.
func (s *Service) upcomingBy(cats map[string]bool, days int, titleRe *regexp.Regexp) []map[string]any {
	days = clampDays(days)
	asOf := s.dateToday()
	horizon := asOf.AddDate(0, 0, days)
	order := []string{}
	best := map[string]map[string]any{}
	for _, ev := range s.cal.eventsFrom(s.calendarPath) {
		title := strOf(ev["event_title"])
		cat := calClassify(title, intOf(ev["event_type_id"]))
		if cats != nil && !cats[cat] {
			continue
		}
		if titleRe != nil {
			norm := strings.NewReplacer("\u200c", "", "\u064a", "\u06cc",
				"\u0643", "\u06a9").Replace(title)
			if !titleRe.MatchString(norm) {
				continue
			}
		}
		dt, ok := parseEventDate(strOf(ev["date_time"]))
		if !ok {
			continue
		}
		d := time.Date(dt.Year(), dt.Month(), dt.Day(), 0, 0, 0, 0, time.UTC)
		if d.Before(asOf) || d.After(horizon) {
			continue
		}
		sym := calSymbol(strOf(ev["asset_symbol_trade"]))
		if sym == "" {
			continue
		}
		day := d.Format("2006-01-02")
		cur, exists := best[sym]
		replace := !exists
		if exists {
			curDay, _ := parseEventDate(strOf(cur["date"]))
			curD := time.Date(curDay.Year(), curDay.Month(), curDay.Day(), 0, 0, 0, 0, time.UTC)
			if d.Before(curD) {
				replace = true
			} else if d.Equal(curD) && cat == "assemblyChange" && cur["cat"] != "assemblyChange" {
				replace = true
			}
		}
		if replace {
			if !exists {
				order = append(order, sym)
			}
			best[sym] = map[string]any{
				"symbol": sym, "date": day, "cat": cat,
				"title":        truncateRunes(title, 140),
				"date_source":  eventDateSource(ev),
				"published_at": ev["published_at"],
			}
		}
	}
	out := make([]map[string]any, 0, len(order))
	for _, sym := range order {
		out = append(out, best[sym])
	}
	sort.SliceStable(out, func(i, j int) bool {
		return out[i]["date"].(string) < out[j]["date"].(string)
	})
	return out
}

var assemblyFamily = map[string]bool{
	"assembly": true, "assemblyExtra": true, "assemblyChange": true,
}

func (s *Service) calendarUpcomingBody(days int) map[string]any {
	span := clampDays(days)
	best := s.upcomingBy(assemblyFamily, span, nil)
	cap := s.upcomingBy(nil, span, capRe)
	return map[string]any{
		"status": "ok", "days": span,
		"count": len(best), "items": best,
		"capital_count": len(cap), "capital": cap,
	}
}

func (s *Service) calendarSymbolBody(symbol string) map[string]any {
	events := s.calEventsFor(symbol)
	return map[string]any{"status": "ok", "symbol": symbol,
		"count": len(events), "events": events}
}
