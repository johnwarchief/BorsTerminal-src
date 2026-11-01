package selection

import (
	"context"
	"database/sql"
	"math"
	"strings"

	"borsterminal/backend/internal/mstat"
)

const (
	PortfolioMin          = 3
	PortfolioMax          = 15
	PortfolioWeightCapPct = 25.0
)

var assetKindByMode = map[string]string{
	"dollar": "dollar",
	"rial":   "rial",
}

type AssetClass struct {
	Cls        string `json:"cls"`
	Kind       string `json:"kind"`
	SectorName string `json:"sector_name"`
}

type DecisionRow struct {
	Symbol       string      `json:"symbol"`
	Name         string      `json:"name"`
	Status       string      `json:"status"`
	Reason       string      `json:"reason"`
	Note         string      `json:"note"`
	StopLoss     string      `json:"stop_loss"`
	AssetKind    string      `json:"asset_kind"`
	WeightPct    float64     `json:"weight_pct"`
	Price        float64     `json:"price"`
	Qty          float64     `json:"qty"`
	Score        int         `json:"score"`
	PricingMode  string      `json:"pricing_mode"`
	Sector       string      `json:"sector"`
	UpdatedAt    string      `json:"updated_at"`
	AssetClass   *AssetClass `json:"asset_class,omitempty"`
	ValueToman   *int64      `json:"value_toman,omitempty"`
	WeightEffPct float64     `json:"weight_eff_pct,omitempty"`
	WeightSource string      `json:"weight_source,omitempty"`
	WeightManual bool        `json:"weight_manual,omitempty"`
	OverCap      bool        `json:"over_cap,omitempty"`
}

type LimitsInfo struct {
	Min                int                `json:"min"`
	Max                int                `json:"max"`
	WeightCapPct       float64            `json:"weight_cap_pct"`
	EqualWeightPct     float64            `json:"equal_weight_pct"`
	SumWeightPct       float64            `json:"sum_weight_pct"`
	WeightSource       string             `json:"weight_source"`
	PortfolioValue     *int64             `json:"portfolio_value_toman"`
	ValueMissingCount  int                `json:"value_missing_count"`
	ClassMixPct        map[string]float64 `json:"class_mix_pct"`
	ClassMissingCount  int                `json:"class_missing_count"`
}

type PortfolioResponse struct {
	Status    string          `json:"status"`
	Decisions []DecisionRow   `json:"decisions"`
	Portfolio []DecisionRow   `json:"portfolio"`
	Monitor   []DecisionRow   `json:"monitor"`
	Counts    map[string]int  `json:"counts"`
	Limits    LimitsInfo      `json:"limits"`
	KindMix   map[string]int  `json:"kind_mix"`
	Message   string          `json:"message,omitempty"`
}

// GetPortfolio گزارش تجمیعی پورتفولیو، زیر نظر و وزن‌ها را تولید می‌کند.
func (s *Service) GetPortfolio(ctx context.Context) PortfolioResponse {
	rows, err := s.userDB.QueryContext(ctx, `
		SELECT symbol, COALESCE(name, ''), COALESCE(status, 'pending'),
		       COALESCE(reason, ''), COALESCE(note, ''), COALESCE(stop_loss, ''),
		       COALESCE(asset_kind, ''), COALESCE(weight_pct, 0), COALESCE(price, 0),
		       COALESCE(qty, 0), COALESCE(score, 0), COALESCE(pricing_mode, ''),
		       COALESCE(sector, ''), COALESCE(updated_at, '')
		FROM selection_decisions
		ORDER BY updated_at DESC
	`)
	if err != nil {
		return PortfolioResponse{
			Status:  "error",
			Message: err.Error(),
		}
	}
	defer rows.Close()

	var decisions []DecisionRow
	symbolsToLookup := make([]string, 0)
	counts := map[string]int{
		"accept":  0,
		"reject":  0,
		"monitor": 0,
		"pending": 0,
	}

	for rows.Next() {
		var d DecisionRow
		if err := rows.Scan(
			&d.Symbol, &d.Name, &d.Status, &d.Reason, &d.Note, &d.StopLoss,
			&d.AssetKind, &d.WeightPct, &d.Price, &d.Qty, &d.Score,
			&d.PricingMode, &d.Sector, &d.UpdatedAt,
		); err != nil {
			continue
		}

		if d.AssetKind == "" {
			if defKind, ok := assetKindByMode[strings.ToLower(strings.TrimSpace(d.PricingMode))]; ok {
				d.AssetKind = defKind
			}
		}

		if _, ok := counts[d.Status]; ok {
			counts[d.Status]++
		}

		decisions = append(decisions, d)
		symbolsToLookup = append(symbolsToLookup, d.Symbol)
	}

	if decisions == nil {
		decisions = []DecisionRow{}
	}

	// نگاشت طبقه‌بندی ابزارها از market.db
	classMap := s.lookupAssetClasses(ctx, symbolsToLookup)
	for i := range decisions {
		if ac, ok := classMap[decisions[i].Symbol]; ok {
			copyAC := ac
			decisions[i].AssetClass = &copyAC
		}
	}

	// استخراج ردیف‌های accept
	var accepted []DecisionRow
	var monitor []DecisionRow
	for _, d := range decisions {
		if d.Status == "accept" {
			accepted = append(accepted, d)
		} else if d.Status == "monitor" {
			monitor = append(monitor, d)
		}
	}
	if accepted == nil {
		accepted = []DecisionRow{}
	}
	if monitor == nil {
		monitor = []DecisionRow{}
	}

	// محاسبه وزن‌ها و مقادیر ریالی
	wmeta := calcWeights(accepted)

	// به‌روزرسانی تصمیمات accepted با مقادیر محاسبه‌شده
	sumW := 0.0
	for i := range accepted {
		sumW += accepted[i].WeightEffPct
	}
	sumW = math.Round(sumW*10) / 10

	// دسته‌بندی نوع دارایی بر مبنای دلار/ریال/ترکیبی
	kinds := map[string]int{"dollar": 0, "rial": 0, "mixed": 0}
	for _, d := range accepted {
		k := d.AssetKind
		if k == "dollar" || k == "rial" {
			kinds[k]++
		} else {
			kinds["mixed"]++
		}
	}

	// ترکیب طبقات دارایی
	mix, missingCount := calcClassMix(accepted)

	limits := LimitsInfo{
		Min:               PortfolioMin,
		Max:               PortfolioMax,
		WeightCapPct:      PortfolioWeightCapPct,
		EqualWeightPct:    wmeta.EqualWeightPct,
		SumWeightPct:      sumW,
		WeightSource:      wmeta.WeightSource,
		PortfolioValue:    wmeta.TotalValue,
		ValueMissingCount: wmeta.ValueMissingCount,
		ClassMixPct:       mix,
		ClassMissingCount: missingCount,
	}

	return PortfolioResponse{
		Status:    "success",
		Decisions: decisions,
		Portfolio: accepted,
		Monitor:   monitor,
		Counts:    counts,
		Limits:    limits,
		KindMix:   kinds,
	}
}

type weightMeta struct {
	EqualWeightPct    float64
	TotalValue        *int64
	ValueMissingCount int
	WeightSource      string
}

func calcWeights(accepted []DecisionRow) weightMeta {
	n := len(accepted)
	if n == 0 {
		return weightMeta{
			EqualWeightPct:    0.0,
			TotalValue:        nil,
			ValueMissingCount: 0,
			WeightSource:      "equal",
		}
	}

	pricedCount := 0
	var sumVal int64 = 0

	for i := range accepted {
		p := accepted[i].Price
		q := accepted[i].Qty
		if p > 0 && q > 0 {
			val := int64(math.Round(p * q))
			accepted[i].ValueToman = &val
			sumVal += val
			pricedCount++
		} else {
			accepted[i].ValueToman = nil
		}
	}

	valueOK := pricedCount == n && n > 0
	eq := math.Round((100.0/float64(n))*10) / 10

	hasManual := false
	for i := range accepted {
		if valueOK && sumVal > 0 {
			eff := math.Round((float64(*accepted[i].ValueToman)/float64(sumVal)*100.0)*10) / 10
			accepted[i].WeightEffPct = eff
			accepted[i].WeightSource = "value"
			accepted[i].WeightManual = false
		} else {
			w := accepted[i].WeightPct
			if w > 0 {
				accepted[i].WeightEffPct = math.Round(w*10) / 10
				accepted[i].WeightSource = "manual"
				accepted[i].WeightManual = true
				hasManual = true
			} else {
				accepted[i].WeightEffPct = eq
				accepted[i].WeightSource = "equal"
				accepted[i].WeightManual = false
			}
		}
		accepted[i].OverCap = accepted[i].WeightEffPct > PortfolioWeightCapPct
	}

	wSource := "equal"
	if valueOK {
		wSource = "value"
	} else if hasManual {
		wSource = "manual"
	}

	var totVal *int64
	if valueOK {
		v := sumVal
		totVal = &v
	}

	return weightMeta{
		EqualWeightPct:    eq,
		TotalValue:        totVal,
		ValueMissingCount: n - pricedCount,
		WeightSource:      wSource,
	}
}

func calcClassMix(accepted []DecisionRow) (map[string]float64, int) {
	mix := make(map[string]float64)
	missing := 0

	for _, d := range accepted {
		if d.AssetClass == nil {
			missing++
			continue
		}
		key := d.AssetClass.Cls
		if d.AssetClass.Cls == mstat.PaperFund {
			key = d.AssetClass.Kind
		}
		mix[key] = math.Round((mix[key]+d.WeightEffPct)*10) / 10
	}

	return mix, missing
}

func (s *Service) lookupAssetClasses(ctx context.Context, symbols []string) map[string]AssetClass {
	if len(symbols) == 0 {
		return map[string]AssetClass{}
	}

	// deduplicate
	uniq := make(map[string]struct{})
	for _, sym := range symbols {
		if sym != "" {
			uniq[sym] = struct{}{}
		}
	}

	placeholders := make([]string, 0, len(uniq))
	args := make([]any, 0, len(uniq))
	for sym := range uniq {
		placeholders = append(placeholders, "?")
		args = append(args, sym)
	}

	query := `
		SELECT l_val18, COALESCE(l_val30, ''), COALESCE(sector_name, ''), paper_type
		FROM instruments
		WHERE l_val18 IN (` + strings.Join(placeholders, ",") + `)
	`

	rows, err := s.marketDB.QueryContext(ctx, query, args...)
	if err != nil {
		return map[string]AssetClass{}
	}
	defer rows.Close()

	out := make(map[string]AssetClass)
	for rows.Next() {
		var sym, name, sector string
		var pt sql.NullInt64
		if err := rows.Scan(&sym, &name, &sector, &pt); err != nil {
			continue
		}

		var ptPtr *int64
		if pt.Valid {
			v := pt.Int64
			ptPtr = &v
		}

		cls, kind := mstat.Classify(ptPtr, name, sym, sector)
		out[sym] = AssetClass{
			Cls:        cls,
			Kind:       kind,
			SectorName: sector,
		}
	}

	return out
}
