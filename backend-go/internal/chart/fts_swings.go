package chart

import (
	"fmt"
	"math"
	"sort"
	"time"

	"borsterminal/backend/internal/pyround"
)

// g2j همان الگوریتمِ jalaali-js است که پایتون (`wm_calendar.g2j`) و فرانت
// (`jalaliDate.ts`) دارند — تنها تبدیلِ تقویمِ مجاز، نه یک نسخهٔ سومی.
var gdm = [12]int{0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334}

func g2j(gy, gm, gd int) (int, int, int) {
	gy2 := gy
	if gm > 2 {
		gy2++
	}
	days := 355666 + 365*gy + (gy2+3)/4 - (gy2+99)/100 + (gy2+399)/400 + gd + gdm[gm-1]
	jy := -1595 + 33*(days/12053)
	days %= 12053
	jy += 4 * (days / 1461)
	days %= 1461
	if days > 365 {
		jy += (days - 1) / 365
		days = (days - 1) % 365
	}
	var jm, jd int
	if days < 186 {
		jm, jd = 1+days/31, 1+days%31
	} else {
		jm, jd = 7+(days-186)/30, 1+(days-186)%30
	}
	return jy, jm, jd
}

// ثابت‌هایِ موتورِ FTS — عینِ api/chart.py (۱۴۰۹–۱۴۳۰).
const (
	ftsStaleBars          = 8
	ftsStaleWindow        = 52
	ftsStaleMinBars       = 12
	ftsJetMinBars         = 60
	ftsStaleMoveMin       = 0.05
	ftsSwingK             = 3
	ftsEqualTol           = 0.005
	ftsTechRulesetVersion = "3"
	ftsCHochDays          = 2
	ftsCHochMargin        = 0.01
	ftsPointTouchTol      = 0.005
)

// candle نمایِ داخلیِ سریِ روزانه؛ موتور فقط همین شش ستون را می‌خواند.
// `_fts_clean_candles` این را از ردیف‌هایِ دیکشنری می‌سازد و هر ردیفِ خراب را
// حذف می‌کند — همان قراردادِ پایتون.
type candle struct {
	Time                   string
	Open, High, Low, Close float64
	Volume                 float64
	// LiveForming همان نشانهٔ ردیفِ تکمیل‌نشدهٔ جلسه است؛ ساختارِ جهت آن را
	// نمی‌بیند (`major_swings.closed_only`).
	LiveForming bool
}

type swing struct {
	Idx   int
	Price float64
	Kind  string // "high" | "low"
	Time  string
	// زمانِ وقوع از زمانِ شناخت جدا است (anti-repaint): پیوتِ idx در کندلِ
	// idx+k تأیید می‌شود و رابط فقط از confirm_time به بعد مجاز است آن را رسم کند.
	ConfirmIdx  int
	ConfirmTime string
}

// resample معادلِ _fts_resample: تجمیعِ روزانه به هفتهٔ شنبه‌محور یا ماهِ میلادی.
func resample(candles []candle, bucket string) []candle {
	if len(candles) == 0 {
		return nil
	}
	type agg struct {
		c   candle
		set bool
	}
	out := map[string]*agg{}
	order := []string{}
	for _, c := range candles {
		t := c.Time
		if len(t) < 10 {
			continue
		}
		d, err := time.Parse("2006-01-02", t[:10])
		if err != nil {
			continue
		}
		var key string
		if bucket == "W" {
			// weekday() پایتون: دوشنبه=۰ … یکشنبه=۶؛ شنبه لنگرِ هفته است.
			wd := (int(d.Weekday()) + 6) % 7 // Go: یکشنبه=۰ → پایتون‌وار
			key = d.AddDate(0, 0, -((wd + 2) % 7)).Format("2006-01-02")
		} else {
			// «ماه» ماهِ جلالی است، نه میلادی: سبدِ ماهانهٔ موتور باید با تقویمِ
			// بازار و چارت یکی باشد (`WMC.month_key`). کلیدِ عددی با عرضِ ثابت
			// تا مرتب‌سازیِ رشته‌ای همان ترتیبِ زمانی باشد.
			jy, jm, _ := g2j(d.Year(), int(d.Month()), d.Day())
			key = fmt.Sprintf("%06d", jy*12+jm-1)
		}
		a := out[key]
		if a == nil {
			a = &agg{}
			out[key] = a
			order = append(order, key)
		}
		if !a.set {
			a.c = candle{Time: t[:10], Open: c.Open, High: c.High, Low: c.Low,
				Close: c.Close, Volume: c.Volume}
			a.set = true
		} else {
			if c.High > a.c.High {
				a.c.High = c.High
			}
			if c.Low < a.c.Low {
				a.c.Low = c.Low
			}
			a.c.Close = c.Close
			a.c.Time = t[:10]
			a.c.Volume += c.Volume
		}
	}
	keys := order
	sort.Strings(keys)
	res := make([]candle, 0, len(keys))
	for _, k := range keys {
		res = append(res, out[k].c)
	}
	return res
}

// swingsOf معادلِ _fts_swings: پیوتِ fractal با قاعدهٔ اکیدِ یک‌طرفه.
//
// سقف پیوت است اگر high[i] دست‌کم برابرِ هر دو طرفِ پنجره باشد و دست‌کم یک طرف
// را *اکیداً* بشکند؛ قرینه‌اش برایِ کف. دو clause یعنی دو سرِ یک فلات همچنان
// پیوت می‌مانند و فقط میانهٔ فلات حذف می‌شود — با «>= دوطرفه» هر روزِ تک‌قیمتیِ
// TSETMC یک پیوتِ بی‌معنا می‌ساخت (api/chart.py:3990-4011).
func swingsOf(series []candle, k int) []swing {
	n := len(series)
	if n < 2*k+2 {
		return nil
	}
	out := []swing{}
	trim := func(s string) string {
		if len(s) > 10 {
			return s[:10]
		}
		return s
	}
	for i := k; i < n-k; i++ {
		hi, lo := series[i].High, series[i].Low
		maxLH, maxRH := series[i-k].High, series[i+1].High
		minLL, minRL := series[i-k].Low, series[i+1].Low
		for j := i - k; j < i; j++ {
			if series[j].High > maxLH {
				maxLH = series[j].High
			}
			if series[j].Low < minLL {
				minLL = series[j].Low
			}
		}
		for j := i + 1; j <= i+k; j++ {
			if series[j].High > maxRH {
				maxRH = series[j].High
			}
			if series[j].Low < minRL {
				minRL = series[j].Low
			}
		}
		t := trim(series[i].Time)
		ct := trim(series[i+k].Time)
		if (hi > maxLH && hi >= maxRH) || (hi >= maxLH && hi > maxRH) {
			out = append(out, swing{Idx: i, Price: hi, Kind: "high", Time: t,
				ConfirmIdx: i + k, ConfirmTime: ct})
		}
		if (lo < minLL && lo <= minRL) || (lo <= minLL && lo < minRL) {
			out = append(out, swing{Idx: i, Price: lo, Kind: "low", Time: t,
				ConfirmIdx: i + k, ConfirmTime: ct})
		}
	}
	return out
}

// closedOnly معادلِ major_swings.closed_only: کندلِ تکمیل‌نشدهٔ جلسه بیرون
// می‌ماند تا یک تیکِ درون‌جلسه پیوتِ «تأییدشده» نسازد.
func closedOnly(series []candle) []candle {
	out := make([]candle, 0, len(series))
	for _, c := range series {
		if !c.LiveForming {
			out = append(out, c)
		}
	}
	return out
}

func highsOf(sw []swing) []swing {
	out := []swing{}
	for _, s := range sw {
		if s.Kind == "high" {
			out = append(out, s)
		}
	}
	return out
}

func lowsOf(sw []swing) []swing {
	out := []swing{}
	for _, s := range sw {
		if s.Kind == "low" {
			out = append(out, s)
		}
	}
	return out
}

// round2 مثلِ round(x, 2)ِ پایتون.
func round2(x float64) float64 { return pyround.Round(x, 2) }

// pyRound1/4/3 برایِ خروجی‌هایِ همان موتور.
func round1(x float64) float64 { return pyround.Round(x, 1) }
func round3(x float64) float64 { return pyround.Round(x, 3) }
func round4(x float64) float64 { return pyround.Round(x, 4) }

// pyTruthy معادلِ bool(x) ِ پایتون برایِ حجمِ محدودِ مقادیرِ موتور.
func pyTruthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case bool:
		return x
	case string:
		return x != ""
	case float64:
		return x != 0
	case int:
		return x != 0
	case int64:
		return x != 0
	}
	return true
}

func numOf(v any) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	}
	return 0, false
}

func pyIsFinite(x float64) bool { return !math.IsNaN(x) && !math.IsInf(x, 0) }
