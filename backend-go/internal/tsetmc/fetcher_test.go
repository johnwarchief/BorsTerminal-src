package tsetmc

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open in-memory db: %v", err)
	}
	t.Cleanup(func() {
		_ = db.Close()
	})
	return db
}

func TestFetchAndIngestMarketWatch(t *testing.T) {
	mux := http.NewServeMux()

	// Mock /StaticData/GetStaticData
	mux.HandleFunc("/StaticData/GetStaticData", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{
			"staticData": [
				{"type": "IndustrialGroup", "code": "27", "name": "فلزات اساسي"},
				{"type": "IndustrialGroup", "code": "44", "name": "خودرو و ساخت قطعات"}
			]
		}`)
	})

	// Mock /ClosingPrice/GetMarketWatch
	mux.HandleFunc("/ClosingPrice/GetMarketWatch", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{
			"marketwatch": [
				{
					"insCode": "35700344742885862",
					"dEven": 20261108,
					"hEven": 123000,
					"pcl": 5000,
					"pdv": 5050,
					"pmn": 4900,
					"pmx": 5100,
					"pMin": 4850,
					"pMax": 5150,
					"py": 4950,
					"pf": 5020,
					"qtj": 10000000,
					"qtc": 50500000000,
					"ztt": 12000,
					"pc": 50,
					"eps": 650,
					"pe": 7.7,
					"ztd": 800000000000,
					"csv": "27",
					"lva": "فولاد",
					"lvc": "فولاد مباركه اصفهان",
					"bv": 1,
					"insID": "IRO1FOLD0009",
					"cGrValCot": "01",
					"flow": 1,
					"pRedTran": 0,
					"buyOP": 0,
					"paperType": 1,
					"marketValue": 0,
					"blDs": [
						{"qmd": 100000, "pmd": 5040, "zmd": 25, "qmo": 50000, "pmo": 5060, "zmo": 15},
						{"qmd": 200000, "pmd": 5030, "zmd": 30, "qmo": 80000, "pmo": 5070, "zmo": 20}
					]
				},
				{
					"insCode": "46348559193224090",
					"dEven": 20261108,
					"hEven": 123000,
					"pcl": 3200,
					"pdv": 3220,
					"pmn": 3150,
					"pmx": 3250,
					"pMin": 3100,
					"pMax": 3300,
					"py": 3180,
					"pf": 3190,
					"qtj": 5000000,
					"qtc": 16000000000,
					"ztt": 8000,
					"pc": 20,
					"eps": 120,
					"pe": 26.8,
					"ztd": 300000000000,
					"csv": "44",
					"lva": "خودرو",
					"lvc": "ايران‌ خودرو",
					"bv": 1,
					"insID": "IRO1IKCO0001",
					"cGrValCot": "02",
					"flow": 1,
					"pRedTran": 0,
					"buyOP": 0,
					"paperType": 1,
					"marketValue": 960000000000000,
					"blDs": []
				}
			]
		}`)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx := context.Background()

	mwRows, instRows, err := client.FetchMarketWatch(ctx)
	if err != nil {
		t.Fatalf("FetchMarketWatch failed: %v", err)
	}

	if len(mwRows) != 2 {
		t.Fatalf("expected 2 market watch rows, got %d", len(mwRows))
	}
	if len(instRows) != 2 {
		t.Fatalf("expected 2 instrument rows, got %d", len(instRows))
	}

	// Verify calculated fields on Symbol 1
	row1 := mwRows[0]
	if row1.InsCode != "35700344742885862" {
		t.Errorf("expected ins_code 35700344742885862, got %s", row1.InsCode)
	}
	if row1.PClosing != 5000 || row1.PLast != 5050 {
		t.Errorf("expected p_closing 5000, p_last 5050; got %f, %f", row1.PClosing, row1.PLast)
	}
	// MarketCap computed from pcl * shares
	expectedMcap1 := 5000.0 * 800000000000.0
	if row1.MarketCap != expectedMcap1 || row1.MarketCapSrc != "tse_board_calc" {
		t.Errorf("expected mcap %f (tse_board_calc), got %f (%s)", expectedMcap1, row1.MarketCap, row1.MarketCapSrc)
	}
	// Best limits depth
	if row1.BuyQVol != 300000 || row1.BuyQCnt != 55 {
		t.Errorf("expected buy_q_vol 300000, buy_q_cnt 55; got %f, %f", row1.BuyQVol, row1.BuyQCnt)
	}
	expectedBuyQVal := 100000.0*5040.0 + 200000.0*5030.0
	if row1.BuyQVal != expectedBuyQVal {
		t.Errorf("expected buy_q_val %f, got %f", expectedBuyQVal, row1.BuyQVal)
	}
	if row1.BuyQ1Vol != 100000 || row1.BuyQ1Px != 5040 || row1.BuyQ1Cnt != 25 {
		t.Errorf("expected buy_q1 vol/px/cnt 100000/5040/25; got %f/%f/%f", row1.BuyQ1Vol, row1.BuyQ1Px, row1.BuyQ1Cnt)
	}

	// Verify Symbol 2 raw market cap
	row2 := mwRows[1]
	if row2.MarketCap != 960000000000000 || row2.MarketCapSrc != "tse_raw" {
		t.Errorf("expected raw mcap 960000000000000 (tse_raw), got %f (%s)", row2.MarketCap, row2.MarketCapSrc)
	}

	// Verify Instruments sector mapping
	inst1 := instRows[0]
	if inst1.LVal18 != "فولاد" || inst1.SectorName != "فلزات اساسي" {
		t.Errorf("expected 'فولاد' and 'فلزات اساسي', got '%s' and '%s'", inst1.LVal18, inst1.SectorName)
	}
	inst2 := instRows[1]
	if inst2.LVal18 != "خودرو" || inst2.SectorName != "خودرو و ساخت قطعات" {
		t.Errorf("expected 'خودرو' and 'خودرو و ساخت قطعات', got '%s' and '%s'", inst2.LVal18, inst2.SectorName)
	}

	// Test Ingest into SQLite DB
	db := setupTestDB(t)
	if err := EnsureMarketWatchSchema(db); err != nil {
		t.Fatalf("EnsureMarketWatchSchema failed: %v", err)
	}

	if err := IngestMarketWatch(ctx, db, mwRows, instRows); err != nil {
		t.Fatalf("IngestMarketWatch failed: %v", err)
	}

	// Assert SQLite database contents
	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM market_watch").Scan(&count); err != nil || count != 2 {
		t.Fatalf("expected 2 rows in market_watch, got %d (err: %v)", count, err)
	}
	if err := db.QueryRow("SELECT COUNT(*) FROM instruments").Scan(&count); err != nil || count != 2 {
		t.Fatalf("expected 2 rows in instruments, got %d (err: %v)", count, err)
	}

	var readSecName, readIsin string
	err = db.QueryRow("SELECT sector_name, isin FROM instruments WHERE ins_code = ?", "35700344742885862").Scan(&readSecName, &readIsin)
	if err != nil || readSecName != "فلزات اساسي" || readIsin != "IRO1FOLD0009" {
		t.Errorf("query instrument error: %v, sector: %s, isin: %s", err, readSecName, readIsin)
	}

	// Test Sticky behavior on update: empty isin and 0 flow must NOT erase existing values
	instUpdate := []InstrumentRow{
		{
			InsCode:     "35700344742885862",
			LVal18:      "فولاد",
			LVal30:      "فولاد مباركه اصفهان",
			SectorCode:  "27",
			SectorName:  "فلزات اساسي",
			TotalShares: 800000000000,
			ISIN:        "", // empty in skinny update
		},
	}
	mwUpdate := []MarketWatchRow{
		{
			InsCode:  "35700344742885862",
			DEven:    20261108,
			PClosing: 5100,
			PLast:    5120,
			Flow:     0, // 0 in skinny update
		},
	}
	if err := IngestMarketWatch(ctx, db, mwUpdate, instUpdate); err != nil {
		t.Fatalf("IngestMarketWatch sticky update failed: %v", err)
	}

	var stickyIsin string
	var stickyFlow int
	err = db.QueryRow("SELECT isin FROM instruments WHERE ins_code = ?", "35700344742885862").Scan(&stickyIsin)
	if err != nil || stickyIsin != "IRO1FOLD0009" {
		t.Errorf("sticky isin failed to preserve original: got %s, err: %v", stickyIsin, err)
	}

	err = db.QueryRow("SELECT flow FROM market_watch WHERE ins_code = ?", "35700344742885862").Scan(&stickyFlow)
	if err != nil || stickyFlow != 1 {
		t.Errorf("sticky flow failed to preserve original: got %d, err: %v", stickyFlow, err)
	}
}

func TestFetchAndIngestClientTypeAll(t *testing.T) {
	mux := http.NewServeMux()

	mux.HandleFunc("/ClientType/GetClientTypeAll", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{
			"clientTypeAllDto": [
				{
					"insCode": "35700344742885862",
					"dEven": 20261108,
					"buy_I_Volume": 8500000,
					"buy_N_Volume": 1500000,
					"buy_DDD_Volume": 0,
					"buy_CountI": 2400,
					"buy_CountN": 12,
					"buy_CountDDD": 0,
					"sell_I_Volume": 3000000,
					"sell_N_Volume": 7000000,
					"sell_CountI": 950,
					"sell_CountN": 45
				}
			]
		}`)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx := context.Background()

	points, err := client.FetchClientTypeAll(ctx)
	if err != nil {
		t.Fatalf("FetchClientTypeAll failed: %v", err)
	}
	if len(points) != 1 {
		t.Fatalf("expected 1 client type point, got %d", len(points))
	}

	pt := points[0]
	if pt.InsCode != "35700344742885862" || pt.BuyIVol != 8500000 || pt.BuyCountI != 2400 {
		t.Errorf("unexpected client type values: %+v", pt)
	}

	// Ingest into SQLite
	db := setupTestDB(t)
	if err := EnsureClientTypeSchema(db); err != nil {
		t.Fatalf("EnsureClientTypeSchema failed: %v", err)
	}

	if err := IngestClientType(ctx, db, points); err != nil {
		t.Fatalf("IngestClientType failed: %v", err)
	}

	var buyIVol float64
	var buyCountI int64
	err = db.QueryRow("SELECT buy_i_vol, buy_count_i FROM client_type WHERE ins_code = ? AND d_even = ?",
		"35700344742885862", 20261108).Scan(&buyIVol, &buyCountI)
	if err != nil || buyIVol != 8500000 || buyCountI != 2400 {
		t.Fatalf("queried client_type error: %v, vol: %f, cnt: %d", err, buyIVol, buyCountI)
	}
}

func TestFetchAndIngestClientTypeHistory(t *testing.T) {
	mux := http.NewServeMux()

	// Native client type history (all 4 values present)
	mux.HandleFunc("/ClientType/GetClientTypeHistory/35700344742885862/20261105", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{
			"clientType": {
				"buy_I_Value": 42500000000,
				"buy_N_Value": 7500000000,
				"sell_I_Value": 15000000000,
				"sell_N_Value": 35000000000,
				"buy_DDD_Value": 0,
				"recDate": 20261105
			}
		}`)
	})

	// Mixed client type history (some missing/null values)
	mux.HandleFunc("/ClientType/GetClientTypeHistory/mixed_ins/20261105", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{
			"clientType": {
				"buy_I_Value": 42500000000,
				"buy_N_Value": null,
				"sell_I_Value": 15000000000,
				"sell_N_Value": 35000000000,
				"buy_DDD_Value": 0,
				"recDate": 20261105
			}
		}`)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx := context.Background()

	// 1. Fetch native
	ptNative, err := client.FetchClientTypeHistory(ctx, "35700344742885862", 20261105)
	if err != nil {
		t.Fatalf("FetchClientTypeHistory native failed: %v", err)
	}
	if ptNative.Kind != "native" {
		t.Errorf("expected kind 'native', got '%s'", ptNative.Kind)
	}
	if ptNative.BuyIVal != 42500000000 || ptNative.SellIVal != 15000000000 {
		t.Errorf("unexpected values for native: %+v", ptNative)
	}

	// 2. Fetch mixed
	ptMixed, err := client.FetchClientTypeHistory(ctx, "mixed_ins", 20261105)
	if err != nil {
		t.Fatalf("FetchClientTypeHistory mixed failed: %v", err)
	}
	if ptMixed.Kind != "mixed" {
		t.Errorf("expected kind 'mixed', got '%s'", ptMixed.Kind)
	}

	// Ingest into SQLite
	db := setupTestDB(t)
	if err := EnsureClientTypeSchema(db); err != nil {
		t.Fatalf("EnsureClientTypeSchema failed: %v", err)
	}

	if err := IngestClientTypeValue(ctx, db, []ClientTypeValuePoint{*ptNative, *ptMixed}); err != nil {
		t.Fatalf("IngestClientTypeValue failed: %v", err)
	}

	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM client_type_value").Scan(&count); err != nil || count != 2 {
		t.Fatalf("expected 2 rows in client_type_value, got %d (err: %v)", count, err)
	}

	var kindNative string
	_ = db.QueryRow("SELECT kind FROM client_type_value WHERE ins_code = ?", "35700344742885862").Scan(&kindNative)
	if kindNative != "native" {
		t.Errorf("expected db kind 'native', got '%s'", kindNative)
	}

	var kindMixed string
	_ = db.QueryRow("SELECT kind FROM client_type_value WHERE ins_code = ?", "mixed_ins").Scan(&kindMixed)
	if kindMixed != "mixed" {
		t.Errorf("expected db kind 'mixed', got '%s'", kindMixed)
	}
}

func TestClient_429RetryWithRetryAfter(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		att := atomic.AddInt32(&attempts, 1)
		if att == 1 {
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status": "ok"}`)
	}))
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	client.BackoffBase = 1 * time.Millisecond

	var result map[string]string
	err := client.GetJSON(context.Background(), "/test", &result)
	if err != nil {
		t.Fatalf("expected success after retry, got: %v", err)
	}
	if result["status"] != "ok" {
		t.Errorf("unexpected result: %+v", result)
	}
	if atomic.LoadInt32(&attempts) != 2 {
		t.Errorf("expected 2 attempts, got %d", attempts)
	}
}

func TestClient_5xxRetry(t *testing.T) {
	var attempts int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		att := atomic.AddInt32(&attempts, 1)
		if att == 1 {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"status": "recovered"}`)
	}))
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	client.BackoffBase = 1 * time.Millisecond

	var result map[string]string
	err := client.GetJSON(context.Background(), "/test", &result)
	if err != nil {
		t.Fatalf("expected success after 5xx retry, got: %v", err)
	}
	if result["status"] != "recovered" {
		t.Errorf("unexpected result: %+v", result)
	}
	if atomic.LoadInt32(&attempts) != 2 {
		t.Errorf("expected 2 attempts, got %d", attempts)
	}
}

func TestClient_ContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(50 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel immediately

	var result map[string]any
	err := client.GetJSON(ctx, "/test", &result)
	if err == nil {
		t.Fatal("expected error on cancelled context, got nil")
	}
	if !strings.Contains(err.Error(), "context canceled") {
		t.Errorf("expected context canceled error, got: %v", err)
	}
}

func TestClient_MaxRetriesExhausted(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	client.BackoffBase = 1 * time.Millisecond
	client.MaxRetries = 2

	var result map[string]any
	err := client.GetJSON(context.Background(), "/test", &result)
	if err == nil {
		t.Fatal("expected error on exhausted retries, got nil")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("expected HTTP 500 error, got: %v", err)
	}
}
