package fundamental

// آزمونِ اوراکل (گاردِ چهارگانهٔ bors-architecture، پلنِ B4 §۳): تنها داورِ این
// لایه فایلِ testdata/vectors/series.json است که اوراکلِ پایتون (fts_engine.py)
// ساخته — نه انتظارِ دستیِ من. dedupe_rows شش ورودی/خروجیِ _dedupe_ym و
// denominator هفت ورودی/خروجیِ ytd_denominator را می‌آورد. مقایسه عددها عددی است
// (۶ با ۶٫۰ یکی)، null با nil یکی، و رشته‌ها عیناً. اگر فایلِ vectors خالی/بی‌مورد
// باشد آزمون عمداً می‌شکند تا «سبزِ ساختگی» نشود.

import (
	"encoding/json"
	"math"
	"os"
	"reflect"
	"testing"
)

type seriesVectorFile struct {
	DedupeRows  []seriesDedupeCase `json:"dedupe_rows"`
	Denominator []seriesDenomCase  `json:"denominator"`
}

type seriesDedupeCase struct {
	In  [][]any `json:"in"`
	Out [][]any `json:"out"`
}

// seriesDenomCase: `out` یا شیء است یا null؛ با RawMessage جدا می‌فهمیم کدام،
// چون یک نقشهٔ nil درِ encoding/json برایِ هر دو «نبود» است.
type seriesDenomCase struct {
	In  [][]any         `json:"in"`
	Out json.RawMessage `json:"out"`
}

func seriesLoadVectors(t *testing.T) seriesVectorFile {
	t.Helper()
	b, err := os.ReadFile("testdata/vectors/series.json")
	if err != nil {
		t.Fatalf("خواندنِ vectors: %v", err)
	}
	var dc seriesVectorFile
	if err := json.Unmarshal(b, &dc); err != nil {
		t.Fatalf("تجزیهٔ vectors: %v", err)
	}
	if len(dc.DedupeRows) == 0 || len(dc.Denominator) == 0 {
		t.Fatalf("فایلِ vectors خالی است: dedupe=%d denom=%d", len(dc.DedupeRows), len(dc.Denominator))
	}
	return dc
}

// seriesNum مثلِ مقایسهٔ عددیِ اوراکل: هر مقداری که عدد است به float64 می‌رسد
// (JSON همه را float64 می‌دهد، توابعِ من year/month را int64).
func seriesNum(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case int64:
		return float64(x), true
	case int:
		return float64(x), true
	}
	return 0, false
}

// seriesValuesEqual دو مقدارِ ردیف/فیلد را مثلِ اوراکل مقایسه می‌کند: nil↔nil،
// عدد↔عدد (حتی ۶ با ۶٫۰)، وگرنه عینِ DeepEqualِ رشته/ترکیب.
func seriesValuesEqual(a, b any) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	af, aok := seriesNum(a)
	bf, bok := seriesNum(b)
	if aok && bok {
		return math.Abs(af-bf) < 1e-9
	}
	if aok != bok {
		return false
	}
	return reflect.DeepEqual(a, b)
}

func seriesRowEqual(a, b []any) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if !seriesValuesEqual(a[i], b[i]) {
			return false
		}
	}
	return true
}

func TestSeriesDedupeYmMatchesOracle(t *testing.T) {
	dc := seriesLoadVectors(t)
	for i, c := range dc.DedupeRows {
		got := SeriesDedupeYm(c.In, 3)
		if len(got) != len(c.Out) {
			t.Fatalf("dedupe case %d: طولِ خروجی %d ≠ %d", i, len(got), len(c.Out))
		}
		for j := range got {
			if !seriesRowEqual(got[j], c.Out[j]) {
				t.Fatalf("dedupe case %d ردیف %d:\n got=%v\n exp=%v", i, j, got[j], c.Out[j])
			}
		}
	}
}

func TestSeriesYtdDenominatorMatchesOracle(t *testing.T) {
	dc := seriesLoadVectors(t)
	for i, c := range dc.Denominator {
		got := SeriesYtdDenominator(c.In)
		wantNil := len(c.Out) == 0 || string(c.Out) == "null"
		if wantNil {
			if got != nil {
				t.Fatalf("denom case %d: انتظارِ nil، دریافت=%v", i, got)
			}
			continue
		}
		var exp map[string]any
		if err := json.Unmarshal(c.Out, &exp); err != nil {
			t.Fatalf("denom case %d: تجزیهٔ out: %v", i, err)
		}
		if got == nil {
			t.Fatalf("denom case %d: انتظارِ نقشه، دریافتِ nil", i)
		}
		if len(got) != len(exp) {
			t.Fatalf("denom case %d: تعدادِ کلیدها %d ≠ %d", i, len(got), len(exp))
		}
		for k, ev := range exp {
			gv, ok := got[k]
			if !ok {
				t.Fatalf("denom case %d: کلیدِ %q غایب درِ خروجی", i, k)
			}
			if !seriesValuesEqual(gv, ev) {
				t.Fatalf("denom case %d کلید %q:\n got=%v\n exp=%v", i, k, gv, ev)
			}
		}
	}
}
