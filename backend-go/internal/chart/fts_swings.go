package chart

import (
	"math"
	"sort"
	"time"

	"borsterminal/backend/internal/pyround"
)

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
)

// candle نمایِ داخلیِ سریِ روزانه؛ موتور فقط همین شش ستون را می‌خواند.
// `_fts_clean_candles` این را از ردیف‌هایِ دیکشنری می‌سازد و هر ردیفِ خراب را
// حذف می‌کند — همان قراردادِ پایتون.
type candle struct {
	Time                   string
	Open, High, Low, Close float64
	Volume                 float64
}

type swing struct {
	Idx   int
	Price float64
	Kind  string // "high" | "low"
	Time  string
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
			key = t[:7]
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

// swings معادلِ _fts_swings: پیوتِ fractal؛ شرطِ هر دو طرف غیراکید است و
// اکیداً بزرگ‌تر بودنِ یک طرف از قرارداد نیست (پلاتویِ تخت چند پیوت می‌دهد).
func swingsOf(series []candle, k int) []swing {
	n := len(series)
	if n < 2*k+2 {
		return nil
	}
	out := []swing{}
	for i := k; i < n-k; i++ {
		hi, lo := series[i].High, series[i].Low
		hiOK, loOK := true, true
		for j := i - k; j < i; j++ {
			if series[j].High > hi {
				hiOK = false
			}
			if series[j].Low < lo {
				loOK = false
			}
		}
		for j := i + 1; j <= i+k; j++ {
			if series[j].High > hi {
				hiOK = false
			}
			if series[j].Low < lo {
				loOK = false
			}
		}
		t := series[i].Time
		if len(t) > 10 {
			t = t[:10]
		}
		if hiOK {
			out = append(out, swing{Idx: i, Price: hi, Kind: "high", Time: t})
		}
		if loOK {
			out = append(out, swing{Idx: i, Price: lo, Kind: "low", Time: t})
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
