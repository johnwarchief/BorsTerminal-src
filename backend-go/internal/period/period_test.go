package period

import (
	"encoding/json"
	"os"
	"testing"
)

type golden struct {
	Canonicalize []struct {
		In  any     `json:"in"`
		Out *string `json:"out"`
	} `json:"canonicalize"`
	FromTitle []struct {
		In  string  `json:"in"`
		Out *string `json:"out"`
	} `json:"from_title"`
	MonthsFromTitle []struct {
		In  string `json:"in"`
		Out *int   `json:"out"`
	} `json:"months_from_title"`
	Derive []struct {
		End   any   `json:"end"`
		Title any   `json:"title"`
		Out   []any `json:"out"`
	} `json:"derive"`
	EffectiveMonths []struct {
		End    any    `json:"end"`
		Months any    `json:"months"`
		Title  string `json:"title"`
		Out    []any  `json:"out"`
	} `json:"effective_months"`
	IsCanonical []struct {
		In  any  `json:"in"`
		Out bool `json:"out"`
	} `json:"is_canonical"`
	IsUndated []struct {
		In  any  `json:"in"`
		Out bool `json:"out"`
	} `json:"is_undated"`
	YM []struct {
		In  any   `json:"in"`
		Out []any `json:"out"`
	} `json:"ym"`
	FiscalYear []struct {
		In  any     `json:"in"`
		Out *string `json:"out"`
	} `json:"fiscal_year"`
	DescSortKey []struct {
		In  any    `json:"in"`
		Out string `json:"out"`
	} `json:"desc_sort_key"`
	Latest []struct {
		In  []any   `json:"in"`
		Out *string `json:"out"`
	} `json:"latest"`
}

func load(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func eqStr(a, b *string) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func eqInt(a, b *int) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func TestGolden(t *testing.T) {
	g := load(t)
	for _, c := range g.Canonicalize {
		if got := Canonicalize(c.In); !eqStr(got, c.Out) {
			t.Errorf("Canonicalize(%v) = %v, want %v", c.In, deref(got), deref(c.Out))
		}
	}
	for _, c := range g.FromTitle {
		if got := FromTitle(c.In); !eqStr(got, c.Out) {
			t.Errorf("FromTitle(%q) = %v, want %v", c.In, deref(got), deref(c.Out))
		}
	}
	for _, c := range g.MonthsFromTitle {
		if got := MonthsFromTitle(c.In); !eqInt(got, c.Out) {
			t.Errorf("MonthsFromTitle(%q) = %v, want %v", c.In, derefInt(got), derefInt(c.Out))
		}
	}
	for _, c := range g.Derive {
		p, src := Derive(c.End, c.Title)
		wantP, _ := c.Out[0].(string)
		wantS, _ := c.Out[1].(string)
		if !eqStr(p, strOrNil(wantP)) || src != wantS {
			t.Errorf("Derive(%v,%v) = %v,%q want %v,%q", c.End, c.Title, deref(p), src, wantP, wantS)
		}
	}
	for _, c := range g.EffectiveMonths {
		n, src := EffectiveMonths(c.End, c.Months, c.Title)
		wantN := -1
		if c.Out[0] != nil {
			wantN = int(c.Out[0].(float64))
		}
		wantS, _ := c.Out[1].(string)
		if (n == nil) != (wantN == -1) || (n != nil && *n != wantN) || src != wantS {
			t.Errorf("EffectiveMonths(%v,%v,%q) = %v,%q want %d,%q", c.End, c.Months, c.Title, derefInt(n), src, wantN, wantS)
		}
	}
	for _, c := range g.IsCanonical {
		if got := IsCanonical(c.In); got != c.Out {
			t.Errorf("IsCanonical(%v) = %v", c.In, got)
		}
	}
	for _, c := range g.IsUndated {
		if got := IsUndated(c.In); got != c.Out {
			t.Errorf("IsUndated(%v) = %v", c.In, got)
		}
	}
	for _, c := range g.YM {
		y, m, ok := YM(c.In)
		wantY, wantM := -1, -1
		if c.Out[0] != nil {
			wantY = int(c.Out[0].(float64))
		}
		if c.Out[1] != nil {
			wantM = int(c.Out[1].(float64))
		}
		if ok != (wantY != -1) || (ok && (y != wantY || m != wantM)) {
			t.Errorf("YM(%v) = %d,%d,%v want %d,%d", c.In, y, m, ok, wantY, wantM)
		}
	}
	for _, c := range g.FiscalYear {
		if got := FiscalYear(c.In); !eqStr(got, c.Out) {
			t.Errorf("FiscalYear(%v) = %v", c.In, deref(got))
		}
	}
	for _, c := range g.DescSortKey {
		if got := DescSortKey(c.In); got != c.Out {
			t.Errorf("DescSortKey(%v) = %q want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Latest {
		if got := Latest(c.In); !eqStr(got, c.Out) {
			t.Errorf("Latest(%v) = %v", c.In, deref(got))
		}
	}
}

func deref(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return *p
}

func derefInt(p *int) int {
	if p == nil {
		return -1
	}
	return *p
}

func strOrNil(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
