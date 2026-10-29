package store

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"testing"
)

// TestSQLTextSHA256 پنجرهٔ دائمیِ بایت‌برابری را می‌بندد: هر ثابتِ SQL باید همان
// بایت‌هایِ متنِ پایتون باشد که tools/parity/extract_board_sql.py هشش را در
// sqlTextSHA256 سنجاق کرده است.
func TestSQLTextSHA256(t *testing.T) {
	texts := map[string]string{
		"BoardSQLBase":  BoardSQLBase,
		"HistVSQL":      HistVSQL,
		"HistFvSQL":     HistFvSQL,
		"HistFvSlotSQL": HistFvSlotSQL,
	}
	names := make([]string, 0, len(sqlTextSHA256))
	for name := range sqlTextSHA256 {
		names = append(names, name)
	}
	sort.Strings(names)
	if len(names) != len(texts) {
		t.Errorf("sqlTextSHA256 lists %d constants, want %d", len(names), len(texts))
	}
	for _, name := range names {
		text, ok := texts[name]
		if !ok {
			t.Errorf("sqlTextSHA256 names unknown constant %q", name)
			continue
		}
		sum := sha256.Sum256([]byte(text))
		got := hex.EncodeToString(sum[:])
		want := sqlTextSHA256[name]
		if got != want {
			t.Errorf("SQL text %s: hash mismatch: want %s, got %s (%d bytes)",
				name, want, got, len(text))
		}
	}
}
