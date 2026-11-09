// Package ocnotify پایهٔ اعلان‌هایِ OC است: اعتبارسنجیِ Event، درجِ append-only
// در oc_client.db، وضعیتِ تحویل برایِ هر کانال و ترجیحاتِ دستگاه. طبقه‌بندیِ
// نهایی/AI/Quiet Hours در P1/P4 تکمیل می‌شود؛ این‌جا فقط قرارداد و ذخیره‌سازی
// واقعی است، نه Toast.
package ocnotify

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

type Severity string

const (
	Critical      Severity = "critical"
	Important     Severity = "important"
	Normal        Severity = "normal"
	Informational Severity = "informational"
)

var severities = map[Severity]bool{Critical: true, Important: true, Normal: true, Informational: true}

// Source allowlist: هیچ متنِ بیرونی (کدال/خبر) مستقیماً اعلان نمی‌سازد؛ فقط
// Publisherهایِ داخلیِ همین دامنه‌ها.
var allowedSources = map[string]bool{
	"strategy": true, "opportunity": true, "portfolio": true, "data": true,
	"security": true, "update": true, "market": true, "registry": true, "system": true,
	"ai": true,
}

var eventIDRe = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`)

type Event struct {
	EventID       string         `json:"event_id"`
	Type          string         `json:"event_type"`
	Category      string         `json:"category"`
	Severity      Severity       `json:"severity"`
	Title         string         `json:"title"`
	Body          string         `json:"body"`
	Subject       map[string]any `json:"subject"`
	DeepLink      string         `json:"deep_link"`
	DedupeKey     string         `json:"dedupe_key"`
	GroupKey      string         `json:"group_key"`
	Source        string         `json:"source"`
	SourceVersion string         `json:"source_version"`
	PayloadHash   string         `json:"payload_hash"`
	Preview       map[string]any `json:"preview"`
	Actions       []any          `json:"actions"`
	OccurredAt    string         `json:"occurred_at"`
	ToastEligible bool           `json:"toast_eligible"`
}

type Published struct {
	Seq        int64
	EventID    string
	Occurrence int
	Deduped    bool
}

type Store struct {
	db  *sql.DB
	now func() time.Time
}

func NewStore(db *sql.DB) *Store { return &Store{db: db, now: time.Now} }

func (s *Store) WithClock(now func() time.Time) *Store {
	if now != nil {
		s.now = now
	}
	return s
}

func canonicalJSON(v any) []byte {
	raw, _ := json.Marshal(v)
	return raw
}

func hashPayload(e Event) string {
	h := sha256.New()
	h.Write(canonicalJSON(map[string]any{
		"type": e.Type, "severity": e.Severity, "title": e.Title, "body": e.Body,
		"subject": e.Subject, "source": e.Source,
	}))
	return hex.EncodeToString(h.Sum(nil))
}

func plainText(v string) bool {
	for _, r := range v {
		if r < 0x20 && r != '\n' && r != '\t' {
			return false
		}
	}
	return true
}

// Normalize اعتبارسنجی و تکمیلِ فیلدهایِ اختیاری است. خطا یعنی Event نباید
// ذخیره شود؛ هیچ فیلدِ ممنوعی «سرِ جایش» اصلاح نمی‌شود.
func (e *Event) Normalize(now time.Time) error {
	e.EventID = strings.TrimSpace(e.EventID)
	e.Type = strings.TrimSpace(e.Type)
	e.Category = strings.TrimSpace(e.Category)
	e.Source = strings.TrimSpace(e.Source)
	e.Title = strings.TrimSpace(e.Title)
	e.Body = strings.TrimSpace(e.Body)
	e.DeepLink = strings.TrimSpace(e.DeepLink)

	if !eventIDRe.MatchString(e.EventID) {
		return errors.New("event_id must match [A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
	}
	if e.Type == "" || len(e.Type) > 96 {
		return errors.New("event_type is required (max 96)")
	}
	if e.Category == "" || len(e.Category) > 64 {
		return errors.New("category is required (max 64)")
	}
	if !severities[e.Severity] {
		return fmt.Errorf("severity %q is not in the policy set", e.Severity)
	}
	if !allowedSources[e.Source] {
		return fmt.Errorf("source %q is not allowlisted", e.Source)
	}
	if e.Source == "ai" && e.Severity != Informational {
		return errors.New("ai source may only publish informational events")
	}
	if e.Title == "" || len(e.Title) > 160 {
		return errors.New("title is required (max 160)")
	}
	if len(e.Body) > 2000 {
		return errors.New("body exceeds 2000 characters")
	}
	if !plainText(e.Title) || !plainText(e.Body) {
		return errors.New("title/body must be plain text without control characters")
	}
	if e.DeepLink != "" {
		low := strings.ToLower(e.DeepLink)
		if strings.HasPrefix(low, "javascript:") || strings.HasPrefix(low, "file:") ||
			strings.HasPrefix(low, "http://") || strings.HasPrefix(low, "https://") ||
			!strings.HasPrefix(e.DeepLink, "#/") {
			return fmt.Errorf("deep_link %q is not an internal hash route", e.DeepLink)
		}
	}
	if e.OccurredAt == "" {
		e.OccurredAt = now.UTC().Format(time.RFC3339)
	}
	if _, err := time.Parse(time.RFC3339, e.OccurredAt); err != nil {
		return fmt.Errorf("occurred_at must be RFC3339: %w", err)
	}
	if e.DedupeKey == "" {
		e.DedupeKey = e.EventID
	}
	if e.GroupKey == "" {
		e.GroupKey = e.Category
	}
	if e.PayloadHash == "" {
		e.PayloadHash = hashPayload(*e)
	}
	if len(e.PayloadHash) != 64 {
		return errors.New("payload_hash must be 64 hex characters")
	}
	if _, err := hex.DecodeString(e.PayloadHash); err != nil {
		return errors.New("payload_hash must be hex")
	}
	if e.Subject == nil {
		e.Subject = map[string]any{}
	}
	if e.Preview == nil {
		e.Preview = map[string]any{}
	}
	if e.Actions == nil {
		e.Actions = []any{}
	}
	if len(e.Actions) > 4 {
		return errors.New("at most 4 actions are allowed")
	}
	if e.Severity == Normal || e.Severity == Informational {
		// Policy §۱۹.۲: Normal/Informational فقط مرکز/تاریخچه‌اند، نه Toast.
		e.ToastEligible = false
	} else {
		e.ToastEligible = true
	}
	return nil
}

// Publish در یک تراکنش Event و ردیف‌هایِ تحویل را می‌نویسد. تکرارِ همان
// event_id درجِ تازه نمی‌سازد؛ occurrence_count بالا می‌رود و last_seen تازه
// می‌شود (Idempotent برایِ Retryِ پل).
func (s *Store) Publish(ctx context.Context, e Event) (Published, error) {
	now := s.now()
	if err := e.Normalize(now); err != nil {
		return Published{}, err
	}
	nowStr := now.UTC().Format(time.RFC3339)

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return Published{}, err
	}
	defer func() { _ = tx.Rollback() }()

	var (
		seq        int64
		occurrence int
	)
	err = tx.QueryRowContext(ctx, `
		INSERT INTO notification_events
		(event_id,event_type,category,severity,title,body,subject_json,deep_link,
		 dedupe_key,group_key,source,source_version,payload_hash,preview_json,actions_json,
		 occurred_at,first_seen_at,last_seen_at,occurrence_count,created_at)
		VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
		ON CONFLICT(event_id) DO UPDATE SET
			last_seen_at=excluded.last_seen_at,
			occurrence_count=notification_events.occurrence_count+1
		RETURNING seq, occurrence_count`,
		e.EventID, e.Type, e.Category, string(e.Severity), e.Title, e.Body,
		string(canonicalJSON(e.Subject)), nullIfEmpty(e.DeepLink),
		e.DedupeKey, e.GroupKey, e.Source, nullIfEmpty(e.SourceVersion), e.PayloadHash,
		string(canonicalJSON(e.Preview)), string(canonicalJSON(e.Actions)),
		e.OccurredAt, nowStr, nowStr, nowStr).Scan(&seq, &occurrence)
	if err != nil {
		return Published{}, fmt.Errorf("insert notification event: %w", err)
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT OR IGNORE INTO notification_deliveries(event_id,channel,state,attempts,shown_at)
		VALUES (?, 'center', 'shown', 1, ?)`, e.EventID, nowStr); err != nil {
		return Published{}, fmt.Errorf("insert center delivery: %w", err)
	}
	if e.ToastEligible {
		if _, err := tx.ExecContext(ctx, `
			INSERT OR IGNORE INTO notification_deliveries(event_id,channel,state,attempts)
			VALUES (?, 'toast', 'pending', 0)`, e.EventID); err != nil {
			return Published{}, fmt.Errorf("insert toast delivery: %w", err)
		}
	}
	if err := tx.Commit(); err != nil {
		return Published{}, err
	}
	// occurrence > 1 یعنی این event_id قبلاً ثبت شده بود (retry).
	return Published{Seq: seq, EventID: e.EventID, Occurrence: occurrence, Deduped: occurrence > 1}, nil
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

// AckDelivery وضعیتِ Toast/مرکز را ثبت می‌کند. فقط وضعیت‌هایِ مجاز و فقط
// کانال‌هایِ معلوم؛ Eventِ ناشناخته خطاست. Idempotent است.
func (s *Store) AckDelivery(ctx context.Context, eventID, channel, state, lastError string) error {
	switch channel {
	case "toast", "center":
	default:
		return fmt.Errorf("unknown delivery channel %q", channel)
	}
	switch state {
	case "shown", "failed", "suppressed_os":
	default:
		return fmt.Errorf("state %q is not a valid delivery state", state)
	}
	now := s.now().UTC().Format(time.RFC3339)
	res, err := s.db.ExecContext(ctx, `
		UPDATE notification_deliveries
		SET state=?, attempts=attempts+1, last_error=?, shown_at=CASE WHEN ?='shown' THEN ? ELSE shown_at END,
		    acked_at=CASE WHEN ? IN ('shown','suppressed_os') THEN ? ELSE acked_at END
		WHERE event_id=? AND channel=?`,
		state, nullIfEmpty(lastError), state, now, state, now, eventID, channel)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return fmt.Errorf("delivery %s/%s not found", eventID, channel)
	}
	return nil
}

func (s *Store) MarkRead(ctx context.Context, eventID string) (bool, error) {
	res, err := s.db.ExecContext(ctx,
		`UPDATE notification_events SET read_at=? WHERE event_id=? AND read_at IS NULL AND archived_at IS NULL`,
		s.now().UTC().Format(time.RFC3339), eventID)
	if err != nil {
		return false, err
	}
	n, err := res.RowsAffected()
	return n > 0, err
}

func (s *Store) MarkAllRead(ctx context.Context) (int64, error) {
	res, err := s.db.ExecContext(ctx,
		`UPDATE notification_events SET read_at=? WHERE read_at IS NULL AND archived_at IS NULL`,
		s.now().UTC().Format(time.RFC3339))
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}

type ListQuery struct {
	Limit     int
	BeforeSeq int64
	Severity  string
	Category  string
	Unread    bool
}

type Row struct {
	Seq             int64             `json:"seq"`
	EventID         string            `json:"event_id"`
	Type            string            `json:"event_type"`
	Category        string            `json:"category"`
	Severity        string            `json:"severity"`
	Title           string            `json:"title"`
	Body            string            `json:"body"`
	DeepLink        string            `json:"deep_link,omitempty"`
	Source          string            `json:"source"`
	OccurredAt      string            `json:"occurred_at"`
	OccurrenceCount int               `json:"occurrence_count"`
	ReadAt          string            `json:"read_at,omitempty"`
	GroupKey        string            `json:"group_key"`
	Actions         json.RawMessage   `json:"actions"`
	Delivery        map[string]string `json:"delivery"`
}

func (s *Store) List(ctx context.Context, q ListQuery) ([]Row, error) {
	limit := q.Limit
	if limit < 1 {
		limit = 50
	}
	if limit > 200 {
		limit = 200
	}
	where := []string{"archived_at IS NULL"}
	args := []any{}
	if q.BeforeSeq > 0 {
		where = append(where, "seq < ?")
		args = append(args, q.BeforeSeq)
	}
	if q.Severity != "" {
		where = append(where, "severity = ?")
		args = append(args, q.Severity)
	}
	if q.Category != "" {
		where = append(where, "category = ?")
		args = append(args, q.Category)
	}
	if q.Unread {
		where = append(where, "read_at IS NULL")
	}
	args = append(args, limit)
	query := `SELECT seq,event_id,event_type,category,severity,title,body,COALESCE(deep_link,''),
		source,occurred_at,occurrence_count,COALESCE(read_at,''),group_key,actions_json
		FROM notification_events WHERE ` + strings.Join(where, " AND ") + ` ORDER BY seq DESC LIMIT ?`
	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Row, 0, limit)
	for rows.Next() {
		var r Row
		var actions string
		if err := rows.Scan(&r.Seq, &r.EventID, &r.Type, &r.Category, &r.Severity, &r.Title, &r.Body,
			&r.DeepLink, &r.Source, &r.OccurredAt, &r.OccurrenceCount, &r.ReadAt, &r.GroupKey, &actions); err != nil {
			return nil, err
		}
		r.Actions = json.RawMessage(actions)
		out = append(out, r)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if err := s.attachDeliveries(ctx, out); err != nil {
		return nil, err
	}
	return out, nil
}

func (s *Store) attachDeliveries(ctx context.Context, rows []Row) error {
	if len(rows) == 0 {
		return nil
	}
	idx := make(map[string]*Row, len(rows))
	for i := range rows {
		idx[rows[i].EventID] = &rows[i]
	}
	ph := make([]string, 0, len(rows))
	args := make([]any, 0, len(rows))
	for _, r := range rows {
		ph = append(ph, "?")
		args = append(args, r.EventID)
	}
	q := `SELECT event_id,channel,state FROM notification_deliveries WHERE event_id IN (` + strings.Join(ph, ",") + `)`
	res, err := s.db.QueryContext(ctx, q, args...)
	if err != nil {
		return err
	}
	defer res.Close()
	for res.Next() {
		var eventID, channel, state string
		if err := res.Scan(&eventID, &channel, &state); err != nil {
			return err
		}
		if r := idx[eventID]; r != nil {
			if r.Delivery == nil {
				r.Delivery = map[string]string{}
			}
			r.Delivery[channel] = state
		}
	}
	return res.Err()
}

// Pending رویدادهایِ Toastِ ارسال‌نشده با seq بزرگ‌تر از afterSeq است؛ پلِ
// Tauri همین را long-poll می‌کند. ترتیب صعودی است تا after_seq قابلِ ادامه باشد.
func (s *Store) Pending(ctx context.Context, afterSeq int64, limit int) ([]Row, error) {
	if limit < 1 || limit > 50 {
		limit = 20
	}
	rows, err := s.db.QueryContext(ctx, `
		SELECT e.seq,e.event_id,e.event_type,e.category,e.severity,e.title,e.body,COALESCE(e.deep_link,''),
		       e.source,e.occurred_at,e.occurrence_count,COALESCE(e.read_at,''),e.group_key,e.actions_json
		FROM notification_events e
		JOIN notification_deliveries d ON d.event_id=e.event_id AND d.channel='toast'
		WHERE d.state='pending' AND e.seq > ? AND e.archived_at IS NULL
		ORDER BY e.seq ASC LIMIT ?`, afterSeq, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Row{}
	for rows.Next() {
		var r Row
		var actions string
		if err := rows.Scan(&r.Seq, &r.EventID, &r.Type, &r.Category, &r.Severity, &r.Title, &r.Body,
			&r.DeepLink, &r.Source, &r.OccurredAt, &r.OccurrenceCount, &r.ReadAt, &r.GroupKey, &actions); err != nil {
			return nil, err
		}
		r.Actions = json.RawMessage(actions)
		r.Delivery = map[string]string{"toast": "pending"}
		out = append(out, r)
	}
	return out, rows.Err()
}

func (s *Store) UnreadCounts(ctx context.Context) (map[string]int, error) {
	rows, err := s.db.QueryContext(ctx,
		`SELECT severity, COUNT(*) FROM notification_events WHERE read_at IS NULL AND archived_at IS NULL GROUP BY severity`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]int{"critical": 0, "important": 0, "normal": 0, "informational": 0, "total": 0}
	for rows.Next() {
		var sev string
		var n int
		if err := rows.Scan(&sev, &n); err != nil {
			return nil, err
		}
		out[sev] = n
		out["total"] += n
	}
	return out, rows.Err()
}

func DefaultPrefs() map[string]any {
	return map[string]any{
		"toast_critical": true, "toast_important": true,
		"toast_normal": false, "toast_informational": false,
		"sound_critical": true, "sound_important": false,
		"sensitive_preview":   false,
		"quiet_hours_enabled": false, "quiet_hours_start": "22:00", "quiet_hours_end": "08:00",
		"critical_during_quiet_hours": true,
		"badge_critical_important":    true,
	}
}

var clockRe = regexp.MustCompile(`^([01][0-9]|2[0-3]):[0-5][0-9]$`)

func validatePrefs(raw map[string]any) error {
	allowed := DefaultPrefs()
	for k, v := range raw {
		def, ok := allowed[k]
		if !ok {
			return fmt.Errorf("unknown preference %q", k)
		}
		switch def.(type) {
		case bool:
			if _, ok := v.(bool); !ok {
				return fmt.Errorf("preference %q must be boolean", k)
			}
		case string:
			s, ok := v.(string)
			if !ok || !clockRe.MatchString(s) {
				return fmt.Errorf("preference %q must be HH:MM", k)
			}
		}
	}
	return nil
}

func (s *Store) Prefs(ctx context.Context) (map[string]any, error) {
	out := DefaultPrefs()
	var raw string
	err := s.db.QueryRowContext(ctx, `SELECT prefs_json FROM notification_prefs WHERE id=1`).Scan(&raw)
	if errors.Is(err, sql.ErrNoRows) {
		return out, nil
	}
	if err != nil {
		return nil, err
	}
	var stored map[string]any
	if err := json.Unmarshal([]byte(raw), &stored); err != nil {
		return nil, err
	}
	for k, v := range stored {
		out[k] = v
	}
	return out, nil
}

func (s *Store) SavePrefs(ctx context.Context, raw json.RawMessage) (map[string]any, error) {
	var p map[string]any
	if err := json.Unmarshal(raw, &p); err != nil {
		return nil, fmt.Errorf("preferences must be a JSON object: %w", err)
	}
	if err := validatePrefs(p); err != nil {
		return nil, err
	}
	merged := DefaultPrefs()
	for k, v := range p {
		merged[k] = v
	}
	blob, err := json.Marshal(merged)
	if err != nil {
		return nil, err
	}
	if _, err := s.db.ExecContext(ctx, `
		INSERT INTO notification_prefs(id,prefs_json,updated_at) VALUES (1,?,?)
		ON CONFLICT(id) DO UPDATE SET prefs_json=excluded.prefs_json, updated_at=excluded.updated_at`,
		string(blob), s.now().UTC().Format(time.RFC3339)); err != nil {
		return nil, err
	}
	return merged, nil
}

func (s *Store) Mute(ctx context.Context, category, until, reason string) error {
	category = strings.TrimSpace(category)
	if category == "" {
		return errors.New("category is required")
	}
	if until != "" {
		if _, err := time.Parse(time.RFC3339, until); err != nil {
			return fmt.Errorf("muted_until must be RFC3339: %w", err)
		}
	}
	_, err := s.db.ExecContext(ctx, `
		INSERT INTO notification_mutes(category,muted_until,reason) VALUES (?,?,?)
		ON CONFLICT(category) DO UPDATE SET muted_until=excluded.muted_until, reason=excluded.reason`,
		category, nullIfEmpty(until), nullIfEmpty(reason))
	return err
}

func (s *Store) IsMuted(ctx context.Context, category string, at time.Time) (bool, error) {
	var until sql.NullString
	err := s.db.QueryRowContext(ctx, `SELECT muted_until FROM notification_mutes WHERE category=?`, category).Scan(&until)
	if errors.Is(err, sql.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if !until.Valid || until.String == "" {
		return true, nil // بدونِ انقضا = خاموشِ دائمی
	}
	t, err := time.Parse(time.RFC3339, until.String)
	if err != nil {
		return false, err
	}
	return at.Before(t), nil
}
