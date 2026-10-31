package chart

import (
	"encoding/json"
	"math"
	"strconv"
	"strings"
)

// پورتِ trend_classify.py — طبقه‌بندِ ترکیبیِ روند (BORS_TREND_ENGINE=hybrid).
// واژگانِ خروجی همان legacy است (neutral→range، کم‌داده→na) و کلیدهایِ ممیزی
// confidence/outcome/evidence/reason_codes اضافه می‌شوند.

var slopeWindows = []int{20, 50, 120}

const (
	neutralBand = 0.12
	minWeekly   = 8
)

var tcWeights = map[string]float64{"structure": 1.3, "slope": 1.2, "ma": 1.0, "eff": 0.9}

// omap نگاشتِ کلید-به-ترتیب برایِ این‌که pyRepr (متنِ reason_codes) با پایتون
// یکی بماند؛ JSON عادی هم از همین عبرت می‌کند.
type kv struct {
	K string
	V any
}
type omap []kv

func (m omap) MarshalJSON() ([]byte, error) {
	var b strings.Builder
	b.WriteByte('{')
	for i, e := range m {
		if i > 0 {
			b.WriteByte(',')
		}
		k, err := json.Marshal(e.K)
		if err != nil {
			return nil, err
		}
		v, err := json.Marshal(e.V)
		if err != nil {
			return nil, err
		}
		b.Write(k)
		b.WriteByte(':')
		b.Write(v)
	}
	b.WriteByte('}')
	return []byte(b.String()), nil
}

func (m omap) get(k string) (any, bool) {
	for _, e := range m {
		if e.K == k {
			return e.V, true
		}
	}
	return nil, false
}

func pyRepr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case bool:
		if x {
			return "True"
		}
		return "False"
	case string:
		return "'" + x + "'"
	case float64:
		return pyFloatStr(x)
	case *float64:
		if x == nil {
			return "None"
		}
		return pyFloatStr(*x)
	case int:
		return strconv.Itoa(x)
	case []string:
		parts := make([]string, len(x))
		for i, s := range x {
			parts[i] = pyRepr(s)
		}
		return "[" + strings.Join(parts, ", ") + "]"
	case omap:
		parts := make([]string, len(x))
		for i, e := range x {
			parts[i] = pyRepr(e.K) + ": " + pyRepr(e.V)
		}
		return "{" + strings.Join(parts, ", ") + "}"
	case map[string]any:
		parts := make([]string, 0, len(x))
		for _, k := range sortedKeys(x) {
			parts = append(parts, pyRepr(k)+": "+pyRepr(x[k]))
		}
		return "{" + strings.Join(parts, ", ") + "}"
	}
	return ""
}

func sortedKeys(m map[string]any) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	for i := 1; i < len(keys); i++ {
		for j := i; j > 0 && keys[j] < keys[j-1]; j-- {
			keys[j], keys[j-1] = keys[j-1], keys[j]
		}
	}
	return keys
}

func tcATR(candles []candle, n int) *float64 {
	if len(candles) < n+1 {
		return nil
	}
	trs := make([]float64, 0, len(candles)-1)
	for i := 1; i < len(candles); i++ {
		tr := math.Max(candles[i].High-candles[i].Low,
			math.Max(math.Abs(candles[i].High-candles[i-1].Close),
				math.Abs(candles[i].Low-candles[i-1].Close)))
		trs = append(trs, tr)
	}
	sum := 0.0
	for _, v := range trs[len(trs)-n:] {
		sum += v
	}
	atr := sum / float64(n)
	last := candles[len(candles)-1].Close
	if last <= 0 {
		return nil
	}
	v := atr / last
	return &v
}

func tcSlope(closes []float64, ap *float64) (float64, omap, bool) {
	if ap == nil || *ap <= 0 {
		return 0.0, omap{}, false
	}
	acc, wsum := 0.0, 0.0
	per := omap{}
	for _, w := range slopeWindows {
		if len(closes) <= w {
			continue
		}
		z := ((closes[len(closes)-1] - closes[len(closes)-1-w]) / closes[len(closes)-1-w] / float64(w)) / *ap
		acc += math.Tanh(z*20.0) * float64(w)
		wsum += float64(w)
		per = append(per, kv{Key("slope", w), round4(z)})
	}
	if wsum == 0 {
		return 0.0, per, false
	}
	return acc / wsum, per, true
}

func Key(prefix string, n int) string { return prefix + strconv.Itoa(n) }

func tcMA(closes []float64) (float64, omap, bool) {
	m := func(n int) *float64 {
		if len(closes) < n {
			return nil
		}
		sum := 0.0
		for _, v := range closes[len(closes)-n:] {
			sum += v
		}
		v := sum / float64(n)
		return &v
	}
	m20, m50, m200 := m(20), m(50), m(200)
	last := closes[len(closes)-1]
	votes := []int{}
	if m20 != nil && m50 != nil {
		if *m20 > *m50 {
			votes = append(votes, 1)
		} else {
			votes = append(votes, -1)
		}
	}
	if m50 != nil && m200 != nil {
		if *m50 > *m200 {
			votes = append(votes, 1)
		} else {
			votes = append(votes, -1)
		}
	}
	if m50 != nil {
		if last > *m50 {
			votes = append(votes, 1)
		} else {
			votes = append(votes, -1)
		}
	}
	if len(votes) == 0 {
		return 0.0, omap{{"ma", "insufficient"}}, false
	}
	sum := 0
	for _, v := range votes {
		sum += v
	}
	ev := omap{
		{"ma20_gt_50", m20 != nil && m50 != nil && *m20 > *m50},
		{"ma50_gt_200", m50 != nil && m200 != nil && *m50 > *m200},
		{"px_gt_ma50", m50 != nil && last > *m50},
	}
	return float64(sum) / float64(len(votes)), ev, true
}

func tcEff(closes []float64, n int) (float64, *float64, bool) {
	if len(closes) <= n+1 {
		return 0.0, nil, false
	}
	net := math.Abs(closes[len(closes)-1] - closes[len(closes)-1-n])
	path := 0.0
	for i := len(closes) - n; i < len(closes); i++ {
		path += math.Abs(closes[i] - closes[i-1])
	}
	er := 0.0
	if path != 0 {
		er = net / path
	}
	v := er
	if closes[len(closes)-1] < closes[len(closes)-1-n] {
		v = -er
	}
	erRounded := round3(er)
	return v, &erRounded, true
}

func tcStructure(sw []swing) (float64, omap, bool) {
	highs := highsOf(sw)
	lows := lowsOf(sw)
	if len(highs) < 2 || len(lows) < 2 {
		return 0.0, omap{{"structure", "کم‌پیوت"}}, false
	}
	h1, h0 := highs[len(highs)-1].Price, highs[len(highs)-2].Price
	l1, l0 := lows[len(lows)-1].Price, lows[len(lows)-2].Price
	hh, hl := h1 > h0, l1 > l0
	lh, ll := h1 < h0, l1 < l0
	label := "flat"
	switch {
	case hh && hl:
		label = "HH+HL"
	case ll && lh:
		label = "LL+LH"
	case hh && ll:
		label = "HH+LL"
	case lh && hl:
		label = "LH+HL"
	}
	v := 0.0
	switch label {
	case "HH+HL":
		v = 1.0
	case "LL+LH":
		v = -1.0
	}
	if label == "HH+LL" || label == "LH+HL" {
		nl := len(lows)
		if nl > 4 {
			nl = 4
		}
		nh := len(highs)
		if nh > 4 {
			nh = 4
		}
		structLow := math.Inf(1)
		for _, s := range lows[len(lows)-nl:] {
			structLow = math.Min(structLow, s.Price)
		}
		structHigh := math.Inf(-1)
		for _, s := range highs[len(highs)-nh:] {
			structHigh = math.Max(structHigh, s.Price)
		}
		if hl && l1 >= structLow {
			v = 0.5
		} else if ll && h1 <= structHigh {
			v = -0.5
		}
	}
	ev := omap{
		{"structure", label},
		{"last_high", round2(h1)}, {"prev_high", round2(h0)},
		{"last_low", round2(l1)}, {"prev_low", round2(l0)},
		{"last_high_time", strOrNilStr(highs[len(highs)-1].Time)},
		{"prev_high_time", strOrNilStr(highs[len(highs)-2].Time)},
		{"last_low_time", strOrNilStr(lows[len(lows)-1].Time)},
		{"prev_low_time", strOrNilStr(lows[len(lows)-2].Time)},
	}
	return v, ev, true
}

// classifyTrendHybrid پورتِ trend_classify.classify_trend.
func classifyTrendHybrid(sw []swing, series []candle) map[string]any {
	closes := make([]float64, len(series))
	for i, c := range series {
		closes[i] = c.Close
	}
	isWeekly := len(series) < 60
	sv, sevid, sOk := tcStructure(sw)
	ap := tcATR(series, 14)
	lv, levid, lOk := tcSlope(closes, ap)
	mv, mevid, mOk := tcMA(closes)
	ev, er, eOk := tcEff(closes, 30)

	sufficient := sOk || (boolToInt(lOk)+boolToInt(mOk)+boolToInt(eOk) >= 2)
	base := map[string]any{
		"hh": nil, "hl": nil, "basis": "hybrid",
		"last_high": nil, "prev_high": nil, "last_low": nil, "prev_low": nil,
		"last_high_time": nil, "prev_high_time": nil,
		"last_low_time": nil, "prev_low_time": nil,
		"stale_bars": nil, "window": nil,
	}
	evidence := map[string]any{"structure": sevid, "slope": levid, "ma": mevid, "er": er}
	if !sufficient {
		missing := []string{}
		if !sOk {
			missing = append(missing, "structure")
		}
		if !lOk {
			missing = append(missing, "slope")
		}
		if !mOk {
			missing = append(missing, "ma")
		}
		if !eOk {
			missing = append(missing, "eff")
		}
		out := copyMap(base)
		out["trend"] = "na"
		out["outcome"] = "insufficient_data"
		out["confidence"] = 0.0
		out["score"] = nil
		out["evidence"] = evidence
		out["reason_codes"] = []string{"MISSING:" + strings.Join(missing, ",")}
		return out
	}

	score := (tcWeights["structure"]*sv + tcWeights["slope"]*lv +
		tcWeights["ma"]*mv + tcWeights["eff"]*ev) / (tcWeights["structure"] + tcWeights["slope"] + tcWeights["ma"] + tcWeights["eff"])
	raw := "neutral"
	if math.Abs(score) >= neutralBand {
		if score > 0 {
			raw = "up"
		} else {
			raw = "down"
		}
	}
	trend := map[string]string{"up": "up", "down": "down", "neutral": "range"}[raw]

	votes := map[string]float64{"structure": sv, "slope": lv, "ma": mv, "eff": ev}
	pro, con := []string{}, []string{}
	for _, k := range []string{"structure", "slope", "ma", "eff"} {
		v := votes[k]
		if (v > 0 && raw == "up") || (v < 0 && raw == "down") {
			pro = append(pro, k)
		}
		if (v < 0 && raw == "up") || (v > 0 && raw == "down") {
			con = append(con, k)
		}
	}
	decisive := []int{}
	for _, v := range []float64{sv, lv, mv} {
		if math.Abs(v) > 1e-9 {
			if v > 0 {
				decisive = append(decisive, 1)
			} else {
				decisive = append(decisive, -1)
			}
		}
	}
	agreement := 0.0
	if len(decisive) > 0 {
		sum := 0
		for _, d := range decisive {
			sum += d
		}
		agreement = math.Abs(float64(sum)) / float64(len(decisive))
	}
	strength := math.Min(1.0, math.Abs(score)/0.6)
	depthDen := 120.0
	if isWeekly {
		depthDen = 40.0
	}
	depth := math.Min(1.0, float64(len(series))/depthDen)
	erVal := 0.0
	if er != nil {
		erVal = *er
	}
	confidence := round3(math.Max(0.0, math.Min(1.0,
		(0.5*agreement+0.3*strength+0.2*erVal)*(0.5+0.5*depth))))

	structureLabel, _ := sevid.get("structure")
	out := copyMap(base)
	for _, k := range []string{"last_high", "prev_high", "last_low", "prev_low",
		"last_high_time", "prev_high_time", "last_low_time", "prev_low_time"} {
		v, _ := sevid.get(k)
		out[k] = v
	}
	out["hh"] = structureLabel == "HH+HL"
	out["hl"] = structureLabel == "HH+HL" || structureLabel == "LH+HL"
	out["trend"] = trend
	out["outcome"] = "classified"
	out["confidence"] = confidence
	out["score"] = round4(score)
	out["method_agreement"] = round3(agreement)
	out["evidence"] = map[string]any{
		"structure": sevid, "slope": levid, "ma": mevid, "er": er,
		"votes": votes, "pro": pro, "con": con,
	}
	out["reason_codes"] = []string{
		"structure=" + pyStr(structureLabel),
		"slopeZ=" + pyRepr(levid),
		"ma=" + pyRepr(mevid),
		"ER=" + pyRepr(er),
		"raw=" + raw,
		"score=" + pyFloatStr(round3(score)),
		"pro=" + pyRepr(pro),
		"con=" + pyRepr(con),
		"bars=" + strconv.Itoa(len(series)),
	}
	return out
}

func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}
