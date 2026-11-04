package live

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"borsterminal/backend/internal/store"
)

func TestFetchOnceParsesAndOverlays(t *testing.T) {
	body := `{"marketwatch":[
		{"lva":"فولاد","pcl":4240,"pdv":4280,"pc":70,"py":4210,"pmx":4300,"pmn":4200,"pf":4215,"qtj":573553735,"qtc":2434652334940,"ztt":7631,"pe":"6.1","hEven":95850},
		{"lva":"خپارس","pcl":1746,"pdv":1744,"pc":-52,"py":1796,"pmx":1800,"pmn":1700,"pf":1790,"qtj":128062692,"qtc":223648567781,"ztt":876,"pe":"-1.1","hEven":95823}
	]}`
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(body))
	}))
	defer srv.Close()

	f := New(0)
	f.SetURL(srv.URL)
	f.SetClient(srv.Client())
	f.FetchOnce(context.Background())
	snap := f.Latest()
	if len(snap.Rows) != 2 || snap.HEven != 95850 || snap.Err != "" {
		t.Fatalf("snapshot=%+v", snap)
	}
	if snap.Rows[norm("فولاد")].Last != 4280 {
		t.Fatalf("فولاد row=%+v", snap.Rows[norm("فولاد")])
	}

	fr := &store.Frame{Codes: []string{"1", "2"}, Cols: map[string][]any{
		"symbol":       {"فولاد", "خپارس"},
		"p_last":       {float64(1), float64(2)},
		"p_closing":    {float64(1), float64(2)},
		"price_change": {float64(0), float64(0)},
		"q_tot_tran":   {float64(0), float64(0)},
		"q_tot_cap":    {float64(0), float64(0)},
		"z_tot_tran":   {float64(0), float64(0)},
		"pe":           {float64(0), float64(0)},
		"h_even":       {int64(0), int64(0)},
	}}
	out := f.Apply(fr)
	if out.Cols["p_last"][0].(float64) != 4280 || out.Cols["p_last"][1].(float64) != 1744 {
		t.Fatalf("overlay p_last=%v", out.Cols["p_last"])
	}
	if out.Cols["pe"][1].(float64) != -1.1 {
		t.Fatalf("overlay negative PE=%v", out.Cols["pe"])
	}
	if out.Cols["h_even"][0].(int64) != 95850 {
		t.Fatalf("overlay h_even=%v", out.Cols["h_even"])
	}
	if fr.Cols["p_last"][0].(float64) != 1 {
		t.Fatal("Apply mutated the cached frame")
	}
}

func TestFetchOnceKeepsLastSnapshotOnForbidden(t *testing.T) {
	hits := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		if hits == 1 {
			_, _ = w.Write([]byte(`{"marketwatch":[{"lva":"فولاد","pdv":10,"hEven":100}]} `))
			return
		}
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()
	f := New(0)
	f.SetURL(srv.URL)
	f.SetClient(srv.Client())
	f.FetchOnce(context.Background())
	first := f.Latest()
	f.FetchOnce(context.Background())
	second := f.Latest()
	if len(second.Rows) != 1 || second.Rows[norm("فولاد")].Last != 10 || second.Err == "" {
		t.Fatalf("snapshot not preserved: %+v", second)
	}
	if first.HEven != second.HEven {
		t.Fatalf("HEven changed on failure: %d -> %d", first.HEven, second.HEven)
	}
}
