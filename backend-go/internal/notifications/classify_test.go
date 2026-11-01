package notifications

import (
	"testing"
)

func TestClassify(t *testing.T) {
	tests := []struct {
		title      string
		letterCode string
		wantKind   string
		wantLevel  string
	}{
		{
			title:     "اطلاعات و صورتهای مالی میاندوره‌ای دوره ۶ ماهه منتهی به ۱۴۰۴/۰۶/۳۱",
			wantKind:  "statements",
			wantLevel: LevelHigh,
		},
		{
			title:     "صورت‌های مالی سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ (حسابرسی شده)",
			wantKind:  "statements",
			wantLevel: LevelHigh,
		},
		{
			title:     "آگهی دعوت به مجمع عمومی عادی سالیانه برای سال مالی منتهی به...",
			wantKind:  "assembly",
			wantLevel: LevelHigh,
		},
		{
			title:     "تصمیمات مجمع عمومی فوق العاده در خصوص افزایش سرمایه",
			wantKind:  "capital",
			wantLevel: LevelHigh,
		},
		{
			title:     "زمانبندی پرداخت سود نقدی پیشنهادی هیئت مدیره",
			wantKind:  "dividend",
			wantLevel: LevelHigh,
		},
		{
			title:     "اطلاعیه عرضه اولیه سهام شرکت...",
			wantKind:  "ipo",
			wantLevel: LevelHigh,
		},
		{
			title:     "سررسید اوراق مرابحه عام دولت...",
			wantKind:  "maturity",
			wantLevel: LevelHigh,
		},
		{
			title:     "گزارش فعالیت ماهانه ۱ ماهه منتهی به ۱۴۰۴/۰۷/۳۰",
			wantKind:  "monthly",
			wantLevel: LevelMedium,
		},
		{
			title:     "گزارش تولید و فروش هفتگی مهر ماه",
			wantKind:  "production",
			wantLevel: LevelMedium,
		},
		{
			title:     "تغییر در ترکیب اعضای هیئت مدیره",
			wantKind:  "governance",
			wantLevel: LevelLow,
		},
		{
			title:     "عنوان کاملاً ناشناخته و متفرقه",
			wantKind:  "other",
			wantLevel: LevelUnclassfied,
		},
	}

	for _, tt := range tests {
		got := Classify(tt.title, tt.letterCode)
		if got.Kind != tt.wantKind {
			t.Errorf("Classify(%q) Kind = %q, want %q", tt.title, got.Kind, tt.wantKind)
		}
		if got.Level != tt.wantLevel {
			t.Errorf("Classify(%q) Level = %q, want %q", tt.title, got.Level, tt.wantLevel)
		}
	}
}

func TestDedupeKey(t *testing.T) {
	k1 := DedupeKey("رمپنا", "گزارش فعالیت ماهانه", "1404/07/30 18:00:00")
	k2 := DedupeKey(" رمپنا ", "گزارش\u200cفعالیت  ماهانه ", "1404/07/30")
	if k1 != k2 {
		t.Errorf("expected k1 == k2, got %q vs %q", k1, k2)
	}
}
