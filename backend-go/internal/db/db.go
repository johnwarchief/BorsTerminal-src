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
	Codal  *sql.DB
	User   *sql.DB
}

// DSN: مسیرِ ویندوزی باید URI شود (file:///C:/...) وگرنه modernc آن را نامِ نسبی می‌خواند.
// _pragma در DSN می‌نشیند تا هر اتصالِ استخرِ database/sql آن را بگیرد؛ Exec بعد از Open
// فقط یک اتصال را می‌گیرد و بقیه بی‌تنظیم می‌مانند.
func dsn(path, mode string) string {
	if abs, err := filepath.Abs(path); err == nil {
		path = abs
	}
	u := url.URL{Scheme: "file", Path: "/" + filepath.ToSlash(path)}
	q := u.Query()
	q.Set("mode", mode)
	q.Add("_pragma", "busy_timeout(30000)")
	q.Add("_pragma", "cache_size(-64000)")
	q.Add("_pragma", "temp_store(MEMORY)")
	q.Add("_pragma", "mmap_size(268435456)")
	if mode == "ro" {
		q.Add("_pragma", "query_only(ON)")
	}
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

func openMemory(mode string) (*sql.DB, error) {
	u := url.URL{Scheme: "file", Path: "/user_mem"}
	q := u.Query()
	q.Set("mode", "memory")
	q.Set("cache", "shared")
	if mode == "ro" {
		q.Add("_pragma", "query_only(ON)")
	}
	u.RawQuery = q.Encode()
	conn, err := sql.Open("sqlite", u.String())
	if err != nil {
		return nil, err
	}
	conn.SetMaxOpenConns(4)
	return conn, nil
}

// Open متد استاندارد باز کردن دیتابیس‌ها برای سرور borsd و سناریوهای عملیاتی:
// ۱. market.db همیشه در Go با mode=ro باز می‌شود (تضمین ساختاری Single Writer در فاز ۱).
// ۲. codal.db در صورت وجود، همواره با mode=ro باز می‌شود (تقارن کامل با market.db).
// ۳. user.db در حالت عادی نوشتنی (rwc) است؛ اما اگر readOnly=true باشد، اجباراً با mode=ro باز می‌شود
//    و اگر فایل روی دیسک نباشد، به هیچ وجه فایل صفر-بایتی نمی‌سازد و در حافظه مدیریت می‌شود.
func Open(dataDir string, readOnly bool) (*Handles, error) {
	return OpenResolved(
		filepath.Join(dataDir, "market.db"),
		filepath.Join(dataDir, "codal.db"),
		dataDir, readOnly,
	)
}

// OpenResolved همان Open است با مسیرهایِ صریحِ market/codal (نسل فعال) و
// userDir که همیشه dataDir می‌ماند. codalPath تهی یعنی این نسل codal.db ندارد.
func OpenResolved(marketPath, codalPath, userDir string, readOnly bool) (*Handles, error) {
	if marketPath == "" {
		return nil, ErrMarketMissing
	}
	if _, err := os.Stat(marketPath); err != nil {
		return nil, ErrMarketMissing
	}
	// قاعده ساختاری فاز ۱: Go هرگز در market.db نمی‌نویسد
	m, err := open(marketPath, "ro")
	if err != nil {
		return nil, fmt.Errorf("open market.db: %w", err)
	}

	// قاعده ساختاری: codal.db در صورت وجود، همیشه mode=ro است
	var c *sql.DB
	if codalPath != "" {
		if _, statErr := os.Stat(codalPath); statErr == nil {
			c, err = open(codalPath, "ro")
			if err != nil {
				m.Close()
				return nil, fmt.Errorf("open codal.db: %w", err)
			}
		}
	}

	// قاعده user.db:
	var u *sql.DB
	userPath := filepath.Join(userDir, "user.db")
	if readOnly {
		if _, err := os.Stat(userPath); err == nil {
			u, err = open(userPath, "ro")
			if err != nil {
				m.Close()
				if c != nil {
					c.Close()
				}
				return nil, fmt.Errorf("open user.db (read-only): %w", err)
			}
		} else {
			// فایل user.db وجود ندارد؛ در حالت read-only نباید فایلی روی دیسک ساخته شود
			u, err = openMemory("ro")
			if err != nil {
				m.Close()
				if c != nil {
					c.Close()
				}
				return nil, fmt.Errorf("open user.db memory (read-only): %w", err)
			}
		}
	} else {
		u, err = open(userPath, "rwc")
		if err != nil {
			m.Close()
			if c != nil {
				c.Close()
			}
			return nil, fmt.Errorf("open user.db: %w", err)
		}
	}

	return &Handles{Market: m, Codal: c, User: u}, nil
}

// OpenRO opens an existing database file strictly in read-only mode with query_only=ON.
func OpenRO(path string) (*sql.DB, error) {
	if _, err := os.Stat(path); err != nil {
		return nil, err
	}
	return open(path, "ro")
}

// OpenRW opens an existing database file in read-write mode.
func OpenRW(path string) (*sql.DB, error) {
	if _, err := os.Stat(path); err != nil {
		return nil, err
	}
	return open(path, "rw")
}

// OpenRWC opens or creates a database file in read-write-create mode.
func OpenRWC(path string) (*sql.DB, error) {
	return open(path, "rwc")
}

// OpenWritableForTest صرفاً برای فیکسچرهای تست در دایرکتوری‌های موقت t.TempDir()
// است تا تست‌های اجزای تحلیل‌گر بتوانند داده‌های ساختگی/لبه‌ای را شبیه‌سازی کنند.
func OpenWritableForTest(dataDir string) (*Handles, error) {
	market := filepath.Join(dataDir, "market.db")
	if _, err := os.Stat(market); err != nil {
		return nil, ErrMarketMissing
	}
	m, err := open(market, "rw")
	if err != nil {
		return nil, fmt.Errorf("open market.db (writable test): %w", err)
	}
	u, err := open(filepath.Join(dataDir, "user.db"), "rwc")
	if err != nil {
		m.Close()
		return nil, fmt.Errorf("open user.db: %w", err)
	}
	return &Handles{Market: m, User: u}, nil
}

func (h *Handles) Ping(ctx context.Context) error {
	if h.Market != nil {
		if err := h.Market.PingContext(ctx); err != nil {
			return err
		}
	}
	if h.Codal != nil {
		if err := h.Codal.PingContext(ctx); err != nil {
			return err
		}
	}
	if h.User != nil {
		return h.User.PingContext(ctx)
	}
	return nil
}

func (h *Handles) Close() error {
	var errs []error
	if h.Market != nil {
		if err := h.Market.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	if h.Codal != nil {
		if err := h.Codal.Close(); err != nil {
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
