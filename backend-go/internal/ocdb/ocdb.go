// Package ocdb مالکِ oc_client.db است: DB محلیِ کلاینت که تنظیمات/تاریخچهٔ
// اعلان، وضعیتِ نصب و فرصت‌ها را نگه می‌دارد و هرگز Snapshot/Registry نمی‌شود.
package ocdb

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/migrate"
)

type Store struct {
	DB   *sql.DB
	Path string
}

func Dir(dataDir string) string { return filepath.Join(dataDir, "oc") }

func Path(dataDir string) string { return filepath.Join(Dir(dataDir), "oc_client.db") }

func BackupDir(dataDir string) string { return filepath.Join(Dir(dataDir), "backups") }

// Open فایل را می‌سازد (اگر نباشد)، Migrationها را اجرا می‌کند و Store می‌دهد.
// user.db هرگز باز/تغییر داده نمی‌شود.
func Open(dataDir string) (*Store, error) {
	if err := os.MkdirAll(Dir(dataDir), 0o700); err != nil {
		return nil, fmt.Errorf("create oc dir: %w", err)
	}
	return OpenPath(Path(dataDir), BackupDir(dataDir))
}

// OpenPath برای تست و ابزارهایِ مهاجرت که مسیرِ صریح دارند.
func OpenPath(dbPath, backupDir string) (*Store, error) {
	conn, err := db.OpenRWC(dbPath)
	if err != nil {
		return nil, fmt.Errorf("open oc_client.db: %w", err)
	}
	if _, err := migrate.Apply(context.Background(), conn, dbPath, backupDir, migrations); err != nil {
		_ = conn.Close()
		return nil, err
	}
	return &Store{DB: conn, Path: dbPath}, nil
}

func (s *Store) Close() error {
	if s == nil || s.DB == nil {
		return nil
	}
	return s.DB.Close()
}
