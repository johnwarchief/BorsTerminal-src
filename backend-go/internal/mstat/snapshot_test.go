package mstat

import (
	"database/sql"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestInTradingSession(t *testing.T) {
	// شنبه ۱۰:۰۰ صبح (جلسه معاملاتی معتبر) -> شنبه 2026-10-31
	sat10am := time.Date(2026, 10, 31, 10, 0, 0, 0, time.UTC)
	if !InTradingSession(100000, sat10am) {
		t.Errorf("expected true for 10:00 on Saturday")
	}

	// قبل از شروع بازار (08:50)
	if InTradingSession(85000, sat10am) {
		t.Errorf("expected false for 08:50 before session open")
	}

	// بعد از پایان بازار (13:10)
	if InTradingSession(131000, sat10am) {
		t.Errorf("expected false for 13:10 after session close")
	}

	// پنج‌شنبه (تعطیل) -> 2026-10-29
	thu10am := time.Date(2026, 10, 29, 10, 0, 0, 0, time.UTC)
	if InTradingSession(100000, thu10am) {
		t.Errorf("expected false for Thursday holiday")
	}

	// جمعه (تعطیل) -> 2026-10-30
	fri10am := time.Date(2026, 10, 30, 10, 0, 0, 0, time.UTC)
	if InTradingSession(100000, fri10am) {
		t.Errorf("expected false for Friday holiday")
	}
}

func TestEncStates(t *testing.T) {
	states := map[string]string{
		"IRO1FOOL0001": "b",
		"IRO1FOLD0001": "s",
		"IRO1KHOR0001": "p",
	}
	blob, err := encStates(states)
	if err != nil {
		t.Fatalf("encStates error: %v", err)
	}
	if blob == "" {
		t.Fatalf("expected non-empty blob")
	}
}

func TestSaveSnapshotTable(t *testing.T) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open sqlite: %v", err)
	}
	defer db.Close()

	// ایجاد جدول mstat_snap و جداول پایه
	_, err = db.Exec(`
		CREATE TABLE market_watch (
			ins_code TEXT,
			p_closing REAL, p_last REAL, price_yesterday REAL, price_first REAL,
			price_min REAL, price_max REAL, allowed_min REAL, allowed_max REAL,
			q_tot_tran REAL, q_tot_cap REAL, z_tot_tran REAL, price_change REAL,
			total_shares REAL, h_even INTEGER, d_even INTEGER
		);
		CREATE TABLE client_type (
			ins_code TEXT, d_even INTEGER,
			buy_i_vol REAL, buy_n_vol REAL, buy_ddd_vol REAL, buy_count_i REAL, buy_count_n REAL,
			sell_i_vol REAL, sell_n_vol REAL, sell_count_i REAL, sell_count_n REAL
		);
		CREATE TABLE instruments (
			ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT, sector_name TEXT,
			base_vol REAL, paper_type INTEGER
		);
		CREATE TABLE mstat_snap (
			d_even INTEGER NOT NULL, h_even INTEGER NOT NULL,
			ts TEXT, agg TEXT, PRIMARY KEY (d_even, h_even)
		);
	`)
	if err != nil {
		t.Fatalf("create tables: %v", err)
	}

	// درج داده نمونه
	_, err = db.Exec(`
		INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code, sector_name, base_vol, paper_type)
		VALUES ('IRO1FOOL0001', 'فولاد', 'فولاد مبارکه', '27', 'فلزات اساسی', 1, 1);
		INSERT INTO market_watch (ins_code, p_closing, p_last, price_yesterday, price_first, price_min, price_max, allowed_min, allowed_max, q_tot_tran, q_tot_cap, z_tot_tran, price_change, total_shares, d_even, h_even)
		VALUES ('IRO1FOOL0001', 5000, 5100, 4900, 4950, 4900, 5150, 4800, 5200, 1000000, 5100000000, 500, 200, 1000000000, 20261028, 103000);
	`)
	if err != nil {
		t.Fatalf("insert sample row: %v", err)
	}

	svc := New(db, ".", nil)

	// تست در روز پنج‌شنبه (خارج از ساعات رسمی)
	thu := time.Date(2026, 10, 29, 10, 30, 0, 0, time.UTC)
	res, err := svc.SaveSnapshot(thu)
	if err != nil {
		t.Fatalf("SaveSnapshot error: %v", err)
	}
	if res["saved"] != false || res["reason"] != "outside_trading_session" {
		t.Errorf("expected outside_trading_session, got: %v", res)
	}

	// تست در روز شنبه (داخل ساعات معاملاتی)
	sat := time.Date(2026, 10, 31, 10, 30, 0, 0, time.UTC)
	res, err = svc.SaveSnapshot(sat)
	if err != nil {
		t.Fatalf("SaveSnapshot error: %v", err)
	}
	if res["saved"] != true {
		t.Errorf("expected saved=true, got: %v", res)
	}

	// بررسی درج در جدول mstat_snap
	var count int
	if err := db.QueryRow("SELECT COUNT(*) FROM mstat_snap WHERE d_even=20261028 AND h_even=103000").Scan(&count); err != nil {
		t.Fatalf("query mstat_snap: %v", err)
	}
	if count != 1 {
		t.Errorf("expected count=1 in mstat_snap, got %d", count)
	}
}
