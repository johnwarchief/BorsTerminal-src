// Package seed prepares the market database from the bundled market.db.lzma.
//
// The installer ships a schema-current but nearly empty market.db (one trading
// day) and a full historical seed (market.db.lzma). Nothing used to extract or
// merge that seed, so an installed app served a single candle. This package
// closes that gap at startup, before borsd opens the database read-only:
//
//   - no market.db          -> decompress the seed to a staging file
//   - market.db present     -> merge seed rows into a copy, keeping every
//     existing row (INSERT OR IGNORE / seed-only tables)
//
// In both cases the staging file is validated (integrity + required schema +
// seed row coverage), the current database is backed up, and activation is a
// single rename. A failure leaves the existing database untouched. The applied
// seed hash is recorded in market_seed.json so a restart does not repeat the
// work.
package seed

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"borsterminal/backend/internal/db"
	"github.com/ulikunitz/xz"
	"github.com/ulikunitz/xz/lzma"
)

const (
	StateFile = "market_seed.json"

	ModeExtract = "extract"
	ModeMerge   = "merge"

	StatusApplied = "applied"
	StatusFailed  = "failed"

	ReasonGenerationActive = "active-generation"
	ReasonNoSeed           = "no-seed"
	ReasonAlreadyApplied   = "already-applied"
	ReasonApplied          = "applied"
)

const stagingName = "market.db.part"

var requiredPriceHistoryColumns = []string{
	"symbol", "date", "open", "high", "low", "close", "volume", "last", "value", "src",
}

// seedOnlyTables are tables the current schema does not define but the Go
// runtime reads (adjust_events/adjust_verdict) or the canonical board SQL
// expects (board_hist_*). They are created from the seed exactly as-is.
var seedOnlyTables = map[string]bool{
	"adjust_events":  true,
	"adjust_verdict": true,
	"board_hist_v":   true,
	"board_hist_fv":  true,
}

// neverMerge tables hold user decisions, derived caches, pipeline state or a
// live snapshot. Copying them from a seed would resurrect stale board rows,
// fork the writer's state, or resurrect user data.
var neverMerge = map[string]bool{
	"user_watchlists":         true,
	"selection_decisions":     true,
	"fts_results":             true,
	"market_watch":            true,
	"order_book":              true,
	"supervision_state":       true,
	"stop_reasons":            true,
	"tsetmc_p0_state":         true,
	"tape_history_state":      true,
	"client_type_value_state": true,
	"pipeline_cursor":         true,
	"pipeline_dirty":          true,
	"pipeline_instrument":     true,
	"pipeline_lock":           true,
	"pipeline_runs":           true,
	"sqlite_sequence":         true,
	"sqlite_stat1":            true,
	"sqlite_stat2":            true,
	"sqlite_stat3":            true,
	"sqlite_stat4":            true,
	"schema_migrations":       true,
}

// State is the durable record of the last seed operation. It is written
// atomically; an unreadable state is treated as absent.
type State struct {
	Version           int    `json:"version"`
	Status            string `json:"status"`
	Source            string `json:"source"`
	SourceSHA256      string `json:"source_sha256"`
	SourceSize        int64  `json:"source_size"`
	SourceModUnix     int64  `json:"source_mod_unix"`
	Mode              string `json:"mode,omitempty"`
	AppliedAtUTC      string `json:"applied_at_utc,omitempty"`
	Backup            string `json:"backup,omitempty"`
	DBPath            string `json:"db_path,omitempty"`
	DBSize            int64  `json:"db_size,omitempty"`
	DBSHA256          string `json:"db_sha256,omitempty"`
	PriceHistoryRows  int64  `json:"price_history_rows,omitempty"`
	PriceHistoryFirst string `json:"price_history_first,omitempty"`
	PriceHistoryLast  string `json:"price_history_last,omitempty"`
	DailyPricesRows   int64  `json:"daily_prices_rows,omitempty"`
	Error             string `json:"error,omitempty"`
}

// Options configures Ensure. SeedPath overrides discovery (tests/ops).
type Options struct {
	DataDir  string
	SeedPath string
	Logger   *slog.Logger
}

// Result reports what Ensure did. Applied is true only when the database was
// activated from a new staging file.
type Result struct {
	Applied bool
	Mode    string
	Reason  string
	State   State
}

// Ensure is idempotent: a matching applied state plus a healthy database is a
// no-op; otherwise it extracts/merges and atomically activates a validated
// copy.
func Ensure(opts Options) (res Result, err error) {
	phase := time.Now()
	mark := func(name string) {
		if opts.Logger != nil {
			opts.Logger.Info("seed phase", "phase", name, "ms", time.Since(phase).Milliseconds())
		}
		phase = time.Now()
	}
	var failSource, failSHA string
	var failSize, failMod int64
	defer func() {
		if err != nil {
			_ = writeState(opts.DataDir, State{
				Version:       1,
				Status:        StatusFailed,
				Source:        failSource,
				SourceSHA256:  failSHA,
				SourceSize:    failSize,
				SourceModUnix: failMod,
				Error:         err.Error(),
			})
		}
	}()

	dataDir, err := filepath.Abs(opts.DataDir)
	if err != nil {
		return Result{}, fmt.Errorf("resolve data dir: %w", err)
	}
	if fi, statErr := os.Stat(dataDir); statErr != nil || !fi.IsDir() {
		return Result{}, fmt.Errorf("data dir %s is not a directory", dataDir)
	}
	dbPath := filepath.Join(dataDir, "market.db")

	// A generation pointer owns the active database; legacy market.db is not
	// what the resolver will open, so touching it would be noise.
	if _, statErr := os.Stat(filepath.Join(dataDir, "active_generation.json")); statErr == nil {
		return Result{Reason: ReasonGenerationActive}, nil
	}

	seedPath, err := resolveSeed(opts.SeedPath, dataDir)
	if err != nil {
		if _, statErr := os.Stat(dbPath); statErr == nil {
			return Result{Reason: ReasonNoSeed}, nil
		}
		return Result{}, err
	}
	fi, err := os.Stat(seedPath)
	if err != nil || fi.IsDir() {
		return Result{}, fmt.Errorf("seed %s is not a file", seedPath)
	}
	res.State.Source = seedPath
	res.State.SourceSize = fi.Size()
	res.State.SourceModUnix = fi.ModTime().Unix()
	failSource, failSize, failMod = seedPath, fi.Size(), fi.ModTime().Unix()

	prev := readState(dataDir)
	seedSHA := prev.SourceSHA256
	if seedSHA == "" || prev.SourceSize != fi.Size() || prev.SourceModUnix != fi.ModTime().Unix() {
		seedSHA, err = hashFile(seedPath)
		if err != nil {
			return Result{}, fmt.Errorf("hash seed: %w", err)
		}
	}
	res.State.SourceSHA256 = seedSHA
	failSHA = seedSHA

	if prev.Status == StatusApplied && prev.SourceSHA256 == seedSHA {
		if healthy, _ := dbCoversState(dbPath, prev); healthy {
			prev.Source = seedPath
			prev.SourceSize = fi.Size()
			prev.SourceModUnix = fi.ModTime().Unix()
			return Result{Reason: ReasonAlreadyApplied, State: prev}, nil
		}
	}

	mode := ModeMerge
	if _, statErr := os.Stat(dbPath); errors.Is(statErr, os.ErrNotExist) {
		mode = ModeExtract
	}

	staging := filepath.Join(dataDir, stagingName)
	cleanupStaging(staging)
	defer cleanupStaging(staging)

	var seedStats dbStats
	if mode == ModeMerge {
		// ATTACH needs a real SQLite file, and coverage must be checked against
		// the seed itself, so materialize the compressed seed once.
		materialized := filepath.Join(dataDir, "market.db.seed.src")
		_ = os.Remove(materialized)
		defer os.Remove(materialized)
		if err := decompress(seedPath, materialized); err != nil {
			return Result{}, fmt.Errorf("decompress seed: %w", err)
		}
		mark("decompress")
		seedStats, err = inspectSeed(materialized)
		if err != nil {
			return Result{}, err
		}
		mark("inspect-seed")
		if err := stageCopy(dbPath, staging); err != nil {
			return Result{}, fmt.Errorf("stage existing market.db: %w", err)
		}
		if err := validateSchema(staging); err != nil {
			return Result{}, err
		}
		mark("stage-copy")
		if err := mergeSeed(staging, materialized); err != nil {
			return Result{}, fmt.Errorf("merge seed: %w", err)
		}
		mark("merge")
	} else {
		if err := decompress(seedPath, staging); err != nil {
			return Result{}, fmt.Errorf("decompress seed: %w", err)
		}
		mark("decompress")
		if err := validateSchema(staging); err != nil {
			return Result{}, err
		}
		seedStats, err = inspectSeed(staging)
		if err != nil {
			return Result{}, err
		}
		mark("inspect-seed")
	}

	if err := validateDB(staging, seedStats); err != nil {
		return Result{}, err
	}
	mark("validate")

	stats, err := readStats(staging)
	if err != nil {
		return Result{}, err
	}

	var backupPath string
	if mode == ModeMerge {
		backupPath, err = backupDB(dataDir, dbPath)
		if err != nil {
			return Result{}, fmt.Errorf("backup current market.db: %w", err)
		}
	}
	mark("backup")

	if err := activate(staging, dbPath); err != nil {
		return Result{}, err
	}
	mark("activate")

	size, sha, err := fileSizeSHA(dbPath)
	if err != nil {
		return Result{}, err
	}
	st := State{
		Version:           1,
		Status:            StatusApplied,
		Source:            seedPath,
		SourceSHA256:      seedSHA,
		SourceSize:        fi.Size(),
		SourceModUnix:     fi.ModTime().Unix(),
		Mode:              mode,
		AppliedAtUTC:      time.Now().UTC().Format(time.RFC3339),
		Backup:            backupPath,
		DBPath:            dbPath,
		DBSize:            size,
		DBSHA256:          sha,
		PriceHistoryRows:  stats.priceRows,
		PriceHistoryFirst: stats.firstDate,
		PriceHistoryLast:  stats.lastDate,
		DailyPricesRows:   stats.dailyRows,
	}
	if err := writeState(dataDir, st); err != nil {
		return Result{}, fmt.Errorf("write seed state: %w", err)
	}
	res.Applied = true
	res.Mode = mode
	res.Reason = ReasonApplied
	res.State = st
	return res, nil
}

type dbStats struct {
	priceRows int64
	firstDate string
	lastDate  string
	dailyRows int64
	symbols   int64
}

func inspectSeed(path string) (dbStats, error) {
	conn, err := openReadOnly(path)
	if err != nil {
		return dbStats{}, fmt.Errorf("open seed: %w", err)
	}
	defer conn.Close()
	stats, err := readStatsConn(conn)
	if err != nil {
		return dbStats{}, fmt.Errorf("inspect seed: %w", err)
	}
	if stats.priceRows == 0 {
		return dbStats{}, errors.New("seed has no price_history rows")
	}
	return stats, nil
}

func readStats(path string) (dbStats, error) {
	conn, err := openReadOnly(path)
	if err != nil {
		return dbStats{}, err
	}
	defer conn.Close()
	return readStatsConn(conn)
}

func readStatsConn(conn *sql.DB) (dbStats, error) {
	var s dbStats
	if err := conn.QueryRow(`SELECT count(*), coalesce(min(date),''), coalesce(max(date),''),
		count(DISTINCT symbol) FROM price_history`).Scan(&s.priceRows, &s.firstDate, &s.lastDate, &s.symbols); err != nil {
		return s, err
	}
	// daily_prices is not required by every lab fixture; absence is not fatal.
	_ = conn.QueryRow(`SELECT count(*) FROM daily_prices`).Scan(&s.dailyRows)
	return s, nil
}

func validateSchema(path string) error {
	conn, err := openReadOnly(path)
	if err != nil {
		return fmt.Errorf("open staged database: %w", err)
	}
	defer conn.Close()
	var integrity string
	if err := conn.QueryRow(`PRAGMA integrity_check`).Scan(&integrity); err != nil {
		return fmt.Errorf("integrity_check: %w", err)
	}
	if integrity != "ok" {
		return fmt.Errorf("integrity_check = %q", integrity)
	}
	cols, err := tableColumns(conn, "main", "price_history")
	if err != nil {
		return err
	}
	have := map[string]bool{}
	for _, c := range cols {
		have[c] = true
	}
	for _, c := range requiredPriceHistoryColumns {
		if !have[c] {
			return fmt.Errorf("price_history is missing column %q", c)
		}
	}
	return nil
}

func validateDB(path string, seed dbStats) error {
	if err := validateSchema(path); err != nil {
		return err
	}
	conn, err := openReadOnly(path)
	if err != nil {
		return fmt.Errorf("open staged database: %w", err)
	}
	defer conn.Close()
	stats, err := readStatsConn(conn)
	if err != nil {
		return fmt.Errorf("read staged stats: %w", err)
	}
	if stats.priceRows < seed.priceRows {
		return fmt.Errorf("staged price_history rows %d < seed rows %d", stats.priceRows, seed.priceRows)
	}
	if seed.firstDate != "" && (stats.firstDate == "" || stats.firstDate > seed.firstDate) {
		return fmt.Errorf("staged first candle %s is newer than seed first candle %s", stats.firstDate, seed.firstDate)
	}
	return nil
}

// mergeSeed copies market data from the seed into the staged database. Existing
// rows always win (INSERT OR IGNORE); tables unique to the seed are created and
// copied. User/computed/pipeline tables are never copied.
func mergeSeed(staging, seedPath string) error {
	conn, err := db.OpenRW(staging)
	if err != nil {
		return err
	}
	defer conn.Close()
	conn.SetMaxOpenConns(1)

	if _, err := conn.Exec(`PRAGMA journal_mode=DELETE`); err != nil {
		return fmt.Errorf("journal_mode: %w", err)
	}
	if _, err := conn.Exec(`ATTACH DATABASE ? AS seedsrc`, seedPath); err != nil {
		return fmt.Errorf("attach seed: %w", err)
	}
	defer conn.Exec(`DETACH DATABASE seedsrc`)

	names, err := tableNames(conn, "seedsrc")
	if err != nil {
		return err
	}
	mainNames, err := tableNames(conn, "main")
	if err != nil {
		return err
	}
	mainSet := map[string]bool{}
	for _, n := range mainNames {
		mainSet[n] = true
	}

	tx, err := conn.Begin()
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()

	for _, name := range names {
		if neverMerge[name] || !safeIdent(name) {
			continue
		}
		if !mainSet[name] {
			if !seedOnlyTables[name] {
				continue
			}
			if err := createFromSeed(tx, name); err != nil {
				return fmt.Errorf("create %s: %w", name, err)
			}
		}
		mainCols, err := tableColumnsTx(tx, "main", name)
		if err != nil {
			return err
		}
		seedCols, err := tableColumnsTx(tx, "seedsrc", name)
		if err != nil {
			return err
		}
		seedSet := map[string]bool{}
		for _, c := range seedCols {
			seedSet[c] = true
		}
		var cols []string
		for _, c := range mainCols {
			if seedSet[c] {
				cols = append(cols, c)
			}
		}
		if len(cols) == 0 {
			continue
		}
		pk, err := pkColumnsTx(tx, "main", name)
		if err != nil {
			return err
		}
		if len(pk) == 0 {
			// No uniqueness constraint: insert only rows that are not already
			// present (whole-row comparison, NULL-safe). Keeps retries
			// idempotent for seed-only tables such as adjust_events.
			notExists := make([]string, len(cols))
			for i, c := range cols {
				q := quoteIdent(c)
				notExists[i] = fmt.Sprintf(`m.%s IS s.%s`, q, q)
			}
			if _, err := tx.Exec(fmt.Sprintf(`INSERT INTO "main".%s (%s) SELECT %s FROM "seedsrc".%s s WHERE NOT EXISTS (SELECT 1 FROM "main".%s m WHERE %s)`,
				quoteIdent(name), quoteList(cols), prefixed(cols, "s"), quoteIdent(name),
				quoteIdent(name), strings.Join(notExists, " AND "))); err != nil {
				return fmt.Errorf("merge %s: %w", name, err)
			}
			continue
		}
		if _, err := tx.Exec(fmt.Sprintf(`INSERT OR IGNORE INTO "main".%s (%s) SELECT %s FROM "seedsrc".%s`,
			quoteIdent(name), quoteList(cols), quoteList(cols), quoteIdent(name))); err != nil {
			return fmt.Errorf("merge %s: %w", name, err)
		}
	}
	return tx.Commit()
}

func createFromSeed(tx *sql.Tx, name string) error {
	var ddl string
	if err := tx.QueryRow(`SELECT sql FROM "seedsrc".sqlite_master WHERE type='table' AND name=?`, name).Scan(&ddl); err != nil {
		return err
	}
	if strings.TrimSpace(ddl) == "" {
		return fmt.Errorf("seed table %s has no DDL", name)
	}
	_, err := tx.Exec(ddl)
	return err
}

func tableNames(conn *sql.DB, schema string) ([]string, error) {
	rows, err := conn.Query(fmt.Sprintf(`SELECT name FROM "%s".sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%%' ORDER BY name`, schema))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var n string
		if err := rows.Scan(&n); err != nil {
			return nil, err
		}
		out = append(out, n)
	}
	return out, rows.Err()
}

func tableColumns(conn *sql.DB, schema, table string) ([]string, error) {
	rows, err := conn.Query(fmt.Sprintf(`PRAGMA "%s".table_info(%s)`, schema, quoteIdent(table)))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanColumns(rows)
}

func tableColumnsTx(tx *sql.Tx, schema, table string) ([]string, error) {
	rows, err := tx.Query(fmt.Sprintf(`PRAGMA "%s".table_info(%s)`, schema, quoteIdent(table)))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanColumns(rows)
}

func scanColumns(rows *sql.Rows) ([]string, error) {
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	var out []string
	for rows.Next() {
		vals := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		// table_info: cid, name, type, notnull, dflt_value, pk
		if name, ok := vals[1].(string); ok {
			out = append(out, name)
		}
	}
	return out, rows.Err()
}

func pkColumnsTx(tx *sql.Tx, schema, table string) ([]string, error) {
	rows, err := tx.Query(fmt.Sprintf(`PRAGMA "%s".table_info(%s)`, schema, quoteIdent(table)))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	var out []string
	for rows.Next() {
		vals := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}
		name, _ := vals[1].(string)
		pk, _ := vals[5].(int64)
		if pk > 0 && name != "" {
			out = append(out, name)
		}
	}
	return out, rows.Err()
}

func openReadOnly(path string) (*sql.DB, error) {
	conn, err := db.OpenRO(path)
	if err != nil {
		return nil, err
	}
	conn.SetMaxOpenConns(1)
	return conn, nil
}

func resolveSeed(explicit, dataDir string) (string, error) {
	var candidates []string
	if explicit != "" {
		candidates = append(candidates, explicit)
	} else {
		dirs := []string{dataDir, "."}
		if exe, err := os.Executable(); err == nil {
			dirs = append([]string{filepath.Dir(exe)}, dirs...)
		}
		// gzip is preferred: its stdlib decoder is roughly two orders of
		// magnitude faster than the pure-Go XZ/LZMA reader for this database,
		// which keeps first launch in seconds instead of minutes.
		for _, name := range []string{"market.db.gz", "market.db.lzma"} {
			for _, d := range dirs {
				candidates = append(candidates, filepath.Join(d, name))
			}
		}
	}
	for _, c := range candidates {
		if fi, err := os.Stat(c); err == nil && !fi.IsDir() {
			return filepath.Abs(c)
		}
	}
	return "", fmt.Errorf("market.db is missing and no market.db.gz/market.db.lzma seed was found (looked in %s)", strings.Join(candidates, ", "))
}

func stageCopy(src, dst string) error {
	if err := copyFile(src, dst); err != nil {
		return err
	}
	for _, suffix := range []string{"-wal", "-shm"} {
		if _, err := os.Stat(src + suffix); err == nil {
			if err := copyFile(src+suffix, dst+suffix); err != nil {
				return err
			}
		}
	}
	return nil
}

func decompress(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	r, err := newArchiveReader(in)
	if err != nil {
		return err
	}
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	buf := make([]byte, 1<<20)
	if _, err := io.CopyBuffer(out, r, buf); err != nil {
		_ = out.Close()
		return err
	}
	if err := out.Sync(); err != nil {
		_ = out.Close()
		return err
	}
	return out.Close()
}

var (
	xzMagic   = []byte{0xfd, '7', 'z', 'X', 'Z', 0x00}
	gzipMagic = []byte{0x1f, 0x8b}
)

// newArchiveReader accepts every container the build has shipped:
// gzip (fast stdlib decoder), XZ (Python lzma default, the current
// market.db.lzma) and legacy LZMA-alone (Go's snapshot builder).
func newArchiveReader(f *os.File) (io.Reader, error) {
	var magic [6]byte
	n, err := io.ReadFull(f, magic[:])
	if err != nil && err != io.ErrUnexpectedEOF {
		return nil, fmt.Errorf("read archive magic: %w", err)
	}
	if _, err := f.Seek(0, io.SeekStart); err != nil {
		return nil, err
	}
	if n >= 2 && bytes.Equal(magic[:2], gzipMagic) {
		return gzip.NewReader(f)
	}
	if n == 6 && bytes.Equal(magic[:], xzMagic) {
		return xz.NewReader(f)
	}
	return lzma.NewReader(f)
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	buf := make([]byte, 1<<20)
	if _, err := io.CopyBuffer(out, in, buf); err != nil {
		_ = out.Close()
		return err
	}
	if err := out.Sync(); err != nil {
		_ = out.Close()
		return err
	}
	return out.Close()
}

func backupDB(dataDir, dbPath string) (string, error) {
	dir := filepath.Join(dataDir, "backups")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	name := "market.db.before-seed-" + time.Now().UTC().Format("20060102T150405") + ".bak"
	dst := filepath.Join(dir, name)
	if err := copyFile(dbPath, dst); err != nil {
		return "", err
	}
	for _, suffix := range []string{"-wal", "-shm"} {
		if _, err := os.Stat(dbPath + suffix); err == nil {
			if err := copyFile(dbPath+suffix, dst+suffix); err != nil {
				return "", err
			}
		}
	}
	return dst, nil
}

func activate(staging, dbPath string) error {
	// A stale -wal/-shm from the old database must never be replayed against
	// the new file. No borsd has opened it yet (instance lock is held).
	for _, suffix := range []string{"-wal", "-shm"} {
		if err := os.Remove(dbPath + suffix); err != nil && !errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("remove stale %s: %w", filepath.Base(dbPath)+suffix, err)
		}
	}
	if err := os.Rename(staging, dbPath); err != nil {
		return fmt.Errorf("activate database: %w", err)
	}
	for _, suffix := range []string{"-wal", "-shm"} {
		_ = os.Remove(staging + suffix)
	}
	return nil
}

func cleanupStaging(staging string) {
	for _, p := range []string{staging, staging + "-wal", staging + "-shm", staging + "-journal"} {
		_ = os.Remove(p)
	}
}

func dbCoversState(path string, st State) (bool, error) {
	if _, err := os.Stat(path); err != nil {
		return false, err
	}
	conn, err := openReadOnly(path)
	if err != nil {
		return false, err
	}
	defer conn.Close()
	var rows int64
	var first string
	if err := conn.QueryRow(`SELECT count(*), coalesce(min(date),'') FROM price_history`).Scan(&rows, &first); err != nil {
		return false, err
	}
	if rows < st.PriceHistoryRows {
		return false, nil
	}
	if st.PriceHistoryFirst != "" && (first == "" || first > st.PriceHistoryFirst) {
		return false, nil
	}
	return true, nil
}

func readState(dataDir string) State {
	raw, err := os.ReadFile(filepath.Join(dataDir, StateFile))
	if err != nil {
		return State{}
	}
	var st State
	if err := json.Unmarshal(raw, &st); err != nil {
		return State{}
	}
	return st
}

func writeState(dataDir string, st State) error {
	raw, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	tmp := filepath.Join(dataDir, StateFile+".tmp")
	if err := os.WriteFile(tmp, raw, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, filepath.Join(dataDir, StateFile))
}

func hashFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func fileSizeSHA(path string) (int64, string, error) {
	fi, err := os.Stat(path)
	if err != nil {
		return 0, "", err
	}
	sha, err := hashFile(path)
	return fi.Size(), sha, err
}

func safeIdent(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !(r == '_' || r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9') {
			return false
		}
	}
	return true
}

func quoteIdent(s string) string { return `"` + strings.ReplaceAll(s, `"`, `""`) + `"` }

func quoteList(cols []string) string {
	q := make([]string, len(cols))
	for i, c := range cols {
		q[i] = quoteIdent(c)
	}
	sort.Strings(q)
	return strings.Join(q, ",")
}

func prefixed(cols []string, alias string) string {
	q := make([]string, len(cols))
	for i, c := range cols {
		q[i] = alias + "." + quoteIdent(c)
	}
	sort.Strings(q)
	return strings.Join(q, ",")
}
