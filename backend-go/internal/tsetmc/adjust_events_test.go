package tsetmc

import (
	"context"
	"database/sql"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	_ "modernc.org/sqlite"
)

func TestFetchPriceAdjustByFlow_Parsing(t *testing.T) {
	mockJSON := `{
		"priceAdjust": [
			{
				"insCode": 0,
				"dEven": 20261004,
				"pClosing": 5710.0,
				"pClosingNotAdjusted": 5730.0,
				"corporateTypeCode": null,
				"instrument": {
					"insCode": "67690708346979840",
					"lVal18AFC": "كماسه",
					"lVal30": "تامين‌ ماسه‌ ريخته‌گري‌"
				}
			},
			{
				"insCode": "67690708346979840",
				"dEven": 20261003,
				"pClosing": 11360.0,
				"pClosingNotAdjusted": 11560.0,
				"corporateTypeCode": 2,
				"instrument": {
					"lVal18AFC": "كماسه"
				}
			}
		]
	}`

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.Path, "/ClosingPrice/GetPriceAdjustByFlow/1/500") {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, mockJSON)
	}))
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx := context.Background()

	events, err := FetchPriceAdjustByFlow(ctx, client, 1, 500)
	if err != nil {
		t.Fatalf("FetchPriceAdjustByFlow failed: %v", err)
	}

	if len(events) != 2 {
		t.Fatalf("expected 2 events, got %d", len(events))
	}

	// First event verification (insCode from nested instrument, corporateTypeCode null)
	ev0 := events[0]
	if ev0.InsCode != "67690708346979840" {
		t.Errorf("expected insCode '67690708346979840', got '%s'", ev0.InsCode)
	}
	if ev0.DEven != 20261004 {
		t.Errorf("expected dEven 20261004, got %d", ev0.DEven)
	}
	if ev0.Symbol != "كماسه" {
		t.Errorf("expected symbol 'كماسه', got '%s'", ev0.Symbol)
	}
	if ev0.PClosing != 5710.0 || ev0.PClosingNotAdjusted != 5730.0 {
		t.Errorf("unexpected prices: %f / %f", ev0.PClosing, ev0.PClosingNotAdjusted)
	}
	if ev0.CorporateTypeCode != nil {
		t.Errorf("expected nil CorporateTypeCode, got %d", *ev0.CorporateTypeCode)
	}
	expectedRatio0 := math.Round((5710.0/5730.0)*1e8) / 1e8
	if math.Abs(ev0.Ratio-expectedRatio0) > 1e-12 {
		t.Errorf("expected ratio %f, got %f", expectedRatio0, ev0.Ratio)
	}
	if ev0.Source != DefaultPriceAdjustSource {
		t.Errorf("expected source '%s', got '%s'", DefaultPriceAdjustSource, ev0.Source)
	}

	// Second event verification (top-level insCode, corporateTypeCode = 2)
	ev1 := events[1]
	if ev1.InsCode != "67690708346979840" {
		t.Errorf("expected insCode '67690708346979840', got '%s'", ev1.InsCode)
	}
	if ev1.DEven != 20261003 {
		t.Errorf("expected dEven 20261003, got %d", ev1.DEven)
	}
	if ev1.CorporateTypeCode == nil || *ev1.CorporateTypeCode != 2 {
		t.Errorf("expected CorporateTypeCode 2, got %v", ev1.CorporateTypeCode)
	}
	expectedRatio1 := math.Round((11360.0/11560.0)*1e8) / 1e8
	if math.Abs(ev1.Ratio-expectedRatio1) > 1e-12 {
		t.Errorf("expected ratio %f, got %f", expectedRatio1, ev1.Ratio)
	}
}

func TestFetchInstrumentShareChangeByFlow_Parsing(t *testing.T) {
	mockJSON := `{
		"instrumentShareChange": [
			{
				"dEven": 20261001,
				"idn": 11,
				"insCode": "46348559193224090",
				"lVal18AFC": "فولاد",
				"lVal30": "فولاد مباركه اصفهان",
				"numberOfShareOld": 50000000000.0,
				"numberOfShareNew": 60000000000.0
			}
		]
	}`

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.Path, "/Instrument/GetInstrumentShareChangeByFlow/1/14") {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, mockJSON)
	}))
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx := context.Background()

	events, err := FetchInstrumentShareChangeByFlow(ctx, client, 1, 14)
	if err != nil {
		t.Fatalf("FetchInstrumentShareChangeByFlow failed: %v", err)
	}

	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}

	ev := events[0]
	if ev.InsCode != "46348559193224090" {
		t.Errorf("expected insCode '46348559193224090', got '%s'", ev.InsCode)
	}
	if ev.DEven != 20261001 {
		t.Errorf("expected dEven 20261001, got %d", ev.DEven)
	}
	if ev.Symbol != "فولاد" {
		t.Errorf("expected symbol 'فولاد', got '%s'", ev.Symbol)
	}
	if ev.SharesOld != 50000000000.0 || ev.SharesNew != 60000000000.0 {
		t.Errorf("unexpected shares: %f -> %f", ev.SharesOld, ev.SharesNew)
	}
	expectedRatio := math.Round((50000000000.0/60000000000.0)*1e8) / 1e8
	if math.Abs(ev.Ratio-expectedRatio) > 1e-12 {
		t.Errorf("expected ratio %f, got %f", expectedRatio, ev.Ratio)
	}
	if ev.Source != DefaultShareChangeSource {
		t.Errorf("expected source '%s', got '%s'", DefaultShareChangeSource, ev.Source)
	}
}

func TestFetchIndividualEndpoints(t *testing.T) {
	mux := http.NewServeMux()

	mux.HandleFunc("/ClosingPrice/GetPriceAdjustList/12345678", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"priceAdjustList": [
			{"insCode": "12345678", "dEven": 20250601, "pClosing": 1000.0, "pClosingNotAdjusted": 1200.0, "corporateTypeCode": null, "lVal18AFC": "شستا"}
		]}`)
	})

	mux.HandleFunc("/Instrument/GetInstrumentShareChange/12345678", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"instrumentShareChange": [
			{"insCode": "12345678", "dEven": 20250501, "numberOfShareOld": 1000000.0, "numberOfShareNew": 2000000.0, "lVal18AFC": "شستا"}
		]}`)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	client := NewClient(server.URL, server.Client())
	ctx := context.Background()

	pa, err := FetchPriceAdjustList(ctx, client, "12345678")
	if err != nil {
		t.Fatalf("FetchPriceAdjustList failed: %v", err)
	}
	if len(pa) != 1 || pa[0].Symbol != "شستا" || pa[0].DEven != 20250601 {
		t.Fatalf("unexpected price adjust list output: %+v", pa)
	}

	sc, err := FetchInstrumentShareChange(ctx, client, "12345678")
	if err != nil {
		t.Fatalf("FetchInstrumentShareChange failed: %v", err)
	}
	if len(sc) != 1 || sc[0].Symbol != "شستا" || sc[0].Ratio != 0.5 {
		t.Fatalf("unexpected share change output: %+v", sc)
	}
}

func TestCorporateSchemaAndIngestion(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	if err := EnsureCorporateSchema(ctx, db); err != nil {
		t.Fatalf("EnsureCorporateSchema failed: %v", err)
	}

	// Idempotent re-run
	if err := EnsureCorporateSchema(ctx, db); err != nil {
		t.Fatalf("EnsureCorporateSchema idempotent re-run failed: %v", err)
	}

	corpCode := 2
	paEvents := []PriceAdjustEvent{
		{
			InsCode:             "INS1",
			DEven:               20260101,
			Symbol:              "نماد۱",
			PClosing:            900,
			PClosingNotAdjusted: 1000,
			CorporateTypeCode:   &corpCode,
			Ratio:               0.9,
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 10:00:00",
		},
		{
			InsCode:             "INS1",
			DEven:               20260201,
			Symbol:              "نماد۱",
			PClosing:            800,
			PClosingNotAdjusted: 1000,
			CorporateTypeCode:   nil,
			Ratio:               0.8,
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 10:00:00",
		},
	}

	if err := IngestPriceAdjustEvents(ctx, db, paEvents); err != nil {
		t.Fatalf("IngestPriceAdjustEvents failed: %v", err)
	}

	// Verify price_adjust_events in DB
	rows, err := db.QueryContext(ctx, "SELECT ins_code, d_even, symbol, corporate_type_code, ratio FROM price_adjust_events ORDER BY d_even")
	if err != nil {
		t.Fatalf("query price_adjust_events failed: %v", err)
	}
	defer rows.Close()

	count := 0
	for rows.Next() {
		var ins, sym string
		var deven int
		var code sql.NullInt64
		var ratio float64
		if err := rows.Scan(&ins, &deven, &sym, &code, &ratio); err != nil {
			t.Fatalf("scan failed: %v", err)
		}
		if count == 0 {
			if !code.Valid || code.Int64 != 2 || ratio != 0.9 {
				t.Errorf("row 0 mismatch: code=%v, ratio=%f", code, ratio)
			}
		} else if count == 1 {
			if code.Valid {
				t.Errorf("row 1 expected NULL code, got %d", code.Int64)
			}
			if ratio != 0.8 {
				t.Errorf("row 1 expected ratio 0.8, got %f", ratio)
			}
		}
		count++
	}
	if count != 2 {
		t.Fatalf("expected 2 price adjust rows, got %d", count)
	}

	// Ingest share change events
	scEvents := []ShareChangeEvent{
		{
			InsCode:   "INS2",
			DEven:     20260301,
			Symbol:    "نماد۲",
			SharesOld: 1000,
			SharesNew: 2000,
			Ratio:     0.5,
			Source:    DefaultShareChangeSource,
			FetchedAt: "2026-11-08 10:00:00",
		},
	}

	if err := IngestShareChangeEvents(ctx, db, scEvents); err != nil {
		t.Fatalf("IngestShareChangeEvents failed: %v", err)
	}

	var scCount int
	if err := db.QueryRowContext(ctx, "SELECT COUNT(*) FROM share_change_events").Scan(&scCount); err != nil {
		t.Fatalf("query share_change_events count failed: %v", err)
	}
	if scCount != 1 {
		t.Fatalf("expected 1 share change row, got %d", scCount)
	}
}

func TestDeduplicationAndUpsert(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	if err := EnsureCorporateSchema(ctx, db); err != nil {
		t.Fatalf("EnsureCorporateSchema failed: %v", err)
	}

	// Send duplicate events in the same slice
	events := []PriceAdjustEvent{
		{
			InsCode:             "DUP1",
			DEven:               20260505,
			Symbol:              "قدیم",
			PClosing:            100,
			PClosingNotAdjusted: 200,
			Ratio:               0.5,
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 09:00:00",
		},
		{
			InsCode:             "DUP1",
			DEven:               20260505,
			Symbol:              "جدید",
			PClosing:            150,
			PClosingNotAdjusted: 200,
			Ratio:               0.75,
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 10:00:00",
		},
	}

	if err := IngestPriceAdjustEvents(ctx, db, events); err != nil {
		t.Fatalf("IngestPriceAdjustEvents with duplicates failed: %v", err)
	}

	var count int
	var sym string
	var ratio float64
	err := db.QueryRowContext(ctx, "SELECT COUNT(*), symbol, ratio FROM price_adjust_events WHERE ins_code='DUP1'").Scan(&count, &sym, &ratio)
	if err != nil {
		t.Fatalf("query failed: %v", err)
	}
	if count != 1 {
		t.Fatalf("expected exactly 1 row after deduplication, got %d", count)
	}
	if sym != "جدید" || ratio != 0.75 {
		t.Errorf("expected upserted values (symbol='جدید', ratio=0.75), got symbol='%s', ratio=%f", sym, ratio)
	}
}

func TestAmendmentAndLateRowDetection(t *testing.T) {
	db := setupTestDB(t)
	ctx := context.Background()

	if err := EnsureCorporateSchema(ctx, db); err != nil {
		t.Fatalf("EnsureCorporateSchema failed: %v", err)
	}

	initialEvents := []PriceAdjustEvent{
		{
			InsCode:             "INS_AMEND",
			DEven:               20260101,
			Symbol:              "تست",
			PClosing:            900,
			PClosingNotAdjusted: 1000,
			Ratio:               0.9,
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 10:00:00",
		},
	}

	// 1. Before ingestion: 1 late row, 0 amendments
	amended, late, err := DetectPriceAdjustAmendments(ctx, db, initialEvents)
	if err != nil {
		t.Fatalf("DetectPriceAdjustAmendments failed: %v", err)
	}
	if late != 1 || amended != 0 {
		t.Fatalf("expected 1 late, 0 amended, got late=%d amended=%d", late, amended)
	}

	// Ingest initial
	if err := IngestPriceAdjustEvents(ctx, db, initialEvents); err != nil {
		t.Fatalf("ingest failed: %v", err)
	}

	// 2. Same event: 0 late, 0 amendments
	amended, late, err = DetectPriceAdjustAmendments(ctx, db, initialEvents)
	if err != nil {
		t.Fatalf("DetectPriceAdjustAmendments failed: %v", err)
	}
	if late != 0 || amended != 0 {
		t.Fatalf("expected 0 late, 0 amended, got late=%d amended=%d", late, amended)
	}

	// 3. New batch: 1 amended ratio (same insCode & dEven, ratio changed to 0.85) + 1 brand new key
	mixedEvents := []PriceAdjustEvent{
		{
			InsCode:             "INS_AMEND",
			DEven:               20260101,
			Symbol:              "تست",
			PClosing:            850,
			PClosingNotAdjusted: 1000,
			Ratio:               0.85, // changed from 0.9
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 11:00:00",
		},
		{
			InsCode:             "INS_NEW",
			DEven:               20260201,
			Symbol:              "جدید",
			PClosing:            500,
			PClosingNotAdjusted: 1000,
			Ratio:               0.5,
			Source:              DefaultPriceAdjustSource,
			FetchedAt:           "2026-11-08 11:00:00",
		},
	}

	amended, late, err = DetectPriceAdjustAmendments(ctx, db, mixedEvents)
	if err != nil {
		t.Fatalf("DetectPriceAdjustAmendments failed: %v", err)
	}
	if late != 1 || amended != 1 {
		t.Fatalf("expected 1 late, 1 amended, got late=%d amended=%d", late, amended)
	}

	// Share change amendment check
	scInitial := []ShareChangeEvent{
		{
			InsCode:   "SC_AMEND",
			DEven:     20260101,
			Symbol:    "سهم",
			SharesOld: 100,
			SharesNew: 200,
			Ratio:     0.5,
			Source:    DefaultShareChangeSource,
			FetchedAt: "2026-11-08 10:00:00",
		},
	}
	if err := IngestShareChangeEvents(ctx, db, scInitial); err != nil {
		t.Fatalf("ingest sc failed: %v", err)
	}

	scAmended := []ShareChangeEvent{
		{
			InsCode:   "SC_AMEND",
			DEven:     20260101,
			Symbol:    "سهم",
			SharesOld: 100,
			SharesNew: 300,
			Ratio:     0.33333333,
			Source:    DefaultShareChangeSource,
			FetchedAt: "2026-11-08 11:00:00",
		},
	}
	scAmendCount, scLateCount, err := DetectShareChangeAmendments(ctx, db, scAmended)
	if err != nil {
		t.Fatalf("DetectShareChangeAmendments failed: %v", err)
	}
	if scLateCount != 0 || scAmendCount != 1 {
		t.Fatalf("expected 0 late, 1 amended for SC, got late=%d amended=%d", scLateCount, scAmendCount)
	}
}

func TestSyncCorporateEvents_SpecificSymbol(t *testing.T) {
	mux := http.NewServeMux()

	mux.HandleFunc("/ClosingPrice/GetPriceAdjustList/FOOLAD_INS", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"priceAdjust": [
			{"insCode": "FOOLAD_INS", "dEven": 20260701, "pClosing": 3600.0, "pClosingNotAdjusted": 4000.0, "corporateTypeCode": null, "instrument": {"lVal18AFC": "فولاد"}}
		]}`)
	})

	mux.HandleFunc("/Instrument/GetInstrumentShareChange/FOOLAD_INS", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"instrumentShareChange": [
			{"insCode": "FOOLAD_INS", "dEven": 20260601, "numberOfShareOld": 1000.0, "numberOfShareNew": 1200.0, "lVal18AFC": "فولاد"}
		]}`)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	// Direct client with redirected BaseURL
	customClient := server.Client()
	customClient.Transport = &rewriteTransport{
		baseTransport: server.Client().Transport,
		targetURL:     server.URL,
	}

	db := setupTestDB(t)
	ctx := context.Background()

	if err := SyncCorporateEvents(ctx, customClient, db, "FOOLAD_INS"); err != nil {
		t.Fatalf("SyncCorporateEvents for symbol failed: %v", err)
	}

	var paCount, scCount int
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM price_adjust_events WHERE ins_code='FOOLAD_INS'").Scan(&paCount)
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM share_change_events WHERE ins_code='FOOLAD_INS'").Scan(&scCount)

	if paCount != 1 || scCount != 1 {
		t.Fatalf("expected 1 PA and 1 SC, got pa=%d sc=%d", paCount, scCount)
	}
}

func TestSyncCorporateEvents_AllFlows(t *testing.T) {
	var flow1PACalls, flow2PACalls int32
	var flow1SCCalls, flow2SCCalls int32

	mux := http.NewServeMux()

	mux.HandleFunc("/ClosingPrice/GetPriceAdjustByFlow/1/500", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&flow1PACalls, 1)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"priceAdjust": [
			{"insCode": "B1", "dEven": 20260501, "pClosing": 100.0, "pClosingNotAdjusted": 110.0, "corporateTypeCode": null, "lVal18AFC": "نماد۱"}
		]}`)
	})

	mux.HandleFunc("/ClosingPrice/GetPriceAdjustByFlow/2/500", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&flow2PACalls, 1)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"priceAdjust": [
			{"insCode": "F1", "dEven": 20260502, "pClosing": 200.0, "pClosingNotAdjusted": 220.0, "corporateTypeCode": 1, "lVal18AFC": "فرابورس۱"}
		]}`)
	})

	mux.HandleFunc("/Instrument/GetInstrumentShareChangeByFlow/1/14", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&flow1SCCalls, 1)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"instrumentShareChange": [
			{"insCode": "B1", "dEven": 20260501, "numberOfShareOld": 100.0, "numberOfShareNew": 150.0, "lVal18AFC": "نماد۱"}
		]}`)
	})

	mux.HandleFunc("/Instrument/GetInstrumentShareChangeByFlow/2/14", func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&flow2SCCalls, 1)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"instrumentShareChange": [
			{"insCode": "F1", "dEven": 20260502, "numberOfShareOld": 200.0, "numberOfShareNew": 300.0, "lVal18AFC": "فرابورس۱"}
		]}`)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	customClient := server.Client()
	customClient.Transport = &rewriteTransport{
		baseTransport: server.Client().Transport,
		targetURL:     server.URL,
	}

	db := setupTestDB(t)
	ctx := context.Background()

	if err := SyncCorporateEvents(ctx, customClient, db, ""); err != nil {
		t.Fatalf("SyncCorporateEvents all flows failed: %v", err)
	}

	if atomic.LoadInt32(&flow1PACalls) != 1 || atomic.LoadInt32(&flow2PACalls) != 1 {
		t.Errorf("flow PA calls expected 1, got flow1=%d flow2=%d", flow1PACalls, flow2PACalls)
	}
	if atomic.LoadInt32(&flow1SCCalls) != 1 || atomic.LoadInt32(&flow2SCCalls) != 1 {
		t.Errorf("flow SC calls expected 1, got flow1=%d flow2=%d", flow1SCCalls, flow2SCCalls)
	}

	var totalPA, totalSC int
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM price_adjust_events").Scan(&totalPA)
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM share_change_events").Scan(&totalSC)

	if totalPA != 2 || totalSC != 2 {
		t.Fatalf("expected 2 PA and 2 SC rows in DB, got pa=%d sc=%d", totalPA, totalSC)
	}
}

// rewriteTransport rewrites requests to hit the test mock server regardless of host.
type rewriteTransport struct {
	baseTransport http.RoundTripper
	targetURL     string
}

func (t *rewriteTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	req = req.Clone(req.Context())
	uri := req.URL.RequestURI()
	uri = strings.TrimPrefix(uri, "/api")
	targetReq, err := http.NewRequestWithContext(req.Context(), req.Method, t.targetURL+uri, req.Body)
	if err != nil {
		return nil, err
	}
	targetReq.Header = req.Header
	tr := t.baseTransport
	if tr == nil {
		tr = http.DefaultTransport
	}
	return tr.RoundTrip(targetReq)
}
