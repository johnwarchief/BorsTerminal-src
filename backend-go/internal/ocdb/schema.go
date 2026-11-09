package ocdb

import "borsterminal/backend/internal/migrate"

// migrations اسکیمای oc_client.db. نسخهٔ ۱ همان قرارداد §۷.۳ + §۱۹.۵ است؛
// نسخه‌های بعدی فقط اضافه می‌شوند و SQL نسخهٔ قبلی هرگز بازنویسی نمی‌شود.
var migrations = []migrate.Migration{
	{
		Version: 1,
		Name:    "oc_client_base",
		SQL: `
CREATE TABLE IF NOT EXISTS registry_state (
    sequence      INTEGER NOT NULL DEFAULT 0,
    index_hash    TEXT,
    source        TEXT,
    fetched_at    TEXT,
    verified_at   TEXT,
    last_error    TEXT
);

CREATE TABLE IF NOT EXISTS installed_bundles (
    strategy_id    TEXT NOT NULL,
    version        TEXT NOT NULL,
    bundle_hash    TEXT NOT NULL,
    manifest_hash  TEXT,
    installed_at   TEXT NOT NULL,
    activated_at   TEXT,
    deactivated_at TEXT,
    status         TEXT NOT NULL,
    runtime_compat TEXT,
    PRIMARY KEY (strategy_id, version)
);

CREATE TABLE IF NOT EXISTS strategy_runtime_state (
    strategy_id     TEXT NOT NULL,
    version         TEXT NOT NULL,
    last_eval_at    TEXT,
    data_generation TEXT,
    config_hash     TEXT,
    state           TEXT NOT NULL,
    last_error      TEXT,
    PRIMARY KEY (strategy_id, version)
);

CREATE TABLE IF NOT EXISTS opportunity_snapshots (
    opportunity_id   TEXT PRIMARY KEY,
    strategy_id      TEXT NOT NULL,
    version          TEXT NOT NULL,
    symbol           TEXT,
    ins_code         TEXT,
    signal_time      TEXT,
    data_generation  TEXT,
    evidence_json    TEXT NOT NULL,
    invalidation_json TEXT,
    freshness        TEXT NOT NULL,
    status           TEXT NOT NULL,
    rank_trace_json  TEXT,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_opp_created ON opportunity_snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_opp_strategy ON opportunity_snapshots(strategy_id, version);

CREATE TABLE IF NOT EXISTS revocations (
    strategy_id    TEXT NOT NULL,
    version        TEXT NOT NULL,
    effective_at   TEXT NOT NULL,
    reason         TEXT NOT NULL,
    index_sequence INTEGER,
    applied_at     TEXT NOT NULL,
    PRIMARY KEY (strategy_id, version)
);

CREATE TABLE IF NOT EXISTS monitoring_observations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    version     TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    kind        TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    prev_hash   TEXT,
    hash        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_events (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id         TEXT UNIQUE NOT NULL,
    event_type       TEXT NOT NULL,
    category         TEXT NOT NULL,
    severity         TEXT NOT NULL CHECK (severity IN ('critical','important','normal','informational')),
    title            TEXT NOT NULL,
    body             TEXT NOT NULL,
    subject_json     TEXT NOT NULL,
    deep_link        TEXT,
    dedupe_key       TEXT NOT NULL,
    group_key        TEXT NOT NULL,
    source           TEXT NOT NULL,
    source_version   TEXT,
    payload_hash     TEXT NOT NULL,
    preview_json     TEXT NOT NULL,
    actions_json     TEXT NOT NULL,
    occurred_at      TEXT NOT NULL,
    first_seen_at    TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    resolved_at      TEXT,
    read_at          TEXT,
    archived_at      TEXT,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_notif_occurred ON notification_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_notif_category ON notification_events(category, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_notif_severity ON notification_events(severity, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_notif_dedupe ON notification_events(dedupe_key, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_notif_read ON notification_events(read_at);
CREATE INDEX IF NOT EXISTS ix_notif_group ON notification_events(group_key);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    event_id   TEXT NOT NULL,
    channel    TEXT NOT NULL CHECK (channel IN ('toast','center')),
    state      TEXT NOT NULL CHECK (state IN ('pending','shown','failed','suppressed_os')),
    attempts   INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    shown_at   TEXT,
    acked_at   TEXT,
    PRIMARY KEY (event_id, channel)
);

CREATE TABLE IF NOT EXISTS notification_prefs (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    prefs_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_mutes (
    category    TEXT PRIMARY KEY,
    muted_until TEXT,
    reason      TEXT
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
`,
	},
}
