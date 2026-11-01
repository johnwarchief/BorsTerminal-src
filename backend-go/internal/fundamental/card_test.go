package fundamental

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/parity"
)

type cardIndexDoc struct {
	Cases []cardCaseMeta `json:"cases"`
}

type cardCaseMeta struct {
	Name     string         `json:"name"`
	Symbol   string         `json:"symbol"`
	Route    string         `json:"route"`
	Settings map[string]any `json:"settings"`
	Body     string         `json:"body"`
}

// openCardService فیکسچرِ یخ‌زده را در یک پوشهٔ موقت کپی می‌کند و سرویس را می‌سازد.
func openCardService(t *testing.T, settings map[string]any) (*Service, string) {
	t.Helper()
	dir := t.TempDir()
	raw, err := os.ReadFile(filepath.Join("testdata", "fixture", "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "market.db"), raw, 0o644); err != nil {
		t.Fatal(err)
	}
	if settings != nil {
		b, err := json.Marshal(settings)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, "fts_thresholds.json"), b, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	h, err := db.Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	s := New(h.Market, dir)
	t.Cleanup(func() { _ = s.Close() })
	return s, dir
}

// TestCardGoldens همهٔ ۱۲ کیسِ طلاییِ کارتِ پنج‌محور را با Go می‌سنجد:
// خروجیِ CardBody باید با طلاییِ ساخته‌شدهٔ اوراکل برابر باشد (Δ=۰).
func TestCardGoldens(t *testing.T) {
	idxPath := filepath.Join("testdata", "golden", "card_index.json")
	rawIdx, err := os.ReadFile(idxPath)
	if err != nil {
		t.Fatalf("read card_index.json: %v", err)
	}
	var doc cardIndexDoc
	if err := json.Unmarshal(rawIdx, &doc); err != nil {
		t.Fatalf("unmarshal card_index.json: %v", err)
	}
	if len(doc.Cases) == 0 {
		t.Fatal("no cases found in card_index.json")
	}

	ctx := context.Background()
	for _, c := range doc.Cases {
		t.Run(c.Name, func(t *testing.T) {
			s, _ := openCardService(t, c.Settings)
			wantRaw, err := os.ReadFile(filepath.Join("testdata", "golden", c.Body))
			if err != nil {
				t.Fatalf("read golden body %s: %v", c.Body, err)
			}
			var want map[string]any
			if err := json.Unmarshal(wantRaw, &want); err != nil {
				t.Fatalf("unmarshal golden body %s: %v", c.Body, err)
			}

			months := 0
			if c.Name == "card_up_months6" {
				months = 6
			}

			got, status, err := s.CardBody(ctx, c.Symbol, months)
			if want["__http_status__"] != nil {
				wantStatus := int(want["__http_status__"].(float64))
				if status != wantStatus {
					t.Fatalf("status = %d, want %d", status, wantStatus)
				}
				if wantStatus == 404 {
					if !errors.Is(err, ErrSymbolNotFound) {
						t.Fatalf("err = %v, want ErrSymbolNotFound", err)
					}
				}
				return
			}

			if err != nil {
				t.Fatalf("CardBody(%s): %v", c.Symbol, err)
			}
			if status != 200 {
				t.Fatalf("status = %d, want 200", status)
			}

			// نرمال‌سازی با Marshal/Unmarshal برای مقایسهٔ دقیق
			gotBytes, err := json.Marshal(got)
			if err != nil {
				t.Fatalf("marshal got: %v", err)
			}
			var gotNorm map[string]any
			if err := json.Unmarshal(gotBytes, &gotNorm); err != nil {
				t.Fatalf("unmarshal got: %v", err)
			}

			res := parity.Compare(want, gotNorm, parity.Options{})
			if !res.Pass {
				for _, d := range res.Diffs {
					t.Errorf("%s diff: %s", c.Name, d)
				}
			}
		})
	}
}
