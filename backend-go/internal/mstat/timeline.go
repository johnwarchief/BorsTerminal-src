package mstat

import (
	"bytes"
	"compress/zlib"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"

	"borsterminal/backend/internal/pyround"
)

// seriesKeys همان _SERIES در mstat_engine.py (به همان ترتیب).
var seriesKeys = []string{"val_bt", "flow_eq_bt", "flow_fixed_bt", "pos", "neg",
	"bq_bt", "sq_bt", "pc_buy", "pc_sell", "bq_n", "sq_n"}

// decodeStates همان _dec_states: base64 → zlib → JSON؛ blobِ تهی/خراب ⇒ {}.
//
// پایتون برایِ JSONِ غیرِشیء (آرایه/تهی) هم چیزی برمی‌گرداند و بعداً در phases
// رویِ .items() می‌شکند؛ این‌جا «نقشهٔ تهی» است تا یک نقطهٔ خراب کلِ پنل را
// نبرد. نگاشتِ مخلوط ({m1:"b", m2:1}) را پایتون کامل نگه می‌دارد ولی هیچ جفتی
// برایِ مقدارِ غیرِرشته نمی‌شمارد؛ Go هم فقط رشته‌ها را کپی می‌کند — شمارشِ
// phases یکی می‌ماند.
func decodeStates(blob string) map[string]string {
	if blob == "" {
		return map[string]string{}
	}
	raw, err := base64.StdEncoding.DecodeString(blob)
	if err != nil {
		return map[string]string{}
	}
	zr, err := zlib.NewReader(bytes.NewReader(raw))
	if err != nil {
		return map[string]string{}
	}
	body, err := io.ReadAll(zr)
	_ = zr.Close()
	if err != nil {
		return map[string]string{}
	}
	var states map[string]any
	if err := json.Unmarshal(body, &states); err != nil || states == nil {
		return map[string]string{}
	}
	// فقط رشته‌ها کپی می‌شوند: پایتونِ phases هم برایِ مقدارِ غیرِرشته هیچ جفتی
	// نمی‌شمارد (کلیدهایِ _TRANS رشته‌اند)، پس انداختنِ آن‌ها همان شمارش است.
	out := make(map[string]string, len(states))
	for k, v := range states {
		if s, ok := v.(string); ok {
			out[k] = s
		}
	}
	return out
}

// toF همان _f برایِ مقدارهایِ aggِ خوانده‌شده از JSON (float64)، ستون‌ها
// (int64) و json.Number.
func toF(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int64:
		return float64(n)
	case json.Number:
		f, _ := n.Float64()
		return f
	default:
		return 0
	}
}

// hhmm همان _hhmm: ۱۰۰۰۰۰ ⇒ «10:00» (ساعتِ دیواری، بدونِ ثانیه).
func hhmm(v any) string {
	h := int(toF(v))
	return fmt.Sprintf("%02d:%02d", h/10000, (h/100)%100)
}

// points همان _points: نقطه‌هایِ آخرین نشستِ ثبت‌شده، فقط داخلِ پنجرهٔ رسمی
// ۰۸:۵۵–۱۳:۰۰ (ردیفِ شبانه/تست خطِ دروغین می‌کشد)، به ترتیبِ h_even، حداکثر ۲۴۰.
func points(db *sql.DB) ([]map[string]any, error) {
	var day sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even) FROM mstat_snap").Scan(&day); err != nil {
		return nil, err
	}
	// جدولِ تهی خطا نیست: MAX یک ردیفِ NULL برمی‌گرداند (err == nil). پس هر
	// errِ غیرِnil یعنی خواندنِ جدول شکسته (قفل/خرابی/جدولِ غایب) و باید بالا برود.
	if !day.Valid {
		return nil, nil
	}
	rows, err := db.Query(`SELECT h_even, agg FROM mstat_snap WHERE d_even=?
	    AND h_even>=? AND h_even<=? ORDER BY h_even`, day.Int64, 85500, 130005)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var h sql.NullInt64
		var agg sql.NullString
		if err := rows.Scan(&h, &agg); err != nil {
			return nil, err
		}
		var j map[string]any
		// پایتون فقط aggِ SQL NULL و JSONِ ناخوانا را رد می‌کند؛ JSONِ خوانا ولی
		// غیرِشیء (null/آرایه/عدد/رشته) در _points استثنا می‌دهد و کلِ پنل را
		// می‌برد. این‌جا آن‌ها هم رد می‌شوند تا یک ردیفِ خراب پنل را نبرد — j تهی
		// و j غیرِشیء یک مسیر دارند.
		if json.Unmarshal([]byte(agg.String), &j) != nil || j == nil {
			continue
		}
		if _, ok := j["h_even"]; !ok {
			j["h_even"] = h.Int64
		}
		out = append(out, j)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(out) > 240 {
		out = out[len(out)-240:]
	}
	return out, nil
}

// timelinePanel همان timeline(): یک داده، دو خوانش. cum=جمعِ تا این لحظه،
// inst=تفاوتِ نقطه‌هایِ پشت‌سرهم. با کمتر از دو نقطه ready=false و UI
// «در حال ساختِ تایم‌لاین» را می‌نویسد — نه خطِ صافِ دروغین از روی یک نقطه.
func timelinePanel(db *sql.DB, mode string) (map[string]any, error) {
	pts, err := points(db)
	if err != nil {
		return nil, err
	}
	cum := map[string][]any{}
	for _, k := range seriesKeys {
		vals := make([]any, len(pts))
		for i, p := range pts {
			vals[i] = p[k]
		}
		cum[k] = vals
	}
	t := make([]string, len(pts))
	for i, p := range pts {
		t[i] = hhmm(p["h_even"])
	}
	instant := func(key string) []any {
		out := make([]any, 0, len(cum[key]))
		var prev any
		for _, v := range cum[key] {
			if v == nil {
				out = append(out, nil)
				continue // prev جلو نمی‌رود: null یک «مقدار» نیست
			}
			if prev == nil {
				out = append(out, nil)
			} else {
				out = append(out, pyround.Round(toF(v)-toF(prev), 2))
			}
			prev = v
		}
		if len(out) > 0 && len(pts) > 0 {
			out[0] = cum[key][0] // نخستین نقطه خودش «مجموعِ تا آن لحظه» است
		}
		return out
	}
	ser := map[string]any{}
	if mode == "inst" {
		for _, k := range seriesKeys {
			ser[k] = instant(k)
		}
	} else {
		for _, k := range seriesKeys {
			ser[k] = cum[k]
		}
	}
	ser["t"] = t

	var day any
	if len(pts) > 0 {
		day = pts[0]["d_even"]
	}
	var board any
	{
		var b sql.NullInt64
		if err := db.QueryRow("SELECT MAX(d_even) FROM market_watch").Scan(&b); err == nil && b.Valid {
			board = b.Int64
		}
	}
	// «دو نقطه داریم» با «این نقطه‌ها مربوط به همین نشستِ تابلو است» دو چیزِ
	// متفاوت‌اند؛ تایم‌لاینِ یک نشستِ قدیمی نباید وضعیتِ امروز خوانده شود.
	stale := false
	if day != nil && board != nil {
		stale = fmt.Sprint(int(toF(day))) != fmt.Sprint(board)
	}
	var note any
	if len(pts) < 2 {
		note = "برای تایم‌لاین دست‌کم به دو همگام‌سازی در یک نشست نیاز است"
	} else if stale {
		note = "این تایم‌لاین به نشستی غیر از آخرین نشستِ تابلو برمی‌گردد — وضعیتِ امروز نیست"
	}
	m := "cum"
	if mode == "inst" {
		m = "inst"
	}
	return map[string]any{
		"status": "ok", "mode": m, "ready": len(pts) >= 2, "points": len(pts),
		"day": day, "board_day": board, "stale": stale, "series": ser,
		"session_open": "08:55", "session_close": "13:00", "note": note,
	}, nil
}

// phasesPanel همان phases(): شمارندهٔ تغییرِ وضعیتِ نمادها بین نقاطِ متوالیِ
// همان نشست. نمادی که در نقطهٔ پیشین نبود (تازه باز شده) شمرده نمی‌شود —
// «از هیچ به صف خرید» چرخش نیست — و فقط جفت‌هایِ ثبت‌شدهٔ _TRANS معنا دارند.
func phasesPanel(db *sql.DB) (map[string]any, error) {
	pts, err := points(db)
	if err != nil {
		return nil, err
	}
	type pair struct{ a, b string }
	counts := map[pair]int{}
	for _, tr := range transitions {
		counts[pair{tr.From, tr.To}] = 0
	}
	for i := 1; i < len(pts); i++ {
		prevBlob, _ := pts[i-1]["st"].(string)
		curBlob, _ := pts[i]["st"].(string)
		prev := decodeStates(prevBlob)
		cur := decodeStates(curBlob)
		if len(prev) == 0 || len(cur) == 0 {
			continue
		}
		for ic, now := range cur {
			was := prev[ic]
			if was != "" && was != now {
				if _, ok := counts[pair{was, now}]; ok {
					counts[pair{was, now}]++
				}
			}
		}
	}
	red, green := []map[string]any{}, []map[string]any{}
	for _, tr := range transitions {
		item := map[string]any{"key": tr.From + ">" + tr.To, "label": tr.Label,
			"count": counts[pair{tr.From, tr.To}]}
		if tr.Color == "red" {
			red = append(red, item)
		} else {
			green = append(green, item)
		}
	}
	return map[string]any{"status": "ok", "points": len(pts), "ready": len(pts) >= 2,
		"red": red, "green": green}, nil
}
