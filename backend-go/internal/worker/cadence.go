package worker

import (
	"context"
	"database/sql"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// timeRegex matches HH:MM:SS or HH:MM from strings like "1402/12/29 18:00:00" or "10:30"
var timeRegex = regexp.MustCompile(`(?:^|[T\s])(\d{1,2}):(\d{2})(?::(\d{2}))?`)

// foldDigits converts Persian and Arabic-Indic unicode digits to standard ASCII (0-9).
func foldDigits(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= 0x06F0 && r <= 0x06F9 { // Persian digits ۰-۹
			b.WriteRune('0' + (r - 0x06F0))
		} else if r >= 0x0660 && r <= 0x0669 { // Arabic-Indic digits ٠-٩
			b.WriteRune('0' + (r - 0x0660))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// getTehranLocation attempts to load "Asia/Tehran" zone info,
// falling back to fixed UTC+3:30 (standard Tehran timezone).
func getTehranLocation() *time.Location {
	loc, err := time.LoadLocation("Asia/Tehran")
	if err == nil {
		return loc
	}
	return time.FixedZone("Asia/Tehran", 3*3600+1800)
}

// CadenceConfig holds configuration options for CadenceManager.
type CadenceConfig struct {
	PeakInterval    time.Duration
	OffPeakInterval time.Duration
	Location        *time.Location
	DynamicPeaks    map[int]bool // optional map of hours (0-23) designated as peak
	UseDynamicPeaks bool
}

// CadenceManager manages adaptive polling cadence based on Tehran market/CODAL peak hours
// and historical announcement patterns.
type CadenceManager struct {
	mu              sync.RWMutex
	peakInterval    time.Duration
	offPeakInterval time.Duration
	location        *time.Location
	dynamicPeaks    map[int]bool
	useDynamic      bool
}

// NewCadenceManager creates a new CadenceManager with the supplied configuration.
// Missing or non-positive durations default to 10 minutes (peak) and 2 hours (off-peak).
func NewCadenceManager(cfg CadenceConfig) *CadenceManager {
	peak := cfg.PeakInterval
	if peak <= 0 {
		peak = 10 * time.Minute
	}
	offPeak := cfg.OffPeakInterval
	if offPeak <= 0 {
		offPeak = 2 * time.Hour
	}
	loc := cfg.Location
	if loc == nil {
		loc = getTehranLocation()
	}

	peaks := make(map[int]bool)
	for h, isPeak := range cfg.DynamicPeaks {
		if h >= 0 && h <= 23 && isPeak {
			peaks[h] = true
		}
	}

	return &CadenceManager{
		peakInterval:    peak,
		offPeakInterval: offPeak,
		location:        loc,
		dynamicPeaks:    peaks,
		useDynamic:      cfg.UseDynamicPeaks || len(peaks) > 0,
	}
}

// PeakInterval returns the configured peak interval.
func (c *CadenceManager) PeakInterval() time.Duration {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.peakInterval
}

// OffPeakInterval returns the configured off-peak interval.
func (c *CadenceManager) OffPeakInterval() time.Duration {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.offPeakInterval
}

// Location returns the timezone location used by the CadenceManager.
func (c *CadenceManager) Location() *time.Location {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.location
}

// SetDynamicMode enables or disables dynamic peak hours identified from historical data.
func (c *CadenceManager) SetDynamicMode(enabled bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.useDynamic = enabled
}

// DynamicPeaks returns a copy of the active dynamic peak hours map.
func (c *CadenceManager) DynamicPeaks() map[int]bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	res := make(map[int]bool, len(c.dynamicPeaks))
	for k, v := range c.dynamicPeaks {
		res[k] = v
	}
	return res
}

// TopPeakHours returns a sorted slice of dynamic peak hours.
func (c *CadenceManager) TopPeakHours() []int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	hours := make([]int, 0, len(c.dynamicPeaks))
	for h, ok := range c.dynamicPeaks {
		if ok {
			hours = append(hours, h)
		}
	}
	sort.Ints(hours)
	return hours
}

// Interval returns the appropriate duration for the current moment:
// PeakInterval if now is during a peak period, otherwise OffPeakInterval.
func (c *CadenceManager) Interval(now time.Time) time.Duration {
	if c.IsPeak(now) {
		c.mu.RLock()
		defer c.mu.RUnlock()
		return c.peakInterval
	}
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.offPeakInterval
}

// IsPeak determines whether the given time falls within market/CODAL peak hours in Tehran.
// Peak rules:
// - Iranian business week: Saturday through Wednesday.
// - Thursday: Morning business window only (09:00 - 13:30). Thursday afternoon (> 13:30) is off-peak.
// - Friday: Entire day is off-peak/weekend.
// - Morning window: 09:00 to 13:30 (inclusive).
// - Afternoon window: 15:00 to 19:30 (inclusive, Saturday through Wednesday).
// If dynamic peaks are enabled and populated, hours matching dynamic peaks are treated as peak
// on business days (respecting the Friday and Thursday afternoon off-peak rules).
func (c *CadenceManager) IsPeak(now time.Time) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()

	local := now.In(c.location)
	weekday := local.Weekday()

	// Friday is the weekend in Iran - always off-peak
	if weekday == time.Friday {
		return false
	}

	minuteOfDay := local.Hour()*60 + local.Minute()

	// Thursday afternoon is off-peak
	if weekday == time.Thursday && minuteOfDay > 13*60+30 {
		return false
	}

	// Dynamic peak hours mode
	if c.useDynamic && len(c.dynamicPeaks) > 0 {
		// If Thursday, only morning dynamic peak hours apply
		if weekday == time.Thursday {
			return minuteOfDay <= 13*60+30 && c.dynamicPeaks[local.Hour()]
		}
		return c.dynamicPeaks[local.Hour()]
	}

	// Default Peak Windows:
	// 1. Morning window: 09:00 to 13:30 (Saturday through Thursday)
	if minuteOfDay >= 9*60 && minuteOfDay <= 13*60+30 {
		return true
	}

	// 2. Afternoon window: 15:00 to 19:30 (Saturday through Wednesday only)
	if weekday != time.Thursday && minuteOfDay >= 15*60 && minuteOfDay <= 19*60+30 {
		return true
	}

	return false
}

// parseHourFromDateStr extracts the hour (0-23) from a date/time string.
func parseHourFromDateStr(raw string) (int, bool) {
	s := foldDigits(strings.TrimSpace(raw))
	if s == "" {
		return 0, false
	}
	matches := timeRegex.FindStringSubmatch(s)
	if len(matches) >= 2 {
		h, err := strconv.Atoi(matches[1])
		if err == nil && h >= 0 && h <= 23 {
			return h, true
		}
	}
	return 0, false
}

// AnalyzeHistoricalPeaks inspects the SQLite codal_notices table (extracting the hour from
// sent_date or publish_date), returns the distribution of notices per hour of day (0-23),
// and dynamically identifies top peak hours.
// If the table is empty or missing, it falls back cleanly to the default peak window.
func (c *CadenceManager) AnalyzeHistoricalPeaks(ctx context.Context, db *sql.DB) (map[int]int, error) {
	dist := make(map[int]int)
	for i := 0; i < 24; i++ {
		dist[i] = 0
	}

	if db == nil {
		c.mu.Lock()
		c.dynamicPeaks = make(map[int]bool)
		c.useDynamic = false
		c.mu.Unlock()
		return dist, nil
	}

	// Check if codal_notices table exists
	var tableCount int
	err := db.QueryRowContext(ctx, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='codal_notices'").Scan(&tableCount)
	if err != nil || tableCount == 0 {
		c.mu.Lock()
		c.dynamicPeaks = make(map[int]bool)
		c.useDynamic = false
		c.mu.Unlock()
		return dist, nil
	}

	// Determine existing columns in codal_notices
	colRows, err := db.QueryContext(ctx, "PRAGMA table_info(codal_notices)")
	if err != nil {
		c.mu.Lock()
		c.dynamicPeaks = make(map[int]bool)
		c.useDynamic = false
		c.mu.Unlock()
		return dist, nil
	}
	defer colRows.Close()

	var hasPublish, hasSent bool
	for colRows.Next() {
		var cid int
		var name, colType string
		var notnull, pk int
		var dfltValue any
		if err := colRows.Scan(&cid, &name, &colType, &notnull, &dfltValue, &pk); err == nil {
			switch strings.ToLower(name) {
			case "publish_date":
				hasPublish = true
			case "sent_date":
				hasSent = true
			}
		}
	}

	if !hasPublish && !hasSent {
		c.mu.Lock()
		c.dynamicPeaks = make(map[int]bool)
		c.useDynamic = false
		c.mu.Unlock()
		return dist, nil
	}

	var query string
	if hasSent && hasPublish {
		query = "SELECT coalesce(nullif(sent_date, ''), publish_date, '') FROM codal_notices WHERE (sent_date IS NOT NULL AND sent_date != '') OR (publish_date IS NOT NULL AND publish_date != '')"
	} else if hasPublish {
		query = "SELECT coalesce(publish_date, '') FROM codal_notices WHERE publish_date IS NOT NULL AND publish_date != ''"
	} else {
		query = "SELECT coalesce(sent_date, '') FROM codal_notices WHERE sent_date IS NOT NULL AND sent_date != ''"
	}

	rows, err := db.QueryContext(ctx, query)
	if err != nil {
		c.mu.Lock()
		c.dynamicPeaks = make(map[int]bool)
		c.useDynamic = false
		c.mu.Unlock()
		return dist, nil
	}
	defer rows.Close()

	total := 0
	for rows.Next() {
		var dateStr string
		if err := rows.Scan(&dateStr); err == nil {
			if h, ok := parseHourFromDateStr(dateStr); ok {
				dist[h]++
				total++
			}
		}
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	if total == 0 {
		// Clean fallback to default peak window
		c.dynamicPeaks = make(map[int]bool)
		c.useDynamic = false
		return dist, nil
	}

	// Dynamically identify top peak hours:
	maxCount := 0
	for h := 0; h < 24; h++ {
		if dist[h] > maxCount {
			maxCount = dist[h]
		}
	}

	avg := float64(total) / 24.0
	threshold := float64(maxCount) * 0.4
	if threshold < avg {
		threshold = avg
	}

	peaks := make(map[int]bool)
	for h := 0; h < 24; h++ {
		if float64(dist[h]) >= threshold && dist[h] > 0 {
			peaks[h] = true
		}
	}

	c.dynamicPeaks = peaks
	c.useDynamic = true

	return dist, nil
}
