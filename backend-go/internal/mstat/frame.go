package mstat

import (
	"database/sql"
	"fmt"
	"math"
	"strconv"
	"strings"
)

// AsOf همان asofِ load_snapshot: روزِ تابلو، ساعتِ تابلو، روزِ ردیفِ مشتری،
// و «آیا ردیفِ مشتری عقب‌تر از تابلوست». هر سه عدد از خودِ بانک می‌آیند؛
// نبودشان nil است، نه صفرِ ساختگی.
type AsOf struct {
	DEven       *int64
	HEven       int64
	ClientDEven *int64
	ClientLag   *bool
	Depth       bool
}

// CTRow یک ردیفِ client_type است — حجم و «تعداد»ِ خرید/فروشِ حقیقی(i) و
// حقوقی(n). ارزش در این فید نیست، پس واحدِ ریالی از حجم×VWAP بازسازی می‌شود.
type CTRow struct {
	BuyIVol, BuyNVol, BuyDDDVol, BuyCountI, BuyCountN float64
	SellIVol, SellNVol, SellCountI, SellCountN        float64
}

// CTVRow یک ردیفِ client_type_value است — ارزشِ ریالیِ مبدأ. نبودِ هر خانه
// یعنی «مبدأ نبود»، نه صفر؛ برایِ همین هر فیلد NaN می‌تواند باشد.
type CTVRow struct {
	BuyIVal, BuyNVal, SellIVal, SellNVal, BuyDDDVal float64
}

// Row یک سطرِ تابلو با هر ستونی است که کوئریِ mstat می‌خواند. هر فیلدِ عددیِ
// nullable با NaN نشان داده می‌شود (قراردادِ سراسریِ پورت) — صفر یعنی «صفرِ
// واقعی»، NaN یعنی «NULL».
type Row struct {
	Code, Symbol, Name, SectorCode, SectorName string
	PClosing, PLast, PYest, PFirst             float64
	PMin, PMax, AllowedMin, AllowedMax         float64
	BuyQVol, BuyQVal, BuyQCnt                  float64
	SellQVol, SellQVal, SellQCnt               float64
	BuyQ1Vol, BuyQ1Px, SellQ1Vol, SellQ1Px     float64
	BuyQ1Cnt                                   float64
	QVol, QVal, NTrades, PriceChange           float64
	TotalShares, BaseVol                       float64
	HEven                                      int64
	HasHEven                                   bool
	PaperType                                  *int64
	Cls, Kind                                  string
	Pct, ClockPct                              *float64
	CT                                         *CTRow
	CTV                                        *CTVRow
	Top50                                      bool
	// M ارقامِ ریالیِ همین ردیف است؛ enrich پر می‌کند و همهٔ تجمیع‌ها از همین
	// می‌خوانند (یک بار money برایِ هر نماد، همان قاعدهٔ enrichِ پایتون).
	M Money
}

type Snapshot struct {
	AsOf    AsOf
	Rows    []*Row
	BaseEst map[string]float64
	Depth   bool
}

func isNaN(v float64) bool { return math.IsNaN(v) }

// f0 همان _f پایتون: NULL/بی‌نهایت/غیرِعدد ⇒ 0. فقط جایی به کار می‌رود که
// خودِ پایتون هم مقدار را با _f می‌خواند (ارقامِ تجمعیِ money)، نه برایِ
// فیلدهایِ nullable.
func f0(v float64) float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return 0
	}
	return v
}

// fopt همان opt(key) پایتون: NaN (یعنی NULL) NaN می‌ماند، ولی بی‌نهایت با _f
// صفر می‌شود — ارقامِ nullable نباید +Inf را تا پنل حمل کنند.
func fopt(v float64) float64 {
	if math.IsInf(v, 0) {
		return 0
	}
	return v
}

func fnum(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int64:
		return float64(n)
	case int:
		return float64(n)
	default:
		return math.NaN()
	}
}

func inum(v any) (int64, bool) {
	switch n := v.(type) {
	case int64:
		return n, true
	case float64:
		return int64(n), true
	case int:
		return int64(n), true
	default:
		return 0, false
	}
}

func text(v any) string {
	switch s := v.(type) {
	case string:
		return s
	case []byte:
		return string(s)
	default:
		return ""
	}
}

// div همان _div: مخرجِ صفر یا طرفِ نبود ⇒ nil (نه صفر). بی‌نهایت پیش از
// تقسیم با _f صفر می‌شود؛ NaN به‌معنایِ None است و nil می‌دهد.
func div(a, b float64) *float64 {
	if isNaN(a) || isNaN(b) {
		return nil
	}
	b = fopt(b)
	if b == 0 {
		return nil
	}
	a = fopt(a)
	x := a / b
	return &x
}

// divF مقدارِ _div را با صفر جایگزین می‌کند (همان الگویِ پایتون که None را در
// جمعِ بعدی صفر می‌گیرد).
func divF(a, b float64) float64 {
	if d := div(a, b); d != nil {
		return *d
	}
	return 0
}

func pxNear(v, ref float64) bool {
	// پایتون هر دو طرف را با _f می‌خواند؛ بی‌نهایت همان‌جا صفر می‌شود.
	v, ref = f0(v), f0(ref)
	return v > 0 && ref > 0 && (1.0/2.0) <= v/ref && v/ref <= 2.0
}

func pxInBand(r *Row, v, ref float64) bool {
	v, ref = f0(v), f0(ref)
	if v <= 0 || ref <= 0 {
		return false
	}
	amin, amax := f0(r.AllowedMin), f0(r.AllowedMax)
	if amin > 0 && amax >= amin {
		if !(amin*0.999 <= v && v <= amax*1.001) {
			return false
		}
	}
	ratio := v / ref
	return 0.5 <= ratio && ratio <= 2.0
}

// hasDepthCol همان _has_queue_cols: ستون‌هایِ عمق فقط در بانکِ همگام‌شده با
// نسخهٔ تازه هستند؛ بانکِ کهنه «بی‌داده» است، نه صفرِ قرمز.
func hasDepthCol(db *sql.DB) bool {
	rows, err := db.Query("PRAGMA table_info(market_watch)")
	if err != nil {
		return false
	}
	defer rows.Close()
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err != nil {
			return false
		}
		if name == "buy_q_val" {
			return true
		}
	}
	return false
}

// loadSnapshot همان load_snapshot است: یک اسکن، بدونِ N+1.
//
// دنبالهٔ ستون‌ها فقط وقتی ستون‌هایِ عمق را دارد که جدول داشته باشد؛ برایِ
// همین SQL با `+` و در انتهایِ خط ساخته می‌شود تا قاعدهٔ semicolon insertion
// به خطِ بعد نچسبد.
func loadSnapshot(db *sql.DB) (*Snapshot, error) {
	var day sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even) FROM market_watch").Scan(&day); err != nil {
		return nil, fmt.Errorf("day: %w", err)
	}
	var dayArg any
	if day.Valid {
		dayArg = day.Int64
	}
	var hour sql.NullInt64
	if err := db.QueryRow("SELECT MAX(h_even) FROM market_watch WHERE d_even=?",
		dayArg).Scan(&hour); err != nil {
		return nil, fmt.Errorf("hour: %w", err)
	}
	// ردیفِ مشتری باید از همان نشستِ تابلو بیاید یا قدیمی‌تر از آن.
	var cday sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even) FROM client_type WHERE d_even<=?",
		dayArg).Scan(&cday); err != nil {
		return nil, fmt.Errorf("client day: %w", err)
	}
	depth := hasDepthCol(db)

	cols := `m.ins_code, i.l_val18, i.l_val30, i.sector_code, i.sector_name,
	         m.p_closing, m.p_last, m.price_yesterday, m.price_first,
	         m.price_min, m.price_max, m.allowed_min, m.allowed_max,`
	if depth {
		cols += ` m.buy_q_vol, m.buy_q_val, m.buy_q_cnt,
		          m.sell_q_vol, m.sell_q_val, m.sell_q_cnt,
		          m.buy_q1_vol, m.buy_q1_px, m.sell_q1_vol, m.sell_q1_px,
		          m.buy_q1_cnt,`
	}
	cols += ` m.q_tot_tran, m.q_tot_cap, m.z_tot_tran, m.price_change,
	          m.total_shares, i.base_vol, m.h_even, i.paper_type`
	rs, err := db.Query("SELECT "+cols+" FROM market_watch m"+
		" LEFT JOIN instruments i ON i.ins_code=m.ins_code WHERE m.d_even=?", dayArg)
	if err != nil {
		return nil, fmt.Errorf("snapshot: %w", err)
	}
	defer rs.Close()
	snap := &Snapshot{Depth: depth, BaseEst: map[string]float64{}}
	snap.AsOf = AsOf{DEven: nil, HEven: hour.Int64, ClientDEven: nil, Depth: depth}
	if day.Valid {
		d := day.Int64
		snap.AsOf.DEven = &d
	}
	if cday.Valid {
		c := cday.Int64
		snap.AsOf.ClientDEven = &c
	}
	if day.Valid && cday.Valid {
		// همان مقایسهٔ رشته‌ایِ پایتون؛ هر دو تاریخِ هشت‌رقمی‌اند.
		v := strconv.FormatInt(day.Int64, 10) > strconv.FormatInt(cday.Int64, 10)
		snap.AsOf.ClientLag = &v
	}
	for rs.Next() {
		colsN := 21
		if depth {
			colsN += 11
		}
		vals := make([]any, colsN)
		ptrs := make([]any, colsN)
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rs.Scan(ptrs...); err != nil {
			return nil, err
		}
		r := &Row{
			Code: text(vals[0]), Symbol: strings.TrimSpace(text(vals[1])),
			Name:       strings.TrimSpace(text(vals[2])),
			SectorCode: text(vals[3]), SectorName: text(vals[4]),
			PClosing: fnum(vals[5]), PLast: fnum(vals[6]), PYest: fnum(vals[7]),
			PFirst: fnum(vals[8]), PMin: fnum(vals[9]), PMax: fnum(vals[10]),
			AllowedMin: fnum(vals[11]), AllowedMax: fnum(vals[12]),
		}
		i := 13
		if depth {
			r.BuyQVol, r.BuyQVal, r.BuyQCnt = fnum(vals[i]), fnum(vals[i+1]), fnum(vals[i+2])
			r.SellQVol, r.SellQVal, r.SellQCnt = fnum(vals[i+3]), fnum(vals[i+4]), fnum(vals[i+5])
			r.BuyQ1Vol, r.BuyQ1Px = fnum(vals[i+6]), fnum(vals[i+7])
			r.SellQ1Vol, r.SellQ1Px = fnum(vals[i+8]), fnum(vals[i+9])
			r.BuyQ1Cnt = fnum(vals[i+10])
			i += 11
		} else {
			// پایتون این کلیدها را در _row_keys(False) اصلاً نمی‌گذارد، پس
			// row.get(...) ⇒ None ⇒ opt(...) ⇒ None. در Go «نبود» همان NaN است؛
			// بی‌آن، صفرِ خالیِ struct «عمقِ واقعیِ صفر» خوانده می‌شد و پنل‌هایِ
			// عمق/تفکیکِ مشتریان ردیف‌هایِ عمقِ خیالی می‌شمردند.
			r.BuyQVol, r.BuyQVal, r.BuyQCnt = math.NaN(), math.NaN(), math.NaN()
			r.SellQVol, r.SellQVal, r.SellQCnt = math.NaN(), math.NaN(), math.NaN()
			r.BuyQ1Vol, r.BuyQ1Px = math.NaN(), math.NaN()
			r.SellQ1Vol, r.SellQ1Px = math.NaN(), math.NaN()
			r.BuyQ1Cnt = math.NaN()
		}
		r.QVol, r.QVal, r.NTrades = fnum(vals[i]), fnum(vals[i+1]), fnum(vals[i+2])
		r.PriceChange, r.TotalShares, r.BaseVol = fnum(vals[i+3]), fnum(vals[i+4]), fnum(vals[i+5])
		if h, ok := inum(vals[i+6]); ok {
			r.HEven, r.HasHEven = h, true
		}
		if pt, ok := inum(vals[i+7]); ok {
			r.PaperType = &pt
		}
		r.Cls, r.Kind = classify(r.PaperType, r.Name, r.Symbol, r.SectorName)
		// بازدهیِ پایانی نسبت به دیروز — قیمتِ دیروز باید هم‌مرتبهٔ پایانی باشد.
		if !isNaN(r.PClosing) && !isNaN(r.PYest) && r.PClosing != 0 && r.PYest != 0 &&
			pxNear(r.PYest, r.PClosing) {
			if d := div(r.PClosing-r.PYest, r.PYest); d != nil {
				v := 100.0 * *d
				r.Pct = &v
			}
		}
		// الگویِ ساعت: «آخرین» فقط اگر داخلِ باندِ مجازِ همین نشست باشد.
		if !isNaN(r.PClosing) && !isNaN(r.PLast) && r.PClosing != 0 &&
			pxInBand(r, r.PLast, r.PClosing) {
			if d := div(r.PLast-r.PClosing, r.PClosing); d != nil {
				v := 100.0 * *d
				r.ClockPct = &v
			}
		}
		snap.Rows = append(snap.Rows, r)
	}
	if err := rs.Err(); err != nil {
		return nil, err
	}
	// client_type: کلید = ins_code؛ ردیفِ تکراری آخرین برنده است (dictِ پایتون).
	if cday.Valid {
		crs, err := db.Query(`SELECT ins_code, buy_i_vol, buy_n_vol, buy_ddd_vol,
		    buy_count_i, buy_count_n, sell_i_vol, sell_n_vol, sell_count_i,
		    sell_count_n FROM client_type WHERE d_even=?`, cday.Int64)
		if err != nil {
			return nil, fmt.Errorf("client_type: %w", err)
		}
		defer crs.Close()
		byCode := map[string]*CTRow{}
		for crs.Next() {
			var vals [10]any
			ptrs := make([]any, 10)
			for i := range vals {
				ptrs[i] = &vals[i]
			}
			if err := crs.Scan(ptrs...); err != nil {
				return nil, err
			}
			byCode[text(vals[0])] = &CTRow{
				BuyIVol: fnum(vals[1]), BuyNVol: fnum(vals[2]), BuyDDDVol: fnum(vals[3]),
				BuyCountI: fnum(vals[4]), BuyCountN: fnum(vals[5]),
				SellIVol: fnum(vals[6]), SellNVol: fnum(vals[7]),
				SellCountI: fnum(vals[8]), SellCountN: fnum(vals[9]),
			}
		}
		if err := crs.Err(); err != nil {
			return nil, err
		}
		for _, r := range snap.Rows {
			r.CT = byCode[r.Code]
		}
	}
	// client_type_value اختیاری است: بانکِ کهنه جدول یا ستونش را ندارد.
	if cday.Valid {
		if crs, err := db.Query(`SELECT ins_code, buy_i_val, buy_n_val, sell_i_val,
		    sell_n_val, buy_ddd_val FROM client_type_value WHERE d_even=?`, cday.Int64); err == nil {
			byCode, ok := scanCTV(crs)
			_ = crs.Close()
			// پایتون با fetchall می‌خواند؛ خطایِ میانِ راه استثنا می‌دهد و except
			// کلِ جدول را «خالی» می‌کند. نگه‌داشتنِ ردیف‌هایِ پیش از خطا یعنی
			// value_source ای که پایتون هرگز نمی‌سازد.
			if ok {
				for _, r := range snap.Rows {
					r.CTV = byCode[r.Code]
				}
			}
		}
	}
	snap.BaseEst = baseVolumeEstimate(db, dayArg)
	return snap, nil
}

// rowScanner کمینهٔ چیزی است که اسکنرهایِ این فایل از *sql.Rows می‌خواهند؛
// تست می‌تواند با همین قرارداد خطایِ میانِ جریان را شبیه‌سازی کند.
type rowScanner interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
}

// scanCTV همهٔ ردیف‌هایِ client_type_value را می‌خواند. هر خطایِ اسکن یا
// پایانِ همراهِ خطا کلِ نتیجه را دور می‌ریزد (`false`)، چون پایتون با
// fetchall می‌خواند و استثنایِ آن همهٔ ردیف‌ها را از دست می‌دهد.
func scanCTV(rows rowScanner) (map[string]*CTVRow, bool) {
	byCode := map[string]*CTVRow{}
	for rows.Next() {
		var vals [6]any
		ptrs := make([]any, 6)
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return nil, false
		}
		byCode[text(vals[0])] = &CTVRow{
			BuyIVal: fnum(vals[1]), BuyNVal: fnum(vals[2]),
			SellIVal: fnum(vals[3]), SellNVal: fnum(vals[4]),
			BuyDDDVal: fnum(vals[5]),
		}
	}
	if err := rows.Err(); err != nil {
		return nil, false
	}
	return byCode, true
}

// baseVolumeEstimate همان _base_volume_estimate: میانگینِ حداکثر ۴ نشستِ
// پیشین (بدونِ امروز) با شرطِ «حداقل دو مقدار». خطایِ میانِ کار (اسکن یا
// پایان) همهٔ برآورد را دور می‌ریزد — پایتون fetchall را در except می‌گیرد و
// {} برمی‌گرداند، نه نیمهٔ ردیف‌هایِ پیش از خطا.
func baseVolumeEstimate(db *sql.DB, dayArg any) map[string]float64 {
	rows, err := db.Query(`SELECT ins_code, q_tot_tran FROM daily_prices
	    WHERE d_even < ? AND q_tot_tran > 0
	      AND d_even >= (SELECT MIN(d_even) FROM (
	           SELECT DISTINCT d_even FROM daily_prices WHERE d_even < ?
	           ORDER BY d_even DESC LIMIT 4))
	    ORDER BY ins_code, d_even DESC`, dayArg, dayArg)
	if err != nil {
		return map[string]float64{}
	}
	defer rows.Close()
	return collectBaseVolumes(rows)
}

// collectBaseVolumes همان بدنهٔ _base_volume_estimate رویِ ردیف‌هایِ خوانده‌شده.
func collectBaseVolumes(rows rowScanner) map[string]float64 {
	acc := map[string][]float64{}
	for rows.Next() {
		var code any
		var v any
		if err := rows.Scan(&code, &v); err != nil {
			return map[string]float64{}
		}
		c := text(code)
		if len(acc[c]) < 4 {
			acc[c] = append(acc[c], f0(fnum(v)))
		}
	}
	if err := rows.Err(); err != nil {
		return map[string]float64{}
	}
	out := map[string]float64{}
	for c, lst := range acc {
		if len(lst) >= 2 {
			sum := 0.0
			for _, x := range lst {
				sum += x
			}
			out[c] = sum / float64(len(lst))
		}
	}
	return out
}

// asOfMap همان asofِ پنل‌هاست: روزِ تابلو، ساعت، روزِ ردیفِ مشتری و تأخیرش،
// عمق، شمارِ top50 و شمارِ ردیف‌ها. «نبود» nil است، نه صفرِ ساختگی.
func asOfMap(snap *Snapshot, top50, n int) map[string]any {
	m := map[string]any{
		"h_even": snap.AsOf.HEven, "depth": snap.AsOf.Depth,
		"top50": top50, "n": n, "d_even": nil, "client_d_even": nil,
		"client_lag_days": nil,
	}
	if snap.AsOf.DEven != nil {
		m["d_even"] = *snap.AsOf.DEven
	}
	if snap.AsOf.ClientDEven != nil {
		m["client_d_even"] = *snap.AsOf.ClientDEven
	}
	if snap.AsOf.ClientLag != nil {
		m["client_lag_days"] = *snap.AsOf.ClientLag
	}
	return m
}
