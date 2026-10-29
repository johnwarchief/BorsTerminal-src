package db

import (
	"context"
	"database/sql"
	"errors"
	"path/filepath"
	"testing"
)

func makeDB(t *testing.T, name string) string {
	t.Helper()
	dir := t.TempDir()
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
	return dir
}

func TestMarketIsReadOnly(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if _, err := h.Market.Exec("INSERT INTO probe VALUES (2)"); err == nil {
		t.Fatal("write on market.db must fail")
	}
	var n int
	if err := h.Market.QueryRow("SELECT COUNT(*) FROM probe").Scan(&n); err != nil || n != 1 {
		t.Fatalf("read failed: %v n=%d", err, n)
	}
}

func TestUserIsWritable(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if _, err := h.User.Exec("CREATE TABLE w(x INTEGER)"); err != nil {
		t.Fatalf("user.db must be writable: %v", err)
	}
}

func TestMissingMarketDB(t *testing.T) {
	_, err := Open(t.TempDir(), true)
	if !errors.Is(err, ErrMarketMissing) {
		t.Fatalf("err = %v", err)
	}
}

func TestPing(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if err := h.Ping(context.Background()); err != nil {
		t.Fatal(err)
	}
}

func TestCloseIsIdempotent(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	if err := h.Close(); err != nil {
		t.Fatal(err)
	}
	if err := h.Close(); err != nil {
		t.Fatal(err)
	}
}
