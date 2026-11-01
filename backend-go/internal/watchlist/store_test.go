package watchlist

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func newTestDB(t *testing.T) (*sql.DB, string) {
	t.Helper()
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "user.db")
	db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(dbPath)+"?mode=rwc")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db, dir
}

func TestStoreCRUD(t *testing.T) {
	ctx := context.Background()
	db, dir := newTestDB(t)

	s, err := NewStore(db, dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	// ۱. لیست خالی
	list, limit, err := s.List(ctx)
	if err != nil {
		t.Fatalf("List on empty: %v", err)
	}
	if len(list) != 0 || limit != UserWatchlistMax {
		t.Fatalf("expected empty list with limit %d, got %v (len=%d)", UserWatchlistMax, list, len(list))
	}

	// ۲. افزودن نماد اول
	res1, err := s.Add(ctx, "رمپنا", "مدیریت پروژه‌های نیروگاهی", "یادداشت تست", "2026-10-01T12:00:00")
	if err != nil {
		t.Fatalf("Add رمپنا: %v", err)
	}
	if res1.Existed {
		t.Errorf("expected Existed=false for new symbol")
	}
	if res1.Count != 1 {
		t.Errorf("expected Count=1, got %d", res1.Count)
	}
	if res1.Watch.Symbol != "رمپنا" || res1.Watch.Norm != "رمپنا" {
		t.Errorf("unexpected watch: %+v", res1.Watch)
	}

	// ۳. افزودن نماد با ي عربی: «داريك»
	res2, err := s.Add(ctx, "داريك", "صندوق داریک", "نوت اولیه", "2026-10-02T12:00:00")
	if err != nil {
		t.Fatalf("Add داريك: %v", err)
	}
	if res2.Count != 2 {
		t.Errorf("expected Count=2, got %d", res2.Count)
	}
	if res2.Watch.Norm != "داریک" {
		t.Errorf("expected Norm=داریک, got %s", res2.Watch.Norm)
	}

	// ۴. آپدیت با املا فارسی «داریک»
	res3, err := s.Add(ctx, "داریک", "", "نوت دوم بروزشده", "2026-10-03T12:00:00")
	if err != nil {
		t.Fatalf("Update داریک: %v", err)
	}
	if !res3.Existed {
		t.Errorf("expected Existed=true on upsert")
	}
	if res3.Count != 2 {
		t.Errorf("count should remain 2 after upsert, got %d", res3.Count)
	}
	if res3.Watch.Note != "نوت دوم بروزشده" {
		t.Errorf("expected note updated, got %s", res3.Watch.Note)
	}
	if res3.Watch.Name != "صندوق داریک" {
		t.Errorf("expected name preserved from prior, got %s", res3.Watch.Name)
	}

	// ۵. لیست و سورت added_at DESC
	list, _, err = s.List(ctx)
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(list))
	}
	if list[0].Norm != "داریک" {
		t.Errorf("expected newest first (داریک), got %s", list[0].Norm)
	}

	// ۶. حذف با نوشتار عربی «داريك»
	deleted, err := s.Remove(ctx, "داريك")
	if err != nil {
		t.Fatalf("Remove: %v", err)
	}
	if deleted != 1 {
		t.Errorf("expected deleted=1, got %d", deleted)
	}

	cnt, err := s.Count(ctx)
	if err != nil {
		t.Fatalf("Count: %v", err)
	}
	if cnt != 1 {
		t.Errorf("expected 1 remaining row, got %d", cnt)
	}
}

func TestStoreCapLimit(t *testing.T) {
	ctx := context.Background()
	db, dir := newTestDB(t)

	// نوشتن کانفیگ با watchlist_max = 2
	cfgJSON := `{"watchlist_max": 2}`
	if err := os.WriteFile(filepath.Join(dir, "fts_thresholds.json"), []byte(cfgJSON), 0644); err != nil {
		t.Fatalf("write cfg: %v", err)
	}

	s, err := NewStore(db, dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	if capVal := s.Cap(); capVal != 2 {
		t.Fatalf("expected Cap=2, got %d", capVal)
	}

	// افزودن نماد ۱ و ۲
	if _, err := s.Add(ctx, "فولاد", "", "", ""); err != nil {
		t.Fatalf("Add فولاد: %v", err)
	}
	if _, err := s.Add(ctx, "فملی", "", "", ""); err != nil {
		t.Fatalf("Add فملی: %v", err)
	}

	// نماد ۳ باید با CapError خطا دهد
	_, err = s.Add(ctx, "شستا", "", "", "")
	if err == nil {
		t.Fatalf("expected CapError when exceeding cap=2")
	}
	var capErr *CapError
	if !asCapError(err, &capErr) {
		t.Fatalf("expected *CapError, got %T: %v", err, err)
	}
	if capErr.Cap != 2 {
		t.Errorf("expected cap 2, got %d", capErr.Cap)
	}

	// اما آپدیت یادداشت نماد موجود باید موفق شود حتی اگر سقف پر باشد
	res, err := s.Add(ctx, "فولاد", "", "یادداشت جدید در سقف", "")
	if err != nil {
		t.Fatalf("updating existing symbol at cap should succeed: %v", err)
	}
	if !res.Existed || res.Watch.Note != "یادداشت جدید در سقف" {
		t.Errorf("unexpected update result: %+v", res)
	}
}

func asCapError(err error, target **CapError) bool {
	if ce, ok := err.(*CapError); ok {
		*target = ce
		return true
	}
	return false
}

func TestStoreNegativeValidations(t *testing.T) {
	ctx := context.Background()
	db, dir := newTestDB(t)
	s, err := NewStore(db, dir)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	// نماد خالی
	_, err = s.Add(ctx, "   ", "", "", "")
	if err != ErrEmptySymbol {
		t.Errorf("expected ErrEmptySymbol, got %v", err)
	}

	// نماد فقط نیم‌فاصله
	_, err = s.Add(ctx, "\u200c", "", "", "")
	if err != ErrInvalidSymbol {
		t.Errorf("expected ErrInvalidSymbol, got %v", err)
	}
}
