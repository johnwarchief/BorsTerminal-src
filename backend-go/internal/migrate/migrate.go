// Package migrate شماره‌دار کردنِ اسکیمای SQLite با PRAGMA user_version است.
// هر Migration در یک تراکنش اجرا می‌شود؛ خطا کلِ همان نسخه را برمی‌گرداند و
// user_version دست‌نخورده می‌ماند. پیش از نخستین تغییر، یک Backup با
// VACUUM INTO گرفته می‌شود تا مسیرِ Restore دستی همیشه ممکن باشد.
package migrate

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

type Migration struct {
	Version int
	Name    string
	SQL     string
}

type Result struct {
	From       int
	To         int
	Applied    []int
	BackupPath string
}

func CurrentVersion(ctx context.Context, conn *sql.DB) (int, error) {
	var v int
	if err := conn.QueryRowContext(ctx, "PRAGMA user_version").Scan(&v); err != nil {
		return 0, fmt.Errorf("read user_version: %w", err)
	}
	return v, nil
}

// Apply مجموعهٔ Migrationها را به‌ترتیبِ version اجرا می‌کند. اجرای دوبارهٔ
// همان مجموعه هیچ کاری نمی‌کند (idempotent). نسخهٔ DB بزرگ‌تر از آخرین
// Migration یعنی DB از این باینری جدیدتر است و رد می‌شود.
func Apply(ctx context.Context, conn *sql.DB, dbPath, backupDir string, migrations []Migration) (Result, error) {
	sorted := append([]Migration(nil), migrations...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].Version < sorted[j].Version })
	if err := validate(sorted); err != nil {
		return Result{}, err
	}
	current, err := CurrentVersion(ctx, conn)
	if err != nil {
		return Result{}, err
	}
	latest := 0
	if len(sorted) > 0 {
		latest = sorted[len(sorted)-1].Version
	}
	if current > latest {
		return Result{}, fmt.Errorf("database schema version %d is newer than latest migration %d", current, latest)
	}
	res := Result{From: current, To: current}
	if current == latest {
		return res, nil
	}

	now := time.Now().UTC()
	res.BackupPath, err = backup(ctx, conn, dbPath, backupDir, current, now)
	if err != nil {
		return Result{}, err
	}

	if _, err := conn.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS schema_migrations (
		version INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		applied_at TEXT NOT NULL
	)`); err != nil {
		return Result{}, fmt.Errorf("ensure schema_migrations: %w", err)
	}

	for _, m := range sorted {
		if m.Version <= current {
			continue
		}
		if err := applyOne(ctx, conn, m, now); err != nil {
			return res, fmt.Errorf("migration %d (%s): %w", m.Version, m.Name, err)
		}
		res.Applied = append(res.Applied, m.Version)
		res.To = m.Version
	}
	return res, nil
}

func validate(migrations []Migration) error {
	if len(migrations) > 0 && migrations[0].Version != 1 {
		return fmt.Errorf("migrations must start at version 1 (got %d)", migrations[0].Version)
	}
	prev := 0
	for i, m := range migrations {
		if m.Version <= prev {
			return fmt.Errorf("migrations must have strictly increasing versions (index %d: %d after %d)", i, m.Version, prev)
		}
		if strings.TrimSpace(m.Name) == "" {
			return fmt.Errorf("migration %d has no name", m.Version)
		}
		if strings.TrimSpace(m.SQL) == "" {
			return fmt.Errorf("migration %d has no SQL", m.Version)
		}
		prev = m.Version
	}
	return nil
}

func applyOne(ctx context.Context, conn *sql.DB, m Migration, now time.Time) error {
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()

	if _, err := tx.ExecContext(ctx, m.SQL); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx,
		`INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)`,
		m.Version, m.Name, now.Format(time.RFC3339)); err != nil {
		return err
	}
	// user_version عددی است و پارامتر نمی‌گیرد؛ مقدار از struct همین باینری است.
	if _, err := tx.ExecContext(ctx, fmt.Sprintf("PRAGMA user_version = %d", m.Version)); err != nil {
		return err
	}
	return tx.Commit()
}

func backup(ctx context.Context, conn *sql.DB, dbPath, backupDir string, from int, now time.Time) (string, error) {
	if strings.TrimSpace(dbPath) == "" {
		return "", errors.New("dbPath is required for backup")
	}
	if err := os.MkdirAll(backupDir, 0o755); err != nil {
		return "", fmt.Errorf("create backup dir: %w", err)
	}
	base := strings.TrimSuffix(filepath.Base(dbPath), filepath.Ext(dbPath))
	name := fmt.Sprintf("%s.v%d.%s.bak", base, from, now.Format("20060102T150405.000000000Z"))
	target := filepath.Join(backupDir, name)

	clean := filepath.Clean(target)
	if _, err := os.Stat(clean); err == nil {
		_ = os.Remove(clean)
	}
	vacuum := fmt.Sprintf("VACUUM INTO '%s'", strings.ReplaceAll(filepath.ToSlash(clean), "'", "''"))
	if _, err := conn.ExecContext(ctx, vacuum); err != nil {
		return "", fmt.Errorf("backup database: %w", err)
	}
	fi, err := os.Stat(clean)
	if err != nil {
		return "", fmt.Errorf("backup file missing: %w", err)
	}
	if fi.Size() == 0 {
		return "", fmt.Errorf("backup file is empty: %s", clean)
	}
	return clean, nil
}

// Restore یک بکاپِ سالم را جای dbPath می‌گذارد. فقط وقتی صدا بزنید که هیچ
// اتصالِ بازی به dbPath نیست. ابتدا در همان پوشه کپی می‌شود و بعد rename، تا
// یک کپیِ نیمه‌کاره فایلِ مقصد را خراب نکند.
func Restore(dbPath, backupPath string) error {
	if _, err := os.Stat(backupPath); err != nil {
		return fmt.Errorf("backup not found: %w", err)
	}
	dir := filepath.Dir(dbPath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(dir, ".restore-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	src, err := os.Open(backupPath)
	if err != nil {
		_ = tmp.Close()
		return err
	}
	if _, err := tmp.ReadFrom(src); err != nil {
		_ = src.Close()
		_ = tmp.Close()
		return err
	}
	_ = src.Close()
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	// فایل‌های جانبیِ WAL مقصد با نسخهٔ بازگردانده‌شده هم‌خوان نیستند.
	for _, suffix := range []string{"-wal", "-shm"} {
		_ = os.Remove(dbPath + suffix)
	}
	if err := os.Rename(tmpName, dbPath); err != nil {
		// ویندوز اگر فایل مقصد باز باشد rename نمی‌دهد؛ پیام صریح بده.
		return fmt.Errorf("replace database (close all connections first): %w", err)
	}
	return nil
}
