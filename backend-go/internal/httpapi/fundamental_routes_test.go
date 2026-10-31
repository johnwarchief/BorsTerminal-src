package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"borsterminal/backend/internal/config"
)

type fakeFundamental struct{ called []string }

func (f *fakeFundamental) hit(name string, w http.ResponseWriter) {
	f.called = append(f.called, name)
	WriteJSON(w, http.StatusOK, map[string]any{"handler": name})
}

func (f *fakeFundamental) Sectors(w http.ResponseWriter, _ *http.Request) { f.hit("sectors", w) }
func (f *fakeFundamental) Quarters(w http.ResponseWriter, _ *http.Request) {
	f.hit("quarters", w)
}

func newFundSrv(t *testing.T, fd Fundamental) http.Handler {
	t.Helper()
	return New(config.Config{Addr: "127.0.0.1:8198", DataDir: t.TempDir(),
		ReadOnly: true, NoLoops: true}, nil, nil, nil, nil, fd)
}

// TestFundamentalRoutesReachTheirHandlers دو مسیرِ پورت‌شده باید به هندلرِ
// خودشون برسند و هر سه مسیرِ مانده (کارت، screen، sync/codal) 501 بدهند؛ این
// همان تعویقِ اعلام‌شده است، نه یک فرض.
func TestFundamentalRoutesReachTheirHandlers(t *testing.T) {
	for _, c := range []struct {
		path, want string
	}{
		{"/api/fundamental/sectors", "sectors"},
		{"/api/fundamental/عادی01/quarters", "quarters"},
	} {
		fake := &fakeFundamental{}
		rec := httptest.NewRecorder()
		newFundSrv(t, fake).ServeHTTP(rec, httptest.NewRequest("GET", c.path, nil))
		if rec.Code != http.StatusOK || len(fake.called) != 1 || fake.called[0] != c.want {
			t.Errorf("%s: status=%d called=%v want %s", c.path, rec.Code, fake.called, c.want)
		}
	}
	// مسیرهایِ نپورت‌شده: هر دو درِ فهرستِ پایتون‌اند، پس 501 و نه 404.
	for _, path := range []string{"/api/fundamental/عادی01", "/api/fundamental/screen"} {
		fake := &fakeFundamental{}
		rec := httptest.NewRecorder()
		newFundSrv(t, fake).ServeHTTP(rec, httptest.NewRequest("GET", path, nil))
		if rec.Code != http.StatusNotImplemented || len(fake.called) != 0 {
			t.Errorf("%s: status=%d called=%v", path, rec.Code, fake.called)
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if body["code"] != "NOT_PORTED" || body["route"] != "GET "+path {
			t.Errorf("%s: body = %s", path, rec.Body.String())
		}
	}
	// قطعهٔ `{symbol}` درِ Starlette و Go فقط **یک** بخش را جور می‌کند، پس
	// `/api/fundamental/X/nope` هیچ مسیرِ شناخته‌شده‌ای نیست: ۴۰۴ و نه ۵۰۱.
	rec := httptest.NewRecorder()
	newFundSrv(t, nil).ServeHTTP(rec,
		httptest.NewRequest("GET", "/api/fundamental/عادی01/nope", nil))
	if rec.Code != http.StatusNotFound ||
		strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
		t.Errorf("three-segment non-route: status=%d body=%s", rec.Code, rec.Body.String())
	}
}

// TestSectorsIsNotSwallowedBySymbolRoute R9 از پلنِ B4، با درسِ مستقیمِ
// `/api/fts/config` درِ B3: `screen` و `sectors` درِ پایتون *پیش از* `{symbol}`
// ثبت شده‌اند. Go امروز آن الگو را ثبت نکرده، پس این آزمون دو چیز را هم‌زمان
// نگهبانی می‌کند: sectors حتماً به هندلر می‌رسد، و اگر روزی `{symbol}` ثبت شد،
// این آزمون با همان bodyِ NOT_PORTED برایِ screen می‌گوید کدام ترتیب لازم است.
func TestSectorsIsNotSwallowedBySymbolRoute(t *testing.T) {
	fake := &fakeFundamental{}
	rec := httptest.NewRecorder()
	newFundSrv(t, fake).ServeHTTP(rec, httptest.NewRequest("GET", "/api/fundamental/sectors", nil))
	if rec.Code != http.StatusOK || len(fake.called) != 1 || fake.called[0] != "sectors" {
		t.Fatalf("sectors swallowed: status=%d called=%v body=%s",
			rec.Code, fake.called, rec.Body.String())
	}
	// «sectors» باید بتواند نماد هم باشد (تطبیقِ عینِ Starlette) — ولی درِ مسیرِ
	// واقعیِ صنعت، هندلرِ صریح برنده است، پس بالا صدایش زدیم.
	rec = httptest.NewRecorder()
	newFundSrv(t, fake).ServeHTTP(rec, httptest.NewRequest("GET", "/api/fundamental/screen", nil))
	if rec.Code != http.StatusNotImplemented || !strings.Contains(rec.Body.String(), "NOT_PORTED") {
		t.Fatalf("screen must stay declared-not-ported: %d %s", rec.Code, rec.Body.String())
	}
}

// TestQuarters422IsNotServedByTheGate بدنهٔ 422 کارِ خودِ هندلر است (تستِ
// handler-level درِ internal/fundamental)؛ اینجا فقط نگهبانی می‌شود که بی‌سرویس
// دروازه زودتر از اعتبارسنجی جواب می‌دهد — همان ترتیبی که گیتِ B4 اندازه می‌گیرد.
func TestQuarters422IsNotServedByTheGate(t *testing.T) {
	rec := httptest.NewRecorder()
	newFundSrv(t, nil).ServeHTTP(rec,
		httptest.NewRequest("GET", "/api/fundamental/X/quarters?limit=abc", nil))
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	// متدِ غلط رویِ همان الگو به فهرستِ پایتون می‌خورد و ۴۰۴ می‌گیرد، نه ۵۰۱.
	rec = httptest.NewRecorder()
	newFundSrv(t, nil).ServeHTTP(rec, httptest.NewRequest("POST", "/api/fundamental/sectors", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("POST sectors: status=%d want 404 (GET-only in the Python inventory)", rec.Code)
	}
}
