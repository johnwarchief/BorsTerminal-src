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

	"borsterminal/backend/internal/board"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/screening"
	"borsterminal/backend/internal/store"
	"borsterminal/backend/internal/tapeflags"
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
	// builtToken همان نشانکِ (mtime_ns, size)ِ market_sync.json است که آخرین
	// بازسازیِ کش‌شده دید؛ اختلافش با توکنِ فعلی یعنی «داده تازه است» — معادلِ
	// cur > mirror_rev در پایتون.
	builtToken string
	// builds شمارندۀ بازسازی‌هایِ کامل‌شدۀ کش‌شده؛ تستِ دلتا با همین می‌بیند
	// بازسازیِ ناهمگام واقعاً اجرا شده است.
	builds int

	rev     int64
	byCode  map[string]map[string]any
	meta    map[string]any
	counts  map[string]any
	journal []journalEntry

	procMu    sync.Mutex
	procAt    time.Time
	procValue bool
}

func New(h *db.Handles, dataDir string) *Service {
	return &Service{market: h.Market, user: h.User, dataDir: dataDir}
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
	body, etag, builtAt, ready := s.body, s.etag, s.builtAt, s.ready
	s.mu.Unlock()
	if !ready {
		b, e, err := s.build(true, true)
		if err != nil {
			return nil, "", "", err
		}
		return b, e, "MISS", nil
	}
	age := time.Since(builtAt)
	if age < ttl {
		return body, etag, "HIT", nil
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
	token := syncToken(s.dataDir)
	fr, err := store.LoadBoard(s.market)
	if err != nil {
		return nil, "", err
	}
	d := board.Derive(fr)
	fl := tapeflags.Apply(fr, d)
	recs := assemble(fr, d, fl, dropUnused)
	meta, err := boardMeta(s.market)
	if err != nil {
		return nil, "", err
	}
	sessionDay := int64(0)
	if v, ok := meta["d_even"].(int64); ok {
		sessionDay = v
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

	s.mu.Lock()
	rev := s.rev
	var changed []string
	if storeCache && s.byCode != nil {
		changed = diffCodes(s.byCode, recs)
		if len(changed) > 0 {
			rev++
			s.journal = append(s.journal, journalEntry{rev: rev, codes: changed})
			if len(s.journal) > journalMax {
				s.journal = s.journal[len(s.journal)-journalMax:]
			}
		}
	}
	s.mu.Unlock()

	payload := map[string]any{
		"status": "success", "rev": rev, "data": recs, "meta": meta,
		"count": len(recs), "live_count": live, "fossil_count": len(recs) - live,
	}
	body, err := json.Marshal(payload)
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
	// فازِ الف: به‌جایِ cur > mirror_revِ پایتون، نشانکِ market_sync.json را
	// می‌سنجیم. مشتریِ دلتا دیگر پشتِ کشِ ۶۰ثانیه‌ای گیر نمی‌کند: هر سینکِ
	// موفق بازسازیِ ناهمگام را راه می‌اندازد و ردیف‌هایِ تازه به آینه می‌رسند.
	if syncToken(s.dataDir) != builtToken {
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

// syncToken «این داده نو است» را از خودِ فایلِ سینکر می‌گیرد: هر سینکِ موفق
// market_sync.json را بازنویسی می‌کند، پس (mtime_ns, size) همان نقشی را دارد
// که sync_count در پروسۀ پایتون داشت.
func syncToken(dataDir string) string {
	p := filepath.Join(dataDir, "market_sync.json")
	st, err := os.Stat(p)
	if err != nil {
		return ""
	}
	return strconv.FormatInt(st.ModTime().UnixNano(), 10) + ":" + strconv.FormatInt(st.Size(), 10)
}
