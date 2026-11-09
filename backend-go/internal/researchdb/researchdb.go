// Package researchdb مالکِ research.db است. این DB فقط در سیستمِ مالک و خارج از
// dataDir تولیدکننده زندگی می‌کند؛ هیچ مسیری از کلاینت آن را باز نمی‌کند.
package researchdb

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/migrate"
)

var migrations = []migrate.Migration{
	{
		Version: 1,
		Name:    "research_base",
		SQL: `
CREATE TABLE IF NOT EXISTS hypotheses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    statement     TEXT NOT NULL,
    universe_spec TEXT NOT NULL,
    horizon       TEXT,
    expected_effect TEXT,
    invalidation  TEXT,
    planned_tests_json TEXT NOT NULL,
    search_budget INTEGER,
    created_at    TEXT NOT NULL,
    hash          TEXT NOT NULL,
    prev_hash     TEXT
);

CREATE TABLE IF NOT EXISTS strategy_identities (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    family     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_versions (
    id         TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    semver     TEXT NOT NULL,
    ir_json    TEXT NOT NULL,
    ir_hash    TEXT NOT NULL,
    ir_schema  TEXT NOT NULL,
    runtime_min TEXT,
    runtime_max TEXT,
    created_at TEXT NOT NULL,
    author     TEXT,
    status     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS datasets (
    hash        TEXT PRIMARY KEY,
    span_start  TEXT,
    span_end    TEXT,
    universe_hash TEXT,
    price_basis TEXT,
    lineage_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id          TEXT PRIMARY KEY,
    version_id  TEXT NOT NULL,
    dataset_hash TEXT NOT NULL,
    protocol_json TEXT NOT NULL,
    cost_model_version TEXT,
    seed        TEXT,
    code_hash   TEXT,
    env_lock_hash TEXT,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    id             TEXT PRIMARY KEY,
    family         TEXT NOT NULL,
    candidate_hash TEXT NOT NULL,
    params_hash    TEXT NOT NULL,
    status         TEXT NOT NULL,
    n_group        TEXT,
    prev_hash      TEXT,
    hash           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validations (
    id            TEXT PRIMARY KEY,
    version_id    TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    policy_hash   TEXT NOT NULL,
    verdict       TEXT NOT NULL,
    metrics_json  TEXT NOT NULL,
    gates_json    TEXT NOT NULL,
    holdout_access_json TEXT,
    created_at    TEXT NOT NULL,
    prev_hash     TEXT,
    hash          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    summary_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id              TEXT PRIMARY KEY,
    version_id      TEXT NOT NULL,
    validation_id   TEXT NOT NULL,
    owner_id        TEXT NOT NULL,
    approval_basis  TEXT NOT NULL,
    policy_hash     TEXT NOT NULL,
    scope_json      TEXT NOT NULL,
    signed_record   TEXT NOT NULL,
    signed_at       TEXT NOT NULL,
    revoked_at      TEXT,
    reason          TEXT,
    prev_hash       TEXT,
    hash            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bundles (
    id            TEXT PRIMARY KEY,
    version_id    TEXT NOT NULL,
    bundle_hash   TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    built_at      TEXT NOT NULL,
    published_at  TEXT
);

CREATE TABLE IF NOT EXISTS gpu_jobs (
    id               TEXT PRIMARY KEY,
    job_hash         TEXT NOT NULL,
    environment_hash TEXT,
    data_scope_hash  TEXT,
    status           TEXT NOT NULL,
    outputs_json     TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    subject     TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    prev_hash   TEXT,
    hash        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS keys (
    key_id     TEXT PRIMARY KEY,
    purpose    TEXT NOT NULL,
    public_key TEXT NOT NULL,
    valid_from TEXT,
    valid_to   TEXT,
    status     TEXT NOT NULL
);
`,
	},
}

type Store struct {
	DB   *sql.DB
	Path string
}

// Open مسیرِ صریحِ پوشهٔ Research را می‌گیرد. اگر پوشه داخلِ dataDir تولیدکننده
// باشد، رد می‌شود: مرزِ داده باید ساختاری باشد، نه قراردادی.
func Open(researchDir, producerDataDir string) (*Store, error) {
	dir := strings.TrimSpace(researchDir)
	if dir == "" {
		return nil, fmt.Errorf("research dir is required")
	}
	absDir, err := filepath.Abs(dir)
	if err != nil {
		return nil, err
	}
	if producerDataDir != "" {
		prodAbs, err := filepath.Abs(producerDataDir)
		if err == nil && within(prodAbs, absDir) {
			return nil, fmt.Errorf("research dir %s is inside producer data dir %s", absDir, prodAbs)
		}
	}
	if err := os.MkdirAll(absDir, 0o700); err != nil {
		return nil, fmt.Errorf("create research dir: %w", err)
	}
	dbPath := filepath.Join(absDir, "research.db")
	conn, err := db.OpenRWC(dbPath)
	if err != nil {
		return nil, fmt.Errorf("open research.db: %w", err)
	}
	if _, err := migrate.Apply(context.Background(), conn, dbPath,
		filepath.Join(absDir, "backups"), migrations); err != nil {
		_ = conn.Close()
		return nil, err
	}
	return &Store{DB: conn, Path: dbPath}, nil
}

func (s *Store) Close() error {
	if s == nil || s.DB == nil {
		return nil
	}
	return s.DB.Close()
}

func within(base, path string) bool {
	rel, err := filepath.Rel(base, path)
	if err != nil {
		return false
	}
	return rel == "." || (rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)))
}
