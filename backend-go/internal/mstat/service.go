package mstat

import (
	"database/sql"
	"fmt"
	"sync"
	"time"

	"borsterminal/backend/internal/datatoken"
)

const (
	// عینِ _MSTAT_TTL_S و _MSTAT_STALE_MAX_S در api/market_status.py.
	DefaultTTL = 45 * time.Second
	StaleMax   = 90 * time.Second
)

type entry struct {
	at   time.Time
	body map[string]any
}

// Options رفتارِ کشِ یکِ پنل را می‌گوید.
type Options struct {
	// TTL صفر یعنی پیش‌فرضِ ۴۵ثانیه‌ای؛ منفی یعنی بی‌کش (ttl_s=0ِ پایتون).
	TTL time.Duration
	// Inline معادلِ refresh="inline": بی‌کش و همیشه‌تازه.
	Inline bool
	// StaleOK=false برایِ پنل‌هایی است که عددشان از ساعتِ دیوار ساخته می‌شود
	// (phase): کهنه سرو نمی‌شود.
	StaleOK bool
}

// Service همان لایهٔ _mstat_call: کشِ هر-حالت، stale-while-revalidate،
// تک‌پروازگی برایِ cold miss، و خطا که هرگز کش نمی‌شود.
type Service struct {
	db      *sql.DB
	dataDir string
	flags   FlagSource

	mu      sync.Mutex
	cache   map[string]entry
	flights map[string]chan struct{}
	clock   func() time.Time
	// memo همان _ASSESS/_STATE_MEMOِ درون‌فرآیندی است؛ با هر Service تازه
	// صفر می‌شود و فقط رویِ cache-miss به‌روز می‌شود.
	memo *verdictMemo
}

func New(db *sql.DB, dataDir string, flags FlagSource) *Service {
	return &Service{db: db, dataDir: dataDir, flags: flags,
		cache: map[string]entry{}, flights: map[string]chan struct{}{},
		clock: time.Now, memo: newVerdictMemo()}
}

func (s *Service) Call(key string, fn func() (map[string]any, error), opt Options) map[string]any {
	ttl := opt.TTL
	if ttl == 0 {
		ttl = DefaultTTL
	}
	if ttl < 0 || opt.Inline {
		return cloneMap(s.compute(fn))
	}
	state, ok := s.state()
	if !ok {
		// پایتون هم وقتی نشانه‌ای ندارد (جدولِ mstat_snap نیست) کش را کامل دور
		// می‌زند؛ بی‌این، Go رویِ بانکِ بی‌mstat_snap چیزی را کش می‌کرد که
		// پایتون نمی‌کرد.
		return cloneMap(s.compute(fn))
	}
	full := key + "\x00" + state
	now := s.clock()

	s.mu.Lock()
	hit, ok := s.cache[full]
	if ok && now.Sub(hit.at) < ttl {
		out := cloneMap(hit.body)
		s.mu.Unlock()
		return out
	}
	if ok && opt.StaleOK && now.Sub(hit.at) <= StaleMax {
		if _, busy := s.flights[full]; !busy {
			done := make(chan struct{})
			s.flights[full] = done
			s.mu.Unlock()
			go func() {
				defer s.finish(full, done)
				s.store(full, s.compute(fn), s.clock())
			}()
		} else {
			s.mu.Unlock()
		}
		return cloneMap(hit.body)
	}
	if done, busy := s.flights[full]; busy {
		// یکی دیگر دارندۀ همین cold miss است؛ منتظرِ همان یک نتیجه می‌مانیم،
		// بی‌این‌که دوباره بسازیم. بی‌پاسخ بماند، همان مسیرِ بی‌کش را می‌رویم.
		s.mu.Unlock()
		select {
		case <-done:
		case <-time.After(5*time.Second + ttl + StaleMax):
		}
		s.mu.Lock()
		hit2, ok2 := s.cache[full]
		s.mu.Unlock()
		if ok2 {
			return cloneMap(hit2.body)
		}
		return cloneMap(s.compute(fn))
	}
	done := make(chan struct{})
	s.flights[full] = done
	s.mu.Unlock()
	defer s.finish(full, done)
	out := s.compute(fn)
	s.store(full, out, now)
	return cloneMap(out)
}

func (s *Service) compute(fn func() (map[string]any, error)) (out map[string]any) {
	// recover عینِ except در _mstat_compute: پنیکِ یک پنل نباید borsd را بکشد و
	// باید همان بدنهٔ status=error را بدهد (هم در مسیرِ درون‌خطی، هم پس‌زمینه).
	defer func() {
		if r := recover(); r != nil {
			out = map[string]any{"status": "error", "message": fmt.Sprint(r),
				"source": mstatSource}
		}
	}()
	out, err := fn()
	if err != nil {
		// یک پنلِ خراب نباید کل تب را ۵۰۰ کند؛ پایتون هم status=error می‌دهد.
		return map[string]any{"status": "error", "message": err.Error(),
			"source": mstatSource}
	}
	if out == nil {
		out = map[string]any{}
	}
	if _, ok := out["source"]; !ok {
		out["source"] = mstatSource
	}
	return out
}

func (s *Service) store(full string, body map[string]any, at time.Time) {
	if body == nil || body["status"] == "error" {
		return
	}
	s.mu.Lock()
	if len(s.cache) > 240 {
		s.cache = map[string]entry{}
	}
	s.cache[full] = entry{at: at, body: body}
	s.mu.Unlock()
}

func (s *Service) finish(full string, done chan struct{}) {
	s.mu.Lock()
	delete(s.flights, full)
	s.mu.Unlock()
	close(done)
}

// state همان نقشِ (revision، static_rev، session_day، marker)ِ پایتون را دارد:
// در فازِ الف شمارندهٔ درون‌پروسه‌ای نیست، پس نشانکِ فایل‌هایِ داده به‌جایِ آن
// می‌نشیند (همان قاعدهٔ کشِ تابلو در B1) و نشانِ mstat_snap جدا افزوده می‌شود.
func (s *Service) state() (string, bool) {
	d, h, ok := mstatMarker(s.db)
	if !ok {
		return "", false
	}
	return datatoken.FileToken(s.dataDir) + "|" + fmt.Sprintf("%d:%d", d, h), true
}

// mstatMarker همان _mstat_marker: آخرین (روز، ساعت)ِ ثبت‌شده در mstat_snap.
// نبودِ جدول یا نبودِ بانک ⇒ ok=false (کش بی‌استفاده می‌شود).
func mstatMarker(db *sql.DB) (int64, int64, bool) {
	if db == nil {
		return 0, 0, false
	}
	var d, h sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even), MAX(h_even) FROM mstat_snap").Scan(&d, &h); err != nil {
		return 0, 0, false
	}
	return d.Int64, h.Int64, true
}

func cloneMap(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}
