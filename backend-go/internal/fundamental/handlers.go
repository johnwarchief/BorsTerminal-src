package fundamental

import (
	"net/http"

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
