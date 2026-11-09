package chart

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

// CorrectionStep represents a single event adjustment ratio from Rahavard reference pack
type CorrectionStep struct {
	Date              string
	Ratio             float64
	Action            string
	EventSig          string
	Type              string // "capital_increase", "dividend", or "combined"
	Class             string
	Confidence        string
	FieldsUsed        string
	Samples           any
	MaxFieldDev       any
	ProdRatio         any
	RefRatio          any
	Source            string
	Method            string
	RefBarsSHA        string
	CorrectionVersion string
	CreatedAt         string
	Reason            string
}

// RawCorrection یک تصحیحِ فیلدِ خام برایِ یک (date, field) است.
type RawCorrection struct {
	Date              string
	Field             string
	Value             float64
	ProductValue      any
	AbsDiff           any
	Source            string
	Method            string
	Confidence        string
	RefBarsSHA        string
	CorrectionVersion string
	CreatedAt         string
	Reason            string
}

// CorrectionPack holds authoritative event corrections for historical parity
type CorrectionPack struct {
	Version   string
	Mode      string
	AsOf      string
	Directory string
	RefSHA    string
	CreatedAt string

	ByIns    map[string][]CorrectionStep // insCode -> steps
	BySymbol map[string][]CorrectionStep // symbol -> steps
	SuppIns  map[string]map[string]bool  // insCode -> date -> true
	SuppSym  map[string]map[string]bool  // symbol -> date -> true
	RawIns   map[string][]RawCorrection
	RawSym   map[string][]RawCorrection

	FactorIndex   map[string]map[string]CorrectionStep
	SuppressIndex map[string]map[string]bool
	RawIndex      map[string]map[string]RawCorrection

	AmbiguousSymbols map[string]bool
}

var (
	packOnce sync.Once
	packInst *CorrectionPack
)

type factorRowJSON struct {
	InsCode       string  `json:"ins_code"`
	Instrument    string  `json:"instrument_code"`
	Symbol        string  `json:"symbol"`
	Action        string  `json:"action"`
	EffectiveDate string  `json:"effective_date"`
	Date          string  `json:"date"`
	Ratio         float64 `json:"ratio"`
	TargetRatio   float64 `json:"target_ratio"`
	Factor        float64 `json:"factor"`
	EventSig      string  `json:"event_sig"`
	Class         string  `json:"class"`
	Confidence    string  `json:"confidence"`
	FieldsUsed    string  `json:"fields_used"`
	Samples       any     `json:"samples"`
	MaxFieldDev   any     `json:"max_field_dev"`
	ProdRatio     any     `json:"prod_ratio"`
	RefRatio      any     `json:"ref_ratio"`
	Source        string  `json:"source"`
	Method        string  `json:"method"`
	RefBarsSHA    string  `json:"ref_bars_sha256"`
	Version       string  `json:"correction_version"`
	CreatedAt     string  `json:"created_at"`
	Reason        string  `json:"reason"`
}

type rawRowJSON struct {
	InsCode       string  `json:"ins_code"`
	Instrument    string  `json:"instrument_code"`
	Symbol        string  `json:"symbol"`
	Date          string  `json:"date"`
	EffectiveDate string  `json:"effective_date"`
	Field         string  `json:"field"`
	ReferenceVal  float64 `json:"reference_value"`
	Value         float64 `json:"value"`
	ProductValue  any     `json:"product_value"`
	AbsDiff       any     `json:"abs_diff"`
	Source        string  `json:"source"`
	Method        string  `json:"method"`
	Confidence    string  `json:"confidence"`
	RefBarsSHA    string  `json:"ref_bars_sha256"`
	Version       string  `json:"correction_version"`
	CreatedAt     string  `json:"created_at"`
	Reason        string  `json:"reason"`
}

type manifestJSON struct {
	Schema            string `json:"schema"`
	CorrectionVersion string `json:"correction_version"`
	CreatedAt         string `json:"created_at"`
	Mode              string `json:"mode"`
	ReferenceSHA      string `json:"reference_sha256"`
	Files             struct {
		Factors string `json:"factors"`
		RawOHLC string `json:"raw_ohlc"`
	} `json:"files"`
	FileSHA map[string]string `json:"file_sha256"`
}

var correctionActions = map[string]bool{"replace_step": true, "suppress_step": true}

func sigToType(sig string) string {
	s := strings.ToLower(strings.TrimSpace(sig))
	switch s {
	case "share":
		return "capital_increase"
	case "dps", "fund_dps", "pa", "base_gap", "ratio_diff":
		return "dividend"
	default:
		return "combined"
	}
}

func normalizeSymbol(s string) string {
	s = strings.NewReplacer("\u064a", "\u06cc", "\u0643", "\u06a9",
		"\u0649", "\u06cc", "\u200c", "", "\u200b", "", "\u200d", "").Replace(s)
	return strings.TrimSpace(s)
}

// stablePackDirectory مسیرِ نسبیِ پایدار: مسیرِ ماشینِ سازنده در پاسخ نمی‌نشیند.
func stablePackDirectory(dir string) string {
	clean := filepath.ToSlash(filepath.Clean(dir))
	if i := strings.LastIndex(clean, "/data/ra365_corrections"); i >= 0 {
		return clean[i+1:]
	}
	return clean
}

func sha256File(path string) string {
	f, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return ""
	}
	return hex.EncodeToString(h.Sum(nil))
}

// FindCorrectionsDir searches known paths for the Rahavard correction pack
func FindCorrectionsDir(dataDir string) string {
	if env := os.Getenv("BORS_CORRECTIONS_DIR"); env != "" {
		if _, err := os.Stat(filepath.Join(env, "manifest.json")); err == nil {
			return env
		}
	}
	candidates := []string{
		filepath.Join(dataDir, "data", "ra365_corrections", "ra365-r32b-v2"),
		filepath.Join(".", "data", "ra365_corrections", "ra365-r32b-v2"),
		filepath.Join("..", "data", "ra365_corrections", "ra365-r32b-v2"),
		filepath.Join("..", "..", "data", "ra365_corrections", "ra365-r32b-v2"),
		filepath.Join("..", "..", "..", "data", "ra365_corrections", "ra365-r32b-v2"),
	}
	for _, c := range candidates {
		if _, err := os.Stat(filepath.Join(c, "manifest.json")); err == nil {
			return c
		}
	}
	return ""
}

// LoadPack loads and parses the authoritative correction pack once
func LoadPack(dataDir string) *CorrectionPack {
	packOnce.Do(func() {
		dir := FindCorrectionsDir(dataDir)
		if dir == "" {
			return
		}
		manBytes, err := os.ReadFile(filepath.Join(dir, "manifest.json"))
		if err != nil {
			return
		}
		var man manifestJSON
		if err := json.Unmarshal(manBytes, &man); err != nil {
			return
		}
		ver := man.CorrectionVersion
		if ver == "" {
			ver = "ra365-r32b-v2"
		}
		factorsName := man.Files.Factors
		if factorsName == "" {
			factorsName = "factors.jsonl"
		}
		rawName := man.Files.RawOHLC
		if rawName == "" {
			rawName = "raw_ohlc.jsonl"
		}
		factorsPath := factorsName
		if !filepath.IsAbs(factorsPath) {
			factorsPath = filepath.Join(dir, factorsPath)
		}
		rawPath := rawName
		if !filepath.IsAbs(rawPath) {
			rawPath = filepath.Join(dir, rawPath)
		}
		if want := man.FileSHA["factors"]; want != "" {
			if _, statErr := os.Stat(factorsPath); statErr == nil {
				if got := sha256File(factorsPath); got != "" && got != want {
					return
				}
			}
		}
		if want := man.FileSHA["raw_ohlc"]; want != "" {
			if _, statErr := os.Stat(rawPath); statErr == nil {
				if got := sha256File(rawPath); got != "" && got != want {
					return
				}
			}
		}
		mode := man.Mode
		if mode != "overlay" && mode != "authoritative" {
			mode = "overlay"
		}
		cp := &CorrectionPack{
			Version: ver, Mode: mode, Directory: stablePackDirectory(dir),
			RefSHA: man.ReferenceSHA, CreatedAt: man.CreatedAt,
			ByIns:            make(map[string][]CorrectionStep),
			BySymbol:         make(map[string][]CorrectionStep),
			SuppIns:          make(map[string]map[string]bool),
			SuppSym:          make(map[string]map[string]bool),
			RawIns:           make(map[string][]RawCorrection),
			RawSym:           make(map[string][]RawCorrection),
			AmbiguousSymbols: make(map[string]bool),
		}
		f, err := os.Open(factorsPath)
		if err != nil {
			return
		}
		symbolIns := map[string]map[string]bool{}
		noteSymbol := func(sym, ins string) {
			if sym == "" {
				return
			}
			set := symbolIns[sym]
			if set == nil {
				set = map[string]bool{}
				symbolIns[sym] = set
			}
			set[ins] = true
		}
		scanner := bufio.NewScanner(f)
		buf := make([]byte, 1024*1024)
		scanner.Buffer(buf, 32*1024*1024)
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" {
				continue
			}
			var row factorRowJSON
			if err := json.Unmarshal([]byte(line), &row); err != nil {
				continue
			}
			ins := strings.TrimSpace(firstNonEmpty(row.InsCode, row.Instrument))
			sym := strings.TrimSpace(row.Symbol)
			date := str10(firstNonEmpty(row.EffectiveDate, row.Date))
			action := strings.TrimSpace(row.Action)
			if action == "" {
				action = "replace_step"
			}
			if !correctionActions[action] {
				action = "replace_step"
			}
			ratio := row.Ratio
			if ratio == 0 {
				ratio = row.TargetRatio
			}
			if ratio == 0 {
				ratio = row.Factor
			}
			if date == "" || (action == "replace_step" && ratio <= 0) {
				continue
			}
			if date > cp.AsOf {
				cp.AsOf = date
			}
			step := CorrectionStep{
				Date: date, Ratio: ratio, Action: action, EventSig: row.EventSig,
				Type: sigToType(row.EventSig), Class: row.Class, Confidence: row.Confidence,
				FieldsUsed: row.FieldsUsed, Samples: row.Samples, MaxFieldDev: row.MaxFieldDev,
				ProdRatio: row.ProdRatio, RefRatio: row.RefRatio,
				Source: row.Source, Method: row.Method,
				RefBarsSHA:        firstNonEmpty(row.RefBarsSHA, man.ReferenceSHA),
				CorrectionVersion: firstNonEmpty(row.Version, ver),
				CreatedAt:         firstNonEmpty(row.CreatedAt, man.CreatedAt),
				Reason:            row.Reason,
			}
			if action == "replace_step" {
				if ins != "" {
					cp.ByIns[ins] = append(cp.ByIns[ins], step)
				}
				if sym != "" {
					cp.BySymbol[sym] = append(cp.BySymbol[sym], step)
					noteSymbol(sym, ins)
					if norm := normalizeSymbol(sym); norm != sym {
						cp.BySymbol[norm] = append(cp.BySymbol[norm], step)
					}
				}
			} else {
				if ins != "" {
					if cp.SuppIns[ins] == nil {
						cp.SuppIns[ins] = map[string]bool{}
					}
					cp.SuppIns[ins][date] = true
				}
				if sym != "" {
					noteSymbol(sym, ins)
					if cp.SuppSym[sym] == nil {
						cp.SuppSym[sym] = map[string]bool{}
					}
					cp.SuppSym[sym][date] = true
					if norm := normalizeSymbol(sym); norm != sym {
						if cp.SuppSym[norm] == nil {
							cp.SuppSym[norm] = map[string]bool{}
						}
						cp.SuppSym[norm][date] = true
					}
				}
			}
		}
		f.Close()

		if rf, err := os.Open(rawPath); err == nil {
			rsc := bufio.NewScanner(rf)
			rsc.Buffer(buf, 32*1024*1024)
			for rsc.Scan() {
				line := strings.TrimSpace(rsc.Text())
				if line == "" {
					continue
				}
				var row rawRowJSON
				if err := json.Unmarshal([]byte(line), &row); err != nil {
					continue
				}
				ins := strings.TrimSpace(firstNonEmpty(row.InsCode, row.Instrument))
				sym := strings.TrimSpace(row.Symbol)
				date := str10(firstNonEmpty(row.Date, row.EffectiveDate))
				field := strings.TrimSpace(row.Field)
				if date == "" || field == "" {
					continue
				}
				val := row.ReferenceVal
				if val == 0 {
					val = row.Value
				}
				if val == 0 {
					continue
				}
				rc := RawCorrection{
					Date: date, Field: field, Value: val, ProductValue: row.ProductValue,
					AbsDiff: row.AbsDiff, Source: row.Source, Method: row.Method,
					Confidence: row.Confidence,
					RefBarsSHA: firstNonEmpty(row.RefBarsSHA, man.ReferenceSHA),
					CorrectionVersion: firstNonEmpty(row.Version, ver),
					CreatedAt:         firstNonEmpty(row.CreatedAt, man.CreatedAt),
					Reason:            row.Reason,
				}
				if ins != "" {
					cp.RawIns[ins] = append(cp.RawIns[ins], rc)
				}
				if sym != "" {
					cp.RawSym[sym] = append(cp.RawSym[sym], rc)
					noteSymbol(sym, ins)
					if norm := normalizeSymbol(sym); norm != sym {
						cp.RawSym[norm] = append(cp.RawSym[norm], rc)
					}
				}
			}
			rf.Close()
		}
		for sym, insSet := range symbolIns {
			distinct := 0
			for ins := range insSet {
				if ins != "" {
					distinct++
				}
			}
			if distinct > 1 {
				cp.AmbiguousSymbols[sym] = true
			}
		}
		for sym := range cp.AmbiguousSymbols {
			delete(cp.BySymbol, sym)
			delete(cp.RawSym, sym)
			delete(cp.SuppSym, sym)
		}
		cp.FactorIndex = map[string]map[string]CorrectionStep{}
		cp.SuppressIndex = map[string]map[string]bool{}
		for ins, rows := range cp.ByIns {
			cp.indexFactor(ins, rows)
		}
		for sym, rows := range cp.BySymbol {
			cp.indexFactor(sym, rows)
		}
		cp.RawIndex = map[string]map[string]RawCorrection{}
		for ins, rows := range cp.RawIns {
			cp.indexRaw(ins, rows)
		}
		for sym, rows := range cp.RawSym {
			cp.indexRaw(sym, rows)
		}
		packInst = cp
	})
	return packInst
}

func str10(s string) string {
	s = strings.TrimSpace(s)
	if len(s) > 10 {
		return s[:10]
	}
	return s
}

func (cp *CorrectionPack) indexFactor(key string, rows []CorrectionStep) {
	rep := map[string]CorrectionStep{}
	sup := map[string]bool{}
	for _, r := range rows {
		switch r.Action {
		case "replace_step":
			rep[r.Date] = r
		case "suppress_step":
			sup[r.Date] = true
		}
	}
	// ردیف‌هایِ suppress جدا از replace ذخیره می‌شوند؛ پایتون هر دو را درِ یکِ
	// `factor_by_*` می‌ریزد و `_index_factor` تفکیک می‌کند. بی‌این ادغام،
	// `suppress_steps` همیشه صفر می‌ماند.
	for d := range cp.SuppIns[key] {
		sup[d] = true
	}
	for d := range cp.SuppSym[key] {
		sup[d] = true
	}
	cp.FactorIndex[key] = rep
	cp.SuppressIndex[key] = sup
}

func (cp *CorrectionPack) indexRaw(key string, rows []RawCorrection) {
	m := map[string]RawCorrection{}
	for _, r := range rows {
		m[r.Date+"\x00"+r.Field] = r
	}
	cp.RawIndex[key] = m
}

// Key معادلِ Pack.key: ins_codeِ داده‌شده مقتدر است و fallback به نام ندارد.
func (cp *CorrectionPack) Key(insCode, symbol string) (string, bool) {
	if cp == nil {
		return "", false
	}
	if ins := strings.TrimSpace(insCode); ins != "" {
		_, f := cp.FactorIndex[ins]
		_, r := cp.RawIndex[ins]
		if f || r {
			return ins, true
		}
		return "", false
	}
	sym := strings.TrimSpace(symbol)
	if sym != "" {
		if _, ok := cp.FactorIndex[sym]; ok {
			return sym, true
		}
		if _, ok := cp.RawIndex[sym]; ok {
			return sym, true
		}
	}
	return "", false
}

// FactorRows معادلِ Pack.factor_rows: (replace, suppress, covered).
func (cp *CorrectionPack) FactorRows(insCode, symbol string) (map[string]CorrectionStep, map[string]bool, bool) {
	key, ok := cp.Key(insCode, symbol)
	if !ok {
		return map[string]CorrectionStep{}, map[string]bool{}, false
	}
	rep := cp.FactorIndex[key]
	if rep == nil {
		rep = map[string]CorrectionStep{}
	}
	sup := cp.SuppressIndex[key]
	if sup == nil {
		sup = map[string]bool{}
	}
	return rep, sup, true
}

// RawRows معادلِ Pack.raw_rows.
func (cp *CorrectionPack) RawRows(insCode, symbol string) (map[string]RawCorrection, bool) {
	key, ok := cp.Key(insCode, symbol)
	if !ok {
		return map[string]RawCorrection{}, false
	}
	m := cp.RawIndex[key]
	if m == nil {
		m = map[string]RawCorrection{}
	}
	return m, true
}

// GetPackSteps returns the authoritative replacement steps for an asset if
// covered. The ins-code rule matches Pack.key: a known ins code never falls
// back to the display name.
func (cp *CorrectionPack) GetPackSteps(insCode, symbol string) ([]CorrectionStep, bool) {
	key, ok := cp.Key(insCode, symbol)
	if !ok {
		return nil, false
	}
	rows := cp.FactorIndex[key]
	if len(rows) == 0 {
		return nil, false
	}
	dates := make([]string, 0, len(rows))
	for d := range rows {
		dates = append(dates, d)
	}
	sort.Strings(dates)
	out := make([]CorrectionStep, 0, len(dates))
	for _, d := range dates {
		out = append(out, rows[d])
	}
	return out, true
}

// GetSuppressSteps تاریخ‌هایِ suppress برایِ یک کلیدِ پوشش‌داده‌شده.
func (cp *CorrectionPack) GetSuppressSteps(insCode, symbol string) ([]string, bool) {
	key, ok := cp.Key(insCode, symbol)
	if !ok {
		return nil, false
	}
	sup := cp.SuppressIndex[key]
	out := make([]string, 0, len(sup))
	for d := range sup {
		out = append(out, d)
	}
	sort.Strings(out)
	return out, true
}

// Capability همان شکلِ AC.capability؛ مسیرِ مطلق افشا نمی‌شود.
func (cp *CorrectionPack) Capability(insCode, symbol string) map[string]any {
	if cp == nil {
		return map[string]any{"enabled": false, "version": nil, "covered": false,
			"replace_steps": 0, "suppress_steps": 0, "raw_fields": 0, "error": nil}
	}
	rep, sup, covered := cp.FactorRows(insCode, symbol)
	raw, _ := cp.RawRows(insCode, symbol)
	return map[string]any{
		"enabled": true, "version": cp.Version, "mode": cp.Mode,
		"directory": cp.Directory, "reference_sha256": cp.RefSHA,
		"covered": covered, "as_of": cp.AsOf,
		"replace_steps": len(rep), "suppress_steps": len(sup),
		"raw_fields": len(raw), "ambiguous_symbol": cp.AmbiguousSymbols[symbol],
		"error": nil,
	}
}

// ApplyFactorEvents معادلِ AC.apply_factor_events: (kept, suppressed, meta).
func (cp *CorrectionPack) ApplyFactorEvents(insCode, symbol string, events []canonEvent) ([]canonEvent, []canonEvent, map[string]any) {
	if cp == nil {
		return events, nil, map[string]any{"enabled": false}
	}
	rep, sup, covered := cp.FactorRows(insCode, symbol)
	if !covered {
		return events, nil, map[string]any{"enabled": true, "covered": false,
			"version": cp.Version, "mode": cp.Mode}
	}
	authoritative := cp.Mode == "authoritative" && (len(rep) > 0 || len(sup) > 0)
	cutoff := ""
	if authoritative {
		cutoff = cp.AsOf
	}
	kept := []canonEvent{}
	suppressed := []canonEvent{}
	futureKept := 0
	for _, e := range events {
		d := date10(e.Date)
		if authoritative && cutoff != "" && d > cutoff {
			kept = append(kept, e)
			futureKept++
			continue
		}
		_, inRep := rep[d]
		if inRep || sup[d] || authoritative {
			suppressed = append(suppressed, e)
			continue
		}
		kept = append(kept, e)
	}
	dates := make([]string, 0, len(rep))
	for d := range rep {
		dates = append(dates, d)
	}
	sort.Strings(dates)
	for _, d := range dates {
		st := rep[d]
		corr := map[string]any{
			"version": st.CorrectionVersion, "class": st.Class,
			"event_sig": st.EventSig, "confidence": st.Confidence,
			"fields_used": st.FieldsUsed, "samples": st.Samples,
			"max_field_dev": st.MaxFieldDev, "prod_ratio": st.ProdRatio,
			"ref_ratio": st.RefRatio, "source": st.Source, "method": st.Method,
			"ref_bars_sha256": st.RefBarsSHA, "created_at": st.CreatedAt,
			"reason": st.Reason,
		}
		kept = append(kept, canonEvent{Date: d, Ratio: st.Ratio,
			Source: "rahavard-reference-correction", Extra: map[string]any{"correction": corr}})
	}
	sort.SliceStable(kept, func(i, j int) bool { return date10(kept[i].Date) < date10(kept[j].Date) })
	return kept, suppressed, map[string]any{"enabled": true, "covered": true,
		"version": cp.Version, "mode": cp.Mode, "as_of": cp.AsOf,
		"future_events_kept": futureKept, "replace_steps": len(rep),
		"suppress_steps": len(sup)}
}

var rawCorrectionFields = []string{"open", "high_raw", "high", "low_raw", "low", "close", "last"}

// ApplyRawCandles معادلِ AC.apply_raw_candles: تصحیحِ نمایشی، in-place.
func (cp *CorrectionPack) ApplyRawCandles(insCode, symbol string, candles []map[string]any) (int, map[string]any) {
	if cp == nil {
		return 0, map[string]any{"enabled": false}
	}
	raw, covered := cp.RawRows(insCode, symbol)
	if !covered || len(raw) == 0 {
		return 0, map[string]any{"enabled": true, "covered": covered, "raw_fields": 0}
	}
	applied := 0
	for _, c := range candles {
		d := date10(firstNonEmpty(stringValue(c["time"]), stringValue(c["date"])))
		for _, field := range rawCorrectionFields {
			r, ok := raw[d+"\x00"+field]
			if !ok {
				continue
			}
			c[field] = r.Value
			applied++
		}
		if _, ok := raw[d+"\x00high_raw"]; ok {
			if _, explicit := raw[d+"\x00high"]; !explicit && c["high_raw"] != nil {
				c["high"] = c["high_raw"]
			}
		}
		if _, ok := raw[d+"\x00low_raw"]; ok {
			if _, explicit := raw[d+"\x00low"]; !explicit && c["low_raw"] != nil {
				c["low"] = c["low_raw"]
			}
		}
	}
	return applied, map[string]any{"enabled": true, "covered": true,
		"version": cp.Version, "raw_fields": len(raw)}
}
