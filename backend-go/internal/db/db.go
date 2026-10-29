package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

var ErrMarketMissing = errors.New("Database market.db not found.")

type Handles struct {
	Market *sql.DB
	User   *sql.DB
}

// DSN: مسیرِ ویندوزی باید URI شود (file:///C:/...) وگرنه modernc آن را نامِ نسبی می‌خواند.
// _pragma در DSN می‌نشیند تا هر اتصالِ استخرِ database/sql آن را بگیرد؛ Exec بعد از Open
// فقط یک اتصال را می‌گیرد و بقیه بی‌تنظیم می‌مانند.
func dsn(path, mode string) string {
	u := url.URL{Scheme: "file", Path: "/" + filepath.ToSlash(path)}
	q := u.Query()
	q.Set("mode", mode)
	q.Add("_pragma", "busy_timeout(30000)")
	q.Add("_pragma", "cache_size(-64000)")
	q.Add("_pragma", "temp_store(MEMORY)")
	q.Add("_pragma", "mmap_size(268435456)")
	u.RawQuery = q.Encode()
	return u.String()
}

func open(path, mode string) (*sql.DB, error) {
	conn, err := sql.Open("sqlite", dsn(path, mode))
	if err != nil {
		return nil, err
	}
	conn.SetMaxOpenConns(4)
	return conn, nil
}

func Open(dataDir string, readOnly bool) (*Handles, error) {
	market := filepath.Join(dataDir, "market.db")
	if _, err := os.Stat(market); err != nil {
		return nil, ErrMarketMissing
	}
	mode := "rw"
	if readOnly {
		mode = "ro"
	}
	m, err := open(market, mode)
	if err != nil {
		return nil, fmt.Errorf("open market.db: %w", err)
	}
	u, err := open(filepath.Join(dataDir, "user.db"), "rwc")
	if err != nil {
		m.Close()
		return nil, fmt.Errorf("open user.db: %w", err)
	}
	return &Handles{Market: m, User: u}, nil
}

func (h *Handles) Ping(ctx context.Context) error {
	if err := h.Market.PingContext(ctx); err != nil {
		return err
	}
	return h.User.PingContext(ctx)
}

func (h *Handles) Close() error {
	var errs []error
	if h.Market != nil {
		if err := h.Market.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	if h.User != nil {
		if err := h.User.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	return errors.Join(errs...)
}
