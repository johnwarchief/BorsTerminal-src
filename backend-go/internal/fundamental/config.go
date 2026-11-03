package fundamental

// آستانه‌های روش‌شناسی — حکمِ جزوه، نه سلیقه. هیچ عددی اینجا عوض نمی‌شود؛
// فایل `fts_thresholds.json` (پنلِ تنظیمات کدال)overrideها را می‌نویسد و
// `v10Thresholds` همان‌ها را با همان ترتیبِ پرابِ پایتون می‌خواند.
// مرجع: `bors_config.py:786-859` (FTS_DEFAULTS/legacy)، `api/market.py:35-112`
// (load_fts_config)، `api/fundamental.py:75-152` (FTS_V10_DEFAULTS/v10_thresholds).

import (
	"bytes"
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"unicode"
)

// v10Defaults عینِ FTS_V10_DEFAULTS درِ api/fundamental.py.
var v10Defaults = map[string]any{
	"monetary_growth_min":    40.0, // ۱الف — کفِ قبولیِ رشد ریالی (= growth_min)
	"monetary_growth_target": 60.0, // ۱الف — هدفِ پوشش تورم؛ برچسب، نه دروازۀ امتیاز
	"volume_growth_min":      0.0,  // ۱ب — رشد تولیدی باید غیرمنفی باشد
	"volume_breadth_min":     0.60, // ۱ب — دادهٔ نمایشی
	"eps_years":              3,    // ۲ — طولِ سابقۀ سودسازی (int)
	"margin_min":             20.0, // ۳ — کف حاشیۀ ناخالص
	"margin_ideal":           30.0, // ۳ — حاشیۀ مطلوب
	"sales_to_mcap_min":      0.33, // ۴الف
	"potential_min":          40.0, // ۴ب
	"inflation_basis":        60.0, // ۱ب — مبنای تورم
}

// ftsDefaultOrder همان ترتیبِ درجِ FTS_DEFAULTS درِ bors_config.py است؛ ترتیب
// درِ پاک‌سازیِ نوع لازم نیست (پایتون رویِ cfg.items() حلقه می‌کند که همان
// ترتیبِ dict است) ولی برایِ بازخوانیِ deterministic نگه داشته می‌شود.
var strKeys = []string{"industry_mode", "hourglass_ma52_position"}
var listKeys = []string{"mandatory_sectors", "free_sectors", "include_industries",
	"exclude_industries", "exclude_rejected_indicators"}

// ftsDefaults پیش‌فرض‌های مشترکِ موتور/پنل. مقدارها عین‌اند؛ نوع هم عینِ پایتون
// (float/int/bool/string/[]string) چون `load_fts_config` بر پایه‌یِ نوعِ همین
// dictionary تصمیم می‌گیرد (`isinstance(FTS_DEFAULTS[k], bool)`).
//
// `mandatory_sectors` عمداً هنوز شش‌عضویِ قدیمی است؛ قفلِ سه‌صنعتیِ حکمِ Task 8
// درِ `cardMandatorySectors` (پایین‌تر) با دلیلش آمده است.
func ftsDefaults() map[string]any {
	return map[string]any{
		"growth_min":                   40.0,
		"eps_years":                    3,
		"margin_min":                   20.0,
		"margin_optimal":               30.0,
		"sales_to_mcap_min":            0.33,
		"sales_to_mcap_ideal":          1.0,
		"profit_potential_min":         40.0,
		"industry_mode":                "Exclude_Mandatory_Pricing",
		"mandatory_sectors":            []string{"خودرو", "نیروگاه", "قند و شکر", "لاستیک", "شوینده", "بیمه"},
		"free_sectors":                 []string{"سیمان", "پتروشیمی", "شیمیایی", "فلزات", "کانی", "کاشی", "سرامیک", "شیشه", "کانه", "معادن", "نفت", "محصولات فلزی"},
		"reject_insurance":             true,
		"watchlist_max":                50,
		"mcap_min_hmt":                 0.0,
		"holdings_sales_na":            true,
		"pharma_margin_exempt_min":     0.0,
		"exclude_base_market":          true,
		"exclude_rejected_indicators":  []string{},
		"suspended_max_stale_sessions": 3,
		"filter_m141":                  false,
		"min_trade_val":                0.0,
		"v10_monetary_growth_min":      60.0,
		"v10_inflation_basis":          60.0,
		"v10_volume_growth_min":        0.0,
		"v10_volume_breadth_min":       0.60,
		"v10_eps_years":                3,
		"v10_margin_min":               20.0,
		"v10_margin_ideal":             30.0,
		"v10_sales_to_mcap_min":        0.33,
		"v10_potential_min":            40.0,
		"include_industries":           []string{},
		"exclude_industries":           []string{},
		"hourglass_rsi_period":         7,
		"hourglass_rsi_oversold":       30.0,
		"hourglass_ma52_position":      "below",
	}
}

var ftsLegacyScalars = map[string]string{
	"streak_periods": "eps_years",
	"ps_good":        "sales_to_mcap_ideal",
	"potential_min":  "profit_potential_min",
}
var ftsLegacyLists = map[string]string{
	"bad_sectors":  "mandatory_sectors",
	"good_sectors": "free_sectors",
}

const inflationFallback = 60.0

// cardMandatorySectors عینِ سه صنعتِ الزامیِ جزوه پس از حکمِ مالک Task 8
// (`bors_config.py:818-826`): خودرو/قطعات، نیروگاه، لاستیک. قند و شکر، شوینده
// و بیمه الزامی نیستند؛ بیمه وتویِ سختِ جداگانه است (`reject_insurance`).
//
// چرا درِ `ftsDefaults` عوض نشد: وکتورهایِ کامیت‌شدۀ `config.json` پیش از همان
// حکم ساخته شده‌اند و حتی نرمال‌سازیِ `_normalise_mandatory_sectors`
// (api/market.py:36-46) را نمی‌شناسند (`body13` هنوز `["الف"]` است)؛ عوض‌کردنِ
// پیش‌فرض بدونِ تولیدِ دوبارۀ آن وکتورها `TestFtsConfigVectors` را قرمز می‌کند.
// تا آن بازتولید، کارت — که طلاییِ تازه‌اش همین سه را دارد — خروجیِ
// `thresholds` را با همان قفلِ اوراکل می‌دهد. TODO: پس از بازتولیدِ config.json
// این قفل به `ftsDefaults`/`LoadFtsConfig` منتقل و این تابع حذف شود.
var cardMandatorySectors = []string{"خودرو", "نیروگاه", "لاستیک"}

// cardThresholds نسخۀ کارت از پنلِ آستانه‌ها — عینِ `load_fts_config()`ِ اوراکل
// که `mandatory_sectors` را با `kept or allowed` به سه صنعتِ جزوه قفل می‌کند
// (ترتیبِ ورودی حفظ می‌شود و فهرستِ تهی ⇒ پیش‌فرض). سایرِ کلیدها دست‌نخورده‌اند.
func cardThresholds(cfg map[string]any) map[string]any {
	out := make(map[string]any, len(cfg))
	for k, v := range cfg {
		out[k] = v
	}
	kept := make([]string, 0, len(cardMandatorySectors))
	switch list := cfg["mandatory_sectors"].(type) {
	case []string:
		for _, s := range list {
			if s = pyTrimStr(s); contains(cardMandatorySectors, s) {
				kept = append(kept, s)
			}
		}
	case []any:
		for _, item := range list {
			s := pyTrimStr(pyStr(item))
			if contains(cardMandatorySectors, s) {
				kept = append(kept, s)
			}
		}
	}
	if len(kept) == 0 {
		kept = append(kept, cardMandatorySectors...)
	}
	out["mandatory_sectors"] = kept
	return out
}

// LoadFtsConfig عینِ api/market.load_fts_config: فایل را می‌خواند (نبود/خرابی ⇒
// {})، کلیدهایِ شناخته‌شده را نگه می‌دارد، کلیدهایِ نسل‌قدیم را مهاجرت می‌دهد،
// و درِ پایان نوعها را پاک‌سازی می‌کند.
func LoadFtsConfig(dataDir string) map[string]any {
	raw := map[string]any{}
	path := filepath.Join(dataDir, "fts_thresholds.json")
	if b, err := os.ReadFile(path); err == nil {
		var v any
		dec := json.NewDecoder(bytes.NewReader(b))
		dec.UseNumber() // «7» باید intِ پایتون بماند، نه float64(7)
		if dec.Decode(&v) == nil {
			if m, ok := v.(map[string]any); ok {
				raw = m
			}
		}
	}
	defaults := ftsDefaults()
	cfg := make(map[string]any, len(defaults))
	for k, v := range defaults {
		cfg[k] = v
	}
	for k, v := range raw {
		if _, ok := defaults[k]; ok {
			cfg[k] = v
		}
	}
	for old, next := range ftsLegacyScalars {
		if _, had := raw[old]; had {
			if _, present := raw[next]; !present {
				if f, ok := asFloat(raw[old]); ok {
					cfg[next] = f
				}
			}
		}
	}
	for old, next := range ftsLegacyLists {
		if val, had := raw[old]; had {
			if _, present := raw[next]; !present {
				cfg[next] = val
			}
		}
	}
	for _, k := range listKeys {
		var out []string
		switch v := cfg[k].(type) {
		case string:
			for _, part := range strings.Split(strings.ReplaceAll(v, "،", ","), ",") {
				if s := pyTrimStr(part); s != "" {
					out = append(out, s)
				}
			}
		case []any:
			for _, item := range v {
				if s := pyTrimStr(pyStr(item)); s != "" {
					out = append(out, s)
				}
			}
		case []string:
			for _, item := range v {
				if s := pyTrimStr(item); s != "" {
					out = append(out, s)
				}
			}
		}
		if out == nil {
			out = []string{}
		}
		cfg[k] = out
	}
	for k, v := range cfg {
		if contains(strKeys, k) {
			cfg[k] = pyStr(v)
			continue
		}
		if contains(listKeys, k) {
			continue
		}
		if isBool(defaults[k]) {
			if k == "reject_insurance" {
				// وتویِ سختِ بیمه فقط با بولِ واقعی خاموش می‌شود؛ JSON `null`
				// یا رشتهٔ "false" نباید بی‌صدا وتو را بردارد (api/market.py:93-95).
				if b, ok := v.(bool); ok {
					cfg[k] = b
				} else {
					cfg[k] = defaults[k]
				}
				continue
			}
			cfg[k] = truthy(v)
			continue
		}
		if strings.HasSuffix(k, "_max") || strings.HasSuffix(k, "_years") ||
			strings.HasSuffix(k, "_sessions") {
			if f, ok := asFloat(v); ok {
				cfg[k] = int(f)
			} else {
				cfg[k] = defaults[k]
			}
			continue
		}
		if strings.HasSuffix(k, "_period") {
			if f, ok := asFloat(v); ok && f == math.Trunc(f) {
				cfg[k] = int(f)
			} else {
				cfg[k] = defaults[k]
			}
			continue
		}
		if f, ok := asFloat(v); ok {
			cfg[k] = f
		} else {
			cfg[k] = defaults[k]
		}
	}

	// پاک‌سازیِ ساعت‌شنی (cfg بد نباید موتور را از کار بیندازد).
	period, ok := asFloat(cfg["hourglass_rsi_period"])
	if !ok || period < 2 || period > 100 {
		period = 7
	} else {
		period = math.Trunc(period)
	}
	oversold, ok := asFloat(cfg["hourglass_rsi_oversold"])
	if !ok || oversold < 5 || oversold > 50 {
		oversold = 30.0
	}
	mode, _ := cfg["hourglass_ma52_position"].(string)
	if mode != "below" && mode != "above" && mode != "either" {
		mode = "below"
	}
	cfg["hourglass_rsi_period"] = int(period)
	cfg["hourglass_rsi_oversold"] = oversold
	cfg["hourglass_ma52_position"] = mode
	return cfg
}

// V10Thresholds عینِ api/fundamental.v10_thresholds — ترتیبِ پراب برایِ هر
// پارامتر: ۱) `v10_<k>` ۲) نگاشتِ نامِ پنل ۳) کلیدِ مشترکِ پنل ۴) پیش‌فرضِ جزوه.
// دو قیدِ مهم که درِ پایتون با_comment ثبت شده‌اند و باید درِ Go هم بمانند:
//   - `monetary_growth_min` هرگز با پرابِ `v10_` دیده نمی‌شود (نامِ تاریخیِ
//     «هدفِ رشد» دقیقاً همان کلید است و وگرنه هدفِ ۶۰ بی‌صدا کف را ۶۰ می‌کرد)؛
//   - `monetary_growth_target` از `v10_monetary_growth_min` نگاشت می‌شود.
func V10Thresholds(cfg map[string]any) map[string]any {
	if cfg == nil {
		cfg = map[string]any{}
	}
	out := make(map[string]any, len(v10Defaults)+1)
	for k, v := range v10Defaults {
		out[k] = v
	}
	shared := map[string]string{
		"eps_years": "eps_years", "margin_min": "margin_min", "margin_ideal": "margin_optimal",
		"monetary_growth_min": "growth_min", "sales_to_mcap_min": "sales_to_mcap_min",
		"potential_min": "profit_potential_min", "volume_growth_min": "volume_growth_min",
		"volume_breadth_min": "volume_breadth_min",
	}
	alias := map[string]string{"monetary_growth_target": "v10_monetary_growth_min"}
	noV10Probe := map[string]bool{"monetary_growth_min": true}

	for key := range v10Defaults {
		probes := []string{}
		if !noV10Probe[key] {
			probes = append(probes, "v10_"+key)
		}
		if a, ok := alias[key]; ok {
			probes = append(probes, a)
		}
		if s, ok := shared[key]; ok {
			probes = append(probes, s)
		}
		for _, probe := range probes {
			raw, present := cfg[probe]
			if !present {
				continue
			}
			if key == "eps_years" {
				// `int(cfg[probe])` — وگرنه ValueError ⇒ probeِ بعدی. اینجا
				// `asInt` غلط بود: از float می‌گذشت و «3.5» را ۳ می‌کرد (پایتون
				// خطا می‌دهد و probeِ بعدی را می‌آزماید).
				if i, ok := pyIntStrict(raw); ok {
					out[key] = int(i)
					break
				}
				continue
			}
			if f, ok := asFloat(raw); ok {
				out[key] = f
				break
			}
		}
	}

	// مبنای تورم: کلیدِ مستقل. صفرِ کاربر «بدونِ تعدیلِ تورم» است، پس `or` ممنوع.
	var infl *float64
	if f, ok := asFloat(cfg["v10_inflation_basis"]); ok {
		v := f
		infl = &v
	}
	if infl != nil && *infl >= 0 {
		out["inflation_benchmark"] = *infl
	} else {
		out["inflation_benchmark"] = inflationFallback
	}
	return out
}

// asFloat مثلِ float(v) درِ پایتون:
//   - ارقامِ Unicode هم می‌پذیرد (`float("۲")==2.0`، `float("٣٤")==34.0`،
//     `float("１２３")==123.0`، `float("१२")==12.0`) — `strconv.ParseFloat` نمی‌پذیرد
//     و پیش از این همان عددِ صحیحِ پنل را بی‌صدا صفر می‌کرد؛
//   - جداکنندهٔ اعشار **فقط** U+002E است: `float("۱۲٫۵")` درِ پایتون ValueError
//     می‌دهد (سنجیده شد)، پس رقمِ فارسی با U+066B عدد نمی‌سازد؛
//   - `_` مجاز است ولی نه ابتدای/انتهایِ هر رقم (`1_0.00` ⇒ 10.0، `1__0` ⇒ خطا)؛
//   - NaN/infِ متنِ بی‌محتوا False می‌ماند: پنل هیچ‌وقت NaN نمی‌نویسد و
//     مسیرهایِ خواندنی باید به جای «عددِ مسموم» به پیش‌فرضِ جزوه برگردند.
func asFloat(v any) (float64, bool) {
	switch x := v.(type) {
	case nil:
		return 0, false
	case float64:
		if math.IsNaN(x) {
			return 0, false
		}
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	case json.Number:
		f, err := x.Float64()
		if err != nil || math.IsNaN(f) {
			return 0, false
		}
		return f, true
	case string:
		f, ok := parsePyFloat(x)
		if !ok || math.IsNaN(f) {
			return 0, false
		}
		return f, true
	}
	return 0, false
}

// parsePyFloat: هر رقمِ decimalِ یونیکد → ASCII، سپس ParseFloat.
func parsePyFloat(s string) (float64, bool) {
	trimmed := pyTrimStr(s)
	if trimmed == "" {
		return 0, false
	}
	var b strings.Builder
	b.Grow(len(trimmed))
	seenDigit := false
	prevDigit := false
	for _, r := range trimmed {
		switch {
		case r >= '0' && r <= '9':
			b.WriteRune(r)
			seenDigit, prevDigit = true, true
		case r == '_':
			// پایتون فقط بی_دو_رقم را می‌پذیرد
			if !prevDigit {
				return 0, false
			}
			b.WriteByte('_')
			prevDigit = false
		case r == '.' || r == '+' || r == '-':
			b.WriteRune(r)
			prevDigit = false
		default:
			d, ok := decimalDigit(r)
			if !ok {
				return 0, false
			}
			b.WriteByte('0' + byte(d))
			seenDigit, prevDigit = true, true
		}
	}
	if !seenDigit {
		// «nan»/«inf» درِ متنِ پنل ساخته نمی‌شوند؛ پشتیبانی نمی‌کنیم
		return 0, false
	}
	out, err := strconv.ParseFloat(strings.TrimSuffix(b.String(), "_"), 64)
	if err != nil || strings.HasSuffix(b.String(), "_") {
		return 0, false
	}
	return out, true
}

// decimalDigit: رقمِ خانواده‌Nd (U+0660 عربی، U+06F0 فارسی، U+FF10 تمام‌عرض،
// U+0966 دیواناگری و …) → مقدارِ ۰..۹. پایتون درِ float() همهٔ رقم‌هایِ decimal
// را می‌پذیرد. هر بلوکِ Nd دقیقاً ده نویسهٔ پیوسته است، پس مبدأِ بلوک با
// عقب‌رفتنِ حداکثرِ نه نویسه پیدا می‌شود.
func decimalDigit(r rune) (int, bool) {
	if !unicode.IsDigit(r) {
		return 0, false
	}
	base := r
	for i := 0; i < 9 && base > 0 && unicode.IsDigit(base-1); i++ {
		base--
	}
	v := int(r - base)
	if v < 0 || v > 9 {
		return 0, false
	}
	return v, true
}

// asInt مثلِ int(v): ابتدا عدد، وگرنه تبدیلِ متن. سرریزِ int64 را False می‌دهد
// (پایتون بی‌سقف است؛ این مسیر فقط eps_years را می‌خواند و سقفِ منطقی دارد).
func asInt(v any) (int, bool) {
	f, ok := asFloat(v)
	if !ok || math.IsInf(f, 0) || f > math.MaxInt64 || f < math.MinInt64 {
		return 0, false
	}
	return int(f), true
}

// pyIntStrict عینِ `int(v)` درِ پایتون — برخلافِ asInt که از float می‌گذرد.
//
// تفاوت‌هایِ داوری‌شده (با پایتون سنجیده شد):
//   - `int("3.5")` ⇒ ValueError (ولی `int(3.5)` ⇒ ۳). پس رشتهٔ اعشاری خطاست
//     و «۳٫۵» (ممیزِ فارسی) هم خطاست.
//   - رقمِ یونیکد پذیرفته می‌شود: `int("٣")==3`، `int("۳")==3`.
//   - `_` فقط میانِ دو رقم: `1_0`⇒۱۰، ولی `1__0`/`_3`/`3_` خطا.
//   - `int(None)` ⇒ TypeError و `int(nan)` ⇒ ValueError ⇒ هر دو «ناموفق».
//   - اعشارِ float رو به صفر بریده می‌شود: `int(-3.9)`⇒−۳.
func pyIntStrict(v any) (int64, bool) {
	switch x := v.(type) {
	case nil:
		return 0, false
	case bool:
		if x {
			return 1, true
		}
		return 0, true
	case int:
		return int64(x), true
	case int64:
		return x, true
	case float64:
		return pyIntFloat(x)
	case float32:
		return pyIntFloat(float64(x))
	case json.Number:
		if i, err := x.Int64(); err == nil {
			return i, true
		}
		f, ok := asFloat(x)
		if !ok {
			return 0, false
		}
		return pyIntFloat(f)
	case string:
		return pyIntString(x)
	}
	return 0, false
}

// pyIntFloat برشِ رو به صفرِ `int(float)` — NaN/Inf خطا (ValueError).
func pyIntFloat(f float64) (int64, bool) {
	if math.IsNaN(f) || math.IsInf(f, 0) || f > math.MaxInt64 || f < math.MinInt64 {
		return 0, false
	}
	return int64(f), true
}

// pyIntString تجزیۀ متن به سبکِ `int(str)`: علامتِ اختیاری، رقم‌های ASCII یا
// یونیکد، و `_` فقط میانِ دو رقم.
func pyIntString(s string) (int64, bool) {
	runes := []rune(pyTrimStr(s))
	if len(runes) == 0 {
		return 0, false
	}
	i := 0
	neg := false
	if runes[0] == '+' || runes[0] == '-' {
		neg = runes[0] == '-'
		i++
	}
	if i >= len(runes) {
		return 0, false
	}
	var val int64
	seen := false
	expectDigit := false
	for ; i < len(runes); i++ {
		r := runes[i]
		if r == '_' {
			if !seen || expectDigit {
				return 0, false
			}
			expectDigit = true
			continue
		}
		var d int
		if r >= '0' && r <= '9' {
			d = int(r - '0')
		} else {
			var ok bool
			d, ok = decimalDigit(r)
			if !ok {
				return 0, false
			}
		}
		expectDigit = false
		seen = true
		val = val*10 + int64(d)
		if val > math.MaxInt64/10+1 {
			return 0, false
		}
	}
	if !seen || expectDigit {
		return 0, false
	}
	if neg {
		return -val, true
	}
	return val, true
}

func isBool(v any) bool { _, ok := v.(bool); return ok }

// pyTrimStr مثلِ str(v).strip() درِ پایتون — U+001C..U+001F هم جای خالی‌اند،
// برخلافِ strings.TrimSpace (همان شکافی که درِ internal/period پین شده است).
func pyTrimStr(s string) string {
	runes := []rune(s)
	start, end := 0, len(runes)
	for start < end && isPySpace(runes[start]) {
		start++
	}
	for end > start && isPySpace(runes[end-1]) {
		end--
	}
	return string(runes[start:end])
}

func isPySpace(r rune) bool {
	switch {
	case r >= '\t' && r <= '\r',
		r >= 0x1c && r <= 0x1f,
		r == ' ', r == 0x85, r == 0xa0, r == 0x1680,
		r >= 0x2000 && r <= 0x200a,
		r == 0x2028, r == 0x2029, r == 0x202f, r == 0x205f, r == 0x3000:
		return true
	}
	return false
}
