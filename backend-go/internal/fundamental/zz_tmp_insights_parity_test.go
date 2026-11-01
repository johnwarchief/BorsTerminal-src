package fundamental

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"borsterminal/backend/internal/parity"
)

type tmpCase struct {
	Name    string         `json:"name"`
	Res     map[string]any `json:"res"`
	Insights []map[string]any `json:"insights"`
	Details map[string]any `json:"details"`
}

func tmpJSON(v any) any {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	var o any
	if err := json.Unmarshal(b, &o); err != nil {
		panic(err)
	}
	return o
}

func tmpLoad(t *testing.T, path string) []tmpCase {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	var cs []tmpCase
	if err := json.Unmarshal(b, &cs); err != nil {
		t.Fatalf("unmarshal %s: %v", path, err)
	}
	return cs
}

func TestTmpInsightsParity(t *testing.T) {
	path := os.Getenv("INS_ORACLE")
	if path == "" {
		path = `C:\Users\PCMOD\AppData\Local\Temp\ins_oracle\oracle\oracle2.json`
	}
	if _, err := os.Stat(path); err != nil {
		t.Skipf("oracle file %s not found: %v", path, err)
	}
	cs := tmpLoad(t, path)
	total, diffs := 0, 0
	for _, c := range cs {
		total++
		gi, gd := BuildInsights(c.Res)
		opts := parity.Options{}
		di := parity.Compare(tmpJSON(c.Insights), tmpJSON(gi), opts)
		dd := parity.Compare(tmpJSON(c.Details), tmpJSON(gd), opts)
		if len(di.Diffs)+len(dd.Diffs) > 0 {
			diffs++
			t.Errorf("case %s insightsDiffs=%v detailsDiffs=%v", c.Name, di.Diffs, dd.Diffs)
		}
	}
	t.Logf("TOTAL cases=%d diffs=%d", total, diffs)
	if diffs != 0 {
		t.Fatalf("%d/%d cases differ", diffs, total)
	}
}

func TestTmpInsightsGoldenNative(t *testing.T) {
	root := `C:\Users\PCMOD\Desktop\BorsTerminal\backend-go\internal\fundamental\testdata\golden`
	files, _ := filepath.Glob(filepath.Join(root, "s1", "fund_*.json"))
	files2, _ := filepath.Glob(filepath.Join(root, "s2", "fund_*.json"))
	files = append(files, files2...)
	total, diffs := 0, 0
	for _, f := range files {
		b, err := os.ReadFile(f)
		if err != nil {
			t.Fatalf("read %s: %v", f, err)
		}
		var g map[string]any
		if err := json.Unmarshal(b, &g); err != nil {
			t.Fatalf("unmarshal %s: %v", f, err)
		}
		if g["__http_status__"] != nil || g["insights"] == nil {
			continue
		}
		res := map[string]any{}
		for _, k := range []string{"indicators", "methodology", "profile", "sector"} {
			if v, ok := g[k]; ok {
				res[k] = v
			}
		}
		total++
		gi, gd := BuildInsights(res)
		opts := parity.Options{}
		di := parity.Compare(tmpJSON(g["insights"]), tmpJSON(gi), opts)
		dd := parity.Compare(tmpJSON(g["details"]), tmpJSON(gd), opts)
		if len(di.Diffs)+len(dd.Diffs) > 0 {
			diffs++
			t.Errorf("golden %s insightsDiffs=%v detailsDiffs=%v", filepath.Base(f), di.Diffs, dd.Diffs)
		}
		_ = reflect.DeepEqual
	}
	t.Logf("GOLDEN cases=%d diffs=%d", total, diffs)
	if diffs != 0 {
		t.Fatalf("%d/%d goldens differ", diffs, total)
	}
}
