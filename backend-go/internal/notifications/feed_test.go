package notifications

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "market.db")
	db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(dbPath)+"?mode=rwc")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func initTestSchema(t *testing.T, db *sql.DB) {
	t.Helper()
	ddl := `
CREATE TABLE codal_notices (
    tracing_no INTEGER PRIMARY KEY,
    symbol TEXT,
    company_name TEXT,
    title TEXT,
    letter_code TEXT,
    publish_date TEXT,
    sent_date TEXT,
    url TEXT,
    fetched_at TEXT
);
`
	if _, err := db.Exec(ddl); err != nil {
		t.Fatalf("init schema: %v", err)
	}
}

func TestSources(t *testing.T) {
	ctx := context.Background()
	db := newTestDB(t)

	svc := NewService(db)
	t.Cleanup(func() { svc.Close() })

	// ۱. جدول هنوز نیست -> unavailable
	srcs, err := svc.Sources(ctx)
	if err != nil {
		t.Fatalf("Sources on missing table err: %v", err)
	}
	list := srcs["sources"].([]map[string]any)
	if len(list) != 1 || list[0]["state"] != "unavailable" {
		t.Fatalf("expected unavailable state, got %+v", list)
	}

	// ۲. ساخت جدول و خالی بودن -> state=empty, rows=0
	initTestSchema(t, db)
	srcs, err = svc.Sources(ctx)
	if err != nil {
		t.Fatalf("Sources on empty table: %v", err)
	}
	list = srcs["sources"].([]map[string]any)
	if list[0]["state"] != "empty" || list[0]["rows"] != 0 {
		t.Fatalf("expected empty state with 0 rows, got %+v", list[0])
	}

	// ۳. درج ردیف -> state=ok, rows=1
	_, err = db.Exec(`INSERT INTO codal_notices(tracing_no, symbol, company_name, title, letter_code, publish_date, fetched_at)
VALUES(1001, 'رمپنا', 'مپنا', 'گزارش فعالیت ماهانه', 'ن-۱', '1404/07/30 18:00:00', '2026-10-22 10:00:00')`)
	if err != nil {
		t.Fatalf("insert notice: %v", err)
	}

	srcs, err = svc.Sources(ctx)
	if err != nil {
		t.Fatalf("Sources with row: %v", err)
	}
	list = srcs["sources"].([]map[string]any)
	if list[0]["state"] != "ok" || list[0]["rows"] != 1 {
		t.Fatalf("expected ok state with 1 row, got %+v", list[0])
	}
}

func TestFeedAndFilters(t *testing.T) {
	ctx := context.Background()
	db := newTestDB(t)
	initTestSchema(t, db)

	// ردیف‌های نمونه
	rows := []struct {
		id      int
		sym     string
		title   string
		code    string
		pub     string
		fetched string
	}{
		{1, "رمپنا", "گزارش فعالیت ماهانه دوره ۱ ماهه", "ن-۱", "1404/07/28 10:00:00", "2026-10-20"},
		{2, "رمپنا", "گزارش فعالیت ماهانه دوره ۱ ماهه", "ن-۱", "1404/07/28 12:00:00", "2026-10-21"}, // تکراری (همان روز و همان عنوان)
		{3, "رمپنا", "اطلاعات و صورتهای مالی میاندوره‌ای", "ن-۲", "1404/07/29 11:00:00", "2026-10-21"}, // سطح high
		{4, "فولاد", "آگهی دعوت به مجمع عمومی", "ن-۳", "1404/07/30 09:00:00", "2026-10-22"},          // سطح high
	}

	for _, r := range rows {
		_, err := db.Exec(`INSERT INTO codal_notices(tracing_no, symbol, title, letter_code, publish_date, fetched_at)
VALUES(?, ?, ?, ?, ?, ?)`, r.id, r.sym, r.title, r.code, r.pub, r.fetched)
		if err != nil {
			t.Fatalf("insert row: %v", err)
		}
	}

	svc := NewService(db)
	t.Cleanup(func() { svc.Close() })

	// ۱. فید کلی
	fAll, err := svc.Feed(ctx, "", nil, 10, "")
	if err != nil {
		t.Fatalf("Feed general: %v", err)
	}
	if fAll["count"].(int) != 3 {
		t.Errorf("expected 3 items (1 duplicate merged), got count=%v", fAll["count"])
	}
	if fAll["merged_duplicates"].(int) != 1 {
		t.Errorf("expected 1 merged duplicate, got %v", fAll["merged_duplicates"])
	}

	// ۲. فیلتر symbol="رمپنا"
	fSym, err := svc.Feed(ctx, "", nil, 10, "رمپنا")
	if err != nil {
		t.Fatalf("Feed symbol: %v", err)
	}
	if fSym["count"].(int) != 2 {
		t.Errorf("expected 2 items for رمپنا, got %v", fSym["count"])
	}
	if fSym["symbol"] != "رمپنا" {
		t.Errorf("expected symbol key = رمپنا, got %v", fSym["symbol"])
	}

	// ۳. فیلتر levels=["high"]
	fHigh, err := svc.Feed(ctx, "", []string{"high"}, 10, "")
	if err != nil {
		t.Fatalf("Feed levels: %v", err)
	}
	if fHigh["count"].(int) != 2 {
		t.Errorf("expected 2 high items (صورتهای مالی + مجمع), got %v", fHigh["count"])
	}

	// ۴. فیلتر since="1404/07/29"
	fSince, err := svc.Feed(ctx, "1404/07/29", nil, 10, "")
	if err != nil {
		t.Fatalf("Feed since: %v", err)
	}
	if fSince["count"].(int) != 2 {
		t.Errorf("expected 2 items since 1404/07/29, got %v", fSince["count"])
	}
}
