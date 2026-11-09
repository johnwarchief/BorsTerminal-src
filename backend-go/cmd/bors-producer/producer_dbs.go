package main

import (
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"borsterminal/backend/internal/db"
)

// ProducerDBAllowlist قراردادِ P0.2 است: Snapshot فقط این دو دارایی را دارد.
// research.db، oc_client.db، user.db و هر .db دیگر دادهٔ محلی‌اند و منتشر نمی‌شوند.
var ProducerDBAllowlist = []string{"market", "codal"}

func isAllowedProducerDB(key string) bool {
	for _, allowed := range ProducerDBAllowlist {
		if key == allowed {
			return true
		}
	}
	return false
}

// collectProducerDBs فقط از allowlist باز می‌کند. market.db اجباری است؛
// codal.db اگر نباشد (نصبِ تازه) حذف می‌شود، ولی خرابیِ آن کل Snapshot را رد
// می‌کند تا مجموعهٔ امضاشده بی‌صدا ناقص منتشر نشود.
func collectProducerDBs(dataDir string) (map[string]*sql.DB, error) {
	dbs := make(map[string]*sql.DB, len(ProducerDBAllowlist))
	closeAll := func() {
		for _, conn := range dbs {
			_ = conn.Close()
		}
	}

	for _, key := range ProducerDBAllowlist {
		path := filepath.Join(dataDir, key+".db")
		fi, err := os.Stat(path)
		if err != nil {
			if key == "market" {
				return nil, fmt.Errorf("market.db is required: %w", err)
			}
			continue
		}
		if fi.IsDir() {
			closeAll()
			return nil, fmt.Errorf("%s.db is a directory, not a database", key)
		}
		conn, err := db.OpenRW(path)
		if err != nil {
			closeAll()
			return nil, fmt.Errorf("open %s.db: %w", key, err)
		}
		// Open تنبل است؛ یک پرس‌وجوی ارزان هدرِ SQLite را می‌خواند تا فایلِ
		// خراب/غیر-SQLite همین‌جا رد شود، نه بعد از یک VACUUM روی مجموعهٔ امضاشده.
		var probe int
		if err := conn.QueryRow("SELECT 1 FROM sqlite_master LIMIT 1").Scan(&probe); err != nil && !errors.Is(err, sql.ErrNoRows) {
			_ = conn.Close()
			closeAll()
			return nil, fmt.Errorf("%s.db is not a readable SQLite database: %w", key, err)
		}
		dbs[key] = conn
	}
	if dbs["market"] == nil {
		closeAll()
		return nil, fmt.Errorf("market.db is required")
	}
	return dbs, nil
}

// rejectedProducerDBs فایل‌های .dbِ ریشهٔ dataDir را که در allowlist نیستند
// برمی‌گرداند — فقط برای گزارش/لاگ؛ هیچ‌کدام باز نمی‌شوند.
func rejectedProducerDBs(dataDir string) ([]string, error) {
	entries, err := os.ReadDir(dataDir)
	if err != nil {
		return nil, err
	}
	var rejected []string
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.EqualFold(filepath.Ext(name), ".db") {
			continue
		}
		key := strings.TrimSuffix(name, filepath.Ext(name))
		if !isAllowedProducerDB(key) {
			rejected = append(rejected, name)
		}
	}
	sort.Strings(rejected)
	return rejected, nil
}
