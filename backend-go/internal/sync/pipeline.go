package sync

import (
	"database/sql"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/httpapi"
)

// CodalPipeline عینِ `GET /api/sync/codal/pipeline` (api/fundamental.py:3043):
// سلامتِ خطِ کدال از جدول‌ها، نه از شمارندهٔ حافظه. زیرمجموعهٔ healthِ پایتون
// که پنلِ UI می‌خواهد برمی‌گردد؛ هر خواندن گارد دارد و جدولِ نبود ⇒ صفر/خالی،
// نه ۵۰۰.
func (h *Handler) CodalPipeline(w http.ResponseWriter, r *http.Request) {
	path := filepath.Join(h.dataDir, "market.db")
	dbConn, err := db.OpenRO(path)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	defer dbConn.Close()
	health := pipelineHealth(dbConn, h.clock())
	activeGenPath := filepath.Join(h.dataDir, "active_generation.json")
	if _, err := os.Stat(activeGenPath); err == nil {
		activeGen := safeReadJSON(activeGenPath)
		if len(activeGen) > 0 {
			health["active_generation"] = activeGen
		}
	}
	httpapi.WriteJSON(w, http.StatusOK, health)
}

func pipelineHealth(db *sql.DB, now time.Time) map[string]any {
	queue := map[string]any{
		"queued": int64(0), "running": int64(0), "done": int64(0), "empty": int64(0),
		"failed": int64(0), "unresolved": int64(0), "quarantined": int64(0),
		"total": int64(0), "legacy": int64(0), "retryable": int64(0),
	}
	if rows, err := db.Query("SELECT COALESCE(state,'legacy'), COUNT(*) FROM codal_extracted GROUP BY 1"); err == nil {
		for rows.Next() {
			var state string
			var n int64
			if err := rows.Scan(&state, &n); err == nil && n >= 0 {
				queue[state] = n
				queue["total"] = queue["total"].(int64) + n
			}
		}
		rows.Close()
	}
	queued, _ := queue["queued"].(int64)
	failed, _ := queue["failed"].(int64)
	queue["retryable"] = queued + failed

	var dirty int64
	_ = db.QueryRow("SELECT COUNT(DISTINCT symbol) FROM pipeline_dirty").Scan(&dirty)

	var quarantineCount int64
	_ = db.QueryRow("SELECT COUNT(*) FROM codal_quarantine").Scan(&quarantineCount)

	var ftsCount int64
	_ = db.QueryRow("SELECT COUNT(DISTINCT symbol) FROM fts_results").Scan(&ftsCount)
	var totalSymbols int64
	_ = db.QueryRow("SELECT COUNT(DISTINCT symbol) FROM tsetmc_instruments").Scan(&totalSymbols)
	if totalSymbols == 0 {
		_ = db.QueryRow("SELECT COUNT(DISTINCT symbol) FROM instruments").Scan(&totalSymbols)
	}
	var lastFTSRecalc any
	var lfr sql.NullString
	if err := db.QueryRow("SELECT MAX(created_at) FROM fts_results").Scan(&lfr); err == nil && lfr.Valid {
		lastFTSRecalc = lfr.String
	}
	ftsCoverage := map[string]any{
		"evaluated_symbols": ftsCount,
		"total_symbols":     totalSymbols,
		"last_recalc":       lastFTSRecalc,
	}

	var lastMarketSync any
	var lms sql.NullString
	if err := db.QueryRow("SELECT MAX(d_even) FROM tsetmc_market_watch").Scan(&lms); err == nil && lms.Valid {
		lastMarketSync = lms.String
	}

	var lastData any
	var ld sql.NullString
	if err := db.QueryRow("SELECT MAX(tried_at) FROM codal_extracted WHERE state='done'").Scan(&ld); err == nil && ld.Valid {
		lastData = ld.String
	}

	gapFlag := false
	var gap string
	if err := db.QueryRow("SELECT value FROM pipeline_cursor WHERE key='notice_gap_flag'").Scan(&gap); err == nil {
		gapFlag = gap == "1"
	}

	var lastOK any
	{
		row := db.QueryRow("SELECT finished_at, cycle, processed, done, failed" +
			" FROM pipeline_runs WHERE finished_at IS NOT NULL AND error IS NULL" +
			" ORDER BY id DESC LIMIT 1")
		var at, cycle sql.NullString
		var processed, done, failed sql.NullInt64
		if err := row.Scan(&at, &cycle, &processed, &done, &failed); err == nil {
			lastOK = map[string]any{
				"at": nullStr(at), "cycle": nullStr(cycle),
				"processed": nullInt(processed), "done": nullInt(done), "failed": nullInt(failed),
			}
		}
	}

	var lastAttempt any
	{
		row := db.QueryRow("SELECT started_at, finished_at, cycle, phase, error, found," +
			" enqueued, processed, done, empty, failed, unresolved" +
			" FROM pipeline_runs ORDER BY id DESC LIMIT 1")
		var started, finished, cycle, phase, errText sql.NullString
		var found, enqueued, processed, done, empty, failed, unresolved sql.NullInt64
		if err := row.Scan(&started, &finished, &cycle, &phase, &errText,
			&found, &enqueued, &processed, &done, &empty, &failed, &unresolved); err == nil {
			lastAttempt = map[string]any{
				"started_at": nullStr(started), "finished_at": nullStr(finished),
				"cycle": nullStr(cycle), "phase": nullStr(phase), "error": nullStr(errText),
				"found": nullInt(found), "enqueued": nullInt(enqueued),
				"processed": nullInt(processed), "done": nullInt(done),
				"empty": nullInt(empty), "failed": nullInt(failed),
				"unresolved": nullInt(unresolved),
			}
		}
	}

	return map[string]any{
		"status":               "success",
		"queue":                queue,
		"dirty_symbols":        dirty,
		"quarantine_count":     quarantineCount,
		"fts_coverage":         ftsCoverage,
		"last_market_sync":     lastMarketSync,
		"last_data_update":     lastData,
		"gap_flag":             gapFlag,
		"last_successful_sync": lastOK,
		"last_attempt":         lastAttempt,
		"checked_at":           now.Format("2006-01-02 15:04:05"),
	}
}

func nullStr(v sql.NullString) any {
	if v.Valid {
		return v.String
	}
	return nil
}

func nullInt(v sql.NullInt64) any {
	if v.Valid {
		return v.Int64
	}
	return nil
}
