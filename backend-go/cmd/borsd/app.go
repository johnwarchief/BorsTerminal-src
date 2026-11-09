package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"borsterminal/backend/internal/chart"
	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/export"
	"borsterminal/backend/internal/ftsconfig"
	"borsterminal/backend/internal/fundamental"
	"borsterminal/backend/internal/funnel"
	"borsterminal/backend/internal/generation"
	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/jobs"
	"borsterminal/backend/internal/live"
	"borsterminal/backend/internal/market"
	"borsterminal/backend/internal/marketindex"
	"borsterminal/backend/internal/mstat"
	"borsterminal/backend/internal/notifications"
	"borsterminal/backend/internal/ocdata"
	"borsterminal/backend/internal/ocdb"
	"borsterminal/backend/internal/ocnotify"
	"borsterminal/backend/internal/screener"
	"borsterminal/backend/internal/selection"
	"borsterminal/backend/internal/snapshot"
	borssync "borsterminal/backend/internal/sync"
	"borsterminal/backend/internal/watchlist"
)

// appInstance یک نسلِ کاملِ سرویس‌هاست: handleهایِ دیتابیس، سرویس‌ها و هندلر.
// هر درخواست یک ref می‌گیرد؛ تعویض، نسخهٔ قبلی را «بازنشسته» می‌کند و بستن
// فقط وقتی رخ می‌دهد که آخرین درخواستِ در جریان تمام شود (بدونِ بستنِ ناگهانی).
type appInstance struct {
	info    generation.Info
	handles *db.Handles
	handler http.Handler
	closers []func() error

	refs    atomic.Int64
	retired atomic.Bool
	closed  chan struct{}
	once    sync.Once
}

func (i *appInstance) acquire() {
	i.refs.Add(1)
}

func (i *appInstance) release() {
	if i.refs.Add(-1) == 0 && i.retired.Load() {
		i.close()
	}
}

func (i *appInstance) close() {
	i.once.Do(func() {
		for _, fn := range i.closers {
			if fn == nil {
				continue
			}
			if err := fn(); err != nil {
				slog.Warn("instance cleanup failed", "err", err)
			}
		}
		close(i.closed)
	})
}

// runtime نسلِ فعال را می‌داند، سرویس‌ها را از همان نسل می‌سازد و پس از
// Apply/Rollback اتمیک تعویض می‌کند. خودش Providerِ /api/oc/data است.
type runtime struct {
	ctx      context.Context
	cfg      config.Config
	resolver *generation.Resolver
	data     *ocdata.Handler
	jobs     *jobs.Manager
	oc       *ocdb.Store
	notify   *ocnotify.Store

	swapMu sync.Mutex
	cur    atomic.Pointer[appInstance]
}

func newRuntime(ctx context.Context, cfg config.Config) (*runtime, error) {
	ocStore, err := ocdb.Open(cfg.DataDir)
	if err != nil {
		return nil, err
	}
	rt := &runtime{ctx: ctx, cfg: cfg, resolver: generation.New(cfg.DataDir),
		jobs: jobs.NewManager(), oc: ocStore, notify: ocnotify.NewStore(ocStore.DB)}
	rt.data = ocdata.NewHandler(rt)

	info, err := rt.resolver.Resolve()
	if err != nil {
		_ = ocStore.Close()
		return nil, err
	}
	inst, err := rt.build(info)
	if err != nil {
		_ = ocStore.Close()
		return nil, err
	}
	rt.cur.Store(inst)
	return rt, nil
}

func (rt *runtime) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	inst := rt.cur.Load()
	if inst == nil {
		httpapi.WriteJSON(w, http.StatusServiceUnavailable, map[string]any{
			"status": "error", "code": "NO_ACTIVE_GENERATION",
		})
		return
	}
	inst.acquire()
	defer inst.release()
	inst.handler.ServeHTTP(w, r)
}

// Reload اشاره‌گرِ نسل را دوباره می‌خواند؛ اگر نسل عوض شده باشد نسخهٔ تازه
// ساخته و اتمیک جایگزین می‌شود. خطای ساخت ⇒ نسخهٔ فعلی دست‌نخورده می‌ماند.
func (rt *runtime) Reload() error {
	rt.swapMu.Lock()
	defer rt.swapMu.Unlock()

	info, err := rt.resolver.Resolve()
	if err != nil {
		return err
	}
	cur := rt.cur.Load()
	if cur != nil && cur.info.Identity() == info.Identity() {
		return nil
	}
	inst, err := rt.build(info)
	if err != nil {
		return err
	}
	rt.cur.Store(inst)
	if cur != nil {
		cur.retired.Store(true)
		cur.release() // ref پایه؛ close فقط بعد از تخلیهٔ درخواست‌ها
	}
	slog.Info("active generation switched", "generation", info.Identity(),
		"market_db", info.MarketPath)
	return nil
}

func (rt *runtime) Rollback() error {
	applier, err := newSnapshotApplier(rt.cfg.DataDir)
	if err != nil {
		return err
	}
	if err := applier.Rollback(); err != nil {
		return err
	}
	return rt.Reload()
}

// DataStatus وضعیتِ «آن‌چه سرو می‌شود» و «آن‌چه روی دیسک است» را جدا می‌دهد؛
// اختلافشان یعنی Apply انجام شده ولی Reload نه.
func (rt *runtime) DataStatus() map[string]any {
	inst := rt.cur.Load()
	serving := map[string]any{"mode": "none"}
	if inst != nil {
		info := inst.info
		serving = map[string]any{
			"mode":           "legacy",
			"market_db":      info.MarketPath,
			"codal_db":       nilIfEmpty(info.CodalPath),
			"user_dir":       info.UserDir,
			"generation_dir": nilIfEmpty(info.GenerationDir),
		}
		if info.Active && info.Pointer != nil {
			serving["mode"] = "generation"
			serving["snapshot_set_id"] = info.Pointer.SnapshotSetID
			serving["schema_version"] = info.Pointer.SchemaVersion
			serving["applied_at_utc"] = info.Pointer.AppliedAtUTC
			serving["previous_snapshot_set_id"] = nilIfEmpty(info.Pointer.PreviousSnapshotSetID)
		}
	}

	pointer := map[string]any{"present": false}
	ptr, err := rt.resolver.CurrentPointer()
	if err != nil {
		pointer["error"] = err.Error()
	} else if ptr != nil {
		pointer = map[string]any{
			"present":         true,
			"snapshot_set_id": ptr.SnapshotSetID,
			"generation_dir":  ptr.GenerationDir,
			"schema_version":  ptr.SchemaVersion,
			"applied_at_utc":  ptr.AppliedAtUTC,
		}
	}

	out := map[string]any{
		"status":       "ok",
		"data_dir":     rt.cfg.DataDir,
		"oc_client_db": rt.oc.Path,
		"serving":      serving,
		"pointer":      pointer,
	}
	if inst != nil && ptr != nil {
		out["pending_reload"] = inst.info.Identity() != "gen:"+ptr.SnapshotSetID
	}
	return out
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func (rt *runtime) build(info generation.Info) (*appInstance, error) {
	handles, err := db.OpenResolved(info.MarketPath, info.CodalPath, info.UserDir, rt.cfg.ReadOnly)
	if err != nil {
		return nil, err
	}

	closers := []func() error{handles.Close}
	fail := func(err error) (*appInstance, error) {
		for _, fn := range closers {
			_ = fn()
		}
		return nil, err
	}

	cfg := rt.cfg
	mkt := market.NewWithOptions(handles, cfg.DataDir, cfg.ReadOnly, cfg.NoLoops)
	var liveFeed *live.Feed
	// Only one TSE live loop may exist at a time (owner decision §9). The Go
	// feed is opt-in so a Python live loop can stay the sole owner until the
	// operator flips BORS_GO_LIVE=1 and stops it.
	// In addition, if cfg.NoLoops is active, no background loop may start.
	// And if cfg.ReadOnly is active, live persistence to market.db is strictly forbidden.
	if !cfg.NoLoops && envBool(os.Getenv("BORS_GO_LIVE")) {
		interval := 1500 * time.Millisecond
		if ms, err := strconv.Atoi(os.Getenv("BORS_GO_LIVE_MS")); err == nil && ms >= 500 {
			interval = time.Duration(ms) * time.Millisecond
		}
		feed := live.New(interval)
		// در حالتِ نسل، نوشتن در dataDir/market.db یعنی دو منبعِ داده هم‌زمان؛
		// فید فقط در حافظه می‌ماند.
		if !cfg.ReadOnly && !info.Active && envBoolDefault(os.Getenv("BORS_GO_LIVE_PERSIST")) {
			feed.EnablePersistence(filepath.Join(cfg.DataDir, "market.db"), 5*time.Second)
		}
		mkt.Live = feed
		liveFeed = feed
		closers = append(closers, feed.Close)
	}
	if liveFeed != nil {
		liveFeed.Start(rt.ctx)
	}
	ms := mstat.NewWithOptions(handles.Market, cfg.DataDir, mkt, cfg.NoLoops)
	ch := chart.New(chart.Config{Market: handles.Market, User: handles.User,
		DataDir: cfg.DataDir, CalendarPath: cfg.CalendarPath})
	closers = append(closers, ch.Close)
	fd := fundamental.New(handles.Market, cfg.DataDir)
	closers = append(closers, fd.Close)

	wlStore, err := watchlist.NewStore(handles.User, cfg.DataDir)
	if err != nil {
		return fail(err)
	}
	wl := watchlist.NewHandler(wlStore, cfg.ReadOnly)

	ntSvc := notifications.NewService(handles.Market)
	closers = append(closers, ntSvc.Close)
	nt := notifications.NewHandler(ntSvc)

	sy := borssync.NewHandlerWithJobs(cfg.DataDir, rt.jobs)
	sy.SetReloadHook(rt.Reload)
	sel := selection.NewService(handles.Market, handles.User)
	mi := marketindex.NewService(cfg.DataDir, nil)
	exp := export.NewService(handles.Market)
	scr := screener.NewService(handles.Market, cfg.DataDir)
	fn := funnel.NewService(handles.Market, cfg.DataDir)

	ftsCfgStore, err := ftsconfig.NewStore(handles.User)
	if err != nil {
		slog.Error("fts config store init failed", "err", err)
	}
	ftsCfg := ftsconfig.NewHandler(ftsCfgStore, cfg.ReadOnly)

	apiHandler := httpapi.NewWithServices(cfg, handles, httpapi.Services{
		Market:        mkt,
		Mstat:         ms,
		Chart:         ch,
		Fundamental:   fd,
		Watchlist:     wl,
		Notifications: nt,
		Sync:          sy,
		Selection:     sel,
		MarketIndex:   mi,
		Export:        exp,
		Screener:      scr,
		Funnel:        fn,
		FtsConfig:     ftsCfg,
		OCData:        rt.data,
		Jobs:          rt.jobs,
		OCNotify:      ocnotify.NewHandler(rt.notify),
	})

	inst := &appInstance{
		info:    info,
		handles: handles,
		handler: apiHandler,
		closers: closers,
		closed:  make(chan struct{}),
	}
	inst.refs.Store(1) // ref پایه تا نسخهٔ فعال بسته نشود
	return inst, nil
}

func envBool(v string) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// live persistence پیش‌فرض روشن است؛ فقط مقدارِ صریحِ 0/false/no خاموشش می‌کند.
func envBoolDefault(v string) bool {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "0", "false", "no":
		return false
	}
	return true
}

func newSnapshotApplier(dataDir string) (*snapshot.Applier, error) {
	key := os.Getenv("BORS_UPDATE_PUBKEY")
	if key == "" {
		key = borssync.DefaultUpdatePubKey
	}
	return snapshot.NewApplier(snapshot.ApplierConfig{DataDir: dataDir, PubKeyStr: key})
}

// Close پس از تخلیهٔ درخواست‌ها فراخوانی می‌شود (RunServer تضمین می‌کند)؛
// نسخهٔ فعلی را بازنشسته و آزاد می‌کند.
func (rt *runtime) Close() {
	rt.swapMu.Lock()
	defer rt.swapMu.Unlock()
	inst := rt.cur.Swap(nil)
	if inst != nil {
		inst.retired.Store(true)
		inst.release()
	}
	if rt.oc != nil {
		_ = rt.oc.Close()
	}
}
