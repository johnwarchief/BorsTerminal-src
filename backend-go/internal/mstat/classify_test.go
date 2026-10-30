package mstat

import "testing"

// برداشت‌ها از dev/mstat_local_v975.py و probes همان فایل؛ هر ردیف یک باگِ
// واقعیِ گذشته را قفل می‌کند.
//
// دو تفاوتِ آگاهانه با متنِ بریف، هر دو با اوراکلِ پایتون سنجیده شده‌اند
// (mstat_engine.classify / fund_kind):
// ۱) «صندوق س.كالاي ديباي معيار» در بریف «etf» انتظار داشت، ولی خودِ همین
// نام «كالا» (کلیدواژهٔ commod) را دارد؛ پایتون commod می‌دهد. مقدارِ درست
// اینجا commod است و قیدِ مرزِ واژه با ردیفِ تازهٔ «صندوق س.ديباي معيار»
// (که فقط «معيار» را دارد) قفل می‌شود.
// ۲) دو ردیفِ دنبالهٔ «-د»/«-ب» در بریف پیش از رسیدن به قاعدهٔ دنباله با
// کلیدواژه («درآمد ثابت»، «بخش») پاسخ می‌گیرند، پس قاعدهٔ دنباله را
// نمی‌سنجند؛ ردیف‌هایِ «صندوق آزاد-د/-ب» همان قاعده را بی‌کلیدواژه
// می‌سنجند (حذفِ قاعدهٔ دنباله باید این‌ها را قرمز کند).
func TestClassify(t *testing.T) {
	pt := func(v int64) *int64 { return &v }
	cases := []struct {
		name, symbol, sector string
		pt                   *int64
		wantCls, wantKind    string
	}{
		{"x", "y", "", pt(1), "stock", "stock"},
		{"x", "y", "", pt(2), "stock", "stock"},
		{"x", "y", "", pt(4), "right", "right"},
		{"اختيارخ اهرم", "ضهرم1", "", pt(6), "other", "other"},
		{"a", "b", "", nil, "other", "other"},
		{"صندوق س.درآمد ثابت دينا-د", "دينا", "", pt(8), "fund", "fixed"},
		{"صندوق اهرم آگاه-س", "اهرم", "", pt(8), "fund", "lev"},
		{"صندوق سرمايه گذاري طلا گلگشت", "گلگشت", "", pt(8), "fund", "gold"},
		{"صندوق نقره-س", "نقره", "", pt(8), "fund", "silver"},
		{"صندوق س.بخشي صنايع دانايان1-ب", "نبات", "", pt(8), "fund", "equity"},
		{"صندوق نامشخص-و", "ايكس", "", pt(8), "fund", "etf"},
		// نشتِ paperType: pt=8 برایِ سهامِ عادی — نام برنده است.
		{"شرکت فولاد مبارکه", "فولاد", "", pt(8), "stock", "stock"},
		// حق تقدم از نمادِ «ح» پایانی.
		{"حق تقدم ا", "حقا", "", pt(1), "right", "right"},
		// اوراق/صکوک از نام، بی‌ توجه به paperType.
		{"صكوك اجاره فولاد006", "صفولا", "", pt(1), "other", "other"},
		{"مشاركت ش كرج712-3ماهه", "شكرج", "", pt(1), "other", "other"},
		// «آتی» فقط با نمادِ عددپایان؛ «آتيه داده پرداز» سهام می‌ماند.
		{"قرارداد آتي سكه", "طلا12", "", pt(1), "other", "other"},
		{"آتيه داده پرداز", "آتيه", "", pt(1), "stock", "stock"},
		// تسهیلات مسکن فقط از سکتور.
		{"اوراق حق تقدم تسهیلات", "ضتسه", "اوراق حق تقدم", pt(1), "other", "other"},
		// قاعدهٔ دنبالهٔ نام، بی‌هیچ کلیدواژه‌ای در نام/نماد.
		{"صندوق آزاد-د", "", "", pt(8), "fund", "fixed"},
		{"صندوق آزاد-ب", "", "", pt(8), "fund", "equity"},
		{"صندوق آزاد", "", "", pt(8), "fund", "etf"},
	}
	for _, c := range cases {
		cls, kind := classify(c.pt, c.name, c.symbol, c.sector)
		if cls != c.wantCls || kind != c.wantKind {
			t.Errorf("classify(%v,%q,%q,%q) = %s/%s, want %s/%s",
				c.pt, c.name, c.symbol, c.sector, cls, kind, c.wantCls, c.wantKind)
		}
	}
}

func TestFundKindTailRules(t *testing.T) {
	if got := fundKind("صندوق س.درآمد ثابت دينا-د", "دينا"); got != "fixed" {
		t.Fatalf("‑د tail = %s", got)
	}
	if got := fundKind("صندوق س.بخشي دانايان-ب", "نبات"); got != "equity" {
		t.Fatalf("‑ب tail = %s", got)
	}
	// «معيار» نباید «عيار» (طلا) خوانده شود.
	if got := fundKind("صندوق س.ديباي معيار", "معيار"); got != "etf" {
		t.Fatalf("word boundary: %s", got)
	}
	// همین نام با «كالا» کلیدواژهٔ commod دارد؛ اوراکلِ پایتون هم commod می‌گوید.
	if got := fundKind("صندوق س.كالاي ديباي معيار", "معيار"); got != "commod" {
		t.Fatalf("commod must win over boundary case: %s", got)
	}
	// rstripِ پایتون NBSP را هم می‌زُداید؛ نامِ صندوقِ درآمد ثابت با فاصلهٔ
	// نشکنِ پایانی باید هنوز fixed بماند، نه etf.
	if got := fundKind("صندوق درآمد ثابت آزمون-د\u00A0", "آزمون"); got != "fixed" {
		t.Fatalf("NBSP tail = %s", got)
	}
}
