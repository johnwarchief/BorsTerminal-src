package mstat

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/parity"
)

func loadGolden(t *testing.T, scenario, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", scenario, name+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

// compareGolden تطبیقِ کاملِ بدنه با canonِ B1؛ استثناها فقط قراردادِ همین
// پنل‌اند (ساعتِ دیواری) و در فهرست صریح آمده‌اند.
//
// بدنهٔ Go پیش از مقایسه از درِ JSON می‌گذرد: canon فقط []any/map[string]any
// را می‌شناسد، ولی پنل‌ها ساختارِ تایپ‌دار می‌سازند ([]map[string]any،
// map[string]bool) و لایهٔ HTTP هم همان را به JSON می‌نویسد. normalize اینجا
// یعنی مقایسه همان چیزی است که کلاینت می‌بیند، نه شکلِ داخلیِ structها.
func compareGolden(t *testing.T, name string, want, got map[string]any, exclude ...string) {
	t.Helper()
	raw, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("%s: marshal body: %v", name, err)
	}
	var norm map[string]any
	if err := json.Unmarshal(raw, &norm); err != nil {
		t.Fatalf("%s: unmarshal body: %v", name, err)
	}
	res := parity.Compare(want, norm, parity.Options{Exclude: exclude})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", name, d)
		}
		t.Fatalf("%s: %d diffs", name, len(res.Diffs))
	}
}

var pinnedNow = time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local)

func TestIndustriesMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "industries", loadGolden(t, "s1", "industries"), got)
}

// TestIndustriesTrimsSectorName: پایتون `(r.get("sector_name") or "").strip()`
// می‌خواند. فاصلهٔ معمولی و NBSP در دو سرِ نام باید همان صنعتِ طلایی بدهد، نه
// صنعتی تازه با نامِ «آلوده» — وگرنه گروه‌بندی و لیدر جابه‌جا می‌شود.
func TestIndustriesTrimsSectorName(t *testing.T) {
	h := openWritableFixture(t)
	for _, c := range []struct{ code, sector string }{
		{"m1", " فلزات اساسي "},
		{"m2", "بانكها و موسسات اعتباري\u00a0"},
	} {
		if _, err := h.Market.Exec(
			"UPDATE instruments SET sector_name = ? WHERE ins_code = ?", c.sector, c.code); err != nil {
			t.Fatal(err)
		}
	}
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "industries-trim", loadGolden(t, "s1", "industries"), got)
	for _, x := range got["rows"].([]map[string]any) {
		name := x["industry"].(string)
		if strings.TrimSpace(name) != name {
			t.Fatalf("industry %q kept surrounding whitespace", name)
		}
	}
}
