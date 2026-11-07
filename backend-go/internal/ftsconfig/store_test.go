package ftsconfig

import (
	"context"
	"database/sql"
	"testing"

	_ "modernc.org/sqlite"
)

func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open memory db: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestStore_DefaultsAndPersistence(t *testing.T) {
	db := newTestDB(t)
	store, err := NewStore(db)
	if err != nil {
		t.Fatalf("NewStore: %v", err)
	}

	ctx := context.Background()

	// 1. Initial Get should return default values
	cfg, err := store.Get(ctx)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if cfg["growth_min"].(float64) != 40.0 {
		t.Errorf("expected growth_min=40, got %v", cfg["growth_min"])
	}
	if cfg["industry_mode"].(string) != "Exclude_Mandatory_Pricing" {
		t.Errorf("expected industry_mode=Exclude_Mandatory_Pricing, got %v", cfg["industry_mode"])
	}
	if cfg["watchlist_max"].(int) != 50 {
		t.Errorf("expected watchlist_max=50, got %v", cfg["watchlist_max"])
	}

	// 2. Save partial update
	updated, err := store.Save(ctx, map[string]any{
		"growth_min":    55.0,
		"watchlist_max": 70,
		"reject_insurance": false,
	})
	if err != nil {
		t.Fatalf("Save: %v", err)
	}
	if updated["growth_min"].(float64) != 55.0 {
		t.Errorf("expected updated growth_min=55, got %v", updated["growth_min"])
	}
	if updated["watchlist_max"].(int) != 70 {
		t.Errorf("expected updated watchlist_max=70, got %v", updated["watchlist_max"])
	}
	if updated["reject_insurance"].(bool) != false {
		t.Errorf("expected updated reject_insurance=false, got %v", updated["reject_insurance"])
	}
	// Other fields should remain unchanged
	if updated["margin_min"].(float64) != 20.0 {
		t.Errorf("expected margin_min=20 to be preserved, got %v", updated["margin_min"])
	}

	// 3. Subsequent Get should return the persisted values
	roundtrip, err := store.Get(ctx)
	if err != nil {
		t.Fatalf("roundtrip Get: %v", err)
	}
	if roundtrip["growth_min"].(float64) != 55.0 {
		t.Errorf("expected roundtrip growth_min=55, got %v", roundtrip["growth_min"])
	}
	if roundtrip["watchlist_max"].(int) != 70 {
		t.Errorf("expected roundtrip watchlist_max=70, got %v", roundtrip["watchlist_max"])
	}
}

func TestStore_NilDB(t *testing.T) {
	store, err := NewStore(nil)
	if err != nil {
		t.Fatalf("NewStore(nil): %v", err)
	}
	ctx := context.Background()
	cfg, err := store.Get(ctx)
	if err != nil {
		t.Fatalf("Get with nil db: %v", err)
	}
	if cfg["growth_min"].(float64) != 40.0 {
		t.Errorf("expected defaults with nil db")
	}
	_, err = store.Save(ctx, map[string]any{"growth_min": 50})
	if err == nil {
		t.Fatal("expected error saving with nil db")
	}
}
