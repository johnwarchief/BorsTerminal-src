package datatoken

import (
	"os"
	"path/filepath"
	"testing"
)

// TestFileTokenTracksFiles سنسور را می‌سنجد، نه نتیجه را: توکنِ دایرکتوریِ تهی
// باید پایدار بماند و با نوشتنِ یکی از سه فایل عوض شود؛ وگرنه کشِ mstat
// («داده تازه است») هرگز کلید عوض نمی‌کند یا همیشه عوض می‌کند.
func TestFileTokenTracksFiles(t *testing.T) {
	dir := t.TempDir()
	empty := FileToken(dir)
	if empty != FileToken(dir) {
		t.Fatal("token of an empty dir is not stable")
	}
	if empty != "-|-|-" {
		t.Fatalf("empty dir token = %q", empty)
	}
	if err := os.WriteFile(filepath.Join(dir, "market_sync.json"), []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	one := FileToken(dir)
	if one == empty {
		t.Fatal("writing market_sync.json did not change the token")
	}
	if got := FileToken(dir); got != one {
		t.Fatal("token changed without a file change")
	}
}

// TestFileTokenTracksWAL همان دلیلِ وجودِ فایلِ سوم را قفل می‌کند:
// market.db و market.db-wal هر دو باید در توکن باشند؛ اگر فقط
// market_sync.json کافی بود، کامیتِ tick_live هرگز دیده نمی‌شد.
func TestFileTokenTracksWAL(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"market.db", "market.db-wal"} {
		before := FileToken(dir)
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
		if got := FileToken(dir); got == before {
			t.Fatalf("writing %s did not change the token", name)
		}
	}
}
