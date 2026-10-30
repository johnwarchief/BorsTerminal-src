package market

import (
	"encoding/json"
	"math"
	"testing"
)

// TestMarshalBoardMatchesEncodingJSON قراردادِ boardEncoder را می‌سنجد: خروجی
// باید *بایت‌به‌بایت* همان json.Marshal باشد، نه فقط JSONِ معتبر. اگر روزی
// کلیدی گم شود یا گریز/قالبِ عدد عوض شود، etag و اندازه و خریدارِ بدنه هم
// عوض می‌شوند و این تست باید قرمز شود، نه اینکه سکوت کند.
func TestMarshalBoardMatchesEncodingJSON(t *testing.T) {
	payload := map[string]any{
		"status": "success", "rev": int64(7), "count": 2,
		"live_count": int64(1), "fossil_count": int64(1),
		"meta": map[string]any{"d_even": int64(20261014), "h_even": nil, "last_sync": "1405/07/20"},
		"data": []map[string]any{
			{
				"ins_code": "IRO1FOLD0001", "symbol": "فولاد", "board": int64(1),
				"buyer_power": 1.49, "ratio": 1.0, "tiny": 1e-7, "edge": 1e-6,
				"huge": 1e21, "big": 1e20, "negzero": math.Copysign(0, -1),
				"pct": 12.25, "is_live": true, "note": "a\"b\\c<d>&e\nf",
				"zwnj": "نیم\u200cفاصله", "ls": "\u2028",
				"plain": "سلام", "empty": "",
			},
			{
				"ins_code": "IRO1FOLD0002", "symbol": "", "null_col": nil,
				"flags": []any{"a", int64(2), 3.5, true, nil},
			},
		},
	}
	want, err := json.Marshal(payload)
	if err != nil {
		t.Fatal(err)
	}
	got, err := marshalBoard(payload)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(want) {
		t.Fatalf("encoder drifted from encoding/json:\n got=%s\nwant=%s", got, want)
	}
}

// TestMarshalBoardRejectsNonFinite مثلِ encoding/json است: NaN/Inf بدنه را
// نمی‌سازد؛ نمی‌شود null نوشت و «موفق» گفت.
func TestMarshalBoardRejectsNonFinite(t *testing.T) {
	for _, v := range []float64{math.NaN(), math.Inf(1), math.Inf(-1)} {
		if _, err := marshalBoard(map[string]any{"x": v}); err == nil {
			t.Fatalf("%v: expected an error", v)
		}
	}
}

// TestFastStringOK هم مسیرِ سریع و هم مسیرِ بازگشتی را می‌سنجد: هر رشته‌ای که
// این‌جا false بگیرد از json.Marshal رد می‌شود و همان بایت‌ها را می‌دهد.
func TestFastStringOK(t *testing.T) {
	cases := []struct {
		s    string
		want bool
	}{
		{"فولاد", true},
		{"نیم\u200cفاصله", true},
		{"", true},
		{"a<b", false},
		{"a&b", false},
		{"a\"b", false},
		{"a\\b", false},
		{"a\nb", false},
		{"\u2028", false},
		{"\xff", false},
	}
	for _, c := range cases {
		if got := fastStringOK(c.s); got != c.want {
			t.Fatalf("fastStringOK(%q)=%v want %v", c.s, got, c.want)
		}
	}
}
