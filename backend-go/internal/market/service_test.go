package market

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/parity"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/tapeflags"
)

func fixtureCopy(t *testing.T) (*db.Handles, string) {
	t.Helper()
	src, _ := filepath.Abs(filepath.Join("..", "board", "testdata", "fixture"))
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		b, err := os.ReadFile(filepath.Join(src, name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	h, err := db.Open(dst, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h, dst
}

func fixtureService(t *testing.T) *Service {
	t.Helper()
	h, dst := fixtureCopy(t)
	return New(h, dst)
}

func golden(t *testing.T, name string) any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "board", "testdata", "golden", name))
	if err != nil {
		t.Fatal(err)
	}
	var v any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func getJSON(t *testing.T, s *Service, target string, hdr map[string]string) (int, any, []byte, string) {
	t.Helper()
	req := httptest.NewRequest("GET", target, nil)
	for k, v := range hdr {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	switch {
	case strings.HasPrefix(target, "/api/market/delta"):
		s.Delta(rec, req)
	case strings.HasPrefix(target, "/api/market/sync-state"):
		s.SyncState(rec, req)
	default:
		s.Board(rec, req)
	}
	var v any
	if rec.Body.Len() > 0 {
		if err := json.Unmarshal(rec.Body.Bytes(), &v); err != nil {
			t.Fatalf("%s: %v", target, err)
		}
	}
	return rec.Code, v, rec.Body.Bytes(), rec.Header().Get("ETag")
}

func TestBoardMatchesPythonGolden(t *testing.T) {
	s := fixtureService(t)
	_, got, body, _ := getJSON(t, s, "/api/market", nil)
	res := parity.Compare(golden(t, "market.json"), got, parity.Options{})
	if !res.Pass {
		t.Fatalf("default board differs: %v", res.Diffs[:min(5, len(res.Diffs))])
	}
	_, gotAll, bodyAll, _ := getJSON(t, s, "/api/market?fields=all", nil)
	if res := parity.Compare(golden(t, "market_all.json"), gotAll, parity.Options{}); !res.Pass {
		t.Fatalf("fields=all differs: %v", res.Diffs[:min(5, len(res.Diffs))])
	}
	// اندازۀ دو بدنه رویِ fixture؛ فقط با -v دیده می‌شود (شاهدِ گزارشِ تسک).
	t.Logf("body bytes: market=%d market_all=%d", len(body), len(bodyAll))
	_, sync, _, _ := getJSON(t, s, "/api/market/sync-state", nil)
	// `running` از شمارشِ زندۀ پروسۀ سینکر می‌آید، نه از داده؛ رویِ ماشینی که
	// سینکرِ پایتون زنده است true می‌شود. شکلش اینجا سنجیده می‌شود، مقدارش را
	// گیتِ دو‌سروری (Task 8) هم‌زمان رویِ هر دو طرف می‌سنجد.
	if res := parity.Compare(golden(t, "sync_state.json"), sync, parity.Options{Exclude: []string{"running"}}); !res.Pass {
		t.Fatalf("sync-state differs: %v", res.Diffs)
	}
}

func TestDeltaContract(t *testing.T) {
	s := fixtureService(t)
	// اول بدنه ساخته می‌شود، بعد دلتا؛ عینِ ترتیبِ ثبتِ golden و بی‌مسیرِ
	// بازسازیِ ناهمگام.
	if _, _, _, etag := getJSON(t, s, "/api/market", nil); etag == "" {
		t.Fatal("board response has no ETag")
	}
	_, full, _, _ := getJSON(t, s, "/api/market/delta?since=-1", nil)
	if res := parity.Compare(golden(t, "delta_negative.json"), full, parity.Options{}); !res.Pass {
		t.Fatalf("delta(-1) differs: %v", res.Diffs)
	}
	// پس از یک ساختِ کش‌شده، «همان ویرایش» یعنی unchanged — نه یک بدنهٔ تازه.
	_, same, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	if res := parity.Compare(golden(t, "delta_mirror.json"), same, parity.Options{}); !res.Pass {
		t.Fatalf("delta(0) differs: %v", res.Diffs)
	}
}

func TestETag304(t *testing.T) {
	s := fixtureService(t)
	_, _, _, etag := getJSON(t, s, "/api/market", nil)
	code, _, body, _ := getJSON(t, s, "/api/market", map[string]string{"If-None-Match": etag})
	if code != 304 || len(body) != 0 {
		t.Fatalf("304 expected, got %d (%d bytes)", code, len(body))
	}
}

// TestDeltaJournalAfterChange مسیرِ آینه را می‌سنجد که goldenها فقط دو حالتِ
// «سرد» و «همان ویرایش» را دارند: یک تغییرِ واقعی در کپیِ fixture باید ویرایش
// را یک پله جلو ببرد و دقیقاً همان نماد را در دلتا بدهد — نه بدنۀ کامل.
func TestDeltaJournalAfterChange(t *testing.T) {
	h, dir := fixtureCopy(t)
	s := New(h, dir)
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}
	w, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	var code string
	if err := w.Market.QueryRow("SELECT ins_code FROM market_watch WHERE ins_code IS NOT NULL LIMIT 1").Scan(&code); err != nil {
		w.Close()
		t.Fatal(err)
	}
	if _, err := w.Market.Exec("UPDATE market_watch SET p_last = p_last + 1 WHERE ins_code = ?", code); err != nil {
		w.Close()
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}

	_, got, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	m, _ := got.(map[string]any)
	if m["status"] != "delta" || m["rev"] != float64(1) {
		t.Fatalf("delta(0) = %v, want delta/rev 1", m["status"])
	}
	rows, _ := m["rows"].([]any)
	if len(rows) != 1 {
		t.Fatalf("delta rows = %d, want 1", len(rows))
	}
	if row, _ := rows[0].(map[string]any); row["ins_code"] != code {
		t.Fatalf("delta row = %v, want %q", rows[0], code)
	}
	for _, k := range []string{"count", "live_count", "fossil_count", "meta"} {
		if _, ok := m[k]; !ok {
			t.Fatalf("delta is missing %q: %v", k, m)
		}
	}
	// مشتریِ جلوتر از آینه: بدنۀ کامل می‌گیرد، نه دلتا.
	_, ahead, _, _ := getJSON(t, s, "/api/market/delta?since=9", nil)
	if am, _ := ahead.(map[string]any); am["status"] != "full" || am["reason"] != "stale-client" {
		t.Fatalf("delta(9) = %v", ahead)
	}
	// و «همان ویرایش» دیگر unchanged است، نه delta.
	_, same, _, _ := getJSON(t, s, "/api/market/delta?since=1", nil)
	if sm, _ := same.(map[string]any); sm["status"] != "unchanged" {
		t.Fatalf("delta(1) = %v", same)
	}
}

// TestAssembleMcapSrcEmptyString قیدِ ردیفِ واقعیِ بانک را می‌بندد: پایتون در
// _slim_records فقط None را می‌اندازد، پس mcap_src = "" هم مقدار است و کلید
// می‌سازد. ستونِ قاب NULL ⇒ کلید نیامد، "" ⇒ کلید با ""، "mw" ⇒ "mw"؛ و
// NULLِ ستونِ objectِ غیرِ _KEEP_NULL عینِ fillna(0) صفر می‌شود، نه نیامدن.
func TestAssembleMcapSrcEmptyString(t *testing.T) {
	fr := &store.Frame{
		Codes: []string{"NULLSRC", "EMPTYSRC", "MWSRC"},
		Cols: map[string][]any{
			"ins_code":    {"NULLSRC", "EMPTYSRC", "MWSRC"},
			"mcap_src":    {nil, "", "mw"},
			"sector_name": {nil, "bank", "other"},
		},
	}
	d := board.Derive(fr)
	recs := assemble(fr, d, tapeflags.Apply(fr, d), nil)
	if len(recs) != 3 {
		t.Fatalf("records = %d, want 3", len(recs))
	}
	if v, ok := recs[0]["mcap_src"]; ok {
		t.Fatalf("NULLِ mcap_src باید کلید نیامده باشد، آمد: %v", v)
	}
	if v, ok := recs[1]["mcap_src"]; !ok || v != "" {
		t.Fatalf(`mcap_src="" باید کلید با "" باشد، got %v (present=%v)`, v, ok)
	}
	if v := recs[2]["mcap_src"]; v != "mw" {
		t.Fatalf("mcap_src = %v, want mw", v)
	}
	if v := recs[0]["sector_name"]; v != int64(0) {
		t.Fatalf("NULLِ ستونِ object = %v (%T), want 0", v, v)
	}
	if v := recs[1]["sector_name"]; v != "bank" {
		t.Fatalf("sector_name = %v, want bank", v)
	}
}

// TestRecordDayUsesMaxLiveDEven قیدِ پایتون را می‌بندد: روزِ ثبت بیشترین d_even
// میانِ ردیف‌هایِ زندهٔ همین قاب است — نه d_evenِ متا و نه بیشترینِ کلِ قاب.
// ردیفِ فسیلی با روزِ بزرگ‌تر و ردیفِ زندهٔ بی‌روز نباید روز را جابه‌جا کنند.
func TestRecordDayUsesMaxLiveDEven(t *testing.T) {
	recs := []map[string]any{
		{"ins_code": "A", "is_live": true, "d_even": int64(20261014)},
		{"ins_code": "B", "is_live": true, "d_even": float64(20261015)},
		{"ins_code": "C", "is_live": false, "d_even": int64(20261016)},
		{"ins_code": "D", "is_live": true},
	}
	if got := recordDay(recs); got != 20261015 {
		t.Fatalf("recordDay = %d, want 20261015 (max d_even among live rows)", got)
	}
	if got := recordDay(recs[2:3]); got != 0 {
		t.Fatalf("fossil-only recordDay = %d, want 0", got)
	}
	if got := recordDay(nil); got != 0 {
		t.Fatalf("empty recordDay = %d, want 0", got)
	}
}

// TestBuildRecordsWithDataToken درِ «همان داده» را به توکنِ فایل‌هایِ داده می‌بندد:
// در این فیکسچر market_sync.json نیست، پس syncTokenِ پیشین "" می‌داد و Record
// برابریِ نشانه را دور می‌زد؛ توکنِ خالی یعنی هر ۲۴۰ثانیه یک passes جعلی. توکنِ
// ثبت باید همان dataToken باشد — ناتهی و پایدار تا وقتی فایل‌هایِ داده نچرخند.
func TestBuildRecordsWithDataToken(t *testing.T) {
	h, dir := fixtureCopy(t)
	s := New(h, dir)
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}
	var day int64
	if err := h.User.QueryRow("SELECT d_even FROM tape_flag_day_meta").Scan(&day); err != nil {
		t.Fatal(err)
	}
	got := s.recorder.LastToken(day)
	if got == "" {
		t.Fatal("recorder token is empty: the same-data gate is disabled")
	}
	if want := dataToken(dir); got != want {
		t.Fatalf("recorder token = %q, want dataToken %q", got, want)
	}
}

// TestBuildRecordsUnderLiveMaxDEven سیم‌کشیِ روزِ ثبت را سرتاسری می‌بندد. در
// تولید meta.d_even و بیشترین d_evenِ ردیف‌هایِ زنده یکی‌اند، پس برایِ جداکردنِ
// دو منبع یک ردیفِ بی‌ins_code با d_evenِ بزرگ‌تر به کپیِ فیکسچر اضافه می‌شود:
// boardMeta آن را می‌بیند (MAX(d_even)) ولی قابِ تابلو کنارش می‌گذارد. ردیف‌هایِ
// ثبت‌شده باید زیرِ روزِ ردیف‌هایِ زنده بنشینند، نه زیرِ روزِ متا.
func TestBuildRecordsUnderLiveMaxDEven(t *testing.T) {
	h, dir := fixtureCopy(t)
	w, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	var liveDay int64
	if err := w.Market.QueryRow("SELECT MAX(d_even) FROM market_watch WHERE ins_code IS NOT NULL").
		Scan(&liveDay); err != nil {
		w.Close()
		t.Fatal(err)
	}
	if _, err := w.Market.Exec("INSERT INTO market_watch(ins_code, d_even, h_even)"+
		" VALUES(NULL, ?, 1)", liveDay+10000); err != nil {
		w.Close()
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	s := New(h, dir)
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}
	var got int64
	if err := h.User.QueryRow("SELECT MAX(d_even) FROM tape_flag_day_meta").Scan(&got); err != nil {
		t.Fatal(err)
	}
	if got != liveDay {
		t.Fatalf("recorded day = %d, want %d (max d_even among live frame rows, not meta)",
			got, liveDay)
	}
}

// buildCount شمارندۀ بازسازی‌هایِ کامل‌شده را زیرِ همان قفل می‌خواند.
func (s *Service) buildCount() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.builds
}

// TestDeltaRebuildsWhenSyncTokenAdvances همان قیدِ پایتون را می‌بندد: rev فقط
// با build بالا می‌رود و فقط Board می‌سازد، پس مشتریِ دلتا-تنها باید خودش
// بازسازی را راه بیندازد. نوشتنِ market_sync.json توکن را از "" جدا می‌کند؛
// delta(0) باید بازسازیِ ناهمگام را شروع کند و شمارندۀ builds تا ۲ ثانیه
// جلو برود. فایل در طولِ تست دست نمی‌خورد، پس توکن پایدار است و بازسازیِ
// تکراری/بی‌پایان ممکن نیست.
func TestDeltaRebuildsWhenSyncTokenAdvances(t *testing.T) {
	h, dir := fixtureCopy(t)
	s := New(h, dir)
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}
	before := s.buildCount()
	if err := os.WriteFile(filepath.Join(dir, "market_sync.json"),
		[]byte(`{"at":"2026-10-30T00:00:00"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	_, got, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	if m, _ := got.(map[string]any); m["status"] != "unchanged" {
		t.Fatalf("delta(0) = %v, want unchanged؛ بازسازی نباید شکلِ پاسخ را عوض کند", got)
	}
	deadline := time.Now().Add(2 * time.Second)
	for s.buildCount() == before {
		if time.Now().After(deadline) {
			t.Fatalf("بعد از ۲ ثانیه بازسازیِ دلتا اجرا نشد (builds=%d)", before)
		}
		time.Sleep(5 * time.Millisecond)
	}
	if after := s.buildCount(); after != before+1 {
		t.Fatalf("builds = %d, want %d؛ توکنِ پایدار باید دقیقاً یک بازسازی بدهد", after, before+1)
	}
}

// TestDeltaRebuildsWhenDBMtimeAdvances همان شکافِ tick_live را می‌بندد: سینکرِ
// پایتون هر ۵ ثانیه ردیف‌ها را در market.db کامیت می‌کند بی بازنویسیِ
// market_sync.json، پس توکنی که فقط آن فایل را می‌دید مشتریِ دلتا-تنها را تا
// سینکِ کاملِ ۹۰ثانیه‌ای کهنه نگه می‌داشت. اینجا فقط mtimeِ خودِ market.db را
// جلو می‌بریم و بی هیچ نوشتنِ محتوا انتظارِ بازسازی داریم.
func TestDeltaRebuildsWhenDBMtimeAdvances(t *testing.T) {
	h, dir := fixtureCopy(t)
	s := New(h, dir)
	if _, _, err := s.build(true, true); err != nil {
		t.Fatal(err)
	}
	before := s.buildCount()
	if _, got, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil); envelopeStatus(got) != "unchanged" {
		t.Fatalf("delta(0) پیش از تغییرِ mtime = %v، انتظار unchanged بود", got)
	}
	dbPath := filepath.Join(dir, "market.db")
	st, err := os.Stat(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	future := st.ModTime().Add(time.Second)
	if err := os.Chtimes(dbPath, future, future); err != nil {
		t.Fatal(err)
	}
	// فراخوانیِ دوم نباید همگام بسازد؛ فقط بازسازیِ ناهمگام را راه می‌اندازد، پس
	// پاکتِ پاسخ همان unchanged/deltaِ معتبر می‌ماند و شکلش عوض نمی‌شود.
	_, got, _, _ := getJSON(t, s, "/api/market/delta?since=0", nil)
	if status := envelopeStatus(got); status != "unchanged" && status != "delta" {
		t.Fatalf("delta(0) بعد از تغییرِ mtime = %v، پاکتِ نامعتبر", got)
	}
	deadline := time.Now().Add(2 * time.Second)
	for s.buildCount() == before {
		if time.Now().After(deadline) {
			t.Fatalf("بعد از ۲ ثانیه بازسازیِ دلتا برایِ market.db اجرا نشد (builds=%d)", before)
		}
		time.Sleep(5 * time.Millisecond)
	}
	if after := s.buildCount(); after != before+1 {
		t.Fatalf("builds = %d, want %d؛ توکنِ پایدار باید دقیقاً یک بازسازی بدهد", after, before+1)
	}
}

// envelopeStatus نامِ پاکتِ پاسخِ دلتا را برمی‌گرداند ("" اگر نقشه نباشد).
func envelopeStatus(v any) string {
	m, _ := v.(map[string]any)
	st, _ := m["status"].(string)
	return st
}

// TestCacheHeaders دو قیدِ هدر را می‌بندد: پاسخِ دلتا مثلِ _ORJ_JSONِ پایتون
// no-store است، و ۳۰۴ِ مسیرِ ساخت X-Cache: MISS-304 می‌گیرد. کشِ داغ (HIT)
// مثلِ _market_from_cache فقط ETag می‌دهد، بی X-Cache.
func TestCacheHeaders(t *testing.T) {
	s := fixtureService(t)
	req := httptest.NewRequest("GET", "/api/market/delta?since=-1", nil)
	rec := httptest.NewRecorder()
	s.Delta(rec, req)
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		t.Fatalf("delta Cache-Control = %q, want no-store", got)
	}

	// fields=all هر بار می‌سازد، پس ۳۰۴ همیشه از مسیرِ ساخت است.
	_, _, _, allETag := getJSON(t, s, "/api/market?fields=all", nil)
	req = httptest.NewRequest("GET", "/api/market?fields=all", nil)
	req.Header.Set("If-None-Match", allETag)
	rec = httptest.NewRecorder()
	s.Board(rec, req)
	if rec.Code != 304 || rec.Header().Get("X-Cache") != "MISS-304" {
		t.Fatalf("fields=all 304: code=%d X-Cache=%q, want 304/MISS-304",
			rec.Code, rec.Header().Get("X-Cache"))
	}

	// کشِ داغ: ۳۰۴ فقط ETag.
	_, _, _, etag := getJSON(t, s, "/api/market", nil)
	req = httptest.NewRequest("GET", "/api/market", nil)
	req.Header.Set("If-None-Match", etag)
	rec = httptest.NewRecorder()
	s.Board(rec, req)
	if rec.Code != 304 || rec.Header().Get("X-Cache") != "" {
		t.Fatalf("hot 304: code=%d X-Cache=%q, want 304/empty",
			rec.Code, rec.Header().Get("X-Cache"))
	}

	// کهنگیِ بیش از سقف ⇒ ساختِ همگام ⇒ ۳۰۴ِ مسیرِ ساخت.
	s.mu.Lock()
	s.builtAt = time.Now().Add(-staleCeiling - time.Second)
	s.mu.Unlock()
	req = httptest.NewRequest("GET", "/api/market", nil)
	req.Header.Set("If-None-Match", etag)
	rec = httptest.NewRecorder()
	s.Board(rec, req)
	if rec.Code != 304 || rec.Header().Get("X-Cache") != "MISS-304" {
		t.Fatalf("cold 304: code=%d X-Cache=%q, want 304/MISS-304",
			rec.Code, rec.Header().Get("X-Cache"))
	}
}

// boardCall یک درخواستِ /api/market می‌زند و پاسخِ خام را برمی‌گرداند؛ هدرِ
// X-Cache و بدنهٔ بایتی برایِ تستِ کش لازم‌اند و getJSON این‌ها را نمی‌دهد.
func boardCall(t *testing.T, s *Service) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	s.Board(rec, httptest.NewRequest("GET", "/api/market", nil))
	if rec.Code != 200 {
		t.Fatalf("board status = %d", rec.Code)
	}
	return rec
}

// TestCachedBodyFollowsDataToken درِ توکنِ کشِ بدنه را می‌بندد. پیش از این،
// cached فقط عمر را می‌سنجید؛ اگر داده زیرِ سرورِ زنده عوض می‌شد، تا ۶۰ ثانیه
// بدنهٔ کهنه HIT می‌گرفت، درحالی‌که پایتون کش را با هر سینک پاک می‌کند. تغییرِ
// mtime کافی است تا توکنِ dataToken عوض شود: پاسخِ بعدی باید بدنهٔ فعلی را با
// X-Cache: STALE بدهد و یک بازسازیِ ناهمگام راه بیندازد؛ پس از نشستنِ بازسازی،
// همان درخواست HIT می‌گیرد و بدنه بایت‌به‌بایت همان اولی است.
func TestCachedBodyFollowsDataToken(t *testing.T) {
	h, dir := fixtureCopy(t)
	s := New(h, dir)
	first := boardCall(t, s)
	if got := first.Header().Get("X-Cache"); got != "MISS" {
		t.Fatalf("first X-Cache = %q, want MISS", got)
	}

	dbPath := filepath.Join(dir, "market.db")
	st, err := os.Stat(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	future := st.ModTime().Add(time.Second)
	if err := os.Chtimes(dbPath, future, future); err != nil {
		t.Fatal(err)
	}

	before := s.buildCount()
	stale := boardCall(t, s)
	if got := stale.Header().Get("X-Cache"); got != "STALE" {
		t.Fatalf("after data change X-Cache = %q, want STALE", got)
	}
	if !bytes.Equal(stale.Body.Bytes(), first.Body.Bytes()) {
		t.Fatal("STALE response must carry the current body unchanged")
	}

	deadline := time.Now().Add(2 * time.Second)
	for s.buildCount() == before {
		if time.Now().After(deadline) {
			t.Fatalf("بعد از ۲ ثانیه بازسازیِ توکنِ کش اجرا نشد (builds=%d)", before)
		}
		time.Sleep(5 * time.Millisecond)
	}

	hit := boardCall(t, s)
	if got := hit.Header().Get("X-Cache"); got != "HIT" {
		t.Fatalf("after rebuild X-Cache = %q, want HIT", got)
	}
	if !bytes.Equal(hit.Body.Bytes(), first.Body.Bytes()) {
		t.Fatal("body changed between the first and the post-rebuild HIT")
	}
}

// TestScreeningReasonUsesLiveSessionDayNotBoardMeta ریشهٔ تنها اختلافِ واقعیِ
// B1 رویِ بانکِ کاری را می‌بندد. پایتون session_day را از market_state (تیکِ
// زنده) می‌گیرد و در پروسۀ بی‌تیک صفر است؛ پس در بدنۀ پیش‌فرض که d_even از
// ردیف حذف شده، _state_reason به fallback نمی‌رسد و «از نشستِ ...» می‌نویسد.
// اگر به‌جایِ صفر، d_evenِ متا به Eligibility داده شود، همان ردیف «طی معاملات»
// می‌گیرد — یعنی علتی که پایتون هرگز در بدنۀ پیش‌فرض نمی‌دهد.
func TestScreeningReasonUsesLiveSessionDayNotBoardMeta(t *testing.T) {
	h, dst := fixtureCopy(t)
	s := New(h, dst)

	_, all, _, _ := getJSON(t, s, "/api/market?fields=all", nil)
	allRows, _ := all.(map[string]any)["data"].([]any)
	var code, metaDay string
	for _, raw := range allRows {
		rec, _ := raw.(map[string]any)
		if live, _ := rec["is_live"].(bool); !live {
			continue
		}
		if ev, ok := rec["stop_state"].(string); ok && ev != "" {
			continue
		}
		code, _ = rec["ins_code"].(string)
		break
	}
	if code == "" {
		t.Fatal("fixture has no live row without stop_state")
	}
	meta, _ := all.(map[string]any)["meta"].(map[string]any)
	if day, ok := meta["d_even"].(float64); ok {
		metaDay = strconv.FormatInt(int64(day), 10)
	}
	if metaDay == "" {
		t.Fatal("fixture meta has no d_even")
	}

	w, err := sql.Open("sqlite", filepath.Join(dst, "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer w.Close()
	if _, err := w.Exec("INSERT INTO instrument_state"+
		" (ins_code, c_etaval, c_etaval_title, d_even, last_h_even)"+
		" VALUES (?, ?, ?, ?, ?)", code, "A", "ممنوع", 20261014, 60100); err != nil {
		t.Fatal(err)
	}

	reason := func(target string) string {
		_, body, _, _ := getJSON(t, s, target, nil)
		rows, _ := body.(map[string]any)["data"].([]any)
		for _, raw := range rows {
			rec, _ := raw.(map[string]any)
			if rec["ins_code"] == code {
				r, _ := rec["screening_exclusion_reason"].(string)
				return r
			}
		}
		return "<row missing>"
	}

	// بدنۀ پیش‌فرض: d_even حذف شده ⇒ fallbackی نیست ⇒ «از نشستِ».
	if got, want := reason("/api/market"), "ممنوع — از نشستِ ۲۰۲۶۱۰۱۴"; got != want {
		t.Fatalf("default reason = %q, want %q", got, want)
	}
	// fields=all: d_even در ردیف هست ⇒ همان نشست ⇒ «طی معاملات».
	if got, want := reason("/api/market?fields=all"), "ممنوع (طی معاملات — ساعت ۰۶:۰۱)"; got != want {
		t.Fatalf("fields=all reason = %q, want %q", got, want)
	}
}

// TestTapeFlagsUsesCache (F1a): قراردادِ TapeFlags این است که از cached()
// بگذرد، نه build(). ساختِ بی‌قید در هر درخواستِ mainwatch، تابلوِ ۵٬۵هزار
// ردیفی را از نو می‌ساخت. builds را build زیرِ همان قفل بالا می‌برد؛ پس N
// فراخوانیِ پیاپی پس از نخستین ساخت باید آن را روی ۱ نگه دارد.
func TestTapeFlagsUsesCache(t *testing.T) {
	s := fixtureService(t)
	first, ok := s.TapeFlags()
	if !ok || len(first) == 0 {
		t.Fatalf("TapeFlags = (%d keys, ok=%v), want an available non-empty map", len(first), ok)
	}
	if got := s.buildCount(); got != 1 {
		t.Fatalf("first TapeFlags builds = %d, want 1 (cold cached())", got)
	}
	for i := 0; i < 8; i++ {
		got, ok := s.TapeFlags()
		if !ok || len(got) != len(first) {
			t.Fatalf("call %d: (%d keys, ok=%v), want (%d, true)",
				i+2, len(got), ok, len(first))
		}
	}
	if got := s.buildCount(); got != 1 {
		t.Fatalf("TapeFlags rebuilt per call: builds = %d, want 1", got)
	}
}

// TestTapeFlagsKeepsZWNJ (F1b): کلیدِ نقشه همان norm_symbolِ پایتون است و
// نیم‌فاصله (U+200C) بخشی از نماد می‌ماند. پنج نمادِ فیکسچر نیم‌فاصله دارند؛
// اگر روزی symStrip با نرمال‌سازِ نیم‌فاصله‌بردار عوض شود، پرچمِ این نمادها
// بی‌صدا گم می‌شود و همهٔ تست‌ها سبز می‌مانند (دو طرفِ جفت‌شدن در mstat یکسان
// نرمال می‌شوند). نقشهٔ TapeFlags این‌جا با ردیفِ همان نماد در گلدنِ تابلو
// مقایسه می‌شود؛ گلدن همان _board_rowsی است که _tape_flag_map از آن می‌خواند.
func TestTapeFlagsKeepsZWNJ(t *testing.T) {
	s := fixtureService(t)
	flags, ok := s.TapeFlags()
	if !ok {
		t.Fatal("TapeFlags unavailable")
	}
	const sym = "پول\u200cهوشمند06"
	if !strings.Contains(sym, "\u200c") {
		t.Fatal("fixture symbol lost its ZWNJ")
	}
	key := symStrip(symNorm.Replace(sym))
	if !strings.Contains(key, "\u200c") {
		t.Fatalf("TapeFlags key %q lost U+200C", key)
	}
	got, ok := flags[key]
	if !ok {
		t.Fatalf("TapeFlags has no key %q (map has %d keys)", key, len(flags))
	}
	if _, ok := flags[strings.ReplaceAll(key, "\u200c", "")]; ok {
		t.Fatalf("TapeFlags also has a ZWNJ-stripped key for %q", key)
	}

	raw, ok := golden(t, "market.json").(map[string]any)
	if !ok {
		t.Fatalf("board golden type = %T", golden(t, "market.json"))
	}
	data, ok := raw["data"].([]any)
	if !ok {
		t.Fatalf("board golden data type = %T", raw["data"])
	}
	var board map[string]any
	for _, item := range data {
		row, ok := item.(map[string]any)
		if !ok {
			t.Fatalf("board golden row type = %T", item)
		}
		if row["symbol"] == sym {
			board = row
			break
		}
	}
	if board == nil {
		t.Fatalf("board golden has no row for %q", sym)
	}
	wantKeys := []string{"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal"}
	if len(got) != len(wantKeys) {
		t.Fatalf("%q: %d flags, want %d", key, len(got), len(wantKeys))
	}
	for _, k := range wantKeys {
		want, ok := board[k].(bool)
		if !ok {
			t.Fatalf("board golden %s = %v (%T), want bool", k, board[k], board[k])
		}
		if got[k] != want {
			t.Errorf("%q: %s = %v, board = %v", key, k, got[k], want)
		}
	}
}
