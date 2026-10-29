// Package clientsplit همان client_split.py است: تنها تعریفِ درصدِ حقیقی/حقوقی.
//
// مبنایِ درصدها ارزشِ خرید و فروش است، نه حجم؛ ارزشِ گم‌شده از ضربِ حجم در
// قیمت بازسازی نمی‌شود. سه قاعده، عینِ پایتون:
//
//	۱. خرید و فروش مستقل حساب می‌شوند؛ مخرجِ هر کسر فقط جمعِ همان سمت است.
//	۲. سهمِ حقوقی مکملِ سهمِ حقیقیِ همان سمت است، با همان گردکردن.
//	۳. نبودِ داده جعل نمی‌شود: منفی، NaN، ±Inf، رشته، مخرجِ صفر و نبودِ یکی از
//	   دو گروه همه «نامشخص» (nil) می‌شوند، نه صفر.
package clientsplit

import "math"

// BasisValue تنها مبنایی است که این لایه می‌سازد؛ همان رشتۀ pct_basis.
const BasisValue = "value"

// Split درصدهایِ هر دو سمت. nil یعنی «نامشخص»؛ Basis فقط وقتی پر می‌شود که
// حداقل یک سمت اندازه گرفته شده باشد (client_split.shares).
//
// نامِ نوع Split است نه Shares: درِ Go نوع و تابع نمی‌توانند هم‌نام باشند و
// نامِ تابعِ قراردادی Shares است (board.Derive و تسکِ ۶ همان را صدا می‌زنند).
type Split struct {
	RetailBuy  *float64
	LegalBuy   *float64
	RetailSell *float64
	LegalSell  *float64
	Basis      *string
}

// money عددِ ریالیِ معتبر یا false — بی‌تخمین و بی‌مطلق‌سازی.
//
// منفی بودنِ ارزشِ یک گروه معنایِ فنی ندارد (سهمِ فروشِ همان گروه درِ TSETMC
// مثبت گزارش می‌شود)، پس منفی «مقدارِ نامعتبر» است نه «صفر». رشته و []byte
// ورودیِ این لایه نیستند حتی اگر عددپذیر باشند: عددِ خوانده‌شده از SQLite عدد
// است، و رشته یعنی قراردادِ ستون جایی بالاتر شکسته شده.
func money(v any) (float64, bool) {
	var x float64
	switch n := v.(type) {
	case float64:
		x = n
	case int64:
		x = float64(n)
	case int:
		x = float64(n)
	default:
		return 0, false
	}
	if math.IsNaN(x) || math.IsInf(x, 0) || x < 0 {
		return 0, false
	}
	return x, true
}

// share سهمِ حقیقی از ارزشِ یک سمت (۰ تا ۱۰۰) — یا nil یعنی نامشخص.
// گردکردن یک‌رقمی و نیم‌به‌زوج، مثلِ round(x, 1) در پایتون.
func share(retail, legal any) *float64 {
	r, ok1 := money(retail)
	l, ok2 := money(legal)
	if !ok1 || !ok2 {
		return nil
	}
	den := r + l
	if den <= 0 {
		return nil
	}
	x := math.RoundToEven(100.0*r/den*10.0) / 10.0
	return &x
}

// complement سهمِ حقوقیِ همان سمت؛ مکملِ سهمِ حقیقیِ *گردشده*، با همان
// گردکردنِ یک‌رقمی. یک سمتِ نصفه‌نیمه درصد ندارد.
func complement(s *float64) *float64 {
	if s == nil {
		return nil
	}
	x := math.RoundToEven((100.0-*s)*10.0) / 10.0
	return &x
}

// Shares چهار درصد و مبنایشان را از چهار ارزشِ مبدأ می‌سازد.
//
// pct_basis تنها وقتی value است که حداقل یک سمت درصد داشته باشد؛ وگرنه nil،
// یعنی «برایِ این نماد در این نشست ارزشِ مبدأ نداریم».
func Shares(buyI, buyN, sellI, sellN any) Split {
	rb := share(buyI, buyN)
	sb := share(sellI, sellN)
	out := Split{
		RetailBuy:  rb,
		LegalBuy:   complement(rb),
		RetailSell: sb,
		LegalSell:  complement(sb),
	}
	if rb != nil || sb != nil {
		basis := BasisValue
		out.Basis = &basis
	}
	return out
}
