package db

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func makeDB(t *testing.T, dir, name string) {
	t.Helper()
	path := filepath.Join(dir, name)
	raw, err := sql.Open("sqlite", dsn(path, "rwc"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := raw.Exec("CREATE TABLE probe(x INTEGER); INSERT INTO probe VALUES (1);"); err != nil {
		t.Fatal(err)
	}
	if err := raw.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestMarketIsAlwaysReadOnlyInOpen(t *testing.T) {
	dir := t.TempDir()
	makeDB(t, dir, "market.db")

	// حتی وقتی readOnly = false باشد، market.db در Open همواره باید ro باشد
	h, err := Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()

	if _, err := h.Market.Exec("INSERT INTO probe VALUES (2)"); err == nil {
		t.Fatal("نوشتن در market.db تحت هر شرایطی در Open باید رد شود")
	} else if !strings.Contains(strings.ToLower(err.Error()), "readonly") {
		t.Fatalf("خطا باید صریحاً حاوی readonly باشد: %v", err)
	}

	var n int
	if err := h.Market.QueryRow("SELECT COUNT(*) FROM probe").Scan(&n); err != nil || n != 1 {
		t.Fatalf("خواندن ناموفق: %v n=%d", err, n)
	}
}

func TestCodalIsAlwaysReadOnlyInOpen(t *testing.T) {
	dir := t.TempDir()
	makeDB(t, dir, "market.db")
	makeDB(t, dir, "codal.db")

	h, err := Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()

	if h.Codal == nil {
		t.Fatal("codal.db باید شناسایی و باز شود")
	}

	if _, err := h.Codal.Exec("INSERT INTO probe VALUES (2)"); err == nil {
		t.Fatal("نوشتن در codal.db باید رد شود")
	} else if !strings.Contains(strings.ToLower(err.Error()), "readonly") {
		t.Fatalf("خطا باید حاوی readonly باشد: %v", err)
	}
}

func TestUserIsWritableWhenNotReadOnly(t *testing.T) {
	dir := t.TempDir()
	makeDB(t, dir, "market.db")

	h, err := Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()

	if _, err := h.User.Exec("CREATE TABLE w(x INTEGER); INSERT INTO w VALUES (42);"); err != nil {
		t.Fatalf("user.db در حالت عادی باید نوشتنی باشد: %v", err)
	}
}

func TestUserIsReadOnlyWhenReadOnlyFlag(t *testing.T) {
	dir := t.TempDir()
	makeDB(t, dir, "market.db")
	makeDB(t, dir, "user.db")

	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()

	if _, err := h.User.Exec("INSERT INTO probe VALUES (2)"); err == nil {
		t.Fatal("user.db در حالت readOnly=true باید فقط‌خواندنی باشد")
	} else if !strings.Contains(strings.ToLower(err.Error()), "readonly") {
		t.Fatalf("خطا باید حاوی readonly باشد: %v", err)
	}
}

func TestMissingUserDBInReadOnlyDoesNotCreateFile(t *testing.T) {
	dir := t.TempDir()
	makeDB(t, dir, "market.db")
	userPath := filepath.Join(dir, "user.db")

	// قبل از فراخوانی، فایل user.db وجود ندارد
	if _, err := os.Stat(userPath); err == nil {
		t.Fatal("فایل user.db نباید در ابتدای تست وجود داشته باشد")
	}

	h, err := Open(dir, true)
	if err != nil {
		t.Fatalf("Open با user.db غایب در حالت read-only باید موفق باشد: %v", err)
	}
	defer h.Close()

	// پس از فراخوانی، نباید فایلی به نام user.db روی دیسک ایجاد شده باشد
	if _, err := os.Stat(userPath); err == nil {
		t.Fatal("تخطی از گیت Zero Disk Writes! فایل user.db روی دیسک ساخته شد")
	}

	// کانکشن User باید کار کند و قابل پینگ باشد
	ctx := context.Background()
	if err := h.Ping(ctx); err != nil {
		t.Fatalf("Ping ناموفق: %v", err)
	}

	// هرگونه نوشتن باید رد شود
	if _, err := h.User.Exec("CREATE TABLE test_mem(x INTEGER)"); err == nil {
		t.Fatal("نوشتن در دیتابیس حافظه‌ای read-only نیز باید رد شود")
	}
}

func TestMissingMarketDB(t *testing.T) {
	_, err := Open(t.TempDir(), true)
	if !errors.Is(err, ErrMarketMissing) {
		t.Fatalf("err = %v, انتظار: ErrMarketMissing", err)
	}
}

func TestWritableFixtureHelper(t *testing.T) {
	dir := t.TempDir()
	makeDB(t, dir, "market.db")

	h, err := OpenWritableForTest(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()

	if _, err := h.Market.Exec("INSERT INTO probe VALUES (99)"); err != nil {
		t.Fatalf("OpenWritableForTest باید اجازه نوشتن در فیکسچر تست را بدهد: %v", err)
	}
}
