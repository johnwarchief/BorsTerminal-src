package sync

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/jobs"
	"borsterminal/backend/internal/snapshot"
	_ "modernc.org/sqlite"
)

func waitForJobState(t *testing.T, h *Handler, id string, want jobs.State) jobs.Job {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		job, ok := h.jobs.Get(id)
		if ok && job.State == want {
			return job
		}
		time.Sleep(20 * time.Millisecond)
	}
	job, _ := h.jobs.Get(id)
	t.Fatalf("job %s did not reach %s; last=%+v", id, want, job)
	return job
}

func TestNewHandlerDownloadClientHasNoOverallTimeout(t *testing.T) {
	h := NewHandler(t.TempDir())

	if h.httpClient.Timeout != 0 {
		t.Fatalf("httpClient.Timeout = %v, want 0: a client-wide timeout also cuts off slow snapshot body reads", h.httpClient.Timeout)
	}
	tr, ok := h.httpClient.Transport.(*http.Transport)
	if !ok {
		t.Fatalf("httpClient.Transport = %T, want *http.Transport", h.httpClient.Transport)
	}
	if tr.ResponseHeaderTimeout != 60*time.Second {
		t.Fatalf("ResponseHeaderTimeout = %v, want 60s", tr.ResponseHeaderTimeout)
	}
}

func TestSyncHandlers(t *testing.T) {
	tmp := t.TempDir()
	h := NewHandler(tmp)
	var res map[string]any

	// 1. GET /api/sync/status
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/api/sync/status", nil)
	h.SyncStatus(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("SyncStatus code = %d", rec.Code)
	}

	// 2. GET /api/sync/codal/db-status
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("GET", "/api/sync/codal/db-status", nil)
	h.CodalDBStatus(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("CodalDBStatus code = %d", rec.Code)
	}

	// 3. GET /api/sync/diagnose
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("GET", "/api/sync/diagnose", nil)
	h.Diagnose(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("Diagnose code = %d", rec.Code)
	}

	// 4. POST /api/sync/market — no implementation ⇒ 501, never a fake job.
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/market", nil)
	h.SyncMarket(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Errorf("SyncMarket code = %d, want 501", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["code"] != "NOT_IMPLEMENTED" {
		t.Errorf("SyncMarket code field = %v", res["code"])
	}
	if _, ok := res["job_id"]; ok {
		t.Errorf("SyncMarket must not invent a job_id: %v", res)
	}

	// 5. POST /api/sync/codal — same honesty rule.
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/codal?mode=optimized", nil)
	h.SyncCodal(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Errorf("SyncCodal code = %d, want 501", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if _, ok := res["job_id"]; ok {
		t.Errorf("SyncCodal must not invent a job_id: %v", res)
	}

	// 6. POST /api/sync/codal/fts-refresh — same honesty rule.
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/codal/fts-refresh?mode=full", nil)
	h.SyncCodalFTSRefresh(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Errorf("SyncCodalFTSRefresh code = %d, want 501", rec.Code)
	}

	// 7. POST /api/sync/codal/db-download while a real job of the same kind is
	// running ⇒ 409 with that job id, not a second job and not 200.
	blockCtx, blockCancel := context.WithCancel(context.Background())
	blocking, _, err := h.jobs.StartExclusive(blockCtx, kindCodalDBDownload, true,
		func(ctx context.Context) error { <-ctx.Done(); return ctx.Err() })
	if err != nil {
		t.Fatal(err)
	}
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/sync/codal/db-download", nil)
	h.SyncCodalDBDownload(rec, req)
	if rec.Code != http.StatusConflict {
		t.Errorf("SyncCodalDBDownload conflict code = %d, want 409", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["job_id"] != blocking.ID {
		t.Errorf("conflict job_id = %v, want %s", res["job_id"], blocking.ID)
	}
	if res["code"] != "JOB_ALREADY_RUNNING" {
		t.Errorf("conflict code = %v", res["code"])
	}
	blockCancel()
	waitForJobState(t, h, blocking.ID, jobs.Failed)

	// 8. POST /api/codal/control (invalid body)
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/codal/control", bytes.NewBufferString("not-json"))
	h.CodalControl(rec, req)
	if rec.Code != http.StatusOK {
		t.Errorf("CodalControl invalid json code = %d", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["status"] != "error" {
		t.Errorf("expected status=error, got %v", res["status"])
	}

	// 9. POST /api/codal/control (unknown cmd)
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/codal/control", bytes.NewBufferString(`{"cmd":"invalid"}`))
	h.CodalControl(rec, req)
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["status"] != "error" {
		t.Errorf("expected status=error for unknown cmd, got %v", res["status"])
	}

	// 10. POST /api/codal/control (valid pause)
	rec = httptest.NewRecorder()
	req = httptest.NewRequest("POST", "/api/codal/control", bytes.NewBufferString(`{"cmd":"pause"}`))
	h.CodalControl(rec, req)
	_ = json.Unmarshal(rec.Body.Bytes(), &res)
	if res["status"] != "success" || res["cmd"] != "pause" {
		t.Errorf("expected status=success cmd=pause, got %v", res)
	}
}

// TestZeroPythonSubprocessesInSync validates via Go AST analysis and file inspection that
// internal/sync contains ZERO invocations of Python processes (python, python3, py, python.exe).
func TestZeroPythonSubprocessesInSync(t *testing.T) {
	fset := token.NewFileSet()
	pkgs, err := parser.ParseDir(fset, ".", nil, parser.ParseComments)
	if err != nil {
		t.Fatalf("failed to parse package internal/sync: %v", err)
	}

	disallowedCommands := []string{"python", "python3", "python.exe", "python3.exe", "py"}

	for pkgName, pkg := range pkgs {
		for fileName, file := range pkg.Files {
			isTestFile := strings.HasSuffix(fileName, "_test.go")

			// Check AST call expressions in all files
			ast.Inspect(file, func(n ast.Node) bool {
				call, ok := n.(*ast.CallExpr)
				if !ok {
					return true
				}

				// Check if call looks like exec.Command or exec.CommandContext
				var funcName string
				switch fun := call.Fun.(type) {
				case *ast.SelectorExpr:
					funcName = fun.Sel.Name
				case *ast.Ident:
					funcName = fun.Name
				}

				if funcName == "Command" || funcName == "CommandContext" {
					for _, arg := range call.Args {
						if lit, ok := arg.(*ast.BasicLit); ok && lit.Kind == token.STRING {
							val := strings.Trim(lit.Value, `"`)
							for _, disallowed := range disallowedCommands {
								if strings.EqualFold(val, disallowed) || strings.HasSuffix(strings.ToLower(val), disallowed) {
									pos := fset.Position(lit.Pos())
									t.Errorf("AST violation in %s (%s:%d): found subprocess call with disallowed command %q",
										pkgName, filepath.Base(fileName), pos.Line, val)
								}
							}
						}
					}
				}
				return true
			})

			// Check raw content in production (non-test) files as secondary guard
			if isTestFile {
				continue
			}
			content, err := os.ReadFile(fileName)
			if err != nil {
				continue
			}
			lower := strings.ToLower(string(content))
			for _, disallowed := range disallowedCommands {
				needle := `"` + disallowed + `"`
				if strings.Contains(lower, needle) {
					t.Errorf("File scan violation in %s: string %q found in %s",
						pkgName, needle, filepath.Base(fileName))
				}
			}
		}
	}
}

// TestSyncCodalDBDownload_MockServerSuccess tests the end-to-end native snapshot ingestion:
// downloads manifest and signed assets from an HTTP test server, applies them via Applier,
// updates status to "done", switches active_generation.json, and confirms zero Python subprocesses.
func TestSyncCodalDBDownload_MockServerSuccess(t *testing.T) {
	serverDir := t.TempDir()
	clientDir := t.TempDir()

	// 1. Generate keypair for Minisign verification
	pubKey, privKey, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	// 2. Create raw SQLite database
	rawDBPath := filepath.Join(serverDir, "codal.db")
	db, err := sql.Open("sqlite", rawDBPath)
	if err != nil {
		t.Fatalf("create sqlite db: %v", err)
	}
	_, err = db.Exec("CREATE TABLE codal_notices (tracing_no INT PRIMARY KEY, symbol TEXT);")
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	_, err = db.Exec("INSERT INTO codal_notices (tracing_no, symbol) VALUES (98765, 'فولاد');")
	if err != nil {
		t.Fatalf("insert row: %v", err)
	}
	_ = db.Close()

	// 3. Compress database using standard LZMA
	lzmaPath := filepath.Join(serverDir, "codal.db.lzma")
	compSHA, compSize, rawSize, err := snapshot.CompressLZMA(rawDBPath, lzmaPath)
	if err != nil {
		t.Fatalf("CompressLZMA failed: %v", err)
	}

	// 4. Sign asset
	assetSigPath, err := snapshot.SignAsset(lzmaPath, privKey, "")
	if err != nil {
		t.Fatalf("SignAsset failed: %v", err)
	}

	// 5. Create Manifest
	manifest := snapshot.NewManifest("set_sync_e2e_20261108", 1)
	manifest.AddAsset("codal", "codal.db.lzma", compSHA, compSize, rawSize)
	manifestPath := filepath.Join(serverDir, "manifest.json")
	if err := manifest.Save(manifestPath); err != nil {
		t.Fatalf("manifest.Save failed: %v", err)
	}

	// 6. Sign manifest
	manifestSigPath, err := snapshot.SignAsset(manifestPath, privKey, "")
	if err != nil {
		t.Fatalf("Sign manifest failed: %v", err)
	}

	// 7. Setup Mock HTTP Server
	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cleanPath := strings.TrimPrefix(r.URL.Path, "/")
		switch cleanPath {
		case "manifest.json":
			http.ServeFile(w, r, manifestPath)
		case "manifest.json.sig":
			http.ServeFile(w, r, manifestSigPath)
		case "codal.db.lzma":
			http.ServeFile(w, r, lzmaPath)
		case "codal.db.lzma.sig":
			http.ServeFile(w, r, assetSigPath)
		default:
			http.NotFound(w, r)
		}
	}))
	defer mockServer.Close()

	// 8. Create Handler configured with mock server
	h := NewHandler(clientDir)
	h.SetSnapshotBaseURL(mockServer.URL)
	h.SetPubKey(pubKey)
	h.SetHTTPClient(mockServer.Client())

	// 9. Trigger SyncCodalDBDownload
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/sync/codal/db-download", nil)
	h.SyncCodalDBDownload(rec, req)

	if rec.Code != http.StatusAccepted {
		t.Fatalf("SyncCodalDBDownload returned status %d, body: %s", rec.Code, rec.Body.String())
	}

	var startResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &startResp); err != nil {
		t.Fatalf("parse start response: %v", err)
	}
	if startResp["status"] != "started" {
		t.Fatalf("expected status=started, got %v", startResp)
	}
	jobID, _ := startResp["job_id"].(string)
	if jobID == "" {
		t.Fatalf("expected a real job_id, got %v", startResp)
	}
	if startResp["status_url"] != "/api/jobs/"+jobID {
		t.Fatalf("status_url = %v", startResp["status_url"])
	}
	job := waitForJobState(t, h, jobID, jobs.Succeeded)

	// 10. Poll for completion of background goroutine
	deadline := time.Now().Add(10 * time.Second)
	var finalStatus map[string]any
	for time.Now().Before(deadline) {
		finalStatus = GetCodalDBStatus(clientDir, false)
		dbMap, ok := finalStatus["db"].(map[string]any)
		if ok {
			stage, _ := dbMap["stage"].(string)
			if stage == "done" || stage == "error" {
				break
			}
		}
		time.Sleep(50 * time.Millisecond)
	}

	dbMap, ok := finalStatus["db"].(map[string]any)
	if !ok {
		t.Fatalf("db status missing from final response: %v", finalStatus)
	}
	if dbMap["stage"] != "done" {
		t.Fatalf("expected stage=done, got stage=%v error=%v detail=%v",
			dbMap["stage"], dbMap["error"], dbMap["detail"])
	}
	if dbMap["percent"] != 100.0 {
		t.Errorf("expected percent=100, got %v", dbMap["percent"])
	}

	// 11. Verify active_generation exists and matches snapshot set ID
	activeGen, ok := finalStatus["active_generation"].(map[string]any)
	if !ok {
		t.Fatalf("expected active_generation in response, got %v", finalStatus)
	}
	if activeGen["snapshot_set_id"] != "set_sync_e2e_20261108" {
		t.Errorf("expected snapshot_set_id set_sync_e2e_20261108, got %v", activeGen["snapshot_set_id"])
	}

	// 12. Verify active SQLite database inside gens/gen_set_sync_e2e_20261108/codal.db
	appliedDBPath := filepath.Join(clientDir, "gens", "gen_set_sync_e2e_20261108", "codal.db")
	if fi, err := os.Stat(appliedDBPath); err != nil || fi.IsDir() {
		t.Fatalf("applied db file %s missing: %v", appliedDBPath, err)
	}

	readDB, err := sql.Open("sqlite", appliedDBPath)
	if err != nil {
		t.Fatalf("open applied db: %v", err)
	}
	defer readDB.Close()

	var sym string
	err = readDB.QueryRow("SELECT symbol FROM codal_notices WHERE tracing_no = 98765").Scan(&sym)
	if err != nil {
		t.Fatalf("query applied db: %v", err)
	}
	if sym != "فولاد" {
		t.Errorf("expected symbol='فولاد', got %q", sym)
	}

	// 13. The real job finished successfully and no other download is running.
	if job.State != jobs.Succeeded || job.Error != "" {
		t.Fatalf("job = %+v", job)
	}
	if running, ok := h.jobs.Running(kindCodalDBDownload); ok {
		t.Errorf("a download job is still running: %+v", running)
	}
}

// TestSyncCodalDBDownload_TamperedSignature verifies that corrupt signatures cause
// the download to abort with status="error" without corrupting data or getting stuck.
func TestSyncCodalDBDownload_TamperedSignature(t *testing.T) {
	serverDir := t.TempDir()
	clientDir := t.TempDir()

	pubKey, privKey, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	manifest := snapshot.NewManifest("set_tamper_test", 1)
	manifestPath := filepath.Join(serverDir, "manifest.json")
	if err := manifest.Save(manifestPath); err != nil {
		t.Fatalf("save manifest: %v", err)
	}

	// Sign manifest with wrong key / tamper signature file
	sigPath, err := snapshot.SignAsset(manifestPath, privKey, "")
	if err != nil {
		t.Fatalf("sign manifest: %v", err)
	}
	_ = os.WriteFile(sigPath, []byte("tampered signature content that cannot be valid"), 0644)

	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cleanPath := strings.TrimPrefix(r.URL.Path, "/")
		switch cleanPath {
		case "manifest.json":
			http.ServeFile(w, r, manifestPath)
		case "manifest.json.sig":
			http.ServeFile(w, r, sigPath)
		default:
			http.NotFound(w, r)
		}
	}))
	defer mockServer.Close()

	h := NewHandler(clientDir)
	h.SetSnapshotBaseURL(mockServer.URL)
	h.SetPubKey(pubKey)
	h.SetHTTPClient(mockServer.Client())

	rec := httptest.NewRecorder()
	req := httptest.NewRequest("POST", "/api/sync/codal/db-download", nil)
	h.SyncCodalDBDownload(rec, req)
	if rec.Code != http.StatusAccepted {
		t.Fatalf("start status = %d, body: %s", rec.Code, rec.Body.String())
	}
	var startResp map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &startResp); err != nil {
		t.Fatal(err)
	}
	jobID, _ := startResp["job_id"].(string)
	if jobID == "" {
		t.Fatalf("missing job_id: %v", startResp)
	}
	job := waitForJobState(t, h, jobID, jobs.Failed)
	if job.Error == "" {
		t.Fatal("failed job must report its error")
	}

	// Poll until error status
	deadline := time.Now().Add(5 * time.Second)
	var finalStatus map[string]any
	for time.Now().Before(deadline) {
		finalStatus = GetCodalDBStatus(clientDir, false)
		dbMap, ok := finalStatus["db"].(map[string]any)
		if ok {
			stage, _ := dbMap["stage"].(string)
			if stage == "error" {
				break
			}
		}
		time.Sleep(50 * time.Millisecond)
	}

	dbMap, ok := finalStatus["db"].(map[string]any)
	if !ok || dbMap["stage"] != "error" {
		t.Fatalf("expected stage=error on tampered signature, got %v", finalStatus)
	}
	if dbMap["error"] == "" {
		t.Errorf("expected non-empty error message")
	}

	// The same job reports the failure; nothing is left "running".
	if running, ok := h.jobs.Running(kindCodalDBDownload); ok {
		t.Errorf("tampered download left a running job: %+v", running)
	}
}

// TestGetCodalDBStatus_ActiveGeneration verifies reporting of active_generation.json.
func TestGetCodalDBStatus_ActiveGeneration(t *testing.T) {
	tmp := t.TempDir()

	// When active_generation.json does not exist
	res := GetCodalDBStatus(tmp, false)
	if _, ok := res["active_generation"]; ok {
		t.Errorf("expected no active_generation when file is absent")
	}

	// Write active_generation.json
	activeData := map[string]any{
		"snapshot_set_id": "gen_test_42",
		"generation_dir":  "gens/gen_test_42",
		"applied_at_utc":  "2026-11-08T06:00:00Z",
		"schema_version":  1,
	}
	raw, _ := json.Marshal(activeData)
	_ = os.WriteFile(filepath.Join(tmp, "active_generation.json"), raw, 0644)

	res = GetCodalDBStatus(tmp, false)
	ag, ok := res["active_generation"].(map[string]any)
	if !ok {
		t.Fatalf("expected active_generation in response, got %v", res)
	}
	if ag["snapshot_set_id"] != "gen_test_42" {
		t.Errorf("expected snapshot_set_id=gen_test_42, got %v", ag["snapshot_set_id"])
	}

	// Check db sub-map also contains it
	dbMap, ok := res["db"].(map[string]any)
	if !ok {
		t.Fatalf("expected db map in response")
	}
	if ag2, ok := dbMap["active_generation"].(map[string]any); !ok || ag2["snapshot_set_id"] != "gen_test_42" {
		t.Errorf("expected db.active_generation to contain snapshot_set_id=gen_test_42, got %v", ag2)
	}
}
