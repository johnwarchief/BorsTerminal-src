package clientsplit

import (
	"math"
	"testing"
)

func TestShares(t *testing.T) {
	got := Shares(10e6, 5e6, 8e6, 6e6)
	if got.RetailBuy == nil || math.Abs(*got.RetailBuy-66.7) > 1e-9 {
		t.Fatalf("retail buy = %v, want 66.7", got.RetailBuy)
	}
	if got.LegalBuy == nil || math.Abs(*got.LegalBuy-33.3) > 1e-9 {
		t.Fatalf("legal buy = %v, want 33.3", got.LegalBuy)
	}
	if got.Basis == nil || *got.Basis != "value" {
		t.Fatalf("basis = %v", got.Basis)
	}
	if got := Shares(0.0, 0.0, 8e6, 6e6); got.RetailBuy != nil {
		t.Fatal("zero denominator must be unknown")
	}
	if got := Shares(-1.0, 5e6, 8e6, 6e6); got.RetailBuy != nil {
		t.Fatal("negative value must be unknown")
	}
}

// TestSharesBothSidesMissing نبودِ ارزشِ مبدأ هیچ درصدی نمی‌سازد؛ برخلافِ
// متنِ بریف که همان را با یک سمتِ سالم می‌سنجید، اینجا هر دو سمت ناقص‌اند تا
// انتظار با client_split.shares بخواند (یک سمتِ سالم ⇒ pct_basis=value).
func TestSharesBothSidesMissing(t *testing.T) {
	got := Shares(nil, 5e6, nil, 6e6)
	if got.RetailBuy != nil || got.LegalBuy != nil || got.RetailSell != nil || got.LegalSell != nil {
		t.Fatalf("missing source values must be unknown, got %+v", got)
	}
	if got.Basis != nil {
		t.Fatalf("basis = %v, want nil when nothing is measured", *got.Basis)
	}
}

// TestSharesSidesAreIndependent قاعدهٔ ۱ِ client_split را قفل می‌کند: مخرجِ هر
// کسر فقط جمعِ همان سمت است و نبودِ یک سمت، سمتِ دیگر را نمی‌بلعد.
func TestSharesSidesAreIndependent(t *testing.T) {
	got := Shares(nil, 5e6, 8e6, 6e6)
	if got.RetailBuy != nil || got.LegalBuy != nil {
		t.Fatal("incomplete buy side must be unknown")
	}
	if got.RetailSell == nil || math.Abs(*got.RetailSell-57.1) > 1e-9 {
		t.Fatalf("retail sell = %v, want 57.1", got.RetailSell)
	}
	if got.LegalSell == nil || math.Abs(*got.LegalSell-42.9) > 1e-9 {
		t.Fatalf("legal sell = %v, want 42.9", got.LegalSell)
	}
	if got.Basis == nil || *got.Basis != "value" {
		t.Fatal("one measured side is enough for pct_basis=value")
	}
}

// TestSharesRejectsNonMoney هر ورودیِ غیرعددی/منفی/NaN/Inf نامشخص است؛ رشته
// حتی اگر عددپذیر باشد تبدیل نمی‌شود (قراردادِ client_split.money).
func TestSharesRejectsNonMoney(t *testing.T) {
	for _, bad := range []any{-1.0, math.NaN(), math.Inf(1), math.Inf(-1), "100", []byte("100"), nil} {
		if got := Shares(bad, 5e6, 8e6, 6e6); got.RetailBuy != nil {
			t.Fatalf("buy_i_val=%#v must be unknown, got %v", bad, *got.RetailBuy)
		}
	}
}

// TestSharesZeroGroupIsReal صفرِ یک گروه ارزشِ معتبر است (فقط مخرجِ صفر
// نامشخص می‌شود): حقیقی ۰ و حقوقی ۱۰۰.
func TestSharesZeroGroupIsReal(t *testing.T) {
	got := Shares(0, 5e6, 5e6, 0)
	if got.RetailBuy == nil || *got.RetailBuy != 0 {
		t.Fatalf("retail buy = %v, want 0", got.RetailBuy)
	}
	if got.LegalBuy == nil || *got.LegalBuy != 100 {
		t.Fatalf("legal buy = %v, want 100", got.LegalBuy)
	}
	if got.RetailSell == nil || *got.RetailSell != 100 {
		t.Fatalf("retail sell = %v, want 100", got.RetailSell)
	}
	if got.LegalSell == nil || *got.LegalSell != 0 {
		t.Fatalf("legal sell = %v, want 0", got.LegalSell)
	}
}

// TestRound1Ties گره‌هایی که roundِ داخلیِ پایتون و rintِ numpy رویِ آن‌ها واگرا
// می‌شوند: round(0.35,1)=0.3 ولی rint(0.35*10)/10=0.4. جفتِ 12.25 گرهِ دقیقِ
// دودویی است و هر دو رژیم 12.2 می‌دهند؛ بقیه پنج مقدار واگرا هستند.
func TestRound1Ties(t *testing.T) {
	cases := []struct{ in, want float64 }{
		{0.35, 0.3},
		{0.45, 0.5},
		{1.15, 1.1},
		{1.05, 1.1},
		{0.15, 0.1},
		{12.25, 12.2},
	}
	for _, c := range cases {
		if got := round1(c.in); got != c.want {
			t.Errorf("round1(%v) = %v, want %v", c.in, got, c.want)
		}
	}
}

// TestSharesSQLiteInts مقادیرِ REAL/INTEGERِ SQLite را می‌پذیرد.
func TestSharesSQLiteInts(t *testing.T) {
	got := Shares(int64(10e6), int64(5e6), int64(8e6), int64(6e6))
	if got.RetailBuy == nil || math.Abs(*got.RetailBuy-66.7) > 1e-9 {
		t.Fatalf("retail buy = %v, want 66.7", got.RetailBuy)
	}
}
