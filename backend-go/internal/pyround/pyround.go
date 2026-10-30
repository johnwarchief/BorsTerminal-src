// Package pyround همان round()ِ داخلیِ پایتون است برایِ اسکالرهایِ float.
//
// چرا RoundToEven(x*10^n)/10^n کافی نیست: پایتون رویِ همان دودوییِ x درست
// گرد می‌کند، ولی ضرب و تقسیمِ اعشاری یک خطایِ دوم اضافه می‌کند (0.35 با
// rint می‌شود 0.4 و پایتون 0.3). FormatFloat('f', n) هم مثلِ CPython رویِ
// دودویی درست گرد می‌کند؛ رویِ ۲۴٬۹۰۰ ورودی (B1) صفر اختلاف داشت.
package pyround

import (
	"math"
	"strconv"
)

// Round x را با n رقمِ اعشار مانندِ round(x, n)ِ CPython برمی‌گرداند.
//
// NaN و ±Inf دست‌نخورده می‌مانند: پایتون هم رویِ آن‌ها همین کار را می‌کند و
// FormatFloat برایشان رشته‌ای می‌سازد که ParseFloat پسش نمی‌دهد.
func Round(x float64, n int) float64 {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return x
	}
	v, err := strconv.ParseFloat(strconv.FormatFloat(x, 'f', n, 64), 64)
	if err != nil {
		return x
	}
	return v
}
