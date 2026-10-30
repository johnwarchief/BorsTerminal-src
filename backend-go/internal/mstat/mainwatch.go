package mstat

import (
	"database/sql"
	"sort"
	"strings"

	"borsterminal/backend/internal/pyround"
)

// FlagSource منبعِ پرچم‌هایِ هفت‌گانهٔ تابلو است: نمادِ نرمال‌شده → پرچم‌ها، به‌همراهِ
// ok. ok=false یعنی «منبع نرسید» و با «هیچ پرچمی ندارد» یکی نیست؛ در آن حالت
// بدنه tape_flags_source="unavailable" می‌گیرد و هیچ ردیفی پرچم نمی‌گیرد.
type FlagSource interface {
	TapeFlags() (map[string]map[string]bool, bool)
}

// symNorm همان str.maketransِ funnel_engine._SYM_TRANS است: ي/ى عربی → ی و ك → ک.
var symNorm = strings.NewReplacer("\u064A", "\u06CC", "\u0649", "\u06CC", "\u0643", "\u06A9")

// normSymbol همان funnel_engine.norm_symbol: stripِ پایتون رویِ لبه‌ها، سپس
// املایِ فارسی. نیم‌فاصله (U+200C) بخشی از خودِ نماد است و برداشته نمی‌شود.
func normSymbol(s string) string { return pyStrip(symNorm.Replace(s)) }

// آستانه‌هایِ الگویِ ساعت — عینِ mstat_engine.CLOCK_PCT/CLOCK_MIN_TRADES/
// CLOCK_MIN_PRICE. predicate و clock_rule هر دو از همین سه می‌خوانند تا تغییرِ
// یکی، آستانه و اعلامِ آن را از هم جدا نکند.
const (
	clockMinPct    = 1.0   // CLOCK_PCT
	clockMinTrades = 30    // CLOCK_MIN_TRADES
	clockMinPrice  = 500.0 // CLOCK_MIN_PRICE
)

// gridSortKeys همان _GRID_SORT_KEYS: کلیدِ مرتب‌سازی → ستونِ سطرِ خروجی.
var gridSortKeys = map[string]string{
	"vol": "vol_b_shares", "val": "val_b_toman", "pc": "p_closing",
	"pl": "p_last", "pct": "pct_close", "pct_last": "pct_last",
	"clock": "clock_pct", "pcb": "pc_buy", "pcs": "pc_sell",
	"pow": "power", "flow": "flow_b_toman", "dv": "dem_vol",
	"dp": "dem_px", "symbol": "symbol",
}

// gridRow یک سطرِ خروجیِ mainwatch است. برخلافِ Rowِ قاب، ارقامِ نمایشی همین‌جا
// یک‌بار ساخته می‌شوند: پایتون هم گردکردنِ شش ستون (pct_last، pct_close،
// clock_pct، pc_buy، pc_sell، power) را *پیش از* مرتب‌سازی رویِ دیکشنری می‌نویسد،
// پس مرتب‌سازی دقیقاً رویِ همان ارقامِ گردشده انجام می‌شود — نه رویِ خام.
type gridRow struct {
	symbol, insCode, name, industry, cls, kind, queue  string
	volB, valB, trades, flowB                          float64
	pLast, pClosing, pFirst, pMax, pMin                float64
	pctLast, pctClose, clockPct                        float64
	pcBuy, pcSell, power, demVol, demPx                float64
	hasPLast, hasPctLast, hasPctClose, hasClock        bool
	hasPCBuy, hasPCSell, hasPower, hasDemVol, hasDemPx bool
	depth, clockOK                                     bool
}

func (g *gridRow) get(col string) (float64, bool) {
	switch col {
	case "vol_b_shares":
		return g.volB, true
	case "val_b_toman":
		return g.valB, true
	case "p_closing":
		return g.pClosing, true
	case "p_last":
		return g.pLast, g.hasPLast
	case "pct_close":
		return g.pctClose, g.hasPctClose
	case "pct_last":
		return g.pctLast, g.hasPctLast
	case "clock_pct":
		return g.clockPct, g.hasClock
	case "pc_buy":
		return g.pcBuy, g.hasPCBuy
	case "pc_sell":
		return g.pcSell, g.hasPCSell
	case "power":
		return g.power, g.hasPower
	case "flow_b_toman":
		return g.flowB, true
	case "dem_vol":
		return g.demVol, g.hasDemVol
	case "dem_px":
		return g.demPx, g.hasDemPx
	}
	return 0, false
}

func (g *gridRow) toMap() map[string]any {
	m := map[string]any{
		"symbol": g.symbol, "ins_code": g.insCode, "name": g.name,
		"industry": g.industry, "cls": g.cls, "kind": g.kind,
		"vol_b_shares": g.volB, "trades": g.trades, "val_b_toman": g.valB,
		"p_last": nil, "p_closing": g.pClosing,
		"p_first": g.pFirst, "p_max": g.pMax, "p_min": g.pMin,
		"pct_last": nil, "pct_close": nil, "clock_pct": nil,
		"pc_buy": nil, "pc_sell": nil, "power": nil,
		"flow_b_toman": g.flowB, "dem_vol": nil, "dem_px": nil,
		"queue": g.queue, "depth": g.depth, "clock_ok": g.clockOK,
	}
	if g.hasPLast {
		m["p_last"] = g.pLast
	}
	if g.hasPctLast {
		m["pct_last"] = g.pctLast
	}
	if g.hasPctClose {
		m["pct_close"] = g.pctClose
	}
	if g.hasClock {
		m["clock_pct"] = g.clockPct
	}
	if g.hasPCBuy {
		m["pc_buy"] = g.pcBuy
	}
	if g.hasPCSell {
		m["pc_sell"] = g.pcSell
	}
	if g.hasPower {
		m["power"] = g.power
	}
	if g.hasDemVol {
		m["dem_vol"] = g.demVol
	}
	if g.hasDemPx {
		m["dem_px"] = g.demPx
	}
	return m
}

// mainwatchPanel همان mstat_engine.mainwatch: جدولِ نمادهایِ یک دسته با ستونِ
// «اختلاف آخرین و پایانی» به‌عنوان مرتبهٔ پیش‌فرض، دو ترمزِ معامله/قیمت برایِ
// الگویِ ساعت، و انتقالِ پرچم‌هایِ تابلو از FlagSource (هیچ فرمولِ دومی برایِ
// پرچم‌ها این‌جا ساخته نمی‌شود).
func mainwatchPanel(db *sql.DB, flags FlagSource, group, industry, sortKey string,
	desc bool, limit int) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	// عینِ _TAB_CAT.get(group, "all") if group in _TAB_CAT else group
	cat := group
	if v, ok := tabCat[group]; ok {
		cat = v
	}
	grid := []*gridRow{}
	for _, r := range selectRows(rows, cat) {
		ind := pyStrip(r.SectorName)
		if industry != "" && ind != industry {
			continue
		}
		m := r.M
		// «آخرین» بیرونِ باندِ مجاز یعنی فیلدِ آلوده (تاریخ در pc) — نه فرصت.
		okLast := !isNaN(r.PLast) && pxInBand(r, r.PLast, r.PClosing)
		g := &gridRow{
			symbol: r.Symbol, insCode: r.Code, name: r.Name, industry: ind,
			cls: r.Cls, kind: r.Kind,
			volB: pyround.Round(m.Vol/1e9, 6), trades: m.Trades,
			valB:     pyround.Round(m.Val/1e10, 1),
			pClosing: f0(r.PClosing), pFirst: f0(r.PFirst),
			pMax: f0(r.PMax), pMin: f0(r.PMin),
			flowB: m.Flow / 1e10, queue: m.QState, depth: !isNaN(m.BQVal),
		}
		if okLast {
			g.pLast, g.hasPLast = r.PLast, true
		}
		if !isNaN(r.PYest) && r.PYest != 0 && okLast && pxNear(r.PYest, r.PClosing) {
			if d := div(r.PLast-r.PYest, r.PYest); d != nil {
				g.pctLast, g.hasPctLast = pyround.Round(100.0**d, 2), true
			}
		}
		if r.Pct != nil {
			g.pctClose, g.hasPctClose = pyround.Round(*r.Pct, 2), true
		}
		if r.ClockPct != nil {
			g.clockPct, g.hasClock = pyround.Round(*r.ClockPct, 2), true
		}
		if !isNaN(m.PCBuy) {
			g.pcBuy, g.hasPCBuy = pyround.Round(m.PCBuy/1e7, 2), true
		}
		if !isNaN(m.PCSell) {
			g.pcSell, g.hasPCSell = pyround.Round(m.PCSell/1e7, 2), true
		}
		if !isNaN(m.Power) {
			g.power, g.hasPower = pyround.Round(m.Power, 2), true
		}
		if !isNaN(m.BQ1Vol) {
			g.demVol, g.hasDemVol = m.BQ1Vol, true
		}
		if !isNaN(m.BQ1Px) {
			g.demPx, g.hasDemPx = m.BQ1Px, true
		}
		g.clockOK = r.ClockPct != nil && *r.ClockPct >= clockMinPct &&
			m.Trades >= clockMinTrades && f0(r.PClosing) >= clockMinPrice
		grid = append(grid, g)
	}
	// مرتب‌سازی: clock فقط نامزدهایِ قابلِ‌اتکا را رتبه می‌دهد؛ symbol رشته‌ای
	// است و بقیه ستونِ عددی. مقدارِ غایب در هر دو جهت آخر می‌نشیند — پایتون هم
	// None را با منفیِ 1e18 (نزولی) یا مثبتِ 1e18 (صعودی) جایگزین می‌کند.
	missing := 1e18
	if desc {
		missing = -1e18
	}
	if sortKey == "symbol" {
		// reverse=True در پایتون ترتیبِ هم‌ارزها را برنمی‌گرداند؛ پس دو جهت را
		// جدا نوشتیم، نه sort و بعد reverse (که هم‌ارزها را هم می‌چرخاند).
		sort.SliceStable(grid, func(i, j int) bool {
			if desc {
				return grid[i].symbol > grid[j].symbol
			}
			return grid[i].symbol < grid[j].symbol
		})
	} else {
		col := gridSortKeys[sortKey]
		if col == "" {
			col = "clock_pct"
		}
		key := func(g *gridRow) float64 {
			if sortKey == "clock" && !g.clockOK {
				return missing
			}
			v, ok := g.get(col)
			if !ok {
				return missing
			}
			return v
		}
		sort.SliceStable(grid, func(i, j int) bool {
			if desc {
				return key(grid[i]) > key(grid[j])
			}
			return key(grid[i]) < key(grid[j])
		})
	}
	// عینِ max(1, min(int(limit or 120), 4000)): صفر در پایتون «بی‌مقدار» است و
	// ۱۲۰ می‌شود، نه ۱؛ منفی به ۱ بسته می‌شود.
	if limit == 0 {
		limit = 120
	}
	if limit < 1 {
		limit = 1
	}
	if limit > 4000 {
		limit = 4000
	}
	if limit > len(grid) {
		limit = len(grid)
	}
	outRows := make([]map[string]any, 0, limit)
	for _, g := range grid[:limit] {
		outRows = append(outRows, g.toMap())
	}
	clockHits := 0
	for _, g := range grid {
		if g.clockOK {
			clockHits++
		}
	}
	out := map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "industry": industry, "sort": sortKey,
		"sort_col": func() string {
			if c, ok := gridSortKeys[sortKey]; ok {
				return c
			}
			return "clock_pct"
		}(),
		"desc": desc, "total": len(grid), "clock_hits": clockHits,
		"clock_rule": map[string]any{
			"min_pct": clockMinPct, "min_trades": clockMinTrades, "min_price": clockMinPrice,
		},
		"rows": outRows,
	}
	// انتقال، نه محاسبه: پرچم‌ها از همان بدنهٔ /api/market می‌آیند؛ نبودِ منبع
	// «unavailable» است و هیچ ردیفی tape_flags نمی‌گیرد (عینِ _attach_tape_flags).
	// نقشهٔ خالی با ok=true هم همان «منبع نرسید» است: پایتون `if not flags` را
	// unavailable می‌خواند، نه «هیچ نمادی پرچم ندارد».
	if flags != nil {
		if m, ok := flags.TapeFlags(); ok && len(m) > 0 {
			for _, row := range outRows {
				sym, _ := row["symbol"].(string)
				row["tape_flags"] = m[normSymbol(sym)]
			}
			out["tape_flags_source"] = "api/market"
		} else {
			out["tape_flags_source"] = "unavailable"
		}
	}
	return out, nil
}
