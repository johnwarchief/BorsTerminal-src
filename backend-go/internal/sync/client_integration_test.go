package sync

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
)

func sha256OfFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func TestClientSnapshotLifecycle_WithUserDB(t *testing.T) {
	ctx := context.Background()
	clientDir := t.TempDir()
	serverDir := t.TempDir()

	// 1. Setup client user database (user.db) with critical user data
	userDBPath := filepath.Join(clientDir, "user.db")
	userDB, err := db.OpenRWC(userDBPath)
	if err != nil {
		t.Fatalf("create user.db: %v", err)
	}
	userDDL := `
	CREATE TABLE user_watchlists (id INTEGER PRIMARY KEY, name TEXT, symbol TEXT);
	CREATE TABLE user_portfolios (id INTEGER PRIMARY KEY, symbol TEXT, shares REAL, buy_price REAL);
	CREATE TABLE user_notes (symbol TEXT PRIMARY KEY, note TEXT, updated_at TEXT);

	INSERT INTO user_watchlists (name, symbol) VALUES ('دیده بان من', 'فولاد');
	INSERT INTO user_watchlists (name, symbol) VALUES ('دیده بان من', 'شستا');
	INSERT INTO user_portfolios (symbol, shares, buy_price) VALUES ('فولاد', 10000, 4800);
	INSERT INTO user_notes (symbol, note, updated_at) VALUES ('فولاد', 'تحلیل بنیادی تایید FTS دارد', '1405-08-01');
	`
	if _, err := userDB.Exec(userDDL); err != nil {
		userDB.Close()
		t.Fatalf("seed user.db: %v", err)
	}
	userDB.Close()

	initialUserDBSHA, err := sha256OfFile(userDBPath)
	if err != nil {
		t.Fatalf("hash user.db: %v", err)
	}
	userDBInfo, err := os.Stat(userDBPath)
	if err != nil {
		t.Fatalf("stat user.db: %v", err)
	}
	initialUserDBSize := userDBInfo.Size()

	// 2. Setup server snapshot sources
	serverMarketPath := filepath.Join(serverDir, "market.db")
	serverMarketDB, err := db.OpenRWC(serverMarketPath)
	if err != nil {
		t.Fatalf("create server market.db: %v", err)
	}
	if _, err := serverMarketDB.Exec(`
		CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, symbol TEXT);
		CREATE TABLE fts_results (symbol TEXT PRIMARY KEY, score INTEGER, verdict TEXT);
		INSERT INTO instruments VALUES ('1001', 'فولاد');
		INSERT INTO instruments VALUES ('1002', 'خودرو');
		INSERT INTO fts_results VALUES ('فولاد', 5, 'STRONG');
		INSERT INTO fts_results VALUES ('خودرو', 4, 'WATCH');
	`); err != nil {
		serverMarketDB.Close()
		t.Fatalf("seed server market.db: %v", err)
	}
	serverMarketDB.Close()

	serverCodalPath := filepath.Join(serverDir, "codal.db")
	serverCodalDB, err := db.OpenRWC(serverCodalPath)
	if err != nil {
		t.Fatalf("create server codal.db: %v", err)
	}
	if _, err := serverCodalDB.Exec(`
		CREATE TABLE codal_notices (tracing_no INTEGER PRIMARY KEY, symbol TEXT);
		INSERT INTO codal_notices VALUES (8888, 'فولاد');
	`); err != nil {
		serverCodalDB.Close()
		t.Fatalf("seed server codal.db: %v", err)
	}
	serverCodalDB.Close()

	// 3. Build snapshot set
	snapshotOutDir := filepath.Join(serverDir, "dist", "snapshots")
	if err := os.MkdirAll(snapshotOutDir, 0755); err != nil {
		t.Fatalf("mkdir snapshotOutDir: %v", err)
	}
	setID := "20261108T130000Z-clientint01"

	marketDBForSnap, err := db.OpenRWC(serverMarketPath)
	if err != nil {
		t.Fatalf("open server market.db for snap: %v", err)
	}
	defer marketDBForSnap.Close()

	codalDBForSnap, err := db.OpenRWC(serverCodalPath)
	if err != nil {
		t.Fatalf("open server codal.db for snap: %v", err)
	}
	defer codalDBForSnap.Close()

	dbMap := map[string]*sql.DB{
		"market": marketDBForSnap,
		"codal":  codalDBForSnap,
	}
	manifest, err := snapshot.BuildSnapshotSet(ctx, dbMap, snapshotOutDir, setID)
	if err != nil {
		t.Fatalf("BuildSnapshotSet: %v", err)
	}

	// 4. Generate Minisign key pair and sign all assets and manifest
	pubStr, privStr, err := snapshot.GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair: %v", err)
	}

	manifestPath := filepath.Join(snapshotOutDir, "manifest.json")
	if _, err := snapshot.SignAsset(manifestPath, privStr, ""); err != nil {
		t.Fatalf("sign manifest: %v", err)
	}
	for _, a := range manifest.Assets {
		assetPath := filepath.Join(snapshotOutDir, a.Path)
		if _, err := snapshot.SignAsset(assetPath, privStr, ""); err != nil {
			t.Fatalf("sign asset %s: %v", a.Path, err)
		}
	}

	// 5. Mock HTTP server serving snapshot assets
	fileServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		filename := filepath.Base(r.URL.Path)
		filePath := filepath.Join(snapshotOutDir, filename)
		if fi, err := os.Stat(filePath); err == nil && !fi.IsDir() {
			http.ServeFile(w, r, filePath)
			return
		}
		http.NotFound(w, r)
	}))
	defer fileServer.Close()

	// 5b. Seed an existing active Generation 1 on client so rollback is valid
	gen1SetID := "20261108T110000Z-gen1"
	gen1Dir := filepath.Join(clientDir, "gens", "gen_"+gen1SetID)
	if err := os.MkdirAll(gen1Dir, 0755); err != nil {
		t.Fatalf("mkdir gen1Dir: %v", err)
	}
	gen1MarketDBPath := filepath.Join(gen1Dir, "market.db")
	gen1DB, err := db.OpenRWC(gen1MarketDBPath)
	if err != nil {
		t.Fatalf("create gen1 market.db: %v", err)
	}
	_, _ = gen1DB.Exec(`CREATE TABLE instruments (ins_code TEXT, symbol TEXT); INSERT INTO instruments VALUES ('9999', 'نماد_قدیمی');`)
	gen1DB.Close()

	initPointer := snapshot.GenerationPointer{
		SnapshotSetID: gen1SetID,
		GenerationDir: filepath.ToSlash(filepath.Join("gens", "gen_"+gen1SetID)),
		AppliedAtUTC:  "2026-11-08T11:00:00Z",
		SchemaVersion: 1,
	}
	initPtrBytes, _ := json.Marshal(initPointer)
	_ = os.WriteFile(filepath.Join(clientDir, "active_generation.json"), initPtrBytes, 0644)

	// 6. Execute Client Ingestion
	h := NewHandler(clientDir)
	h.pubKey = pubStr
	h.snapshotBaseURL = fileServer.URL

	err = h.DownloadAndApplySnapshot(ctx, fileServer.URL)
	if err != nil {
		t.Fatalf("DownloadAndApplySnapshot failed: %v", err)
	}

	// 7. Verify Client Status & Active Generation
	status := GetCodalDBStatus(clientDir, false)
	dbStatus, _ := status["db"].(map[string]any)
	if dbStatus["stage"] != "done" {
		t.Errorf("expected stage done, got %v (err: %v)", dbStatus["stage"], dbStatus["error"])
	}
	if dbStatus["percent"] != 100.0 {
		t.Errorf("expected percent 100, got %v", dbStatus["percent"])
	}

	activeGenPath := filepath.Join(clientDir, "active_generation.json")
	if _, err := os.Stat(activeGenPath); err != nil {
		t.Fatalf("active_generation.json missing: %v", err)
	}

	activeGenDir := filepath.Join(clientDir, "gens", "gen_"+setID)
	appliedMarketDB := filepath.Join(activeGenDir, "market.db")
	appliedDB, err := db.OpenRO(appliedMarketDB)
	if err != nil {
		t.Fatalf("open applied market.db: %v", err)
	}
	var ftsCount int
	if err := appliedDB.QueryRow("SELECT count(*) FROM fts_results").Scan(&ftsCount); err != nil || ftsCount != 2 {
		appliedDB.Close()
		t.Fatalf("expected 2 fts_results in active generation, got %d (err: %v)", ftsCount, err)
	}
	appliedDB.Close()

	// 8. CRITICAL VERIFICATION: USER.DB DATA INTEGRITY
	postUserDBInfo, err := os.Stat(userDBPath)
	if err != nil {
		t.Fatalf("user.db was unexpectedly deleted or moved! err: %v", err)
	}
	if postUserDBInfo.Size() != initialUserDBSize {
		t.Errorf("user.db size changed! before=%d, after=%d", initialUserDBSize, postUserDBInfo.Size())
	}
	postUserDBSHA, err := sha256OfFile(userDBPath)
	if err != nil {
		t.Fatalf("hash user.db after snapshot: %v", err)
	}
	if postUserDBSHA != initialUserDBSHA {
		t.Errorf("CRITICAL DATA LOSS / CORRUPTION: user.db SHA-256 changed after snapshot ingestion!\nBefore: %s\nAfter:  %s", initialUserDBSHA, postUserDBSHA)
	}

	// Verify user.db rows can be read cleanly
	chkUserDB, err := db.OpenRO(userDBPath)
	if err != nil {
		t.Fatalf("re-open user.db: %v", err)
	}
	var watchlistCount int
	if err := chkUserDB.QueryRow("SELECT count(*) FROM user_watchlists").Scan(&watchlistCount); err != nil || watchlistCount != 2 {
		chkUserDB.Close()
		t.Errorf("expected 2 watchlist items, got %d (err: %v)", watchlistCount, err)
	}
	var noteText string
	if err := chkUserDB.QueryRow("SELECT note FROM user_notes WHERE symbol = 'فولاد'").Scan(&noteText); err != nil || noteText != "تحلیل بنیادی تایید FTS دارد" {
		chkUserDB.Close()
		t.Errorf("expected note preserved, got %q (err: %v)", noteText, err)
	}
	chkUserDB.Close()

	// 9. ROLLBACK VERIFICATION
	applier, err := snapshot.NewApplier(snapshot.ApplierConfig{
		DataDir:   clientDir,
		PubKeyStr: pubStr,
	})
	if err != nil {
		t.Fatalf("new applier: %v", err)
	}

	// Execute rollback
	if err := applier.Rollback(); err != nil {
		t.Fatalf("Rollback failed: %v", err)
	}

	// Verify pointer points back to Generation 1
	activeGen, err := applier.ActiveGeneration()
	if err != nil {
		t.Fatalf("ActiveGeneration after rollback: %v", err)
	}
	if activeGen.SnapshotSetID != gen1SetID {
		t.Errorf("expected active generation after rollback to be %s, got %s", gen1SetID, activeGen.SnapshotSetID)
	}

	// Verify user.db is still 100% intact after rollback
	afterRollbackSHA, _ := sha256OfFile(userDBPath)
	if afterRollbackSHA != initialUserDBSHA {
		t.Errorf("user.db was corrupted during rollback!")
	}
}
