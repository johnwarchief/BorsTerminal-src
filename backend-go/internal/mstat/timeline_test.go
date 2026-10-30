package mstat

import (
	"bytes"
	"compress/zlib"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"reflect"
	"testing"
)

const (
	noteNeedsTwo = "برای تایم‌لاین دست‌کم به دو همگام‌سازی در یک نشست نیاز است"
	noteStale    = "این تایم‌لاین به نشستی غیر از آخرین نشستِ تابلو برمی‌گردد — وضعیتِ امروز نیست"
)

// zlibBlob همان کاری را می‌کند که snapshot_agg در پایتون: JSON → zlib → base64.
func zlibBlob(t *testing.T, body []byte) string {
	t.Helper()
	var buf bytes.Buffer
	zw := zlib.NewWriter(&buf)
	if _, err := zw.Write(body); err != nil {
		t.Fatal(err)
	}
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	return base64.StdEncoding.EncodeToString(buf.Bytes())
}

// stateBlob نگاشتِ ins_code→حرفِ وضعیت را به همان blobِ نقطه می‌بندد.
func stateBlob(t *testing.T, states map[string]string) string {
	t.Helper()
	raw, err := json.Marshal(states)
	if err != nil {
		t.Fatal(err)
	}
	return zlibBlob(t, raw)
}

// insertSnapJSON یک نقطهٔ خام را در کپیِ موقت می‌نشاند؛ فایلِ ردیابی‌شده هرگز
// نوشتنی نمی‌شود (همان الگویِ openWritableFixture).
func insertSnapJSON(t *testing.T, conn *sql.DB, day, hEven int64, aggJSON string) {
	t.Helper()
	if _, err := conn.Exec(
		"INSERT OR REPLACE INTO mstat_snap (d_even, h_even, ts, agg) VALUES (?,?,?,?)",
		day, hEven, "2026-10-28 10:00:00", aggJSON); err != nil {
		t.Fatal(err)
	}
}

func insertSnap(t *testing.T, conn *sql.DB, day, hEven int64, agg map[string]any) {
	t.Helper()
	raw, err := json.Marshal(agg)
	if err != nil {
		t.Fatal(err)
	}
	insertSnapJSON(t, conn, day, hEven, string(raw))
}

func clearSnaps(t *testing.T, conn *sql.DB) {
	t.Helper()
	if _, err := conn.Exec("DELETE FROM mstat_snap"); err != nil {
		t.Fatal(err)
	}
}

// shiftSnaps همان جهشِ صحنهٔ ۲ در tools/parity/gen_mstat_golden.py:227-229 است:
// هر نقطه یک روز عقب، هم در ستون و هم داخلِ agg — چون _points روزِ داخلِ agg را
// ترجیح می‌دهد، جابه‌جا کردنِ فقط ستون «کهنه» نمی‌سازد.
func shiftSnaps(t *testing.T, conn *sql.DB) {
	t.Helper()
	if _, err := conn.Exec("UPDATE mstat_snap SET d_even = d_even - 1," +
		" agg = json_set(agg, '$.d_even', d_even - 1)"); err != nil {
		t.Fatal(err)
	}
}

func seriesOf(t *testing.T, body map[string]any, key string) []any {
	t.Helper()
	ser, ok := body["series"].(map[string]any)
	if !ok {
		t.Fatalf("series is %T, want map[string]any", body["series"])
	}
	vals, ok := ser[key].([]any)
	if !ok {
		t.Fatalf("series[%s] is %T, want []any", key, ser[key])
	}
	return vals
}

func TestTimelineGoldens(t *testing.T) {
	h := openFixture(t)
	for _, mode := range []string{"cum", "inst"} {
		got, err := timelinePanel(h.Market, mode)
		if err != nil {
			t.Fatal(err)
		}
		compareGolden(t, "timeline_"+mode, loadGolden(t, "s1", "timeline_"+mode), got)
	}

	// صحنهٔ ۲ رویِ کپیِ نوشتنی ساخته می‌شود؛ فیکسچرِ s1 هرگز به‌جای s2 مقایسه نمی‌شود.
	old := openWritableFixture(t)
	shiftSnaps(t, old.Market)
	got, err := timelinePanel(old.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "s2 timeline", loadGolden(t, "s2", "timeline_cum"), got)
}

func TestPhasesGoldens(t *testing.T) {
	h := openFixture(t)
	got, err := phasesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "s1 phases", loadGolden(t, "s1", "phases"), got)

	old := openWritableFixture(t)
	shiftSnaps(t, old.Market)
	got, err = phasesPanel(old.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "s2 phases", loadGolden(t, "s2", "phases"), got)
}

// TestDecodeStates: blobِ ساختِ Go باید برگردد و هر ورودیِ خراب/غیرِشیء باید
// نگاشتِ تهی بدهد، نه panic.
func TestDecodeStates(t *testing.T) {
	round := decodeStates(stateBlob(t, map[string]string{"m1": "b", "m2": "s"}))
	if len(round) != 2 || round["m1"] != "b" || round["m2"] != "s" {
		t.Fatalf("round-trip = %#v", round)
	}

	cases := []struct{ name, blob string }{
		{"empty", ""},
		{"invalid base64", "%%%not-base64%%%"},
		{"base64 of raw bytes", base64.StdEncoding.EncodeToString([]byte("not zlib at all"))},
		{"zlib of empty body", zlibBlob(t, nil)},
		{"zlib of JSON array", zlibBlob(t, []byte(`["b","s"]`))},
		{"zlib of JSON null", zlibBlob(t, []byte(`null`))},
	}
	for _, c := range cases {
		got := decodeStates(c.blob)
		if got == nil {
			t.Errorf("%s: nil map, want empty map", c.name)
			continue
		}
		if len(got) != 0 {
			t.Errorf("%s: %#v, want empty map", c.name, got)
		}
	}

	// خواندنِ دوباره نباید نقشهٔ مشترک بدهد؛ هر فراخوانی مستقل است.
	a := decodeStates(stateBlob(t, map[string]string{"m1": "b"}))
	a["m1"] = "s"
	if b := decodeStates(stateBlob(t, map[string]string{"m1": "b"})); b["m1"] != "b" {
		t.Fatalf("decodeStates returns aliased map: %#v", b)
	}
}

// TestPointsWindowOrderHEven: پنجرهٔ رسمی ۰۸:۵۵–۱۳:۰۰، ترتیب بر ستونِ h_even،
// و h_evenِ غایب از agg با ستون پر می‌شود (setdefaultِ پایتون).
func TestPointsWindowOrderHEven(t *testing.T) {
	h := openWritableFixture(t)
	insertSnap(t, h.Market, 20261014, 70000, map[string]any{"val_bt": 1.0})
	insertSnap(t, h.Market, 20261014, 140000, map[string]any{"val_bt": 2.0})
	insertSnap(t, h.Market, 20261014, 90000, map[string]any{"val_bt": 3.0})
	insertSnap(t, h.Market, 20261014, 95000, map[string]any{"val_bt": 3.5, "h_even": 95555})
	insertSnap(t, h.Market, 20261014, 125000, map[string]any{"val_bt": 4.0})

	pts, err := points(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	want := []float64{90000, 95555, 100000, 110000, 120000, 125000}
	if len(pts) != len(want) {
		t.Fatalf("points = %d, want %d", len(pts), len(want))
	}
	for i, w := range want {
		if got := toF(pts[i]["h_even"]); got != w {
			t.Errorf("point %d h_even = %v, want %v", i, got, w)
		}
	}
	// ردیفی که agg‌اش h_even ندارد مقدار را از ستون می‌گیرد (int64، نه صفر).
	if got, ok := pts[0]["h_even"].(int64); !ok || got != 90000 {
		t.Errorf("default h_even = %#v, want int64(90000)", pts[0]["h_even"])
	}
	// اگر agg خودش h_even دارد، همان می‌ماند (ستون ۹۵۰۰۰ ولی مقدار ۹۵۵۵۵).
	if got, ok := pts[1]["h_even"].(float64); !ok || got != 95555 {
		t.Errorf("json h_even = %#v, want float64(95555)", pts[1]["h_even"])
	}
}

// TestTimelineInstVectors: inst تفاوتِ نقطه‌هایِ متوالی است، نقطهٔ نخست خودش
// «جمعِ تا آن لحظه» می‌ماند، و null در میانه prev را جلو نمی‌برد.
func TestTimelineInstVectors(t *testing.T) {
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	insertSnap(t, h.Market, 20261014, 100000,
		map[string]any{"d_even": 20261014, "val_bt": 10.0, "pc_sell": 5.0})
	insertSnap(t, h.Market, 20261014, 110000,
		map[string]any{"d_even": 20261014, "val_bt": 20.0, "pc_buy": 7.0})
	insertSnap(t, h.Market, 20261014, 120000,
		map[string]any{"d_even": 20261014, "val_bt": 30.0, "pc_buy": 9.0, "pc_sell": 9.0})

	cum, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	inst, err := timelinePanel(h.Market, "inst")
	if err != nil {
		t.Fatal(err)
	}

	wantCum := map[string][]any{
		"val_bt":  {10.0, 20.0, 30.0},
		"pc_sell": {5.0, nil, 9.0},
		"pc_buy":  {nil, 7.0, 9.0},
	}
	for k, want := range wantCum {
		if got := seriesOf(t, cum, k); !reflect.DeepEqual(got, want) {
			t.Errorf("cum[%s] = %#v, want %#v", k, got, want)
		}
	}
	wantInst := map[string][]any{
		"val_bt":  {10.0, 10.0, 10.0},
		"pc_sell": {5.0, nil, 4.0},
		"pc_buy":  {nil, nil, 2.0},
	}
	for k, want := range wantInst {
		if got := seriesOf(t, inst, k); !reflect.DeepEqual(got, want) {
			t.Errorf("inst[%s] = %#v, want %#v", k, got, want)
		}
	}
	// نخستین نقطهٔ هر سری در هر دو خوانش یکی است.
	for _, k := range seriesKeys {
		c, i := seriesOf(t, cum, k), seriesOf(t, inst, k)
		if len(c) != len(i) {
			t.Fatalf("%s: cum len %d, inst len %d", k, len(c), len(i))
		}
		if !reflect.DeepEqual(i[0], c[0]) {
			t.Errorf("%s: inst[0] = %#v, want cum[0] %#v", k, i[0], c[0])
		}
	}

	// modeِ ناشناس همان cum است (نه inst، نه خطا).
	weird, err := timelinePanel(h.Market, "weird")
	if err != nil {
		t.Fatal(err)
	}
	if weird["mode"] != "cum" {
		t.Errorf("mode = %#v, want cum", weird["mode"])
	}
	if got := seriesOf(t, weird, "val_bt"); !reflect.DeepEqual(got, []any{10.0, 20.0, 30.0}) {
		t.Errorf("weird series = %#v, want cum series", got)
	}
}

// TestTimelineReadyAndNote: با کمتر از دو نقطه ready=false و یادداشتِ ساختِ
// تایم‌لاین می‌آید؛ سری هم به طولِ همان نقطه‌های موجود می‌ماند.
func TestTimelineReadyAndNote(t *testing.T) {
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	insertSnap(t, h.Market, 20261014, 100000, map[string]any{"d_even": 20261014, "val_bt": 10.0})

	one, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	if one["ready"] != false || one["points"] != 1 {
		t.Errorf("one point: ready=%v points=%v", one["ready"], one["points"])
	}
	if one["note"] != noteNeedsTwo {
		t.Errorf("one point note = %#v", one["note"])
	}
	if one["stale"] != false {
		t.Errorf("one point stale = %v", one["stale"])
	}
	for _, k := range seriesKeys {
		if got := seriesOf(t, one, k); len(got) != 1 {
			t.Errorf("one point series[%s] len = %d, want 1", k, len(got))
		}
	}
	if ts := one["series"].(map[string]any)["t"].([]string); len(ts) != 1 || ts[0] != "10:00" {
		t.Errorf("one point t = %#v", one["series"].(map[string]any)["t"])
	}

	clearSnaps(t, h.Market)
	zero, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	if zero["ready"] != false || zero["points"] != 0 || zero["day"] != nil {
		t.Errorf("zero points: ready=%v points=%v day=%#v", zero["ready"], zero["points"], zero["day"])
	}
	if zero["note"] != noteNeedsTwo {
		t.Errorf("zero points note = %#v", zero["note"])
	}
	for _, k := range seriesKeys {
		if got := seriesOf(t, zero, k); len(got) != 0 {
			t.Errorf("zero points series[%s] len = %d, want 0", k, len(got))
		}
	}
}

// TestTimelineStaleNote: روزِ نقطه‌ها با آخرین روزِ تابلو یکی نیست ⇒ stale=true
// و یادداشتِ «وضعیتِ امروز نیست» — حتی وقتی ready=true است.
func TestTimelineStaleNote(t *testing.T) {
	h := openWritableFixture(t)
	shiftSnaps(t, h.Market)
	got, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	if got["stale"] != true {
		t.Errorf("stale = %v, want true", got["stale"])
	}
	if got["note"] != noteStale {
		t.Errorf("note = %#v", got["note"])
	}
	if toF(got["day"]) != 20261013 || toF(got["board_day"]) != 20261014 {
		t.Errorf("day/board_day = %v/%v, want 20261013/20261014", got["day"], got["board_day"])
	}
	if got["ready"] != true {
		t.Errorf("ready = %v, want true", got["ready"])
	}
}

// TestPhasesCounts: فقط جفت‌هایِ ثبت‌شده شمرده می‌شوند، نمادِ غایب در نقطهٔ
// پیشین نه، و blobِ تهی/خراب در هر دو سویِ جفت آن جفت را کامل رد می‌کند.
func TestPhasesCounts(t *testing.T) {
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	put := func(hm int64, blob string) {
		insertSnap(t, h.Market, 20261014, hm, map[string]any{"d_even": 20261014, "st": blob})
	}
	put(100000, stateBlob(t, map[string]string{"m1": "b", "m2": "s", "m3": "p", "m6": "b"}))
	// m4 و m9 در نقطهٔ پیشین نبوده‌اند؛ m3 جفتِ ثبت‌نشدهٔ p>n می‌سازد.
	put(101000, stateBlob(t, map[string]string{"m1": "s", "m2": "b", "m3": "n", "m4": "b", "m6": "s", "m9": "s"}))
	put(102000, "")                                                    // تهی: جفتِ ۲→۳ رد می‌شود
	put(103000, base64.StdEncoding.EncodeToString([]byte("not zlib"))) // خراب: ۳→۴ رد
	put(104000, stateBlob(t, map[string]string{"m1": "b", "m9": "s"})) // ۴→۵ رد (پیشین خراب)
	put(105000, stateBlob(t, map[string]string{"m1": "s", "m9": "p"}))

	got, err := phasesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if got["points"] != 6 || got["ready"] != true {
		t.Errorf("points=%v ready=%v", got["points"], got["ready"])
	}
	want := map[string]int{"b>s": 3, "p>s": 0, "b>n": 0, "s>b": 1, "n>b": 0, "s>p": 1}
	labels := map[string]string{}
	for _, tr := range transitions {
		labels[tr.From+">"+tr.To] = tr.Label
	}
	seen := 0
	for _, col := range []string{"red", "green"} {
		items, ok := got[col].([]map[string]any)
		if !ok {
			t.Fatalf("%s is %T", col, got[col])
		}
		for _, it := range items {
			key, _ := it["key"].(string)
			w, ok := want[key]
			if !ok {
				t.Fatalf("%s: unexpected key %q", col, key)
			}
			if it["count"] != w {
				t.Errorf("%s count = %v, want %d", key, it["count"], w)
			}
			if it["label"] != labels[key] {
				t.Errorf("%s label = %#v, want %#v", key, it["label"], labels[key])
			}
			seen++
		}
	}
	if seen != len(want) {
		t.Errorf("emitted %d transition keys, want %d", seen, len(want))
	}
}

// TestPointsQueryError: خطایِ واقعیِ پرس‌وجو (DBِ بسته) نباید «بدونِ داده» شود؛
// فقط جدولِ تهیِ سالم مسیرِ ok-تهی است. کنترل: خفه کردنِ دوبارهٔ خطا ⇒ قرمز.
func TestPointsQueryError(t *testing.T) {
	// جدولِ تهیِ سالم: MAX یک ردیفِ NULL می‌دهد (err == nil)، نه خطا.
	empty := openWritableFixture(t)
	clearSnaps(t, empty.Market)
	pts, err := points(empty.Market)
	if err != nil {
		t.Fatalf("empty table points err = %v, want nil", err)
	}
	if len(pts) != 0 {
		t.Fatalf("empty table points = %d, want 0", len(pts))
	}
	body, err := timelinePanel(empty.Market, "cum")
	if err != nil {
		t.Fatalf("empty table timeline err = %v, want nil", err)
	}
	if body["status"] != "ok" || body["points"] != 0 || body["ready"] != false || body["note"] != noteNeedsTwo {
		t.Errorf("empty table body = status:%v points:%v ready:%v note:%#v",
			body["status"], body["points"], body["ready"], body["note"])
	}
	if zero := seriesOf(t, body, "val_bt"); len(zero) != 0 {
		t.Errorf("empty table series len = %d, want 0", len(zero))
	}
	phases, err := phasesPanel(empty.Market)
	if err != nil {
		t.Fatalf("empty table phases err = %v, want nil", err)
	}
	if phases["status"] != "ok" || phases["points"] != 0 || phases["ready"] != false {
		t.Errorf("empty table phases = status:%v points:%v ready:%v",
			phases["status"], phases["points"], phases["ready"])
	}

	// DBِ بسته: هر پرس‌وجو خطا می‌دهد؛ «به دو همگام‌سازی نیاز است» پاسخِ دروغین است.
	dead := openWritableFixture(t)
	if err := dead.Market.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := points(dead.Market); err == nil {
		t.Error("points on closed DB = nil error, want error")
	}
	if deadBody, err := timelinePanel(dead.Market, "cum"); err == nil || deadBody != nil {
		t.Errorf("closed DB timeline = (%#v, %v), want (nil, error)", deadBody, err)
	}
	if deadBody, err := phasesPanel(dead.Market); err == nil || deadBody != nil {
		t.Errorf("closed DB phases = (%#v, %v), want (nil, error)", deadBody, err)
	}
}

// TestDecodeStatesMixedMap: یک مقدارِ غیرِرشته نباید کلِ نگاشت را بیندازد؛
// پایتون رشته‌ها را نگه می‌دارد و phases همان چرخش را می‌شمارد.
func TestDecodeStatesMixedMap(t *testing.T) {
	got := decodeStates(zlibBlob(t, []byte(`{"m1":"b","m2":1}`)))
	if got["m1"] != "b" {
		t.Errorf("m1 = %q, want b (mixed map must keep string values)", got["m1"])
	}
	if _, ok := got["m2"]; ok {
		t.Errorf("m2 survived as %#v, want dropped", got["m2"])
	}
	if len(got) != 1 {
		t.Errorf("mixed map = %#v, want only m1", got)
	}

	// phases: m1 از b به s می‌رود، m2 در نقطهٔ دوم عدد است — فقط m1 شمرده می‌شود.
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	insertSnap(t, h.Market, 20261014, 100000,
		map[string]any{"d_even": 20261014, "st": zlibBlob(t, []byte(`{"m1":"b","m2":"s"}`))})
	insertSnap(t, h.Market, 20261014, 101000,
		map[string]any{"d_even": 20261014, "st": zlibBlob(t, []byte(`{"m1":"s","m2":1}`))})
	body, err := phasesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if body["points"] != 2 {
		t.Fatalf("points = %v, want 2", body["points"])
	}
	found := map[string]int{}
	for _, col := range []string{"red", "green"} {
		items, ok := body[col].([]map[string]any)
		if !ok {
			t.Fatalf("%s is %T", col, body[col])
		}
		for _, it := range items {
			found[it["key"].(string)] = it["count"].(int)
		}
	}
	if found["b>s"] != 1 {
		t.Errorf("b>s = %d, want 1 (mixed map must not drop the whole interval)", found["b>s"])
	}
	for k, v := range found {
		if k != "b>s" && v != 0 {
			t.Errorf("%s = %d, want 0 (non-string value must not form a pair)", k, v)
		}
	}
}

// TestPointsTailCap: سقفِ ۲۴۰ = out[-240:]؛ با ۲۴۵ نقطهٔ درون‌پنجره، پنج نقطهٔ
// نخست می‌افتند و ترتیب حفظ می‌شود.
func TestPointsTailCap(t *testing.T) {
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	for i := 0; i < 245; i++ {
		insertSnap(t, h.Market, 20261014, int64(100000+i),
			map[string]any{"d_even": 20261014, "val_bt": float64(i)})
	}
	pts, err := points(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if len(pts) != 240 {
		t.Fatalf("points = %d, want 240 (tail cap)", len(pts))
	}
	if got := toF(pts[0]["h_even"]); got != 100005 {
		t.Errorf("first h_even = %v, want 100005 (6th smallest)", got)
	}
	if got := toF(pts[239]["h_even"]); got != 100244 {
		t.Errorf("last h_even = %v, want 100244", got)
	}
	if got := toF(pts[0]["val_bt"]); got != 5 {
		t.Errorf("first val_bt = %v, want 5 (sixth inserted point)", got)
	}
	body, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	if body["points"] != 240 {
		t.Errorf("timeline points = %v, want 240", body["points"])
	}
	if vals := seriesOf(t, body, "val_bt"); len(vals) != 240 || vals[0] != 5.0 {
		t.Errorf("timeline val_bt len=%d first=%v, want 240/5", len(vals), vals[0])
	}
}

// TestPointsSkipsMalformedAgg: ردیف با aggِ SQL NULL، JSONِ ناخوانا یا JSONِ
// خوانا-ولی-غیرِشیء رد می‌شود و بقیهٔ پنجره دست‌نخورده می‌ماند.
func TestPointsSkipsMalformedAgg(t *testing.T) {
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	insertSnap(t, h.Market, 20261014, 100000, map[string]any{"d_even": 20261014, "val_bt": 1.0})
	insertSnapJSON(t, h.Market, 20261014, 101000, "null")  // JSONِ null
	insertSnapJSON(t, h.Market, 20261014, 102000, "[1]")   // آرایه
	insertSnapJSON(t, h.Market, 20261014, 103000, `{"a":`) // ناخوانا
	insertSnapJSON(t, h.Market, 20261014, 104000, `"b"`)   // رشته
	insertSnapJSON(t, h.Market, 20261014, 105000, "7")     // عدد
	if _, err := h.Market.Exec(
		"INSERT OR REPLACE INTO mstat_snap (d_even, h_even, ts, agg) VALUES (?,?,?,NULL)",
		20261014, 106000, "2026-10-28 10:00:00"); err != nil {
		t.Fatal(err)
	}
	insertSnap(t, h.Market, 20261014, 130000, map[string]any{"d_even": 20261014, "val_bt": 2.0})

	pts, err := points(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if len(pts) != 2 {
		t.Fatalf("points = %d, want 2 (malformed/NULL agg rows skipped)", len(pts))
	}
	if toF(pts[0]["h_even"]) != 100000 || toF(pts[1]["h_even"]) != 130000 {
		t.Errorf("kept h_even = %v/%v, want 100000/130000", pts[0]["h_even"], pts[1]["h_even"])
	}
	body, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	if body["points"] != 2 {
		t.Errorf("timeline points = %v, want 2", body["points"])
	}
	if vals := seriesOf(t, body, "val_bt"); !reflect.DeepEqual(vals, []any{1.0, 2.0}) {
		t.Errorf("timeline val_bt = %#v, want [1 2]", vals)
	}
}

// TestPointsWindowBoundaries: لبه‌هایِ ۸۵۵۰۰ و ۱۳۰۰۰۵ خودشان داخل‌اند؛ یک دقیقه
// بیرون‌تر نه (همان >= و <= پایتون).
func TestPointsWindowBoundaries(t *testing.T) {
	h := openWritableFixture(t)
	clearSnaps(t, h.Market)
	for _, hm := range []int64{85499, 85500, 130005, 130006} {
		insertSnap(t, h.Market, 20261014, hm,
			map[string]any{"d_even": 20261014, "val_bt": float64(hm)})
	}
	pts, err := points(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if len(pts) != 2 {
		t.Fatalf("points = %d, want 2 (85500 and 130005 inclusive)", len(pts))
	}
	if toF(pts[0]["h_even"]) != 85500 || toF(pts[1]["h_even"]) != 130005 {
		t.Errorf("kept h_even = %v/%v, want 85500/130005", pts[0]["h_even"], pts[1]["h_even"])
	}
}
