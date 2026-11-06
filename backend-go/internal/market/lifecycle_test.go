package market

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"io/fs"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/db"
)

type fileSnapshot struct {
	size int64
	hash string
}

func takeTreeSnapshot(t *testing.T, dir string) map[string]fileSnapshot {
	t.Helper()
	snap := make(map[string]fileSnapshot)
	err := filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(dir, path)
		if err != nil {
			return err
		}
		rel = filepath.ToSlash(rel)

		info, err := d.Info()
		if err != nil {
			return err
		}

		f, err := os.Open(path)
		if err != nil {
			return err
		}
		defer f.Close()

		h := sha256.New()
		if _, err := io.Copy(h, f); err != nil {
			return err
		}

		snap[rel] = fileSnapshot{
			size: info.Size(),
			hash: hex.EncodeToString(h.Sum(nil)),
		}
		return nil
	})
	if err != nil {
		t.Fatalf("takeTreeSnapshot failed: %v", err)
	}
	return snap
}

// TestReadOnlyZeroDiskWrites آزمون تجربی و اثبات دقیق Zero Disk Writes است:
// ۱. دیتابیس غایب: user.db روی دیسک نیست و به هیچ وجه نباید فایل خالی یا نو ساخته شود.
// ۲. فایلهای SQLite: فایلهای -wal و -shm نباید ایجاد یا دستکاری شوند.
// ۳. هش محتوا و اندازه: محتوای market.db دقیقاً صفر بایت تغییر می‌کند.
// ۴. هیچ فایل لاگ، کش یا متنی نباید روی دیسک نوشته شود.
func TestReadOnlyZeroDiskWrites(t *testing.T) {
	srcFixture, _ := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture", "market.db"))
	tempDir := t.TempDir()

	rawMarket, err := os.ReadFile(srcFixture)
	if err != nil {
		t.Fatalf("خواندن فیکسچر market.db: %v", err)
	}

	targetMarket := filepath.Join(tempDir, "market.db")
	if err := os.WriteFile(targetMarket, rawMarket, 0o644); err != nil {
		t.Fatalf("نوشتن market.db در دایرکتوری موقت: %v", err)
	}

	// پیش‌شرط: user.db نباید در دایرکتوری وجود داشته باشد
	userDBPath := filepath.Join(tempDir, "user.db")
	if _, err := os.Stat(userDBPath); err == nil {
		t.Fatal("user.db نباید در آغاز تست وجود داشته باشد")
	}

	// ثبت عکس لحظه‌ای کامل از دایرکتوری قبل از اجرای سرویس
	snapBefore := takeTreeSnapshot(t, tempDir)

	// راه‌اندازی سرور و سرویس در حالت read-only و no-loops
	handles, err := db.Open(tempDir, true)
	if err != nil {
		t.Fatalf("db.Open با readOnly=true باید موفق باشد: %v", err)
	}

	s := NewWithOptions(handles, tempDir, true, true)

	// اجرای عملیات مختلف تابلو و درخواست‌ها
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/market", nil)
	s.Board(rec, req)

	// بازسازی تابلو و کش حافظه‌ای
	if _, _, err := s.build(true, true); err != nil {
		t.Fatalf("s.build در حالت read-only نباید با خطا مواجه شود: %v", err)
	}

	deltaRec := httptest.NewRecorder()
	deltaReq := httptest.NewRequest("GET", "/api/market/delta?since=0", nil)
	s.Delta(deltaRec, deltaReq)

	// بستن اتصال‌ها
	if err := handles.Close(); err != nil {
		t.Fatalf("handles.Close: %v", err)
	}

	// ثبت عکس لحظه‌ای کامل از دایرکتوری پس از توقف سرویس
	snapAfter := takeTreeSnapshot(t, tempDir)

	// ۱. بررسی عدم ایجاد فایل‌های جدید
	for path := range snapAfter {
		if _, existed := snapBefore[path]; !existed {
			t.Errorf("تخطی از گیت Zero Disk Writes! فایل غیرمجاز روی دیسک ایجاد شد: %s", path)
		}
	}

	// ۲. بررسی عدم ساخت user.db
	if _, err := os.Stat(userDBPath); err == nil {
		t.Errorf("تخطی! user.db در حالت read-only روی دیسک ساخته شد")
	}

	// ۳. بررسی عدم ساخت فایلهای -wal و -shm
	for _, ext := range []string{"market.db-wal", "market.db-shm", "user.db-wal", "user.db-shm"} {
		if _, err := os.Stat(filepath.Join(tempDir, ext)); err == nil {
			t.Errorf("تخطی! فایل ژورنال موقت %s روی دیسک ایجاد شد", ext)
		}
	}

	// ۴. بررسی عدم تغییر حتی یک بایت در فایلهای موجود
	for path, before := range snapBefore {
		after, exists := snapAfter[path]
		if !exists {
			t.Errorf("فایل %s پس از تست حذف شد!", path)
			continue
		}
		if before.size != after.size {
			t.Errorf("اندازه فایل %s تغییر کرد! قبل: %d, بعد: %d", path, before.size, after.size)
		}
		if before.hash != after.hash {
			t.Errorf("محتوای فایل %s تغییر کرد! هش قبل: %s, هش بعد: %s", path, before.hash, after.hash)
		}
	}
}

// TestNoLoopsSuppressesAsyncWork اثبات می‌کند که با فعال بودن --no-loops
// متد rebuildAsync کاملاً بی‌اثر بوده و هیچ Goroutine یا کار پس‌زمینه‌ای آغاز نمی‌شود.
func TestNoLoopsSuppressesAsyncWork(t *testing.T) {
	srcFixture, _ := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture", "market.db"))
	tempDir := t.TempDir()

	rawMarket, err := os.ReadFile(srcFixture)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(tempDir, "market.db"), rawMarket, 0o644); err != nil {
		t.Fatal(err)
	}

	handles, err := db.Open(tempDir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer handles.Close()

	// ایجاد با noLoops = true
	s := NewWithOptions(handles, tempDir, true, true)

	// فراخوانی مکرر rebuildAsync
	for i := 0; i < 5; i++ {
		s.rebuildAsync()
	}

	// وضعیت building باید کاملاً false بماند
	s.mu.Lock()
	isBuilding := s.building
	s.mu.Unlock()

	if isBuilding {
		t.Fatal("با noLoops=true، فلگ building نباید true شود")
	}

	time.Sleep(50 * time.Millisecond)

	s.mu.Lock()
	isBuildingAfter := s.building
	s.mu.Unlock()

	if isBuildingAfter {
		t.Fatal("هیچ کار پس‌زمینه‌ای نباید با noLoops=true فعال شود")
	}
}
