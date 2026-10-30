package market

import (
	"context"
	"crypto/md5"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode"

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/screening"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/tapeflags"
	"borsterminal/backend/internal/tapehistory"
)

const (
	ttl          = 60 * time.Second
	staleCeiling = 300 * time.Second
	journalMax   = 240
	// عینِ api/_core._PROC_TTL_S — نفسِ اندازه‌گیری‌شده، نه یک عددِ خودی.
	procCacheTTL = 10 * time.Second
	procTimeout  = 15 * time.Second
)

type journalEntry struct {
	rev   int64
	codes []string
}

type Service struct {
	market  *sql.DB
	user    *sql.DB
	dataDir string

	mu       sync.Mutex
	body     []byte
	etag     string
	builtAt  time.Time
	ready    bool
	building bool
	// builtToken همان نشانکِ (mtime_ns, size)ِ فایل‌هایِ داده است که آخرین
	// بازسازیِ کش‌شده دید؛ اختلافش با توکنِ فعلی یعنی «داده تازه است» — معادلِ
	// cur > mirror_rev در پایتون. کشِ بدنه هم همین را می‌سنجد: پایتون هر سینک را
	// با پاک‌کردنِ کش جواب می‌دهد، پس بدنهٔ داغ نباید ۶۰ ثانیه رویِ دادهٔ کهنه بماند.
	builtToken string
	// builds شمارندۀ بازسازی‌هایِ کامل‌شدۀ کش‌شده؛ تستِ دلتا با همین می‌بیند
	// بازسازیِ ناهمگام واقعاً اجرا شده است.
	builds int
	// cacheSeq با هر انتشارِ کش بالا می‌رود و فقط شناسهٔ نسلِ نقشهٔ byCode است:
	// دو map را نمی‌شود با == سنجید، ولی با این شمارنده می‌شود فهمید بازسازیِ
	// هم‌زمانی بینِ گرفتنِ نقشه و انتشارِ بعدی منتشر شده یا نه.
	cacheSeq int

	rev     int64
	byCode  map[string]map[string]any
	meta    map[string]any
	counts  map[string]any
	journal []journalEntry

	// recorder سابقۀ روزانۀ هفت فیلتر در user.db را می‌نویسد؛ قفلِ خودش را دارد،
	// پس با muِ کش قفل نمی‌شود.
	recorder *tapehistory.Recorder

	procMu    sync.Mutex
	procAt    time.Time
	procValue bool

	// frame قابِ ایستایِ کش‌شده و نشانکِ داده‌ای که با آن ساخته شده — همان
	// _STATIC_FRAMEِ پایتون در لایۀ Go. فقط RAM؛ هیچ نوشتنی به بانک ندارد.
	frameMu      sync.Mutex
	frame        *store.Frame
	frameNumeric map[string]bool
	frameToken   string
}

func New(h *db.Handles, dataDir string) *Service {
	return &Service{market: h.Market, user: h.User, dataDir: dataDir, recorder: tapehistory.NewRecorder()}
}

// symNorm همان str.maketransِ funnel_engine._SYM_TRANS است: ي/ى عربی → ی و ك → ک.
// همین تبدیل در mstat.normSymbol هم هست؛ کلیدِ نقشهٔ پرچم‌ها باید با آن یکی دربیاید.
var symNorm = strings.NewReplacer("\u064A", "\u06CC", "\u0649", "\u06CC", "\u0643", "\u06A9")

// symStrip همان str.strip()ِ پایتون (norm_symbol) رویِ لبهٔ نماد: U+001C..U+001F
// هم whitespaceِ پایتون‌اند ولی unicode.IsSpace نیستند.
func symStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1C && r <= 0x1F)
	})
}

// TapeFlags پرچم‌هایِ هفت‌گانهٔ ردیف‌هایِ تابلو، کلید = نمادِ نرمال‌شده. منبعش
// همان کشِ /api/market است (همان مسیری که پایتون در _board_snapshot می‌رود)،
// پس هیچ فرمولِ دومی ساخته نمی‌شود.
//
// از cached() می‌گذرد، نه build(): ساختِ بی‌قید در هر درخواستِ mainwatch،
// تابلوِ ۵٬۵هزارردیفی را از نو می‌ساخت و همان چیزی می‌شد که کشِ mstat برایِ
// حذفش هست. cached() داغ ⇒ بی‌محاسبه؛ سرد ⇒ یک ساخت؛ داده تازه ⇒ همان رفتارِ
// STALE و بازسازیِ پس‌زمینه. ok=false یعنی منبع نرسید (کش ساختنی نبود یا
// هنوز منتشر نشده) — با «هیچ پرچمی ندارد» یکی نیست.
func (s *Service) TapeFlags() (map[string]map[string]bool, bool) {
	if _, _, _, err := s.cached(); err != nil {
		return nil, false
	}
	s.mu.Lock()
	byCode := s.byCode
	s.mu.Unlock()
	if byCode == nil {
		return nil, false
	}
	keys := []string{"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal"}
	out := make(map[string]map[string]bool, len(byCode))
	for _, rec := range byCode {
		sym, _ := rec["symbol"].(string)
		key := symStrip(symNorm.Replace(sym))
		if key == "" {
			continue
		}
		flags := make(map[string]bool, len(keys))
		for _, k := range keys {
			b, _ := rec[k].(bool)
			flags[k] = b
		}
		out[key] = flags
	}
	// پایتون _tape_flag_map با نقشهٔ خالی ({}), «منبع نرسید» را یکی می‌داند
	// («if not flags: unavailable»)؛ همان قرارداد این‌جا هم برقرار است.
	return out, len(out) > 0
}

// boardFrame قابِ ایستایِ تابلو را زیرِ نشانکِ داده کش می‌کند — همان کاری که
// پایتون با _STATIC_FRAME/_static_key می‌کند. پایتون کلید را از شمارنده‌هایِ
// درون‌پروسه (sync_count، session_day، static_rev) می‌سازد؛ در فازِ الفِ Go
// چنین شمارنده‌ای نیست، پس همان نشانکِ فایل‌هایِ داده نقشش را دارد: هر نویسنده
// که محتوایِ تابلو را عوض کند دست‌کم mtime/size یکی از سه فایلِ توکن را عوض
// می‌کند. بی‌این کش، هر بازسازی کوئریِ سنگینِ تابلو را از نو می‌زد و از پایتون
// کندتر می‌شد، درحالی‌که پایتون قابِ ایستا را در RAM نگه می‌دارد.
func (s *Service) boardFrame(token string) (*store.Frame, map[string]bool, error) {
	s.frameMu.Lock()
	if s.frame != nil && s.frameToken == token {
		fr, numeric := s.frame, s.frameNumeric
		s.frameMu.Unlock()
		return fr, numeric, nil
	}
	s.frameMu.Unlock()
	// بارگذاری بیرونِ قفل: دو بازسازیِ هم‌زمان حداکثر دو بار می‌خوانند، ولی
	// هیچ درخواستی پشتِ کوئریِ سنگینِ تابلو نمی‌ماند.
	fr, err := store.LoadBoard(s.market)
	if err != nil {
		return nil, nil, err
	}
	// نوعِ هر ستون یک‌بار بر قاب حساب می‌شود، نه یک‌بار بر بازسازی.
	numeric := numericCols(fr)
	s.frameMu.Lock()
	s.frame, s.frameNumeric, s.frameToken = fr, numeric, token
	s.frameMu.Unlock()
	return fr, numeric, nil
}

func (s *Service) Board(w http.ResponseWriter, r *http.Request) {
	if r.URL.Query().Get("fields") == "all" {
		body, etag, err := s.build(false, false)
		if err != nil {
			httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
			return
		}
		if inm := r.Header.Get("If-None-Match"); inm != "" && inm == etag {
			w.Header().Set("ETag", etag)
			// این ۳۰۴ پاسخِ مسیرِ ساخت است، نه کشِ داغ: پایتون هم همین‌جا
			// X-Cache: MISS-304 می‌فرستد.
			w.Header().Set("X-Cache", "MISS-304")
			w.WriteHeader(http.StatusNotModified)
			return
		}
		writeBody(w, body, etag, "MISS")
		return
	}
	body, etag, xcache, err := s.cached()
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	if inm := r.Header.Get("If-None-Match"); inm != "" && inm == etag {
		w.Header().Set("ETag", etag)
		// کشِ داغ (HIT/STALE) مثلِ _market_from_cache فقط ETag می‌دهد؛ فقط
		// ساختِ سرد (MISS) نشانکِ MISS-304 می‌گیرد.
		if xcache == "MISS" {
			w.Header().Set("X-Cache", "MISS-304")
		}
		w.WriteHeader(http.StatusNotModified)
		return
	}
	writeBody(w, body, etag, xcache)
}

func writeBody(w http.ResponseWriter, body []byte, etag, xcache string) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "max-age=15")
	w.Header().Set("X-Cache", xcache)
	w.Header().Set("ETag", etag)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(body)
}

func (s *Service) cached() ([]byte, string, string, error) {
	s.mu.Lock()
	body, etag, builtAt, ready, builtToken := s.body, s.etag, s.builtAt, s.ready, s.builtToken
	s.mu.Unlock()
	if !ready {
		b, e, err := s.build(true, true)
		if err != nil {
			return nil, "", "", err
		}
		return b, e, "MISS", nil
	}
	// درِ توکن پیش از درِ عمر: پایتون _STATIC_FRAME/کش را با هر سینک پاک می‌کند،
	// پس بدنهٔ تازه‌ساخته هم اگر داده زیرش عوض شده باشد نباید HIT بگیرد. رفتار
	// همان مسیرِ STALE است: بدنهٔ فعلی می‌رود و یک بازسازیِ ناهمگام شروع می‌شود.
	age := time.Since(builtAt)
	if age < ttl {
		if dataToken(s.dataDir) == builtToken {
			return body, etag, "HIT", nil
		}
		s.rebuildAsync()
		return body, etag, "STALE", nil
	}
	if age > staleCeiling {
		b, e, err := s.build(true, true)
		if err != nil {
			return nil, "", "", err
		}
		return b, e, "MISS", nil
	}
	s.rebuildAsync()
	return body, etag, "STALE", nil
}

func (s *Service) rebuildAsync() {
	s.mu.Lock()
	if s.building {
		s.mu.Unlock()
		return
	}
	s.building = true
	s.mu.Unlock()
	go func() {
		defer func() {
			s.mu.Lock()
			s.building = false
			s.mu.Unlock()
		}()
		if _, _, err := s.build(true, true); err != nil {
			// خطایِ بازسازیِ ناهمگام به پاسخِ HTTP نمی‌رسد؛ بی‌این خط، شکستِ
			// کشِ داغ در لاگ هیچ اثری نمی‌گذاشت (پایتون هم چاپ می‌کند).
			log.Printf("[market] background rebuild failed: %v", err)
		}
	}()
}

func (s *Service) build(dropUnused, storeCache bool) ([]byte, string, error) {
	// توکنِ همین بازسازی: اگر سینکر وسطِ کار فایلش را عوض کند، بازسازیِ بعدی
	// آن را می‌بیند و یک بار دیگر می‌سازد.
	token := dataToken(s.dataDir)
	fr, numeric, err := s.boardFrame(token)
	if err != nil {
		return nil, "", err
	}
	d := board.Derive(fr)
	fl := tapeflags.Apply(fr, d)
	recs := assemble(fr, d, fl, numeric)
	meta, err := boardMeta(s.market)
	if err != nil {
		return nil, "", err
	}
	// روزِ نشست را پایتون از market_state (تیکِ زنده) می‌گیرد، نه از d_evenِ متا.
	// در پروسۀ فازِ الف هیچ تیکی اجرا نمی‌شود، پس همان صفر است — و این در بدنۀ
	// پیش‌فرض دیده می‌شود: d_even از ردیف حذف شده، پس _state_reasonِ پایتون به
	// fallbackِ d_evenِ ردیف نمی‌رسد و علت را «از نشستِ ...» می‌نویسد. d_evenِ
	// متا این fallback را زنده نگه می‌داشت و «طی معاملات» می‌گفت (اختلافِ واقعیِ
	// B1 رویِ ردیفِ 3202).
	sessionDay := int64(0)
	// ثبتِ سابقۀ پرچم‌ها — همان side effectِ پایتون، پیش از حذفِ ستون‌ها. روزِ ثبت
	// از ردیف‌هایِ زندهٔ همین قاب می‌آید (عینِ int(_live_df["d_even"].max() or 0))،
	// نه از d_evenِ متا؛ و نشانه dataToken است تا با نبودنِ market_sync.json هم
	// درِ «همان داده» خاموش نشود.
	if day := recordDay(recs); day != 0 {
		_, _ = s.recorder.Record(s.user, recs, day, token, time.Now())
	}
	if dropUnused {
		dropUnusedFields(recs)
	}
	for _, rec := range recs {
		ok, code, reason := screening.Eligibility(rec, sessionDay)
		rec["screening_eligible"] = ok
		if !ok {
			rec["screening_exclusion_code"] = code
			rec["screening_exclusion_reason"] = reason
		}
	}
	live := 0
	for _, rec := range recs {
		if v, _ := rec["is_live"].(bool); v {
			live++
		}
	}
	counts := map[string]any{"count": len(recs), "live_count": live, "fossil_count": len(recs) - live}

	// نقشهٔ کهنه را زیرِ قفل برمی‌داریم و مقایسه را بیرون انجام می‌دهیم: byCode
	// فقط جایگزین می‌شود، هرگز درجا تغییر نمی‌کند، پس مرجعِ گرفته‌شده امن است و
	// marshalِ ۱۲ مگابایتیِ ردیف‌هایِ کهنه/تازه دیگر mu را ۱۰۰ تا ۲۰۰ میلی‌ثانیه
	// نگه نمی‌دارد (هر بازسازیِ کش‌شده یک درخواستِ تابلو را پشتِ خود می‌خواباند).
	s.mu.Lock()
	oldByCode, oldSeq := s.byCode, s.cacheSeq
	rev := s.rev
	s.mu.Unlock()
	var changed []string
	if storeCache && oldByCode != nil {
		changed = diffCodes(oldByCode, recs)
	}

	// انتشار دوباره زیرِ قفل: rev و journal باید عینِ مسیرِ پیشین بمانند. اگر در
	// این فاصله بازسازیِ هم‌زمانی منتشر شده باشد، مقایسه رویِ نقشهٔ تازه تکرار
	// می‌شود تا دلتا همان چیزی باشد که پشتِ‌سرِهم بودن می‌داد.
	s.mu.Lock()
	if storeCache && oldByCode != nil && s.cacheSeq != oldSeq {
		changed = nil
		if s.byCode != nil {
			changed = diffCodes(s.byCode, recs)
		}
	}
	rev = s.rev
	if storeCache && oldByCode != nil && len(changed) > 0 {
		rev++
		s.journal = append(s.journal, journalEntry{rev: rev, codes: changed})
		if len(s.journal) > journalMax {
			s.journal = s.journal[len(s.journal)-journalMax:]
		}
	}
	s.mu.Unlock()

	payload := map[string]any{
		"status": "success", "rev": rev, "data": recs, "meta": meta,
		"count": len(recs), "live_count": live, "fossil_count": len(recs) - live,
	}
	body, err := marshalBoard(payload)
	if err != nil {
		return nil, "", err
	}
	sum := md5.Sum(body)
	etag := `"` + hex.EncodeToString(sum[:])[:16] + `"`

	if storeCache {
		s.mu.Lock()
		s.body, s.etag, s.builtAt, s.ready = body, etag, time.Now(), true
		s.byCode = indexByCode(recs)
		s.meta, s.counts, s.rev = meta, counts, rev
		s.builtToken = token
		s.builds++
		s.cacheSeq++
		s.mu.Unlock()
	}
	return body, etag, nil
}

func indexByCode(recs []map[string]any) map[string]map[string]any {
	out := make(map[string]map[string]any, len(recs))
	for _, r := range recs {
		if code, ok := r["ins_code"].(string); ok {
			out[code] = r
		}
	}
	return out
}

func diffCodes(old map[string]map[string]any, recs []map[string]any) []string {
	var out []string
	seen := make(map[string]bool, len(recs))
	for _, r := range recs {
		code, _ := r["ins_code"].(string)
		seen[code] = true
		prev, ok := old[code]
		if !ok || !sameRecord(prev, r) {
			out = append(out, code)
		}
	}
	// کدِ رفته: همان مجموعه، بی اسکنِ خطی برایِ هر کد — رویِ تابلو (~۵٬۵۰۰
	// ردیف) حلقهٔ تو‌در‌تو ۳۰ میلیون مقایسه در هر بازسازی می‌شد.
	for code := range old {
		if !seen[code] {
			out = append(out, code)
		}
	}
	return out
}

func sameRecord(a, b map[string]any) bool {
	x, err1 := json.Marshal(a)
	y, err2 := json.Marshal(b)
	return err1 == nil && err2 == nil && string(x) == string(y)
}

func boardMeta(db *sql.DB) (map[string]any, error) {
	var dEven, hEven sql.NullInt64
	var lastSync sql.NullString
	err := db.QueryRow("SELECT d_even, MAX(h_even), MAX(fetched_at) FROM market_watch"+
		" WHERE d_even = (SELECT MAX(d_even) FROM market_watch)").Scan(&dEven, &hEven, &lastSync)
	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}
	meta := map[string]any{"d_even": nil, "h_even": nil, "last_sync": nil}
	if err == nil {
		// ردیفِ تجمیع وجود دارد ⇒ عینِ int(_r[0] or 0): NULLِ d_even/h_even
		// صفر می‌شود و فقط last_sync می‌تواند null بماند.
		meta["d_even"], meta["h_even"] = int64(0), int64(0)
		if dEven.Valid {
			meta["d_even"] = dEven.Int64
		}
		if hEven.Valid {
			meta["h_even"] = hEven.Int64
		}
		if lastSync.Valid {
			meta["last_sync"] = lastSync.String
		}
	}
	return meta, nil
}

func (s *Service) Delta(w http.ResponseWriter, r *http.Request) {
	since, _ := strconv.ParseInt(r.URL.Query().Get("since"), 10, 64)
	if r.URL.Query().Get("since") == "" {
		since = -1
	}
	payload := s.delta(since)
	// عینِ _ORJ_JSONِ پایتون: پاسخِ دلتا هرگز کش نمی‌شود.
	w.Header().Set("Cache-Control", "no-store")
	httpapi.WriteJSON(w, http.StatusOK, payload)
}

func (s *Service) delta(since int64) map[string]any {
	s.mu.Lock()
	ready, mirrorRev, meta, counts, byCode, journal := s.ready, s.rev, s.meta, s.counts, s.byCode, s.journal
	builtToken := s.builtToken
	s.mu.Unlock()
	if !ready {
		s.rebuildAsync()
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "no-cache"}
	}
	// فازِ الف: به‌جایِ cur > mirror_revِ پایتون، نشانکِ فایل‌هایِ داده را
	// می‌سنجیم. مشتریِ دلتا دیگر پشتِ کشِ ۶۰ثانیه‌ای گیر نمی‌کند: هر سینکِ
	// موفق یا هر کامیتِ tick_live بازسازیِ ناهمگام را راه می‌اندازد و ردیف‌هایِ
	// تازه به آینه می‌رسند.
	if dataToken(s.dataDir) != builtToken {
		s.rebuildAsync()
	}
	if since == mirrorRev {
		return withCounts(map[string]any{"status": "unchanged", "rev": mirrorRev, "meta": meta}, counts)
	}
	if since < 0 {
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "no-cache"}
	}
	if since > mirrorRev {
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "stale-client"}
	}
	if len(journal) == 0 || journal[0].rev-1 > since {
		return map[string]any{"status": "full", "rev": mirrorRev, "reason": "journal-gap"}
	}
	codes := map[string]bool{}
	for _, e := range journal {
		if since < e.rev && e.rev <= mirrorRev {
			for _, c := range e.codes {
				codes[c] = true
			}
		}
	}
	rows := make([]map[string]any, 0, len(codes))
	for c := range codes {
		row, ok := byCode[c]
		if !ok {
			return map[string]any{"status": "full", "rev": mirrorRev, "reason": "missing-rows"}
		}
		rows = append(rows, row)
	}
	return withCounts(map[string]any{"status": "delta", "rev": mirrorRev, "rows": rows, "meta": meta}, counts)
}

func withCounts(m, counts map[string]any) map[string]any {
	for k, v := range counts {
		m[k] = v
	}
	return m
}

func (s *Service) SyncState(w http.ResponseWriter, r *http.Request) {
	last := map[string]any{}
	if raw, err := os.ReadFile(filepath.Join(s.dataDir, "market_sync.json")); err == nil {
		_ = json.Unmarshal(raw, &last)
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "success", "running": s.marketRunning(), "last": last,
	})
}

// recordDay روزِ ثبتِ سابقه را از خودِ ردیف‌هایِ زندهٔ قاب می‌گیرد — عینِ
// int(_live_df["d_even"].max() or 0) در api/market.py؛ نه d_evenِ متای تابلو.
// صفر یعنی «ردیفِ زندهٔ روزدار نداری» و ثبت انجام نمی‌شود. d_even در این‌جا
// int64 است (ستونِ INTEGER) یا float64 (قابِ ساختگی/نوعِ REAL)؛ put مقدارِ
// NaN را پیش‌تر به 0.0 کرده، پس تنها همین دو نوع می‌رسند.
func recordDay(recs []map[string]any) int64 {
	var day int64
	for _, rec := range recs {
		if live, _ := rec["is_live"].(bool); !live {
			continue
		}
		switch v := rec["d_even"].(type) {
		case int64:
			if v > day {
				day = v
			}
		case float64:
			if d := int64(v); d > day {
				day = d
			}
		}
	}
	return day
}

// marketRunning عینِ _count_procs("test_tsetmc") با کشِ ۱۰ثانیه‌ای.
func (s *Service) marketRunning() bool {
	s.procMu.Lock()
	defer s.procMu.Unlock()
	if time.Since(s.procAt) < procCacheTTL {
		return s.procValue
	}
	s.procAt = time.Now()
	s.procValue = false
	ctx, cancel := context.WithTimeout(context.Background(), procTimeout)
	defer cancel()
	ps := exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-Command",
		"(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'test_tsetmc' }).Count")
	hideWindow(ps)
	out, err := ps.Output()
	if err == nil {
		n, _ := strconv.Atoi(strings.TrimSpace(string(out)))
		s.procValue = n > 0
	}
	return s.procValue
}

// dataToken «این داده نو است» را از خودِ فایل‌هایِ داده می‌گیرد. هر سینکِ موفق
// market_sync.json را بازنویسی می‌کند، و tick_live هر ۵ ثانیه ردیف‌ها را در
// market.db (با WAL) کامیت می‌کند بی آنکه آن فایل را دست بزند؛ پس فقط
// (mtime_ns, size)ِ market_sync.json کافی نیست و هر سه فایل باید در توکن باشند —
// همان نقشی که revision() و sync_count در پروسۀ پایتون داشتند. غایب ⇒ "-"، تا
// توکن پایدار بماند. فقط os.Stat: نه بازکردنِ SQLite، نه خواندنِ محتوا.
func dataToken(dataDir string) string {
	var b strings.Builder
	for _, name := range []string{"market_sync.json", "market.db", "market.db-wal"} {
		if b.Len() > 0 {
			b.WriteByte('|')
		}
		st, err := os.Stat(filepath.Join(dataDir, name))
		if err != nil {
			b.WriteByte('-')
			continue
		}
		b.WriteString(strconv.FormatInt(st.ModTime().UnixNano(), 10))
		b.WriteByte(':')
		b.WriteString(strconv.FormatInt(st.Size(), 10))
	}
	return b.String()
}
