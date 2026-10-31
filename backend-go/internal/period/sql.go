package period

// این فایل نقیضِ تابعیِ codal_periods.py نیست، بلکه **متنِ SQL** آن است: همان
// رشته‌ها یکی‌یکی از پایتون طلایی شده‌اند (testdata/cases.json → sql.text) و
// رفتارشان رویِ SQLite هم از خودِ SQLite ثبت شده (sql.rows). دو زبان پس یکی
// می‌فرستند و SQLite هم یک جواب می‌دهد.

// ValidGlob عینِ codal_periods.VALID_GLOB. الگو فقط رقمِ ASCII و «/» دارد، پس
// رقمِ فارسی/عربی و خطِ تیره خودبه‌خود بی‌دوره می‌مانند.
const ValidGlob = "GLOB '[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]'"

// periodCol مثلِ `_col` درِ پایتون: بی‌مستعار «period_end»، با مستعار «alias.period_end».
// رشتهٔ خالی هم مثلِ None درِ پایتون «بی‌مستعار» است (شرطِ `if alias`).
func periodCol(alias string) string {
	if alias == "" {
		return "period_end"
	}
	return alias + ".period_end"
}

// DatedSQL شرطِ «این ردیف دوره دارد» — با مستعارِ اختیاریِ جدول.
func DatedSQL(alias string) string {
	c := periodCol(alias)
	return "(" + c + " IS NOT NULL AND trim(" + c + ") " + ValidGlob + ")"
}

// UndatedSQL نقیضِ DatedSQL است، نه تعریفِ دوم (بندِ ۱ codal_periods).
func UndatedSQL(alias string) string {
	c := periodCol(alias)
	return "(" + c + " IS NULL OR trim(" + c + ") NOT " + ValidGlob + ")"
}

// OrderExpr عبارتِ «تازۀترین دورۀ اول، بی‌دوره آخر» بی‌کلیدواژهٔ ORDER BY، تا درِ
// ترتیب‌هایِ مرکّب (`ORDER BY symbol, …`) هم جا بیفتد.
func OrderExpr(alias string) string {
	return "CASE WHEN " + DatedSQL(alias) + " THEN 0 ELSE 1 END, " + periodCol(alias) + " DESC"
}

// LatestOrderSQL همان OrderExpr با پیشوندِ ORDER BY. بی‌دوره اینجا **حذف** نمی‌شود،
// فقط بازندۀ ترتیب است؛ پس نمادی که فقط ردیفِ بی‌دوره دارد بی‌جواب نمی‌ماند.
func LatestOrderSQL(alias string) string { return "ORDER BY " + OrderExpr(alias) }
