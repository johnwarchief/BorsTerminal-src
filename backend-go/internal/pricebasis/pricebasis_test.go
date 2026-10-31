package pricebasis

import (
	"os"
	"path/filepath"
	"testing"
)

func candle(open, high, low, close float64, last any) map[string]any {
	return map[string]any{"time": "2026-10-27", "open": open, "high": high,
		"low": low, "close": close, "last": last}
}

func TestCurrentReadsSettingFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "price_basis.json")
	r := New(path)
	if got := r.Current(); got != Last {
		t.Fatalf("missing file: %q", got)
	}
	os.WriteFile(path, []byte(`{"basis":"closing"}`), 0o600)
	if got := r.Current(); got != Closing {
		t.Fatalf("closing: %q", got)
	}
	os.WriteFile(path, []byte(`{"basis":"bogus"}`), 0o600)
	if got := r.Current(); got != Default {
		t.Fatalf("bogus must fall back: %q", got)
	}
	os.WriteFile(path, []byte(`"closing"`), 0o600)
	if got := r.Current(); got != Closing {
		t.Fatalf("bare string: %q", got)
	}
	os.WriteFile(path, []byte(`{broken`), 0o600)
	if got := r.Current(); got != Default {
		t.Fatalf("broken json must not panic: %q", got)
	}
}

func TestApplyBasisLastMissingFallsBackToClosing(t *testing.T) {
	cands := []map[string]any{
		candle(100, 110, 90, 105, 106.0),
		candle(105, 115, 95, 108, nil),
		candle(1200, 1100, 1000, 1150, 1140.0),
	}
	meta, out := ApplyBasis(cands, true, Last)
	if meta.BasisApplied != Closing || meta.BasisReason != "last_missing:1/3" ||
		meta.LastMissing != 1 || meta.Count != 3 {
		t.Fatalf("meta=%+v", meta)
	}
	if out[0]["close"] != 105.0 || out[1]["close"] != 108.0 || out[2]["close"] != 1150.0 {
		t.Fatalf("close must be closing: %v %v %v", out[0]["close"], out[1]["close"], out[2]["close"])
	}
	if out[0]["basis"] != Closing {
		t.Fatalf("basis tag=%v", out[0]["basis"])
	}
}

func TestApplyBasisLastAppliedAndGeometry(t *testing.T) {
	cands := []map[string]any{
		candle(100, 110, 90, 105, 106.0),
		candle(1200, 1100, 1000, 1150, 1140.0),
	}
	meta, out := ApplyBasis(cands, true, Last)
	if meta.BasisApplied != Last || meta.BasisReason != "" {
		t.Fatalf("meta=%+v", meta)
	}
	if out[0]["close"] != 106.0 || out[1]["close"] != 1140.0 {
		t.Fatalf("close must be last: %v %v", out[0]["close"], out[1]["close"])
	}
	if out[1]["high"] != 1200.0 || out[1]["low"] != 1000.0 {
		t.Fatalf("geometry must widen to the body (open included): %v %v", out[1]["high"], out[1]["low"])
	}
	if meta.GeometryWidened != 1 {
		t.Fatalf("widened=%d", meta.GeometryWidened)
	}
	// idempotence: another pass with closing must recompute from the raw shadow.
	meta2, out2 := ApplyBasis(out, false, Closing)
	if meta2.BasisApplied != Closing || out2[1]["close"] != 1150.0 ||
		out2[1]["high"] != 1200.0 || out2[1]["low"] != 1000.0 {
		t.Fatalf("second pass: meta=%+v candle=%v", meta2, out2[1])
	}
	if meta2.GeometryWidened != 1 {
		t.Fatalf("second pass must not re-widen from a widened shadow: %d", meta2.GeometryWidened)
	}
	// originals stay untouched when copy=true
	if cands[1]["high"] != 1100.0 || cands[1]["close"] != 1150.0 {
		t.Fatalf("copy=true mutated the source: %v", cands[1])
	}
}

func TestResolvePayloadColorsAndStamp(t *testing.T) {
	cands := []map[string]any{
		candle(100, 110, 90, 105, 106.0),
		map[string]any{"time": "2026-10-28", "open": 110.0, "high": 112.0,
			"low": 107.0, "close": 108.0, "last": 108.0},
	}
	vols := []map[string]any{
		{"time": "2026-10-27", "value": 1.0, "color": "x"},
		{"time": "2026-10-28", "value": 2.0, "color": "x"},
	}
	res := map[string]any{"status": "success", "candles": cands, "volumes": vols}
	out := ResolvePayload(res, "candles", [2]string{"#10b981", "#f43f5e"}, Closing)
	gotVols := out["volumes"].([]map[string]any)
	if gotVols[0]["color"] != "#10b981" || gotVols[1]["color"] != "#f43f5e" {
		t.Fatalf("colors=%v", gotVols)
	}
	if out["priceBasis"] != Closing || out["priceBasisRequested"] != Closing ||
		out["priceBasisLastMissing"] != 0 {
		t.Fatalf("stamp=%v", out)
	}
	if _, ok := out["priceBasisReason"]; ok {
		t.Fatal("no reason must be emitted when none exists")
	}
	// empty series is returned untouched (no stamp), like the Python early return
	if got := ResolvePayload(map[string]any{"status": "success"}, "candles",
		[2]string{"a", "b"}, Closing); len(got) != 1 {
		t.Fatalf("empty series must not be stamped: %v", got)
	}
}
