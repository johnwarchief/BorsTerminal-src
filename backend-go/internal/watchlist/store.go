package watchlist

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"borsterminal/backend/internal/fundamental"
)

const (
	UserWatchlistMax = 60
	MatrixProbeMax   = 60
	MaxNote          = 200
	MaxName          = 120
)

const ddl = `
CREATE TABLE IF NOT EXISTS user_watchlists (
    symbol_norm TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL DEFAULT '',
    name        TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    added_at    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_uwl_added ON user_watchlists(added_at);
`

type Row struct {
	Symbol  string `json:"symbol"`
	Name    string `json:"name"`
	Note    string `json:"note"`
	AddedAt string `json:"added_at"`
	Norm    string `json:"norm"`
}

var normFaRepl = strings.NewReplacer("ي", "ی", "ك", "ک", "ى", "ی", "‌", "")

// NormFa یکسان‌سازی نوشتار عربی/فارسی و حذف نیم‌فاصله عینِ fts_engine.norm_fa.
func NormFa(s string) string {
	return normFaRepl.Replace(s)
}

func truncateRunes(s string, maxLen int) string {
	r := []rune(s)
	if len(r) > maxLen {
		return string(r[:maxLen])
	}
	return s
}

var (
	ErrEmptySymbol   = errors.New("نماد ارسال نشده")
	ErrInvalidSymbol = errors.New("نماد نامعتبر (تهی پس از نرمال‌سازی)")
)

type CapError struct {
	Cap int
}

func (e *CapError) Error() string {
	return fmt.Sprintf("سقف واچ‌لیست (%d سهم) پر است — از پنل تنظیمات کدال آن را تغییر دهید", e.Cap)
}

type Store struct {
	db      *sql.DB
	dataDir string
}

func NewStore(db *sql.DB, dataDir string) (*Store, error) {
	if _, err := db.Exec(ddl); err != nil {
		return nil, fmt.Errorf("ensure user_watchlists table: %w", err)
	}
	return &Store{db: db, dataDir: dataDir}, nil
}

func (s *Store) Cap() int {
	cfg := fundamental.LoadFtsConfig(s.dataDir)
	capVal := 50
	if v, ok := cfg["watchlist_max"]; ok {
		switch n := v.(type) {
		case int:
			capVal = n
		case float64:
			capVal = int(n)
		}
	}
	if capVal < 1 {
		capVal = 1
	} else if capVal > UserWatchlistMax {
		capVal = UserWatchlistMax
	}
	return capVal
}

func (s *Store) List(ctx context.Context) ([]Row, int, error) {
	rows, err := s.db.QueryContext(ctx, "SELECT symbol_norm, symbol, name, note, added_at FROM user_watchlists ORDER BY added_at DESC, symbol_norm ASC")
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	out := make([]Row, 0)
	for rows.Next() {
		var r Row
		if err := rows.Scan(&r.Norm, &r.Symbol, &r.Name, &r.Note, &r.AddedAt); err != nil {
			return nil, 0, err
		}
		out = append(out, r)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}
	return out, UserWatchlistMax, nil
}

func (s *Store) Get(ctx context.Context, symbolNorm string) (*Row, error) {
	var r Row
	err := s.db.QueryRowContext(ctx, "SELECT symbol_norm, symbol, name, note, added_at FROM user_watchlists WHERE symbol_norm = ?", symbolNorm).
		Scan(&r.Norm, &r.Symbol, &r.Name, &r.Note, &r.AddedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &r, nil
}

func (s *Store) Count(ctx context.Context) (int, error) {
	var n int
	err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM user_watchlists").Scan(&n)
	if err != nil {
		return 0, err
	}
	return n, nil
}

type AddResult struct {
	Watch   *Row
	Count   int
	Limit   int
	Existed bool
}

func (s *Store) Add(ctx context.Context, symbol, name, note, when string) (*AddResult, error) {
	sym := strings.TrimSpace(symbol)
	if sym == "" {
		return nil, ErrEmptySymbol
	}
	key := NormFa(sym)
	if key == "" {
		return nil, ErrInvalidSymbol
	}

	prior, err := s.Get(ctx, key)
	if err != nil {
		return nil, err
	}
	existed := prior != nil

	capVal := s.Cap()
	cnt, err := s.Count(ctx)
	if err != nil {
		return nil, err
	}

	if !existed && cnt >= capVal {
		return nil, &CapError{Cap: capVal}
	}

	stamp := when
	if stamp == "" {
		stamp = time.Now().Format("2006-01-02T15:04:05")
	}

	symTrunc := truncateRunes(sym, MaxName)
	nameTrunc := truncateRunes(name, MaxName)
	noteTrunc := truncateRunes(note, MaxNote)

	query := `
INSERT INTO user_watchlists(symbol_norm, symbol, name, note, added_at)
VALUES(?,?,?,?,?)
ON CONFLICT(symbol_norm) DO UPDATE SET
  symbol=excluded.symbol,
  name=CASE WHEN excluded.name<>'' THEN excluded.name ELSE user_watchlists.name END,
  note=CASE WHEN excluded.note<>'' THEN excluded.note ELSE user_watchlists.note END;
`
	if _, err := s.db.ExecContext(ctx, query, key, symTrunc, nameTrunc, noteTrunc, stamp); err != nil {
		return nil, fmt.Errorf("insert user_watchlists: %w", err)
	}

	rec, err := s.Get(ctx, key)
	if err != nil {
		return nil, err
	}
	if rec == nil {
		return nil, ErrInvalidSymbol
	}

	newCount, err := s.Count(ctx)
	if err != nil {
		return nil, err
	}

	return &AddResult{
		Watch:   rec,
		Count:   newCount,
		Limit:   capVal,
		Existed: existed,
	}, nil
}

func (s *Store) Remove(ctx context.Context, symbol string) (int, error) {
	key := NormFa(strings.TrimSpace(symbol))
	if key == "" {
		return 0, nil
	}
	res, err := s.db.ExecContext(ctx, "DELETE FROM user_watchlists WHERE symbol_norm = ?", key)
	if err != nil {
		return 0, err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return 0, err
	}
	return int(n), nil
}
