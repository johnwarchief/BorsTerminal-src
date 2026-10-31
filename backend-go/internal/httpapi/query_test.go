package httpapi

import (
	"encoding/json"
	"math"
	"math/big"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

// این شاهدِ زنده است، نه حدس: جدولِ پایین با FastAPI 0.141.1 / pydantic 2.12.5 /
// starlette 1.6.0 اندازه گرفته شد (پروبِ موقتی با TestClient و دو امضایِ عینِ
// پروژه: `limit: int = 16` درِ api/fundamental.py:2216 و `days: int = 20` درِ
// api/market.py:1449؛ تاریخِ اندازه‌گیری 2026-10-14). بدنه‌ها عینِ متنِ خامِ
// پاسخ‌هایِ پایتون‌اند.
//
// تنها جایی که بدنهٔ 200 مو‌به‌مو مقایسه نمی‌شود، قدرهایِ بی‌سقف‌اند: پایتون
// عددِ بی‌سقف را درِ پاسخِ پروبِ خودش برمی‌گرداند و Go آن را سیرابه می‌کند، پس
// آن سطرها درِ clampِ مسیر مقایسه می‌شود (همان چیزی که مصرف‌کننده می‌بیند).
type measuredInt struct {
	name   string
	route  string // "quarters" (limit=16) یا "tape" (days=20)
	param  string
	query  string // raw query string روی سیم
	status int    // وضعیتِ اندازه‌گیری‌شده از FastAPI
	pyBody string // بدنهٔ خامِ اندازه‌گیری‌شده
}

// نویسه‌هایِ غیرASCII با codepoint ساخته می‌شوند، نه با نویسهٔ خامِ وسطِ متنِ
// فارسی: ویرایشِ مستقیمِ رقم/نویسه درِ متن، رقم را می‌دزدد (قیدِ شکست‌پذیرِ ریپو).
var (
	nbspChar        = string(rune(0x00A0))
	arabicIndic     = string([]rune{0x0660, 0x0661, 0x0662})
	fullwidthDigits = string([]rune{0xFF11, 0xFF12, 0xFF13})
)

var measuredInts = []measuredInt{
	// — شش رفتارِ خواستۀ بخشِ اولِ کار —
	{"blank-is-not-default", "quarters", "limit", "limit=", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":""}]}`},
	{"float-shaped-integral", "quarters", "limit", "limit=1.0", 200, `{"ok":true,"limit":1}`},
	{"float-shaped-fraction", "quarters", "limit", "limit=1.9", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"1.9"}]}`},
	{"leading-space", "quarters", "limit", "limit=%207", 200, `{"ok":true,"limit":7}`},
	{"huge-int-no-cap", "quarters", "limit", "limit=99999999999999999999", 200,
		`{"ok":true,"limit":99999999999999999999}`},
	{"duplicate-last-wins", "tape", "days", "days=3&days=5", 200, `{"ok":true,"days":5}`},
	// — کناره‌هایِ همان قواعد —
	{"dup-blank-last", "tape", "days", "days=5&days=", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","days"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":""}]}`},
	{"dup-blank-first", "tape", "days", "days=&days=5", 200, `{"ok":true,"days":5}`},
	{"dup-bad-then-good", "tape", "days", "days=abc&days=5", 200, `{"ok":true,"days":5}`},
	{"dup-good-then-bad", "tape", "days", "days=5&days=abc", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","days"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"abc"}]}`},
	{"absent-key-default", "quarters", "limit", "", 200, `{"ok":true,"limit":16}`},
	{"absent-key-days-default", "tape", "days", "", 200, `{"ok":true,"days":20}`},
	{"not-a-number", "quarters", "limit", "limit=abc", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"abc"}]}`},
	{"space-only", "quarters", "limit", "limit=%20", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":" "}]}`},
	{"leading-zeros", "quarters", "limit", "limit=007", 200, `{"ok":true,"limit":7}`},
	{"plus-sign", "quarters", "limit", "limit=%2B7", 200, `{"ok":true,"limit":7}`},
	{"exponent-rejected", "quarters", "limit", "limit=1e2", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"1e2"}]}`},
	{"trailing-dot-rejected", "quarters", "limit", "limit=5.", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"5."}]}`},
	{"leading-dot-rejected", "quarters", "limit", "limit=.5", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":".5"}]}`},
	{"underscore-mid", "quarters", "limit", "limit=1_000", 200, `{"ok":true,"limit":1000}`},
	{"underscore-double", "quarters", "limit", "limit=1__0", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"1__0"}]}`},
	{"underscore-first", "quarters", "limit", "limit=_1", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"_1"}]}`},
	{"underscore-before-dot", "quarters", "limit", "limit=1_.0", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"1_.0"}]}`},
	{"underscore-in-fraction", "quarters", "limit", "limit=1.00_00", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"1.00_00"}]}`},
	{"underscore-in-intpart-float", "quarters", "limit", "limit=1_0.00", 200, `{"ok":true,"limit":10}`},
	{"non-ascii-digits", "quarters", "limit", "limit=%D9%A0%D9%A1%D9%A2", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":` +
			`"Input should be a valid integer, unable to parse string as an integer",` +
			`"input":"` + arabicIndic + `"}]}`},
	{"nbsp-stripped", "quarters", "limit", "limit=%C2%A07", 200, `{"ok":true,"limit":7}`},
	{"tab-stripped", "quarters", "limit", "limit=%097", 200, `{"ok":true,"limit":7}`},
	{"negative-zero", "quarters", "limit", "limit=-0", 200, `{"ok":true,"limit":0}`},
	{"negative-float-shaped", "quarters", "limit", "limit=-1.0", 200, `{"ok":true,"limit":-1}`},
	{"beyond-uint64", "quarters", "limit", "limit=18446744073709551616", 200,
		`{"ok":true,"limit":18446744073709551616}`},
	{"huge-negative", "quarters", "limit", "limit=-99999999999999999999", 200,
		`{"ok":true,"limit":-99999999999999999999}`},
	{"sign-then-space", "quarters", "limit", "limit=%2B%201", 422,
		`{"detail":[{"type":"int_parsing","loc":["query","limit"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"+ 1"}]}`},
	{"huge-float-shaped", "quarters", "limit", "limit=99999999999999999999.0", 200,
		`{"ok":true,"limit":99999999999999999999}`},
}

// probe همان کاری است که هندلرهایِ واقعی می‌کنند: یک کوئریِ خام روی سیم و
// IntQuery با پیش‌فرضِ امضایِ پایتون؛ اگر IntQuery رد نکرد، پاسخِ 200 هم مثلِ
// پروبِ پایتون نوشته می‌شود.
func probe(t *testing.T, row measuredInt) (*httptest.ResponseRecorder, int, bool) {
	t.Helper()
	def := 16
	if row.route == "tape" {
		def = 20
	}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/"+row.route+"?"+row.query, nil)
	v, ok := IntQuery(rec, req, row.param, def)
	// IntQuery درِ مسیرِ موفق چیزی نمی‌نویسد؛ نشانهٔ نوشتن، هدرِ JSON است.
	if ok && rec.Header().Get("Content-Type") == "" {
		WriteJSON(rec, http.StatusOK, map[string]any{"ok": true, row.param: v})
	}
	return rec, v, ok
}

func decodeNumbers(t *testing.T, s string) any {
	t.Helper()
	dec := json.NewDecoder(strings.NewReader(s))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		t.Fatalf("decode %s: %v", s, err)
	}
	return v
}

// routeClamp عینِ دو خطِ مسیرِ پایتون است: `max(1, min(limit, 40))` درِ
// api/fundamental.py:2271 و `max(1, min(int(days or 20), 120))` درِ
// api/market.py:1463. مقایسه درِ همین فضای clamp است، چون سیرابهٔ Go فقط همان‌جا
// دیده می‌شود.
func routeClamp(route string, v *big.Int) *big.Int {
	if route == "tape" {
		if v.Sign() == 0 {
			v = big.NewInt(20) // int(days or 20)
		}
		return clampBig(v, 1, 120)
	}
	return clampBig(v, 1, 40)
}

func clampBig(v *big.Int, lo, hi int64) *big.Int {
	out := new(big.Int).Set(v)
	if out.Cmp(big.NewInt(hi)) > 0 {
		out.SetInt64(hi)
	}
	if out.Cmp(big.NewInt(lo)) < 0 {
		out.SetInt64(lo)
	}
	return out
}

func bigOfJSON(t *testing.T, n json.Number) *big.Int {
	t.Helper()
	b, ok := new(big.Int).SetString(n.String(), 10)
	if !ok {
		t.Fatalf("not an integer on the wire: %q", n.String())
	}
	return b
}

// TestIntQueryMatchesLiveFastAPI هر سطرِ جدول را می‌زند: وضعیت عیناً، بدنه درِ
// معنای JSON (کلیدها بی‌ترتیب؛ ترتیبِ کلیدهایِ Go الفبایی است و پایتون
// type/loc/msg/input را می‌نویسد، گیتِ پاریتی هم parsed-JSON را می‌سنجد)، و برای
// پاسخ‌هایِ 200 مقدارِ مؤثرِ پس از clampِ مسیر.
func TestIntQueryMatchesLiveFastAPI(t *testing.T) {
	for _, row := range measuredInts {
		row := row
		t.Run(row.name, func(t *testing.T) {
			rec, goVal, ok := probe(t, row)
			if rec.Code != row.status {
				t.Fatalf("status = %d body=%s want %d (%s)",
					rec.Code, rec.Body.String(), row.status, row.pyBody)
			}
			if row.status == 200 && !ok {
				t.Fatalf("IntQuery refused a value FastAPI accepts: %s", row.query)
			}
			if row.status == 422 && ok {
				t.Fatalf("IntQuery accepted a value FastAPI rejects: %s", row.query)
			}
			want := decodeNumbers(t, row.pyBody)
			got := decodeNumbers(t, rec.Body.String())
			if row.status == 422 {
				if !reflect.DeepEqual(got, want) {
					t.Fatalf("422 body = %s want (semantically) %s", rec.Body.String(), row.pyBody)
				}
				return
			}
			wantVal := bigOfJSON(t, want.(map[string]any)[row.param].(json.Number))
			gotVal := bigOfJSON(t, got.(map[string]any)[row.param].(json.Number))
			wantClamp, gotClamp := routeClamp(row.route, wantVal), routeClamp(row.route, gotVal)
			if wantClamp.Cmp(gotClamp) != 0 {
				t.Fatalf("clamped value: go=%s want=%s (py-raw=%s go-raw=%d)",
					gotClamp, wantClamp, wantVal, goVal)
			}
			// اگر عدد درِ int جا شد، بدنه هم باید عیناً یکی باشد؛ سطرهایِ بی‌سقف
			// (سیرابهٔ Go) فقط درِ همان clamp یکی‌اند.
			if wantVal.IsInt64() && gotVal.Cmp(wantVal) == 0 && !reflect.DeepEqual(got, want) {
				t.Fatalf("small-int body = %s want %s", rec.Body.String(), row.pyBody)
			}
		})
	}
}

// TestIntQueryBodyShape بدنهٔ خامِ 422 را پین می‌کند (شکلِ `detail[0]` با
// type/loc/msg/input) تا جابه‌جاییِ این چهار کلید بی‌صدا نگذرد.
func TestIntQueryBodyShape(t *testing.T) {
	rec, _, ok := probe(t, measuredInt{name: "shape", route: "quarters",
		param: "limit", query: "limit=1.5", status: 422})
	if ok {
		t.Fatal("1.5 must be rejected")
	}
	want := `{"detail":[{"input":"1.5","loc":["query","limit"],` +
		`"msg":"Input should be a valid integer, unable to parse string as an integer",` +
		`"type":"int_parsing"}]}`
	if strings.TrimSpace(rec.Body.String()) != want {
		t.Fatalf("body = %s want %s", rec.Body.String(), want)
	}
}

// TestIntQueryAbsentKeyWritesNothing کلیدِ غایب نباید چیزی روی سیم بگذارد؛
// هندلر خودش پاسخِ 200 را می‌نویسد (پیش‌فرضِ امضا، نه 422).
func TestIntQueryAbsentKeyWritesNothing(t *testing.T) {
	rec := httptest.NewRecorder()
	v, ok := IntQuery(rec, httptest.NewRequest(http.MethodGet, "/tape?codes=1", nil), "days", 20)
	if !ok || v != 20 {
		t.Fatalf("v=%d ok=%v want 20/true", v, ok)
	}
	if rec.Header().Get("Content-Type") != "" || rec.Body.Len() != 0 {
		t.Fatalf("gate spoke: code=%d body=%q", rec.Code, rec.Body.String())
	}
}

// TestParseFastAPIIntRule قاعدۀ خالصِ رشته→int را جدا می‌زند تا خطایِ خودِ
// پارسر از خطایِ هندلرِ HTTP تفکیک بماند (هر سطر از جدولِ زندۀ بالا آمده).
func TestParseFastAPIIntRule(t *testing.T) {
	for _, c := range []struct {
		in     string
		want   int64
		wantOK bool
	}{
		{"16", 16, true}, {"", 0, false}, {" ", 0, false},
		{"1.0", 1, true}, {"1.9", 0, false}, {"0.0", 0, true}, {"-0.0", 0, true},
		{"2.00", 2, true}, {"0.0000", 0, true}, {"0.", 0, false}, {".0", 0, false},
		{"1e2", 0, false}, {"1.0e2", 0, false}, {"nan", 0, false}, {"inf", 0, false},
		{"7", 7, true}, {" 7 ", 7, true}, {"\t7", 7, true}, {"\r7", 7, true},
		{nbspChar + "7", 7, true},
		{"+7", 7, true}, {"-3", -3, true}, {"--7", 0, false}, {"+-1", 0, false},
		{"+ 1", 0, false}, {"1 000", 0, false}, {",", 0, false}, {"1,000", 0, false},
		{"007", 7, true}, {"00", 0, true}, {"-0", 0, true},
		{"1_000", 1000, true}, {"0_0", 0, true}, {"12_34_56", 123456, true},
		{"_1", 0, false}, {"1_", 0, false}, {"1__0", 0, false}, {"-_1", 0, false},
		{"1_.0", 0, false}, {"1._0", 0, false}, {"1.0_0", 0, false},
		{"1.00_00", 0, false}, {"1_0.00", 10, true}, {"0_0.0", 0, true},
		{arabicIndic, 0, false}, {fullwidthDigits, 0, false},
		{"99999999999999999999", int64(math.MaxInt), true},
		{"99999999999999999999.0", int64(math.MaxInt), true},
		{"-99999999999999999999", int64(math.MinInt), true},
	} {
		got, ok := parseFastAPIInt(c.in)
		if ok != c.wantOK {
			t.Errorf("parseFastAPIInt(%q) ok=%v want %v (value %d)", c.in, ok, c.wantOK, got)
			continue
		}
		if ok && int64(got) != c.want {
			t.Errorf("parseFastAPIInt(%q) = %d want %d", c.in, got, c.want)
		}
	}
}
