// Package candle همان قاعدهٔ یکتای هندسهٔ کندلِ candle_contract.widen است.
//
// فقط widen پورت شده: از candle_contract.py تنها همین یک تابع در مسیرهایِ
// پورت‌شده صدا زده می‌شود (stored adjust events و سازنده‌هایِ ردیف مالِ
// حلقه‌هایِ نویسنده‌اند، B6). قاعده: سایه گِشاد می‌شود؛ بدنه و پایانی هرگز
// خُرد نمی‌شوند — zero یعنی «منبع هنوز پر نکرده» و با بدنه عوض می‌شود.
package candle

// Widen مثلِ candle_contract.widen: high فقط سقف را باز می‌کند و low فقط کف را.
// صفر در ورودی‌ها یعنی «غایب» (همان falsyِ پایتون).
func Widen(open, high, low float64, prices ...float64) (float64, float64) {
	body := make([]float64, 0, 1+len(prices))
	if open != 0 {
		body = append(body, open)
	}
	for _, p := range prices {
		if p != 0 {
			body = append(body, p)
		}
	}
	if len(body) == 0 {
		return high, low
	}
	hi := high
	lo := low
	if hi == 0 {
		hi = body[0]
	}
	if lo == 0 {
		lo = body[0]
	}
	for _, p := range body {
		if p > hi {
			hi = p
		}
		if p < lo {
			lo = p
		}
	}
	return hi, lo
}
