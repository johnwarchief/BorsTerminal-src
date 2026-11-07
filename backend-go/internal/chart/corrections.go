package chart

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// CorrectionStep represents a single event adjustment ratio from Rahavard reference pack
type CorrectionStep struct {
	Date     string
	Ratio    float64
	Action   string
	EventSig string
	Type     string // "capital_increase", "dividend", or "combined"
}

// CorrectionPack holds authoritative event corrections for historical parity
type CorrectionPack struct {
	Version  string
	Mode     string
	AsOf     string
	ByIns    map[string][]CorrectionStep // insCode -> steps
	BySymbol map[string][]CorrectionStep // symbol -> steps
	SuppIns  map[string]map[string]bool  // insCode -> date -> true
	SuppSym  map[string]map[string]bool  // symbol -> date -> true
}

var (
	packOnce sync.Once
	packInst *CorrectionPack
)

type factorRowJSON struct {
	InsCode       string  `json:"ins_code"`
	Symbol        string  `json:"symbol"`
	Action        string  `json:"action"`
	EffectiveDate string  `json:"effective_date"`
	Ratio         float64 `json:"ratio"`
	EventSig      string  `json:"event_sig"`
}

type manifestJSON struct {
	Schema            string `json:"schema"`
	CorrectionVersion string `json:"correction_version"`
	Mode              string `json:"mode"`
	Files             struct {
		Factors string `json:"factors"`
	} `json:"files"`
}

func sigToType(sig string) string {
	s := strings.ToLower(strings.TrimSpace(sig))
	switch s {
	case "share":
		return "capital_increase"
	case "dps", "fund_dps", "pa":
		return "dividend"
	default:
		return "combined"
	}
}

func normalizeSymbol(s string) string {
	s = strings.ReplaceAll(s, "ي", "ی")
	s = strings.ReplaceAll(s, "ك", "ک")
	s = strings.ReplaceAll(s, "\u200c", "")
	return strings.TrimSpace(s)
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
		factorsFile := filepath.Join(dir, "factors.jsonl")
		f, err := os.Open(factorsFile)
		if err != nil {
			return
		}
		defer f.Close()

		cp := &CorrectionPack{
			Version:  man.CorrectionVersion,
			Mode:     man.Mode,
			ByIns:    make(map[string][]CorrectionStep),
			BySymbol: make(map[string][]CorrectionStep),
			SuppIns:  make(map[string]map[string]bool),
			SuppSym:  make(map[string]map[string]bool),
		}

		scanner := bufio.NewScanner(f)
		buf := make([]byte, 1024*1024)
		scanner.Buffer(buf, 10*1024*1024)

		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" {
				continue
			}
			var row factorRowJSON
			if err := json.Unmarshal([]byte(line), &row); err != nil {
				continue
			}
			ins := strings.TrimSpace(row.InsCode)
			sym := strings.TrimSpace(row.Symbol)
			date := strings.TrimSpace(row.EffectiveDate)
			if len(date) > 10 {
				date = date[:10]
			}
			if date == "" {
				continue
			}
			if date > cp.AsOf {
				cp.AsOf = date
			}

			if row.Action == "replace_step" && row.Ratio > 0 {
				step := CorrectionStep{
					Date:     date,
					Ratio:    row.Ratio,
					Action:   row.Action,
					EventSig: row.EventSig,
					Type:     sigToType(row.EventSig),
				}
				if ins != "" {
					cp.ByIns[ins] = append(cp.ByIns[ins], step)
				}
				if sym != "" {
					cp.BySymbol[sym] = append(cp.BySymbol[sym], step)
					if norm := normalizeSymbol(sym); norm != sym {
						cp.BySymbol[norm] = append(cp.BySymbol[norm], step)
					}
				}
			} else if row.Action == "suppress_step" {
				if ins != "" {
					if cp.SuppIns[ins] == nil {
						cp.SuppIns[ins] = make(map[string]bool)
					}
					cp.SuppIns[ins][date] = true
				}
				if sym != "" {
					if cp.SuppSym[sym] == nil {
						cp.SuppSym[sym] = make(map[string]bool)
					}
					cp.SuppSym[sym][date] = true
					if norm := normalizeSymbol(sym); norm != sym {
						if cp.SuppSym[norm] == nil {
							cp.SuppSym[norm] = make(map[string]bool)
						}
						cp.SuppSym[norm][date] = true
					}
				}
			}
		}

		packInst = cp
	})
	return packInst
}

// GetPackSteps returns the authoritative replacement steps for an asset if covered
func (cp *CorrectionPack) GetPackSteps(insCode, symbol string) ([]CorrectionStep, bool) {
	if cp == nil {
		return nil, false
	}
	if insCode != "" {
		if steps, ok := cp.ByIns[insCode]; ok && len(steps) > 0 {
			return steps, true
		}
	}
	if symbol != "" {
		if steps, ok := cp.BySymbol[symbol]; ok && len(steps) > 0 {
			return steps, true
		}
		if norm := normalizeSymbol(symbol); norm != symbol {
			if steps, ok := cp.BySymbol[norm]; ok && len(steps) > 0 {
				return steps, true
			}
		}
	}
	return nil, false
}
