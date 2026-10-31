package chart

// taxonomyِ واحدِ سیگنال (دورِ J): هر پرچم یک نقش دارد، نه بیشتر.
var ftsRoles = map[string]string{
	"jet": "entry", "choch_bullish": "entry", "point_hunt": "entry",
	"double_bottom": "entry", "range_break": "entry", "hourglass": "entry",
	"fib_zone": "context", "trend": "context", "support_resistance": "context",
	"third_peak": "warning", "rsi_divergence": "warning",
	"rsi_rollover": "warning", "ma14_pending": "warning",
	"hard_stop": "exit", "ma14_exit": "exit", "choch_bearish": "exit",
	"channel_break": "exit", "double_top": "exit", "hs_break": "exit",
}

var ftsTriggerLabels = map[string]string{
	"jet":           "جت",
	"point_hunt":    "شکار نقطه",
	"choch_bullish": "تغییرِ ساختارِ صعودی",
	"double_bottom": "کفِ دوقلو",
	"range_break":   "شکستِ باکسِ رنج",
	"hourglass":     "ساعتِ شنی",
}

var ftsStatusPriority = []string{"hard_stop", "confirmed_exit", "weekly_veto",
	"entry_trigger", "warning", "context_only", "no_signal", "insufficient"}

var ftsStatusText = map[string]string{
	"hard_stop":      "حدِ ضررِ سخت خورده شد — خروج",
	"confirmed_exit": "خروجِ تأییدشده (موتورِ چهارلایه)",
	"weekly_veto":    "وتوی تایم هفتگی — فرصت ورود نمی‌دهد",
	"entry_trigger":  "تریگرِ فعال رویِ کندلِ امروز",
	"warning":        "هشدار (پایش/کاهش پوزیشن) — خروجِ تأییدشده نیست",
	"context_only":   "فقطِ موقعیت (کمربندِ فیبو یا ساختار) — سیگنالِ ورود نیست",
	"no_signal":      "هیچِ سیگنالِ فعالی نیست",
	"insufficient":   "داده برایِ داوری کافی نیست — سنجیده نشد",
}

func asMap(v any) map[string]any {
	m, _ := v.(map[string]any)
	return m
}

func subMap(m map[string]any, key string) map[string]any {
	if m == nil {
		return nil
	}
	return asMap(m[key])
}

func flagged(v any, want bool) bool {
	b, ok := v.(bool)
	return ok && b == want
}

func dateTruthy(v any) bool {
	s, ok := v.(string)
	return ok && s != ""
}

// rolesCopy کپیِ جدولِ نقش‌ها — لایهٔ نمایش نقش را دوباره نمی‌سازد.
func rolesCopy() map[string]string {
	out := make(map[string]string, len(ftsRoles))
	for k, v := range ftsRoles {
		out[k] = v
	}
	return out
}

// statusBlock معادلِ _fts_status_block: وضعیتِ canonical از همان اعدادِ موتور.
func statusBlock(candles []candle, out map[string]any) map[string]any {
	var lastDate any
	if len(candles) > 0 {
		lastDate = trim10(candles[len(candles)-1].Time)
	}
	ex := subMap(out, "exit_engine")
	l1 := subMap(ex, "l1")
	l2 := subMap(ex, "l2")
	l3 := subMap(ex, "l3")
	l4 := subMap(ex, "l4")
	jet := subMap(out, "jet")
	ch := subMap(out, "choch")
	ph := subMap(out, "point_hunt")
	dbl := subMap(out, "double_bottom")
	box := subMap(out, "range_box")
	hg := subMap(out, "hourglass")
	fib := subMap(out, "fib")

	type trigCand struct {
		kind  string
		flag  any
		price any
		date  any
	}
	trigCands := []trigCand{
		{"jet", jet["active"], jet["resistance"], lastDate},
		{"point_hunt", ph["active"], ph["floor_price"], ph["trigger_date"]},
		{"choch_bullish", ch["bullish"], ch["level"], lastDate},
		{"double_bottom", dbl["active"], dbl["neckline"], lastDate},
		{"range_break", box["active"], box["top"], lastDate},
		{"hourglass", hg["active"], hg["ma52"], lastDate},
	}
	var trig map[string]any
	for _, tc := range trigCands {
		if flagged(tc.flag, true) && tc.price != nil && dateTruthy(tc.date) {
			label := ftsTriggerLabels[tc.kind]
			if label == "" {
				label = tc.kind
			}
			trig = map[string]any{"kind": tc.kind, "price": tc.price,
				"date": tc.date, "label": label, "role": "entry"}
			break
		}
	}

	type nf struct {
		name string
		v    any
	}
	exitFlags := []nf{
		{"hard_stop", l1["stop_hit"]},
		{"choch_bearish", l2["choch_break"]},
		{"channel_break", l2["channel_break"]},
		{"double_top", l3["double_top"]},
		{"hs_break", l3["hs_break"]},
		{"ma14_exit", l1["ma14_exit"]},
	}
	warnFlags := []nf{
		{"third_peak", l3["third_peak"]},
		{"rsi_divergence", l4["rsi_divergence"]},
		{"rsi_rollover", l4["rsi_rollover"]},
		{"ma14_pending", l1["ma14_exit_pending"]},
	}
	allFlags := []nf{}
	for _, tc := range trigCands {
		allFlags = append(allFlags, nf{tc.kind, tc.flag})
	}
	allFlags = append(allFlags, exitFlags...)
	allFlags = append(allFlags, warnFlags...)
	exits := []string{}
	warnings := []string{}
	unknown := []string{}
	measured := false
	for _, f := range exitFlags {
		if flagged(f.v, true) {
			exits = append(exits, f.name)
		}
	}
	for _, f := range warnFlags {
		if flagged(f.v, true) {
			warnings = append(warnings, f.name)
		}
	}
	for _, f := range allFlags {
		if f.v == nil {
			unknown = append(unknown, f.name)
		} else {
			measured = true
		}
	}
	decision := ""
	if m := subMap(subMap(out, "trend"), "matrix"); m != nil {
		decision, _ = m["decision"].(string)
	}
	vetoed := decision == "REJECT"
	z1 := subMap(fib, "zone_33_40")
	z2 := subMap(fib, "zone_618_70")
	inFib := flagged(z1["in_zone"], true) || flagged(z2["in_zone"], true)

	var code string
	switch {
	case containsStr(exits, "hard_stop"):
		code = "hard_stop"
	case hasOtherExit(exits):
		code = "confirmed_exit"
	case vetoed:
		code = "weekly_veto"
	case trig != nil:
		code = "entry_trigger"
	case len(warnings) > 0:
		code = "warning"
	case inFib:
		code = "context_only"
	case !measured:
		code = "insufficient"
	default:
		code = "no_signal"
	}
	text := ftsStatusText[code]
	if code == "entry_trigger" {
		text = text + ": " + trig["label"].(string)
	}
	if code == "weekly_veto" && flagged(jet["active"], true) {
		text = text + " (جتِ امروز هم فعال است، ولی وتو بر ورود غالب است)"
	}
	priority := make([]string, len(ftsStatusPriority))
	copy(priority, ftsStatusPriority)
	return map[string]any{
		"code": code, "text": text, "trigger": trig,
		"exits": exits, "warnings": warnings, "unknown": unknown,
		"vetoed":       vetoed,
		"context_only": inFib && trig == nil && len(exits) == 0 && len(warnings) == 0,
		"priority":     priority, "roles": rolesCopy(),
	}
}

func containsStr(list []string, s string) bool {
	for _, v := range list {
		if v == s {
			return true
		}
	}
	return false
}

func hasOtherExit(exits []string) bool {
	for _, e := range exits {
		if e != "hard_stop" {
			return true
		}
	}
	return false
}
