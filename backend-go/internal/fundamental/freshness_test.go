package fundamental

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
)

// openFreshnessService یک کپیِ موقتِ فیکسچر می‌سازد، ردیف‌هایِ سناریویِ تازگی را
// پیش از بازکردنِ read-only درج می‌کند و سرویس را برمی‌گرداند.
func openFreshnessService(t *testing.T, quarantinePub string) *Service {
	t.Helper()
	dir := t.TempDir()
	raw, err := os.ReadFile(filepath.Join("testdata", "fixture", "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	dbPath := filepath.Join(dir, "market.db")
	if err := os.WriteFile(dbPath, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	conn, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	stmts := []string{
		`CREATE TABLE IF NOT EXISTS pipeline_dirty (symbol TEXT, axis TEXT, reason TEXT)`,
		`CREATE TABLE IF NOT EXISTS codal_extracted (tracing_no INTEGER, state TEXT,
			kind TEXT, last_error TEXT)`,
		`INSERT INTO instruments (ins_code,l_val18,l_val30,sector_name,updated_at,paper_type)
		 VALUES ('FRESH01','تازگی01','تازگی','فلزات','2026-11-03 12:00:00',1)`,
		`INSERT INTO market_watch (ins_code,d_even) VALUES ('FRESH01',20261103)`,
		`INSERT INTO codal_notices (tracing_no,symbol,publish_date)
		 VALUES (88001,'تازگی01','1405/06/31 09:00:00')`,
		`INSERT INTO monthly_sales (tracing_no,symbol,period_end,year,month,ytd_revenue)
		 VALUES (88001,'تازگی01','1405/06/31',1405,6,1000)`,
		`INSERT INTO financial_statements (tracing_no,symbol,title,report_kind,
			period_months,period_end,publish_date,revenue,net_profit,basic_eps,
			is_audited,is_consolidated,fiscal_year)
		 VALUES (99001,'تازگی01','صورت مالی سالانه حسابرسی‌شده غیرتلفیقی','annual',
			12,'1404/12/29','1405/08/01 09:00:00',500,100,50,1,0,'1404')`,
		`INSERT INTO pipeline_dirty (symbol,axis,reason)
		 VALUES ('تازگی01','1_growth','در انتظار بازمحاسبه')`,
	}
	if quarantinePub != "" {
		stmts = append(stmts,
			`INSERT INTO codal_notices (tracing_no,symbol,publish_date)
			 VALUES (88002,'تازگی01','`+quarantinePub+`')`,
			`INSERT INTO codal_extracted (tracing_no,state,kind,last_error)
			 VALUES (88002,'quarantined','ms','رد جدید')`,
		)
	}
	for _, stmt := range stmts {
		if _, err := conn.Exec(stmt); err != nil {
			t.Fatalf("%s: %v", stmt, err)
		}
	}
	conn.Close()

	freshnessMu.Lock()
	freshnessCache = map[string]freshnessEntry{}
	freshnessMu.Unlock()

	h, err := db.Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	s := New(h.Market, dir)
	t.Cleanup(func() { _ = s.Close() })
	return s
}

func TestFreshness(t *testing.T) {
	s := openFreshnessService(t, "1405/01/01")
	body, err := s.FreshnessBody(context.Background(), []string{"تازگی01"})
	if err != nil {
		t.Fatal(err)
	}
	items, _ := body["items"].([]any)
	if len(items) != 1 {
		t.Fatalf("items=%v", body)
	}
	one, _ := items[0].(map[string]any)
	axes, _ := one["axes"].(map[string]any)
	get := func(k string) map[string]any { m, _ := axes[k].(map[string]any); return m }

	a1 := get("1_growth")
	if a1["state"] != "stale" || a1["as_of"] != "2026-09-22T09:00:00+03:30" {
		t.Fatalf("1_growth=%v", a1)
	}
	if a1["reason"] != "در انتظار بازمحاسبه" {
		t.Fatalf("1_growth reason=%v", a1["reason"])
	}
	a2 := get("2_eps_trend")
	if a2["state"] != "fresh" || a2["period_end"] != "1404/12/29" {
		t.Fatalf("2_eps_trend=%v", a2)
	}
	a4 := get("4_sales_to_mcap")
	if a4["as_of"] != "2026-11-03" {
		t.Fatalf("4_sales_to_mcap=%v", a4)
	}
	a5 := get("5_industry")
	if a5["as_of"] != "2026-11-03" {
		t.Fatalf("5_industry=%v", a5)
	}
	if one["as_of"] != "2026-09-22T09:00:00+03:30" {
		t.Fatalf("card as_of=%v", one["as_of"])
	}
}

func TestFreshnessQuarantineBeatsCanonicalWhenNewer(t *testing.T) {
	s := openFreshnessService(t, "1405/07/01")
	body, err := s.FreshnessBody(context.Background(), []string{"تازگی01"})
	if err != nil {
		t.Fatal(err)
	}
	one := body["items"].([]any)[0].(map[string]any)
	axes := one["axes"].(map[string]any)
	for _, key := range []string{"1_growth", "4_sales_to_mcap"} {
		ax := axes[key].(map[string]any)
		if ax["state"] != "quarantined" || ax["reason"] != "رد جدید" {
			t.Fatalf("%s=%v", key, ax)
		}
	}
	if ax := axes["2_eps_trend"].(map[string]any); ax["state"] != "fresh" {
		t.Fatalf("fs quarantine leaked into eps: %v", ax)
	}
}
