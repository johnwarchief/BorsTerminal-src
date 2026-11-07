package fundamental

import (
	"net/http"
	"strings"

	"borsterminal/backend/internal/httpapi"
)

// Sectors بدنهٔ پایتون‌شکل را می‌دهد و خطایِ خواندن را مثلِ FastAPI به ۵۰۰ می‌برد.
// بدنهٔ ۵۰۰ عینِ الگویِ ثابتِ همین فاز است: internal/market/service.go:178 و :194
// (`{"status":"error","message":…}`) — هیچ شکلِ تازه‌ای اینجا ساخته نمی‌شود.
func (s *Service) Sectors(w http.ResponseWriter, r *http.Request) {
	body, err := s.SectorsBody(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, body)
}

func (s *Service) Quarters(w http.ResponseWriter, r *http.Request) {
	limit, ok := httpapi.IntQuery(w, r, "limit", 16)
	if !ok {
		return
	}
	body, err := s.QuartersBody(r.Context(), r.PathValue("symbol"), limit)
	if err != nil {
		// همان ۵۰۰ِ internal/market/service.go:178 — بانکِ خراب «count: 0» نیست.
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, body)
}

func (s *Service) Card(w http.ResponseWriter, r *http.Request) {
	months, ok := httpapi.IntQuery(w, r, "months", 0)
	if !ok {
		return
	}
	symbol := r.PathValue("symbol")
	body, status, err := s.CardBody(r.Context(), symbol, months)
	if err != nil {
		if status == http.StatusNotFound {
			httpapi.WriteJSON(w, http.StatusNotFound, map[string]any{"detail": "Symbol not found"})
			return
		}
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	httpapi.WriteJSON(w, status, body)
}

// Freshness عینِ `api_fundamental_freshness`: فهرستِ نمادها (حداکثر ۲۰۰) یا
// پیش‌فرضِ ۲۰۰ نمادِ اولِ تابلویِ سهام. بدنه از FreshnessBody با کشِ ۶۰ثانیه.
func (s *Service) Freshness(w http.ResponseWriter, r *http.Request) {
	raw := strings.TrimSpace(r.URL.Query().Get("symbols"))
	var syms []string
	if raw == "" {
		rows, err := s.rows(r.Context(),
			"SELECT l_val18 FROM instruments WHERE COALESCE(paper_type,1)=1"+
				" ORDER BY l_val18 LIMIT 200", nil)
		if err != nil {
			httpapi.WriteJSON(w, http.StatusInternalServerError,
				map[string]any{"status": "error", "message": err.Error()})
			return
		}
		for _, row := range rows {
			syms = append(syms, strOr(row["l_val18"]))
		}
	} else {
		syms = strings.Split(raw, ",")
	}
	if len(syms) > 200 {
		syms = syms[:200]
	}
	body, err := s.FreshnessBody(r.Context(), syms)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError,
			map[string]any{"status": "error", "message": err.Error()})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, body)
}
