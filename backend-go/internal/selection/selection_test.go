package selection

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	_ "modernc.org/sqlite"
)

func setupTestDBs(t *testing.T) (*sql.DB, *sql.DB) {
	marketDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open marketDB: %v", err)
	}

	_, err = marketDB.Exec(`
		CREATE TABLE instruments (
			ins_code TEXT PRIMARY KEY,
			l_val18 TEXT,
			l_val30 TEXT,
			sector_name TEXT,
			paper_type INTEGER
		);
		CREATE TABLE market_watch (
			ins_code TEXT,
			d_even INTEGER,
			p_last REAL,
			p_closing REAL
		);

		-- داده‌های تست:
		-- ۱. نماد سهام عادی
		INSERT INTO instruments VALUES ('1001', 'فولاد', 'فولاد مبارکه اصفهان', 'فلزات اساسی', 1);
		INSERT INTO market_watch VALUES ('1001', 20261101, 5500.0, 5450.0);

		-- ۲. صندوق طلا
		INSERT INTO instruments VALUES ('1002', 'طلا', 'صندوق پشتوانه طلا لوتوس', 'صندوق سرمایه گذاری قابل معامله', 8);
		INSERT INTO market_watch VALUES ('1002', 20261101, 250000.0, 248000.0);

		-- ۳. اختیار معامله (نباید در انتخاب بیاید)
		INSERT INTO instruments VALUES ('1003', 'ضفولاد', 'اختیار خرید فولاد', 'اختیار معامله', 6);
		INSERT INTO market_watch VALUES ('1003', 20261101, 100.0, 95.0);
	`)
	if err != nil {
		t.Fatalf("failed to init marketDB: %v", err)
	}

	userDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open userDB: %v", err)
	}

	_, err = userDB.Exec(`
		CREATE TABLE selection_decisions (
			symbol TEXT PRIMARY KEY,
			name TEXT,
			status TEXT,
			reason TEXT,
			note TEXT,
			stop_loss TEXT,
			asset_kind TEXT,
			weight_pct REAL,
			price REAL,
			qty REAL,
			score INTEGER,
			pricing_mode TEXT,
			sector TEXT,
			updated_at TEXT
		);
	`)
	if err != nil {
		t.Fatalf("failed to init userDB: %v", err)
	}

	return marketDB, userDB
}

func TestSearchSymbols(t *testing.T) {
	marketDB, userDB := setupTestDBs(t)
	defer marketDB.Close()
	defer userDB.Close()

	svc := NewService(marketDB, userDB)
	res := svc.SearchSymbols(context.Background(), "فولاد", 10)

	if res.Status != "success" {
		t.Fatalf("expected success, got %s: %s", res.Status, res.Message)
	}
	// باید فولاد باشد اما ضفولاد (اختیار معامله) حذف شده باشد
	if len(res.Data) != 1 {
		t.Fatalf("expected 1 result, got %d", len(res.Data))
	}
	if res.Data[0].Symbol != "فولاد" {
		t.Errorf("expected symbol فولاد, got %s", res.Data[0].Symbol)
	}
	if res.Data[0].Price == nil || *res.Data[0].Price != 5500.0 {
		t.Errorf("expected price 5500, got %v", res.Data[0].Price)
	}

	// تست صندوق طلا
	goldRes := svc.SearchSymbols(context.Background(), "طلا", 10)
	if len(goldRes.Data) != 1 || goldRes.Data[0].Symbol != "طلا" {
		t.Fatalf("expected gold fund, got %+v", goldRes.Data)
	}
}

func TestPostAndGetPortfolio(t *testing.T) {
	marketDB, userDB := setupTestDBs(t)
	defer marketDB.Close()
	defer userDB.Close()

	svc := NewService(marketDB, userDB)
	ctx := context.Background()

	// ۱. ثبت تصمیم accept برای فولاد
	p1 := map[string]any{
		"symbol":     "فولاد",
		"name":       "فولاد مبارکه",
		"status":     "accept",
		"price":      5000.0,
		"qty":        1000.0, // ارزش: ۵,۰۰۰,۰۰۰ تومان
		"asset_kind": "rial",
	}
	postRes1 := svc.SaveDecision(ctx, p1)
	if postRes1.Status != "success" || postRes1.Decision == nil {
		t.Fatalf("failed to post decision 1: %+v", postRes1)
	}

	// ۲. ثبت تصمیم accept برای طلا
	p2 := map[string]any{
		"symbol":     "طلا",
		"name":       "صندوق طلا",
		"status":     "accept",
		"price":      250000.0,
		"qty":        60.0, // ارزش: ۱۵,۰۰۰,۰۰۰ تومان
		"asset_kind": "dollar",
	}
	postRes2 := svc.SaveDecision(ctx, p2)
	if postRes2.Status != "success" {
		t.Fatalf("failed to post decision 2: %+v", postRes2)
	}

	// ۳. ثبت تصمیم monitor
	p3 := map[string]any{
		"symbol": "فملی",
		"name":   "ملی مس",
		"status": "monitor",
	}
	postRes3 := svc.SaveDecision(ctx, p3)
	if postRes3.Status != "success" {
		t.Fatalf("failed to post decision 3: %+v", postRes3)
	}

	// ۴. دریافت گزارش پورتفولیو
	port := svc.GetPortfolio(ctx)
	if port.Status != "success" {
		t.Fatalf("failed to get portfolio: %s", port.Message)
	}
	if len(port.Portfolio) != 2 {
		t.Fatalf("expected 2 in portfolio, got %d", len(port.Portfolio))
	}
	if len(port.Monitor) != 1 {
		t.Fatalf("expected 1 in monitor, got %d", len(port.Monitor))
	}
	if port.Counts["accept"] != 2 || port.Counts["monitor"] != 1 {
		t.Errorf("unexpected counts: %+v", port.Counts)
	}

	// بررسی منبع وزن: چون هر دو ارزش دارند، باید value باشد
	if port.Limits.WeightSource != "value" {
		t.Errorf("expected weight_source=value, got %s", port.Limits.WeightSource)
	}
	// مجموع ارزش: ۵,۰۰۰,۰۰۰ + ۱۵,۰۰۰,۰۰۰ = ۲۰,۰۰۰,۰۰۰
	if port.Limits.PortfolioValue == nil || *port.Limits.PortfolioValue != 20000000 {
		t.Errorf("expected total value 20000000, got %v", port.Limits.PortfolioValue)
	}

	// ۵. تست بازگشت به pending (حذف فیزیکی)
	pendingPayload := map[string]any{
		"symbol": "فملی",
		"status": "pending",
	}
	pendRes := svc.SaveDecision(ctx, pendingPayload)
	if pendRes.Status != "success" {
		t.Fatalf("failed to set pending: %+v", pendRes)
	}

	portAfter := svc.GetPortfolio(ctx)
	if len(portAfter.Monitor) != 0 || portAfter.Counts["monitor"] != 0 {
		t.Errorf("expected 0 monitor after pending, got %+v", portAfter.Counts)
	}

	// ۶. تست RemoveDecision
	delRes := svc.RemoveDecision(ctx, "طلا")
	if delRes.Status != "success" || delRes.Deleted != 1 {
		t.Errorf("failed to delete decision: %+v", delRes)
	}
}

func TestHTTPHandlers(t *testing.T) {
	marketDB, userDB := setupTestDBs(t)
	defer marketDB.Close()
	defer userDB.Close()

	svc := NewService(marketDB, userDB)

	// تست GET /api/selection/symbols?q=فولاد
	req := httptest.NewRequest("GET", "/api/selection/symbols?q=فولاد", nil)
	w := httptest.NewRecorder()
	svc.Symbols(w, req)
	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}

	// تست POST /api/selection/decision
	body, _ := json.Marshal(map[string]any{
		"symbol": "فولاد",
		"status": "accept",
	})
	reqPost := httptest.NewRequest("POST", "/api/selection/decision", bytes.NewReader(body))
	wPost := httptest.NewRecorder()
	svc.PostDecision(wPost, reqPost)
	if wPost.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wPost.Code)
	}

	// تست GET /api/selection/portfolio
	reqPort := httptest.NewRequest("GET", "/api/selection/portfolio", nil)
	wPort := httptest.NewRecorder()
	svc.Portfolio(wPort, reqPort)
	if wPort.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wPort.Code)
	}

	// تست DELETE /api/selection/decision/فولاد
	reqDel := httptest.NewRequest("DELETE", "/api/selection/decision/فولاد", nil)
	wDel := httptest.NewRecorder()
	svc.DeleteDecision(wDel, reqDel)
	if wDel.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", wDel.Code)
	}
}
