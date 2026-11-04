package live

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/store"
)

func TestFetchOnceParsesAndOverlays(t *testing.T) {
	body := `{"marketwatch":[
		{"lva":"فولاد","pcl":4240,"pdv":4280,"pc":70,"py":4210,"pmx":4300,"pmn":4200,"pf":4215,"qtj":573553735,"qtc":2434652334940,"ztt":7631,"pe":"6.1","dEven":20261104,"hEven":95850,
		 "blDs":[{"pmd":28680,"qmd":623979,"zmd":19,"pmo":28690,"qmo":50988,"zmo":2},{"pmd":28670,"qmd":77468,"zmd":26,"pmo":28700,"qmo":105411,"zmo":3}]},
		{"lva":"خپارس","pcl":1746,"pdv":1744,"pc":-52,"py":1796,"pmx":1800,"pmn":1700,"pf":1790,"qtj":128062692,"qtc":223648567781,"ztt":876,"pe":"-1.1","hEven":95823}
	]}`
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(body))
	}))
	defer srv.Close()

	f := New(0)
	f.SetURL(srv.URL)
	f.SetClient(srv.Client())
	f.FetchOnce(context.Background())
	snap := f.Latest()
	if len(snap.Rows) != 2 || snap.HEven != 95850 || snap.Err != "" {
		t.Fatalf("snapshot=%+v", snap)
	}
	if snap.Rows[norm("فولاد")].Last != 4280 {
		t.Fatalf("فولاد row=%+v", snap.Rows[norm("فولاد")])
	}
	book := snap.Rows[norm("فولاد")].Book
	if !book.OK || book.Buy1Px != 28680 || book.BuyVol != 701447 || book.SellCnt != 5 {
		t.Fatalf("book=%+v", book)
	}

	fr := &store.Frame{Codes: []string{"1", "2"}, Cols: map[string][]any{
		"symbol":       {"فولاد", "خپارس"},
		"p_last":       {float64(1), float64(2)},
		"p_closing":    {float64(1), float64(2)},
		"price_change": {float64(0), float64(0)},
		"q_tot_tran":   {float64(0), float64(0)},
		"q_tot_cap":    {float64(0), float64(0)},
		"z_tot_tran":   {float64(0), float64(0)},
		"pe":           {float64(0), float64(0)},
		"h_even":       {int64(0), int64(0)},
	}}
	out := f.Apply(fr)
	if out.Cols["p_last"][0].(float64) != 4280 || out.Cols["p_last"][1].(float64) != 1744 {
		t.Fatalf("overlay p_last=%v", out.Cols["p_last"])
	}
	if out.Cols["pe"][1].(float64) != -1.1 {
		t.Fatalf("overlay negative PE=%v", out.Cols["pe"])
	}
	if out.Cols["h_even"][0].(int64) != 95850 {
		t.Fatalf("overlay h_even=%v", out.Cols["h_even"])
	}
	if fr.Cols["p_last"][0].(float64) != 1 {
		t.Fatal("Apply mutated the cached frame")
	}
}

func TestFetchOnceKeepsLastSnapshotOnForbidden(t *testing.T) {
	hits := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		if hits == 1 {
			_, _ = w.Write([]byte(`{"marketwatch":[{"lva":"فولاد","pdv":10,"hEven":100}]} `))
			return
		}
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()
	f := New(0)
	f.SetURL(srv.URL)
	f.SetClient(srv.Client())
	f.FetchOnce(context.Background())
	first := f.Latest()
	f.FetchOnce(context.Background())
	second := f.Latest()
	if len(second.Rows) != 1 || second.Rows[norm("فولاد")].Last != 10 || second.Err == "" {
		t.Fatalf("snapshot not preserved: %+v", second)
	}
	if first.HEven != second.HEven {
		t.Fatalf("HEven changed on failure: %d -> %d", first.HEven, second.HEven)
	}
}

const (
	testInsCode = "46348559193224090"
	testSymbol  = "فولاد"
)

func newTestMarketDB(t *testing.T) string {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "market.db")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	stmts := []string{
		`CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT)`,
		`CREATE TABLE market_watch (
			ins_code TEXT PRIMARY KEY, d_even INTEGER, h_even INTEGER,
			p_closing REAL, p_last REAL, price_min REAL, price_max REAL,
			price_yesterday REAL, price_first REAL, q_tot_tran REAL,
			q_tot_cap REAL, z_tot_tran REAL, price_change REAL, pe REAL,
			buy_q_vol REAL, buy_q_val REAL, buy_q_cnt REAL,
			sell_q_vol REAL, sell_q_val REAL, sell_q_cnt REAL,
			buy_q1_vol REAL, buy_q1_px REAL, sell_q1_vol REAL, sell_q1_px REAL,
			buy_q1_cnt REAL, fetched_at TEXT)`,
		`INSERT INTO instruments VALUES ('` + testInsCode + `','` + testSymbol + `')`,
		`INSERT INTO market_watch (ins_code,d_even,h_even,p_closing,p_last,
			price_min,price_max,price_yesterday,price_first,q_tot_tran,q_tot_cap,
			z_tot_tran,price_change,pe,fetched_at) VALUES ('` + testInsCode + `',
			20261028,80000,4200,4210,4150,4250,4210,4200,100,200,3,10,5.9,
			'2026-10-28 12:00:00')`,
	}
	for _, s := range stmts {
		if _, err := db.Exec(s); err != nil {
			t.Fatalf("%s: %v", s, err)
		}
	}
	return dbPath
}

type storedRow struct {
	deven, heven                    int64
	closing, last, qVol, change, pe float64
	buyQVol                         float64
	fetched                         string
}

func readStored(t *testing.T, dbPath string) storedRow {
	t.Helper()
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var r storedRow
	var buyQ sql.NullFloat64
	if err := db.QueryRow(`SELECT d_even,h_even,p_closing,p_last,q_tot_tran,price_change,pe,buy_q_vol,fetched_at
		FROM market_watch WHERE ins_code=?`, testInsCode).
		Scan(&r.deven, &r.heven, &r.closing, &r.last, &r.qVol, &r.change, &r.pe, &buyQ, &r.fetched); err != nil {
		t.Fatal(err)
	}
	if buyQ.Valid {
		r.buyQVol = buyQ.Float64
	}
	return r
}

func readBook(t *testing.T, dbPath, insCode string) (deven, heven int64, txt, updated string, err error) {
	t.Helper()
	db, oerr := sql.Open("sqlite", dbPath)
	if oerr != nil {
		t.Fatal(oerr)
	}
	defer db.Close()
	err = db.QueryRow(`SELECT d_even,h_even,book_txt,updated_at FROM order_book WHERE ins_code=?`,
		insCode).Scan(&deven, &heven, &txt, &updated)
	return deven, heven, txt, updated, err
}

func TestPersistUpdatesMarketWatchAndStatus(t *testing.T) {
	dbPath := newTestMarketDB(t)
	f := New(0)
	f.EnablePersistence(dbPath, time.Second)
	defer f.Close()
	rows := map[string]Row{
		norm(testSymbol): {
			Symbol: testSymbol, Closing: 4240, Last: 4280, Change: 70,
			Prev: 4210, Max: 4300, Min: 4200, First: 4215,
			Volume: 573553735, Value: 2434652334940, Trades: 7631, PE: 6.1,
			DEven: 20261104, HEven: 95850,
			Book: Book{
				Txt:    `[[28680,623979,19,28690,50988,2],[28670,77468,26,28700,105411,3]]`,
				BuyVol: 701447, BuyVal: 20117000000, BuyCnt: 45,
				SellVol: 156399, SellVal: 4489000000, SellCnt: 5,
				Buy1Vol: 623979, Buy1Px: 28680, Sell1Vol: 50988, Sell1Px: 28690,
				Buy1Cnt: 19, OK: true,
			},
		},
		norm("ناشناس"): {Symbol: "ناشناس", Last: 99, DEven: 20261104, HEven: 95850},
	}
	if err := f.persist(context.Background(), rows); err != nil {
		t.Fatal(err)
	}
	got := readStored(t, dbPath)
	if got.deven != 20261104 || got.heven != 95850 {
		t.Fatalf("date/time not updated: %+v", got)
	}
	if got.closing != 4240 || got.last != 4280 || got.qVol != 573553735 || got.change != 70 || got.pe != 6.1 {
		t.Fatalf("prices not updated: %+v", got)
	}
	if got.buyQVol != 701447 {
		t.Fatalf("queue aggregate not updated: %+v", got)
	}
	if got.fetched == "" {
		t.Fatal("fetched_at empty")
	}
	bde, bhe, btxt, bupdated, err := readBook(t, dbPath, testInsCode)
	if err != nil {
		t.Fatal(err)
	}
	if bde != 20261104 || bhe != 95850 || bupdated == "" {
		t.Fatalf("book session not updated: %d %d %q", bde, bhe, bupdated)
	}
	var lines [][]float64
	if err := json.Unmarshal([]byte(btxt), &lines); err != nil || len(lines) != 2 || lines[0][0] != 28680 {
		t.Fatalf("book_txt=%q err=%v", btxt, err)
	}

	raw, err := os.ReadFile(filepath.Join(filepath.Dir(dbPath), "market_sync.json"))
	if err != nil {
		t.Fatal(err)
	}
	var st map[string]any
	if err := json.Unmarshal(raw, &st); err != nil {
		t.Fatal(err)
	}
	if st["stage"] != "tsetmc" || st["phase"] != "live" || st["total"].(float64) != 1 {
		t.Fatalf("status=%v", st)
	}
	if _, ok := st["elapsed"]; !ok {
		t.Fatalf("status missing elapsed: %v", st)
	}
}

func TestPersistPreservesStoredPricesOnZero(t *testing.T) {
	dbPath := newTestMarketDB(t)
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`CREATE TABLE order_book (ins_code TEXT PRIMARY KEY,
		d_even INTEGER, h_even INTEGER, book_txt TEXT, updated_at TEXT)`); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`INSERT INTO order_book VALUES (?,?,?,?,?)`, testInsCode,
		20261028, 80000, `[[1,2,3,4,5,6]]`, "2026-10-28 12:00:00"); err != nil {
		t.Fatal(err)
	}
	db.Close()
	f := New(0)
	f.EnablePersistence(dbPath, time.Second)
	defer f.Close()
	rows := map[string]Row{
		norm(testSymbol): {Symbol: testSymbol, Volume: 5, DEven: 20261104, HEven: 95860},
	}
	if err := f.persist(context.Background(), rows); err != nil {
		t.Fatal(err)
	}
	got := readStored(t, dbPath)
	if got.closing != 4200 || got.last != 4210 || got.pe != 5.9 {
		t.Fatalf("stored prices overwritten by zero: %+v", got)
	}
	if got.qVol != 5 || got.heven != 95860 {
		t.Fatalf("volume/time not updated: %+v", got)
	}
	_, bhe, btxt, _, err := readBook(t, dbPath, testInsCode)
	if err != nil || bhe != 80000 || btxt != `[[1,2,3,4,5,6]]` {
		t.Fatalf("stale book not preserved: heven=%d txt=%q err=%v", bhe, btxt, err)
	}
}

func TestPersistSurvivesRestart(t *testing.T) {
	dbPath := newTestMarketDB(t)
	f1 := New(0)
	f1.EnablePersistence(dbPath, time.Second)
	defer f1.Close()
	if err := f1.persist(context.Background(), map[string]Row{
		norm(testSymbol): {Symbol: testSymbol, Last: 4300, DEven: 20261104, HEven: 95900},
	}); err != nil {
		t.Fatal(err)
	}
	f2 := New(0)
	f2.EnablePersistence(dbPath, time.Second)
	defer f2.Close()
	if err := f2.persist(context.Background(), map[string]Row{
		norm(testSymbol): {Symbol: testSymbol, Last: 4310, DEven: 20261104, HEven: 95910},
	}); err != nil {
		t.Fatal(err)
	}
	if got := readStored(t, dbPath); got.last != 4310 || got.heven != 95910 {
		t.Fatalf("second run did not update: %+v", got)
	}
}
