package chart

import (
	"context"
	"database/sql"
	"math"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/pricebasis"
	"borsterminal/backend/internal/symbolid"
)

func TestAdjustmentEngine_ComputeFactors(t *testing.T) {
	times := []string{
		"2024-01-01",
		"2024-03-01",
		"2024-06-01",
		"2024-09-01",
		"2024-12-01",
	}

	events := []AdjustEventItem{
		{Date: "2024-02-15", Ratio: 0.80, Type: "capital_increase", Source: "share_change"},
		{Date: "2024-07-20", Ratio: 0.90, Type: "dividend", Source: "price_adjust"},
	}

	t.Run("AdjustmentRaw (mode=0) returns 1.0 for all candles", func(t *testing.T) {
		factors := ComputeAdjustmentFactors(times, events, AdjustmentRaw)
		if len(factors) != len(times) {
			t.Fatalf("expected %d factors, got %d", len(times), len(factors))
		}
		for i, f := range factors {
			if f != 1.0 {
				t.Errorf("expected 1.0 at index %d, got %f", i, f)
			}
		}
	})

	t.Run("AdjustmentCapitalIncrease (mode=1) only applies capital increase events", func(t *testing.T) {
		factors := ComputeAdjustmentFactors(times, events, AdjustmentCapitalIncrease)
		// 2024-01-01 is before 2024-02-15 (ratio 0.80), so factor = 0.80
		// 2024-03-01 onwards is after 2024-02-15, so factor = 1.0
		expected := []float64{0.80, 1.0, 1.0, 1.0, 1.0}
		for i, exp := range expected {
			if math.Abs(factors[i]-exp) > 1e-6 {
				t.Errorf("at index %d: expected %f, got %f", i, exp, factors[i])
			}
		}
	})

	t.Run("AdjustmentDividend (mode=2) only applies dividend events", func(t *testing.T) {
		factors := ComputeAdjustmentFactors(times, events, AdjustmentDividend)
		// 2024-01-01, 2024-03-01, 2024-06-01 are before 2024-07-20 (ratio 0.90), so factor = 0.90
		// 2024-09-01, 2024-12-01 are after 2024-07-20, so factor = 1.0
		expected := []float64{0.90, 0.90, 0.90, 1.0, 1.0}
		for i, exp := range expected {
			if math.Abs(factors[i]-exp) > 1e-6 {
				t.Errorf("at index %d: expected %f, got %f", i, exp, factors[i])
			}
		}
	})

	t.Run("AdjustmentFunctional (mode=3) applies combined cumulative backward product", func(t *testing.T) {
		factors := ComputeAdjustmentFactors(times, events, AdjustmentFunctional)
		// 2024-01-01: before both events -> 0.80 * 0.90 = 0.72
		// 2024-03-01, 2024-06-01: after cap increase, before dividend -> 0.90
		// 2024-09-01, 2024-12-01: after both events -> 1.0
		expected := []float64{0.72, 0.90, 0.90, 1.0, 1.0}
		for i, exp := range expected {
			if math.Abs(factors[i]-exp) > 1e-6 {
				t.Errorf("at index %d: expected %f, got %f", i, exp, factors[i])
			}
		}
	})

	t.Run("Empty events returns 1.0 cleanly", func(t *testing.T) {
		factors := ComputeAdjustmentFactors(times, nil, AdjustmentFunctional)
		for i, f := range factors {
			if f != 1.0 {
				t.Errorf("expected 1.0 at index %d, got %f", i, f)
			}
		}
	})

	t.Run("Empty times returns empty slice cleanly", func(t *testing.T) {
		factors := ComputeAdjustmentFactors([]string{}, events, AdjustmentFunctional)
		if len(factors) != 0 {
			t.Errorf("expected empty slice, got %d items", len(factors))
		}
	})
}

func TestIsNearDate(t *testing.T) {
	cases := []struct {
		d1, d2  string
		maxDays int
		want    bool
	}{
		{"2026-08-05", "2026-08-03", 4, true},
		{"2026-08-05", "2026-08-05", 0, true},
		{"2026-08-05", "2026-08-10", 4, false},
		{"2026-08-05", "2026-08-09", 4, true},
		{"invalid", "invalid", 4, true},
		{"2026-08-05", "invalid", 4, false},
	}
	for _, c := range cases {
		got := isNearDate(c.d1, c.d2, c.maxDays)
		if got != c.want {
			t.Errorf("isNearDate(%q, %q, %d) = %v, want %v", c.d1, c.d2, c.maxDays, got, c.want)
		}
	}
}

func Test20FamousSymbols_AdjustmentScenarios(t *testing.T) {
	symbols := []string{
		"فولاد", "فملی", "شستا", "شپنا", "شبندر",
		"شتران", "خودرو", "خساپا", "وبملت", "وتجارت",
		"وبصادر", "فارس", "تاپیکو", "کگل", "کچاد",
		"وغدیر", "ومعادن", "وامید", "رمپنا", "پارس",
	}

	times := []string{
		"2023-01-01", "2023-06-01", "2024-01-01", "2024-06-01",
		"2025-01-01", "2025-06-01", "2026-01-01", "2026-08-01",
	}

	for _, sym := range symbols {
		// شبیه‌سازی رویدادهای مجمع و افزایش سرمایه متناسب با نمادهای واقعی
		events := []AdjustEventItem{
			{Date: "2023-07-20", Ratio: 0.85, Type: "capital_increase", Source: "share_change"},
			{Date: "2024-07-25", Ratio: 0.95, Type: "dividend", Source: "price_adjust"},
			{Date: "2025-03-15", Ratio: 0.75, Type: "capital_increase", Source: "share_change"},
			{Date: "2026-07-20", Ratio: 0.92, Type: "dividend", Source: "price_adjust"},
		}

		rawFactors := ComputeAdjustmentFactors(times, events, AdjustmentRaw)
		for i, f := range rawFactors {
			if f != 1.0 {
				t.Errorf("%s raw factor at %d = %f, want 1.0", sym, i, f)
			}
		}

		capFactors := ComputeAdjustmentFactors(times, events, AdjustmentCapitalIncrease)
		divFactors := ComputeAdjustmentFactors(times, events, AdjustmentDividend)
		funcFactors := ComputeAdjustmentFactors(times, events, AdjustmentFunctional)

		// اطمینان از اینکه ضرایب تعدیل همواره کاهشی یا برابر به عقب هستند (F(t) <= F(t+1))
		for i := 0; i < len(times)-1; i++ {
			if capFactors[i] > capFactors[i+1]+1e-9 {
				t.Errorf("%s cap factor increasing backwards at %d: %f > %f", sym, i, capFactors[i], capFactors[i+1])
			}
			if divFactors[i] > divFactors[i+1]+1e-9 {
				t.Errorf("%s div factor increasing backwards at %d: %f > %f", sym, i, divFactors[i], divFactors[i+1])
			}
			if funcFactors[i] > funcFactors[i+1]+1e-9 {
				t.Errorf("%s functional factor increasing backwards at %d: %f > %f", sym, i, funcFactors[i], funcFactors[i+1])
			}
		}

		// در تاریخ‌های قبل از همه رویدادها، ضریب عملکردی برابر حاصل‌ضرب ضریب افزایش سرمایه و سود نقدی است
		expectedEarlyFunc := capFactors[0] * divFactors[0]
		if math.Abs(funcFactors[0]-expectedEarlyFunc) > 1e-6 {
			t.Errorf("%s early functional factor mismatch: got %f, want %f", sym, funcFactors[0], expectedEarlyFunc)
		}
	}
}

func Test20FamousSymbols_RealMarketDB(t *testing.T) {
	dbPath, err := filepath.Abs(filepath.Join("..", "..", "..", "market.db"))
	if err != nil {
		t.Skip("skipping real market.db test: db path err")
		return
	}
	db, err := sql.Open("sqlite", "file:"+filepath.ToSlash(dbPath)+"?mode=ro")
	if err != nil {
		t.Skip("skipping real market.db test: db not openable")
		return
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		t.Skip("skipping real market.db test: db ping failed")
		return
	}

	symbols := []string{
		"فولاد", "فملی", "شستا", "شپنا", "شبندر",
		"شتران", "خودرو", "خساپا", "وبملت", "وتجارت",
		"وبصادر", "فارس", "تاپیکو", "کگل", "کچاد",
		"وغدیر", "ومعادن", "وامید", "رمپنا", "پارس",
	}

	ctx := context.Background()
	sid := symbolid.New(db)
	defer sid.Close()
	svc := &Service{
		market: db,
		sid:    sid,
		basis:  pricebasis.New(pricebasis.Last),
	}

	for _, sym := range symbols {
		evs := svc.LoadAutonomousAdjustmentEvents(ctx, sym)
		if len(evs) == 0 {
			t.Errorf("symbol %s: expected autonomous adjustment events, got 0", sym)
		}

		// بررسی صحت فیلدهای هر رویداد
		for i, ev := range evs {
			if ev.Date == "" {
				t.Errorf("%s event[%d] has empty date", sym, i)
			}
			if ev.Ratio <= 0 || math.IsNaN(ev.Ratio) {
				t.Errorf("%s event[%d] has invalid ratio: %f", sym, i, ev.Ratio)
			}
			if ev.Type != "capital_increase" && ev.Type != "dividend" && ev.Type != "combined" {
				t.Errorf("%s event[%d] has unknown type: %q", sym, i, ev.Type)
			}
		}

		// بررسی محاسبه فاکتورها روی تاریخچه‌های واقعی
		times := []string{
			"2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01",
			"2024-01-01", "2025-01-01", "2026-01-01", "2026-10-01",
		}
		raw := ComputeAdjustmentFactors(times, evs, AdjustmentRaw)
		cap := ComputeAdjustmentFactors(times, evs, AdjustmentCapitalIncrease)
		div := ComputeAdjustmentFactors(times, evs, AdjustmentDividend)
		fnc := ComputeAdjustmentFactors(times, evs, AdjustmentFunctional)

		for i := 0; i < len(times); i++ {
			if raw[i] != 1.0 {
				t.Errorf("%s raw factor at %d != 1.0", sym, i)
			}
			if cap[i] <= 0 || div[i] <= 0 || fnc[i] <= 0 {
				t.Errorf("%s factors must be positive, got cap=%f, div=%f, fnc=%f at %d", sym, cap[i], div[i], fnc[i], i)
			}
		}

		// رویدادهای شرکتی
		corpEvs := svc.corporateEvents(ctx, sym)
		// نمادهای شاخص مانند فولاد، فملی، شستا، شپنا باید رویداد شرکتی داشته باشند
		if sym == "فولاد" || sym == "فملی" || sym == "شستا" || sym == "شپنا" {
			if len(corpEvs) == 0 {
				t.Errorf("%s expected non-empty corporateEvents, got 0", sym)
			}
		}
	}
}

func TestRahavardCorrectionPackParity_ShastaFemeli(t *testing.T) {
	// This test pins the legacy R32B overlay pack. The product default is now
	// the Phase 4.9 reference-verified rebuild, so load the legacy directory
	// explicitly to keep testing the pack the assertion was written for.
	legacy := ""
	for _, base := range []string{"..", "../..", "../../..", "../../../.."} {
		p := filepath.Join(base, "data", "ra365_corrections", "ra365-r32b-v2")
		if _, err := os.Stat(filepath.Join(p, "manifest.json")); err == nil {
			legacy = p
			break
		}
	}
	if legacy == "" {
		t.Skip("legacy ra365-r32b-v2 pack not found")
		return
	}
	pack := loadPackFromDir(legacy)
	if pack == nil {
		t.Skip("legacy Rahavard correction pack could not be loaded")
		return
	}

	// ۱. بررسی پوشش شستا
	shastaSteps, coveredShasta := pack.GetPackSteps("", "شستا")
	if !coveredShasta || len(shastaSteps) == 0 {
		t.Fatalf("expected شستا to be covered by Rahavard pack, got covered=%v len=%d", coveredShasta, len(shastaSteps))
	}

	// ۲. بررسی پوشش فملی
	femeliSteps, coveredFemeli := pack.GetPackSteps("", "فملی")
	if !coveredFemeli || len(femeliSteps) == 0 {
		t.Fatalf("expected فملی to be covered by Rahavard pack, got covered=%v len=%d", coveredFemeli, len(femeliSteps))
	}

	// ۳. راستی‌آزمایی گام‌های شستا: باید شامل سود نقدی سال‌های تاریخی قبل از ۲۰۲۴ باشد
	foundOldShastaDividend := false
	for _, step := range shastaSteps {
		if step.Date < "2024-01-01" && (step.Type == "dividend" || step.EventSig == "dps") {
			foundOldShastaDividend = true
			break
		}
	}
	if !foundOldShastaDividend {
		t.Errorf("expected historical pre-2024 dividend step for شستا in pack")
	}

	// ۴. راستی‌آزمایی گام ترکیبی ۲۰۲۶ فملی
	foundFemeliJointStep := false
	for _, step := range femeliSteps {
		if step.Date >= "2026-07-01" && step.Date <= "2026-08-15" {
			// ضریب گام مشترک رهاورد در راند ۳۲ب تقریباً ۰.۷۱۳۴۱۳۷۱۴ است
			if math.Abs(step.Ratio-0.713413714) < 1e-4 {
				foundFemeliJointStep = true
				break
			}
		}
	}
	if !foundFemeliJointStep {
		t.Errorf("expected Rahavard joint step ratio ~0.713413714 for فملی")
	}
}
