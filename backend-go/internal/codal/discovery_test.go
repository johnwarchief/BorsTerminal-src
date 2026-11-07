package codal_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"sync/atomic"
	"testing"
	"time"

	"borsterminal/backend/internal/codal"
	_ "modernc.org/sqlite"
)

func createTestDB(t *testing.T) *sql.DB {
	t.Helper()
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "test_codal.db")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatalf("failed to open test sqlite db: %v", err)
	}
	t.Cleanup(func() {
		_ = db.Close()
	})
	return db
}

func TestDiscoverFeed_PaginationAndCursor_Category1(t *testing.T) {
	var pageRequests int32

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		pageStr := r.URL.Query().Get("PageNumber")
		catStr := r.URL.Query().Get("Category")
		if catStr != "1" {
			t.Errorf("expected Category=1, got %s", catStr)
		}

		page, _ := strconv.Atoi(pageStr)
		atomic.AddInt32(&pageRequests, 1)

		w.Header().Set("Content-Type", "application/json")
		switch page {
		case 1:
			resp := map[string]any{
				"Page":  1,
				"Total": 3,
				"Letters": []map[string]any{
					{
						"TracingNo":       1002,
						"Symbol":          "فولاد",
						"CompanyName":     "فولاد مبارکه اصفهان",
						"Title":           "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۲/۱۲/۲۹",
						"LetterCode":      "ن-۳۰",
						"PublishDateTime": "1402/12/29 18:00:00",
						"SentDateTime":    "1402/12/29 17:50:00",
						"Url":             "/Reports/Decision.aspx?LetterSerial=1002",
					},
					{
						"TracingNo":       1001,
						"Symbol":          "فملی",
						"CompanyName":     "ملی صنایع مس ایران",
						"Title":           "اطلاعات و صورت‌های مالی میاندوره‌ای دوره ۶ ماهه",
						"LetterCode":      "ن-۱۰",
						"PublishDateTime": "1402/12/28 15:30:00",
						"SentDateTime":    "1402/12/28 15:20:00",
						"Url":             "/Reports/Decision.aspx?LetterSerial=1001",
					},
				},
			}
			_ = json.NewEncoder(w).Encode(resp)
		case 2:
			resp := map[string]any{
				"Page":  2,
				"Total": 3,
				"Letters": []map[string]any{
					{
						"TracingNo":       1000,
						"Symbol":          "شستا",
						"CompanyName":     "سرمایه گذاری تامین اجتماعی",
						"Title":           "صورت‌های مالی سال مالی منتهی به ۱۴۰۲/۰۳/۳۱",
						"LetterCode":      "ن-۲۰",
						"PublishDateTime": "1402/12/27 11:00:00",
						"SentDateTime":    "1402/12/27 10:45:00",
						"Url":             "/Reports/Decision.aspx?LetterSerial=1000",
					},
				},
			}
			_ = json.NewEncoder(w).Encode(resp)
		default:
			// Page 3: empty letters to indicate end of feed
			resp := map[string]any{
				"Page":    page,
				"Total":   3,
				"Letters": []map[string]any{},
			}
			_ = json.NewEncoder(w).Encode(resp)
		}
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		HTTPClient:    server.Client(),
		MinRequestGap: 10 * time.Millisecond,
		BaseURL:       server.URL,
	})

	db := createTestDB(t)
	ctx := context.Background()

	// First Discovery run
	notices, err := codal.DiscoverFeed(ctx, client, db, 1)
	if err != nil {
		t.Fatalf("DiscoverFeed failed: %v", err)
	}

	if len(notices) != 3 {
		t.Fatalf("expected 3 notices, got %d", len(notices))
	}
	if notices[0].TracingNo != 1002 || notices[0].Symbol != "فولاد" {
		t.Errorf("unexpected first notice: %+v", notices[0])
	}
	if notices[0].URL != "https://codal.ir/Reports/Decision.aspx?LetterSerial=1002" {
		t.Errorf("expected absolute URL, got %s", notices[0].URL)
	}

	// Verify insertion into codal_notices
	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM codal_notices").Scan(&count); err != nil {
		t.Fatalf("query count failed: %v", err)
	}
	if count != 3 {
		t.Fatalf("expected 3 rows in codal_notices, got %d", count)
	}

	// Verify pipeline_cursor
	var cursorVal string
	err = db.QueryRow("SELECT value FROM pipeline_cursor WHERE key = 'notice_scan_tn_cat1'").Scan(&cursorVal)
	if err != nil {
		t.Fatalf("failed to query pipeline_cursor: %v", err)
	}
	if cursorVal != "1002" {
		t.Fatalf("expected cursor value '1002', got '%s'", cursorVal)
	}

	// Second Discovery run: deduplication check.
	// Since all notices on the server are <= watermark 1002 and already in DB,
	// DiscoverFeed should return 0 new notices.
	noticesRound2, err := codal.DiscoverFeed(ctx, client, db, 1)
	if err != nil {
		t.Fatalf("DiscoverFeed round 2 failed: %v", err)
	}
	if len(noticesRound2) != 0 {
		t.Fatalf("expected 0 new notices in round 2, got %d", len(noticesRound2))
	}

	// DB count should remain 3
	_ = db.QueryRow("SELECT COUNT(*) FROM codal_notices").Scan(&count)
	if count != 3 {
		t.Fatalf("expected count 3 after deduplication, got %d", count)
	}
}

func TestDiscoverFeed_Category3_PersianDigits(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		catStr := r.URL.Query().Get("Category")
		if catStr != "3" {
			t.Errorf("expected Category=3, got %s", catStr)
		}

		pageStr := r.URL.Query().Get("PageNumber")
		w.Header().Set("Content-Type", "application/json")
		if pageStr == "1" {
			resp := map[string]any{
				"Page":  1,
				"Total": 1,
				"Letters": []map[string]any{
					{
						"TracingNo":       3001,
						"Symbol":          "شپنا",
						"CompanyName":     "پالایش نفت اصفهان",
						"Title":           "گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۲/۱۲/۲۹",
						"LetterCode":      "ن-۳۰",
						"PublishDateTime": "۱۴۰۲/۱۲/۲۹ ۱۸:۳۰:۰۰",
						"SentDateTime":    "۱۴۰۲/۱۲/۲۹ ۱۸:۲۵:۰۰",
						"Url":             "https://codal.ir/Reports/Decision.aspx?LetterSerial=3001",
					},
				},
			}
			_ = json.NewEncoder(w).Encode(resp)
		} else {
			resp := map[string]any{
				"Page":    2,
				"Total":   1,
				"Letters": []map[string]any{},
			}
			_ = json.NewEncoder(w).Encode(resp)
		}
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		HTTPClient:    server.Client(),
		MinRequestGap: 10 * time.Millisecond,
		BaseURL:       server.URL,
	})

	db := createTestDB(t)
	ctx := context.Background()

	notices, err := codal.DiscoverFeed(ctx, client, db, 3)
	if err != nil {
		t.Fatalf("DiscoverFeed category 3 failed: %v", err)
	}

	if len(notices) != 1 {
		t.Fatalf("expected 1 notice, got %d", len(notices))
	}

	// Verify Persian digits were converted to ASCII canonical date
	expectedDate := "1402/12/29 18:30:00"
	if notices[0].PublishDate != expectedDate {
		t.Errorf("expected publish date '%s', got '%s'", expectedDate, notices[0].PublishDate)
	}

	// Verify pipeline_cursor key for category 3
	var cursorVal string
	err = db.QueryRow("SELECT value FROM pipeline_cursor WHERE key = 'notice_scan_tn_cat3'").Scan(&cursorVal)
	if err != nil {
		t.Fatalf("failed to query pipeline_cursor for cat3: %v", err)
	}
	if cursorVal != "3001" {
		t.Fatalf("expected cursor value '3001', got '%s'", cursorVal)
	}
}

func TestDiscoverFeed_ContextCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"Page":1,"Total":0,"Letters":[]}`))
	}))
	defer server.Close()

	client := codal.NewPoliteClient(codal.PoliteClientConfig{
		HTTPClient:    server.Client(),
		MinRequestGap: 10 * time.Millisecond,
		BaseURL:       server.URL,
	})

	db := createTestDB(t)
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	_, err := codal.DiscoverFeed(ctx, client, db, 1)
	if err == nil {
		t.Fatalf("expected context cancellation error, got nil")
	}
}
