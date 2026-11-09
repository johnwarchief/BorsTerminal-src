package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
	"borsterminal/backend/internal/tsetmc"
)

var (
	pipelineMu      sync.Mutex
	pipelineRunning bool
)

// PipelineStatusMeta records structured metadata for the most recent snapshot pipeline execution.
type PipelineStatusMeta struct {
	SnapshotSetID   string `json:"snapshot_set_id,omitempty"`
	StartedAt       string `json:"started_at"`
	FinishedAt      string `json:"finished_at"`
	Status          string `json:"status"` // "success" or "error"
	Phase           string `json:"phase"`
	Error           string `json:"error,omitempty"`
	Published       bool   `json:"published"`
	PublishTag      string `json:"publish_tag,omitempty"`
	PublishRepo     string `json:"publish_repo,omitempty"`
	AssetCount      int    `json:"asset_count,omitempty"`
	RecalculatedFTS int    `json:"recalculated_fts,omitempty"`
}

// EnsurePipelineRunsSchema creates pipeline_runs table if it does not already exist.
func EnsurePipelineRunsSchema(dbConn *sql.DB) error {
	if dbConn == nil {
		return errors.New("nil db connection")
	}
	ddl := `
	CREATE TABLE IF NOT EXISTS pipeline_runs (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		started_at TEXT,
		finished_at TEXT,
		cycle TEXT,
		phase TEXT,
		error TEXT,
		found INTEGER DEFAULT 0,
		enqueued INTEGER DEFAULT 0,
		processed INTEGER DEFAULT 0,
		done INTEGER DEFAULT 0,
		empty INTEGER DEFAULT 0,
		failed INTEGER DEFAULT 0,
		unresolved INTEGER DEFAULT 0
	);`
	_, err := dbConn.Exec(ddl)
	return err
}

// RecordPipelineRun records a pipeline execution row in pipeline_runs.
func RecordPipelineRun(dbConn *sql.DB, startedAt, finishedAt, cycle, phase, errText string, done, failed int) error {
	if dbConn == nil {
		return errors.New("nil db connection")
	}
	if err := EnsurePipelineRunsSchema(dbConn); err != nil {
		return err
	}
	var errVal any = nil
	if errText != "" {
		errVal = errText
	}
	query := `INSERT INTO pipeline_runs (started_at, finished_at, cycle, phase, error, done, failed) VALUES (?, ?, ?, ?, ?, ?, ?)`
	_, err := dbConn.Exec(query, startedAt, finishedAt, cycle, phase, errVal, done, failed)
	return err
}

// parseDailyUTCTime parses HH:MM format strings into hours and minutes.
func parseDailyUTCTime(timeStr string) (int, int, error) {
	trimmed := strings.TrimSpace(timeStr)
	parts := strings.Split(trimmed, ":")
	if len(parts) != 2 {
		return 6, 0, fmt.Errorf("invalid daily UTC time %q, expected HH:MM", timeStr)
	}
	h, err := strconv.Atoi(parts[0])
	if err != nil || h < 0 || h > 23 {
		return 6, 0, fmt.Errorf("invalid hour in daily UTC time %q", timeStr)
	}
	m, err := strconv.Atoi(parts[1])
	if err != nil || m < 0 || m > 59 {
		return 6, 0, fmt.Errorf("invalid minute in daily UTC time %q", timeStr)
	}
	return h, m, nil
}

// NextDailyUTCDuration calculates the duration until the next occurrence of hour:minute UTC.
// If the time has already passed today, it calculates the delay until tomorrow's occurrence.
func NextDailyUTCDuration(now time.Time, hour, minute int) time.Duration {
	nowUTC := now.UTC()
	target := time.Date(nowUTC.Year(), nowUTC.Month(), nowUTC.Day(), hour, minute, 0, 0, time.UTC)
	if !nowUTC.Before(target) {
		target = target.AddDate(0, 0, 1)
	}
	delay := target.Sub(nowUTC)
	if delay <= 0 {
		delay = 24 * time.Hour
	}
	return delay
}

// LastSuccessfulSnapshotDate reads last_pipeline_status.json and returns the YYYY-MM-DD date of last success.
func LastSuccessfulSnapshotDate(snapshotOutDir string) string {
	metaPath := filepath.Join(snapshotOutDir, "last_pipeline_status.json")
	data, err := os.ReadFile(metaPath)
	if err != nil {
		return ""
	}
	var meta PipelineStatusMeta
	if err := json.Unmarshal(data, &meta); err != nil {
		return ""
	}
	if meta.Status == "success" && len(meta.FinishedAt) >= 10 {
		return meta.FinishedAt[:10]
	}
	return ""
}

func savePipelineStatusMeta(snapshotOutDir string, meta PipelineStatusMeta) {
	_ = os.MkdirAll(snapshotOutDir, 0755)
	data, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return
	}
	metaPath := filepath.Join(snapshotOutDir, "last_pipeline_status.json")
	tmpPath := metaPath + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0644); err == nil {
		_ = os.Rename(tmpPath, metaPath)
	}
}

func recordPipelineFailure(cfg DaemonConfig, startedAt, phase, errText string) {
	finishedAt := time.Now().UTC().Format(time.RFC3339)
	slog.Error("scheduled snapshot pipeline failed", "phase", phase, "err", errText)

	marketPath := filepath.Join(cfg.DataDir, "market.db")
	if mdb, err := db.OpenRWC(marketPath); err == nil {
		_ = RecordPipelineRun(mdb, startedAt, finishedAt, "scheduled_snapshot", phase, errText, 0, 1)
		_ = mdb.Close()
	}

	meta := PipelineStatusMeta{
		StartedAt:  startedAt,
		FinishedAt: finishedAt,
		Status:     "error",
		Phase:      phase,
		Error:      errText,
	}
	savePipelineStatusMeta(cfg.SnapshotOutDir, meta)
}

// ExecuteScheduledSnapshotPipeline executes the complete end-to-end pipeline:
//  1. Acquires writer lock and runs dirty FTS recalculation across market.db
//  2. Discovers all .db files in DataDir and builds LZMA2-compressed snapshot assets
//  3. Signs assets and manifest with Minisign Ed25519
//  4. If publishing is enabled: uploads data assets + signatures, verifies availability, and uploads manifest last
//  5. Records result in pipeline_runs table and last_pipeline_status.json
func ExecuteScheduledSnapshotPipeline(ctx context.Context, cfg DaemonConfig, now time.Time) (*snapshot.Manifest, error) {
	pipelineMu.Lock()
	if pipelineRunning {
		pipelineMu.Unlock()
		slog.Warn("scheduled snapshot pipeline already running, skipping duplicate invocation")
		return nil, nil
	}
	pipelineRunning = true
	pipelineMu.Unlock()

	defer func() {
		pipelineMu.Lock()
		pipelineRunning = false
		pipelineMu.Unlock()
	}()

	startedAt := now.UTC().Format(time.RFC3339)
	slog.Info("executing scheduled snapshot pipeline", "started_at", startedAt, "out_dir", cfg.SnapshotOutDir)

	if err := os.MkdirAll(cfg.SnapshotOutDir, 0755); err != nil {
		errStr := fmt.Sprintf("failed to create snapshot out dir: %v", err)
		recordPipelineFailure(cfg, startedAt, "init_dir", errStr)
		return nil, errors.New(errStr)
	}

	// 1. Acquire writer lock
	lock, err := tsetmc.AcquireWriterLockWithTimeout(ctx, cfg.DataDir, 3*time.Second)
	if err != nil {
		errStr := fmt.Sprintf("acquire writer lock timed out: %v", err)
		recordPipelineFailure(cfg, startedAt, "lock_acquisition", errStr)
		return nil, errors.New(errStr)
	}
	defer lock.Release()

	// 2. Open market.db and recalculate dirty FTS
	marketPath := filepath.Join(cfg.DataDir, "market.db")
	marketDB, err := db.OpenRWC(marketPath)
	if err != nil {
		errStr := fmt.Sprintf("open market.db failed: %v", err)
		recordPipelineFailure(cfg, startedAt, "open_market_db", errStr)
		return nil, errors.New(errStr)
	}
	defer marketDB.Close()

	if err := codal.EnsureRecalcSchema(marketDB); err != nil {
		errStr := fmt.Sprintf("ensure recalc schema failed: %v", err)
		recordPipelineFailure(cfg, startedAt, "recalc_schema", errStr)
		return nil, errors.New(errStr)
	}

	recalcCount, err := codal.RecalculateDirtyFTS(ctx, marketDB, nil)
	if err != nil {
		errStr := fmt.Sprintf("recalculate dirty FTS failed: %v", err)
		recordPipelineFailure(cfg, startedAt, "recalc_fts", errStr)
		return nil, errors.New(errStr)
	}
	slog.Info("pipeline: dirty FTS recalculation complete", "recalculated", recalcCount)

	// 3. Collect databases — allowlist صریح، نه اسکنِ پوشه.
	// Snapshot فقط دادهٔ مشترکِ بازار است؛ research.db / oc_client.db / user.db و
	// هر .db دیگر هرگز نباید منتشر شود (P0.2). اسکنِ قبلی هر فایلی را برمی‌داشت.
	dbs, err := collectProducerDBs(cfg.DataDir)
	if err != nil {
		errStr := fmt.Sprintf("collect databases failed: %v", err)
		recordPipelineFailure(cfg, startedAt, "collect_dbs", errStr)
		return nil, errors.New(errStr)
	}
	defer func() {
		for _, conn := range dbs {
			if conn != nil {
				_ = conn.Close()
			}
		}
	}()
	if rejected, rerr := rejectedProducerDBs(cfg.DataDir); rerr == nil && len(rejected) > 0 {
		slog.Info("pipeline: ignoring non-producer databases", "names", rejected)
	}

	tag := strings.TrimSpace(cfg.PublishTag)
	if tag == "" {
		tag = fmt.Sprintf("data-%s", now.UTC().Format("20060102"))
	}
	snapshotSetID := fmt.Sprintf("%sT%sZ-%s", now.UTC().Format("20060102"), now.UTC().Format("150405"), tag)

	// 4. Build LZMA2 snapshot set
	manifest, err := snapshot.BuildSnapshotSet(ctx, dbs, cfg.SnapshotOutDir, snapshotSetID)
	if err != nil {
		errStr := fmt.Sprintf("build snapshot set failed: %v", err)
		recordPipelineFailure(cfg, startedAt, "build_snapshot", errStr)
		return nil, errors.New(errStr)
	}

	// 5. Sign Manifest and Assets
	privKey := getMinisignSecretKey()
	password := getMinisignPassword()

	if cfg.PublishEnabled && strings.TrimSpace(privKey) == "" {
		errStr := "minisign secret key is required for snapshot publishing (set BORS_MINISIGN_SECRET_KEY)"
		recordPipelineFailure(cfg, startedAt, "signing_auth", errStr)
		return nil, errors.New(errStr)
	}

	if strings.TrimSpace(privKey) != "" {
		manifestPath := filepath.Join(cfg.SnapshotOutDir, "manifest.json")
		sigPath, err := snapshot.SignAsset(manifestPath, privKey, password)
		if err != nil {
			errStr := fmt.Sprintf("sign manifest failed: %v", err)
			recordPipelineFailure(cfg, startedAt, "sign_manifest", errStr)
			return nil, errors.New(errStr)
		}
		slog.Info("pipeline: manifest signed", "sig_path", sigPath)

		for name, assetMeta := range manifest.Assets {
			assetPath := assetMeta.Path
			if !filepath.IsAbs(assetPath) {
				assetPath = filepath.Join(cfg.SnapshotOutDir, assetPath)
			}
			asig, err := snapshot.SignAsset(assetPath, privKey, password)
			if err != nil {
				errStr := fmt.Sprintf("sign asset %s failed: %v", name, err)
				recordPipelineFailure(cfg, startedAt, "sign_asset", errStr)
				return nil, errors.New(errStr)
			}
			slog.Debug("pipeline: asset signed", "asset", name, "sig_path", asig)
		}
	}

	// 6. Publish Snapshot (if enabled)
	published := false
	if cfg.PublishEnabled {
		token := os.Getenv("GITHUB_TOKEN")
		if strings.TrimSpace(token) == "" {
			errStr := "GITHUB_TOKEN is required for snapshot publishing"
			recordPipelineFailure(cfg, startedAt, "publish_token", errStr)
			return nil, errors.New(errStr)
		}

		repo := strings.TrimSpace(cfg.PublishRepo)
		if envRepo := os.Getenv("BORS_GITHUB_REPO"); envRepo != "" {
			repo = envRepo
		}
		if repo == "" {
			repo = "johnwarchief/BorsTerminal"
		}
		parts := strings.Split(repo, "/")
		if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
			errStr := fmt.Sprintf("invalid publish repo %q, expected 'owner/repo'", repo)
			recordPipelineFailure(cfg, startedAt, "publish_repo_format", errStr)
			return nil, errors.New(errStr)
		}
		owner, repoName := parts[0], parts[1]

		baseURL := cfg.PublishBaseURL
		if baseURL == "" {
			baseURL = os.Getenv("GITHUB_API_BASE_URL")
		}

		err = snapshot.PublishSnapshotSet(ctx, http.DefaultClient, token, owner, repoName, tag, cfg.SnapshotOutDir, manifest, privKey, password, baseURL)
		if err != nil {
			errStr := fmt.Sprintf("publish snapshot set failed: %v", err)
			recordPipelineFailure(cfg, startedAt, "publish_upload", errStr)
			return nil, errors.New(errStr)
		}
		published = true
		slog.Info("pipeline: published snapshot set successfully", "repo", repo, "tag", tag, "snapshot_set_id", manifest.SnapshotSetID)
	}

	// 7. Record Success
	// زمانِ پایان از همان لنگرِ اجرا می‌آید، نه ساعتِ دیوار: شناسهٔ SnapshotSet و
	// تاریخِ «آخرین موفقیت» باید به یک اجرا تعلق داشته باشند و تست با لنگرِ ثابت
	// قابلِ بازتولید بماند.
	finishedAt := now.UTC().Format(time.RFC3339)
	_ = RecordPipelineRun(marketDB, startedAt, finishedAt, "scheduled_snapshot", "complete", "", 1, 0)

	meta := PipelineStatusMeta{
		SnapshotSetID:   manifest.SnapshotSetID,
		StartedAt:       startedAt,
		FinishedAt:      finishedAt,
		Status:          "success",
		Phase:           "complete",
		Published:       published,
		PublishTag:      tag,
		PublishRepo:     cfg.PublishRepo,
		AssetCount:      len(manifest.Assets),
		RecalculatedFTS: recalcCount,
	}
	savePipelineStatusMeta(cfg.SnapshotOutDir, meta)

	slog.Info("scheduled snapshot pipeline completed successfully",
		"snapshot_set_id", manifest.SnapshotSetID,
		"asset_count", len(manifest.Assets),
		"published", published,
		"recalculated_fts", recalcCount,
	)
	return manifest, nil
}
