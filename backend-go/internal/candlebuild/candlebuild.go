// Package candlebuild materializes the Phase 4.9.2 adjusted candle history
// from the reference raw series and the measured adjustment factors. All
// computation is in Go; the tables carry a revision so a rebuild is
// reproducible and idempotent.
package candlebuild

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"borsterminal/backend/internal/chart"
)

const schemaSQL = `
CREATE TABLE IF NOT EXISTS adjusted_candles(
  symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
  close REAL NOT NULL, volume REAL, factor REAL NOT NULL, revision TEXT NOT NULL,
  PRIMARY KEY(symbol,date));
CREATE TABLE IF NOT EXISTS adjustment_verification(
  symbol TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL,
  reference_close REAL, adjusted_close REAL, rel_error REAL,
  revision TEXT NOT NULL, capture_sha256 TEXT,
  PRIMARY KEY(symbol,date));
CREATE TABLE IF NOT EXISTS candle_build_revisions(
  symbol TEXT PRIMARY KEY, revision TEXT NOT NULL, capture_sha256 TEXT,
  raw_rows INTEGER NOT NULL, factor_rows INTEGER NOT NULL,
  adjusted_rows INTEGER NOT NULL, max_rel_error REAL, worst_date TEXT,
  built_at TEXT NOT NULL);
`

// Result is the build summary; one entry per covered symbol.
type Result struct {
	Symbols       int      `json:"symbols"`
	AdjustedRows  int      `json:"adjusted_rows"`
	VerifiedRows  int      `json:"verified_rows"`
	ExactRows     int      `json:"exact_rows"`
	MismatchRows  int      `json:"mismatch_rows"`
	MaxRelError   float64  `json:"max_rel_error"`
	WorstSymbol   string   `json:"worst_symbol"`
	WorstDate     string   `json:"worst_date"`
	Revisions     []string `json:"revisions"`
	MissingRaw    []string `json:"missing_reference_raw"`
	MissingVerify []string `json:"missing_reference_adjusted"`
}

type factorRow struct {
	date     string
	ratio    float64
	revision string
	capture  string
}

type rawRow struct {
	date            string
	open, high, low float64
	close, volume   float64
}

func ensureSchema(db *sql.DB) error {
	_, err := db.Exec(schemaSQL)
	return err
}

// Build recomputes adjusted_candles and adjustment_verification for every
// symbol the reference series covers, with or without measured events. It is
// idempotent: a second run deletes and rewrites the same rows with the same
// revision.
func Build(db *sql.DB) (Result, error) {
	res := Result{Revisions: []string{}, MissingRaw: []string{},
		MissingVerify: []string{}}
	if err := ensureSchema(db); err != nil {
		return res, err
	}
	symbols, err := coveredSymbols(db)
	if err != nil {
		return res, err
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05Z")
	for _, symbol := range symbols {
		if err := buildSymbol(db, symbol, now, &res); err != nil {
			return res, fmt.Errorf("%s: %w", symbol, err)
		}
	}
	return res, nil
}

// coveredSymbols یک نماد را پوشیده می‌داند اگر سری مرجع دارد، چه رویدادِ
// اندازه‌گیری‌شده داشته باشد چه نداشته باشد.
func coveredSymbols(db *sql.DB) ([]string, error) {
	rows, err := db.Query(
		"SELECT symbol FROM adjustment_factors UNION " +
			"SELECT symbol FROM reference_raw ORDER BY symbol")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []string{}
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func buildSymbol(db *sql.DB, symbol, now string, res *Result) error {
	factors, err := loadFactors(db, symbol)
	if err != nil {
		return err
	}
	raw, err := loadRaw(db, symbol)
	if err != nil {
		return err
	}
	if len(raw) == 0 {
		res.MissingRaw = append(res.MissingRaw, symbol)
		return nil
	}
	times := make([]string, len(raw))
	dates := make([]string, len(factors))
	ratios := make([]float64, len(factors))
	revision, capture := "", ""
	if len(factors) == 0 {
		revision, capture, err = referenceIdentity(db, symbol)
		if err != nil {
			return err
		}
	} else {
		revision, capture = factors[0].revision, factors[0].capture
	}
	for i, r := range raw {
		times[i] = r.date
	}
	for i, f := range factors {
		dates[i], ratios[i] = f.date, f.ratio
		if f.revision != revision {
			return fmt.Errorf("multiple factor revisions for %s", symbol)
		}
	}
	chain := chart.ChainFactors(times, dates, ratios)

	ref, err := loadReferenceAdjusted(db, symbol)
	if err != nil {
		return err
	}
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.Exec("DELETE FROM adjusted_candles WHERE symbol=?", symbol); err != nil {
		return err
	}
	if _, err := tx.Exec("DELETE FROM adjustment_verification WHERE symbol=?", symbol); err != nil {
		return err
	}
	maxRel, worstDate := 0.0, ""
	exact, mismatch, verified := 0, 0, 0
	for i, r := range raw {
		f := chain[i]
		o := r.open
		if o <= 0 {
			o = r.close
		}
		// سری مرجع دست‌نخورده می‌ماند: type7 = type0 × factor، بدون Widen.
		if _, err := tx.Exec(
			"INSERT INTO adjusted_candles VALUES(?,?,?,?,?,?,?,?,?)",
			symbol, r.date, o*f, r.high*f, r.low*f, r.close*f, r.volume, f,
			revision); err != nil {
			return err
		}
		res.AdjustedRows++
		refClose, ok := ref[r.date]
		if !ok {
			continue
		}
		verified++
		rel := math.Abs(r.close*f/refClose - 1.0)
		status := "EXACT"
		if rel > 1e-9 {
			status = "DIFF"
			mismatch++
		} else {
			exact++
		}
		if rel > maxRel {
			maxRel, worstDate = rel, r.date
			res.WorstSymbol = symbol
		}
		if _, err := tx.Exec(
			"INSERT INTO adjustment_verification VALUES(?,?,?,?,?,?,?,?)",
			symbol, r.date, status, refClose, r.close*f, rel, revision,
			capture); err != nil {
			return err
		}
	}
	if verified == 0 {
		res.MissingVerify = append(res.MissingVerify, symbol)
	}
	if _, err := tx.Exec(
		"INSERT OR REPLACE INTO candle_build_revisions VALUES(?,?,?,?,?,?,?,?,?)",
		symbol, revision, capture, len(raw), len(factors), len(raw), maxRel,
		worstDate, now); err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	res.Symbols++
	res.VerifiedRows += verified
	res.ExactRows += exact
	res.MismatchRows += mismatch
	if maxRel > res.MaxRelError {
		res.MaxRelError = maxRel
		res.WorstDate = worstDate
	}
	if len(res.Revisions) == 0 || res.Revisions[len(res.Revisions)-1] != revision {
		res.Revisions = append(res.Revisions, revision)
	}
	return nil
}

func loadFactors(db *sql.DB, symbol string) ([]factorRow, error) {
	rows, err := db.Query(
		"SELECT date, ratio, revision, capture_sha256 FROM adjustment_factors "+
			"WHERE symbol=? ORDER BY date", symbol)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []factorRow{}
	for rows.Next() {
		var f factorRow
		var date, rev, cap sql.NullString
		var ratio sql.NullFloat64
		if err := rows.Scan(&date, &ratio, &rev, &cap); err != nil {
			return nil, err
		}
		if !date.Valid || !ratio.Valid || ratio.Float64 <= 0 {
			continue
		}
		f.date, f.ratio = date.String, ratio.Float64
		if rev.Valid {
			f.revision = rev.String
		}
		if cap.Valid {
			f.capture = cap.String
		}
		out = append(out, f)
	}
	return out, rows.Err()
}

// referenceIdentity لنگرِ نمادِ بدون رویداد است: همان capture که سری مرجع از
// آن آمده، چون هیچ ردیفِ ضریبی وجود ندارد که revision بدهد.
func referenceIdentity(db *sql.DB, symbol string) (string, string, error) {
	var capture, run sql.NullString
	if err := db.QueryRow(
		"SELECT MAX(capture_sha256), MAX(run_id) FROM reference_raw WHERE symbol=?",
		symbol).Scan(&capture, &run); err != nil {
		return "", "", err
	}
	revision := ""
	if capture.Valid {
		revision = capture.String
	}
	if revision == "" && run.Valid {
		revision = run.String
	}
	return revision, capture.String, nil
}

func loadRaw(db *sql.DB, symbol string) ([]rawRow, error) {
	rows, err := db.Query(
		"SELECT date, open, high, low, close, volume FROM reference_raw "+
			"WHERE symbol=? ORDER BY date", symbol)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []rawRow{}
	for rows.Next() {
		var date sql.NullString
		var o, h, l, c, v sql.NullFloat64
		if err := rows.Scan(&date, &o, &h, &l, &c, &v); err != nil {
			return nil, err
		}
		if !date.Valid || !c.Valid || c.Float64 <= 0 || !v.Valid || v.Float64 <= 0 {
			continue
		}
		r := rawRow{date: date.String, close: c.Float64, volume: v.Float64}
		if o.Valid {
			r.open = o.Float64
		}
		if h.Valid {
			r.high = h.Float64
		}
		if l.Valid {
			r.low = l.Float64
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func loadReferenceAdjusted(db *sql.DB, symbol string) (map[string]float64, error) {
	rows, err := db.Query(
		"SELECT date, close FROM reference_adjusted WHERE symbol=?", symbol)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]float64{}
	for rows.Next() {
		var date sql.NullString
		var closeP sql.NullFloat64
		if err := rows.Scan(&date, &closeP); err != nil {
			return nil, err
		}
		if date.Valid && closeP.Valid && closeP.Float64 > 0 {
			out[date.String] = closeP.Float64
		}
	}
	return out, rows.Err()
}

// FactorRevision is the stable revision hash for a set of measured factors.
func FactorRevision(captureSHA string, symbol string, dates []string, ratios []float64) string {
	parts := make([]string, len(dates))
	for i := range dates {
		parts[i] = fmt.Sprintf("%s|%.17g", dates[i], ratios[i])
	}
	sort.Strings(parts)
	h := sha256.New()
	h.Write([]byte(captureSHA + "\n" + symbol + "\n" + strings.Join(parts, "\n")))
	return hex.EncodeToString(h.Sum(nil))
}
