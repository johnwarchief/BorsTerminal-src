package mstat

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/marketphase"
)

// qstr همان Query(...)ِ FastAPI: نبودِ پارامتر ⇒ default، ولی ?group= تهی
// می‌ماند (FastAPI مقدارِ تهی را با نبودن یکی نمی‌کند؛ ?group= دستهٔ ناشناخته
// است و صفر ردیف می‌دهد).
func qstr(r *http.Request, name, def string) string {
	if !r.URL.Query().Has(name) {
		return def
	}
	return r.URL.Query().Get(name)
}

// fastBool همان مجموعهٔ رشته‌ایِ Pydantic است، نه strconv.ParseBool.
func fastBool(v string) (bool, bool) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "t", "true", "y", "yes", "on":
		return true, true
	case "0", "f", "false", "n", "no", "off":
		return false, true
	}
	return false, false
}

func writePanel(w http.ResponseWriter, body map[string]any) {
	httpapi.WriteJSON(w, http.StatusOK, body)
}

func (s *Service) Summary(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("summary", func() (map[string]any, error) {
		return summaryPanel(s.db, s.clock())
	}, Options{StaleOK: true}))
}

func (s *Service) Histogram(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "all")
	writePanel(w, s.Call("histogram|"+group, func() (map[string]any, error) {
		return histogramPanel(s.db, group)
	}, Options{StaleOK: true}))
}

func (s *Service) Thermometer(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "all")
	writePanel(w, s.Call("thermometer|"+group, func() (map[string]any, error) {
		return thermometerPanel(s.db, group)
	}, Options{StaleOK: true}))
}

func (s *Service) Depth(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "all")
	writePanel(w, s.Call("depth|"+group, func() (map[string]any, error) {
		return depthPanel(s.db, group)
	}, Options{StaleOK: true}))
}

func (s *Service) ClientSplit(w http.ResponseWriter, r *http.Request) {
	tab := qstr(r, "tab", "all")
	writePanel(w, s.Call("clientsplit|"+tab, func() (map[string]any, error) {
		return clientSplitPanel(s.db, tab)
	}, Options{StaleOK: true}))
}

func (s *Service) MarketSnapshot(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("market-snapshot", func() (map[string]any, error) {
		return marketSnapshotPanel(s.db, s.clock())
	}, Options{StaleOK: true}))
}

func (s *Service) Phase(w http.ResponseWriter, r *http.Request) {
	// stale_ok=False: تنها فیلدی که میانِ دو ساختِ یکسانِ حالتِ بانک فرق می‌کند
	// clock_now است، پس پنلِ ارزان درِ انقضا درون‌خطی ساخته می‌شود.
	writePanel(w, s.Call("phase", func() (map[string]any, error) {
		return phasePanel(s.db, s.clock())
	}, Options{StaleOK: false}))
}

func (s *Service) Mainwatch(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "eq_all")
	industry := qstr(r, "industry", "")
	sortKey := qstr(r, "sort", "clock")
	desc := true
	if r.URL.Query().Has("desc") {
		raw := r.URL.Query().Get("desc")
		v, ok := fastBool(raw)
		if !ok {
			httpapi.UnprocessableAs(w, "bool_parsing", []string{"query", "desc"},
				"Input should be a valid boolean, unable to interpret input", raw)
			return
		}
		desc = v
	}
	limit := 120
	if r.URL.Query().Has("limit") {
		raw := r.URL.Query().Get("limit")
		v, err := strconv.Atoi(raw)
		if err != nil {
			httpapi.UnprocessableAs(w, "int_parsing", []string{"query", "limit"},
				"Input should be a valid integer, unable to parse string as an integer", raw)
			return
		}
		limit = v
	}
	key := fmt.Sprintf("mainwatch|%s|%s|%s|%t|%d", group, industry, sortKey, desc, limit)
	writePanel(w, s.Call(key, func() (map[string]any, error) {
		return mainwatchPanel(s.db, s.flags, group, industry, sortKey, desc, limit)
	}, Options{StaleOK: true}))
}

func (s *Service) Industries(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("industries", func() (map[string]any, error) {
		return industriesPanel(s.db)
	}, Options{StaleOK: true}))
}

func (s *Service) Timeline(w http.ResponseWriter, r *http.Request) {
	mode := qstr(r, "mode", "cum")
	writePanel(w, s.Call("timeline|"+mode, func() (map[string]any, error) {
		return timelinePanel(s.db, mode)
	}, Options{StaleOK: true}))
}

func (s *Service) Phases(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("phases", func() (map[string]any, error) {
		return phasesPanel(s.db)
	}, Options{StaleOK: true}))
}

// phasePanel همان dict(MP.from_db(conn), status="ok"). Phase خودش Status ندارد
// (پایتون هم آن را در session_phase می‌گذارد، نه در موتورِ فاز)، پس این‌جا
// می‌نشیند و تستِ مسیر تنها نگهبانِ آن است.
func phasePanel(db *sql.DB, now time.Time) (map[string]any, error) {
	ph := marketphase.FromDB(db, now)
	raw, err := json.Marshal(ph)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	out["status"] = "ok"
	return out, nil
}
