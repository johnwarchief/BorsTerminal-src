package fundamental

import (
	"net/http"

	"borsterminal/backend/internal/httpapi"
)

func (s *Service) Sectors(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.SectorsBody(r.Context()))
}

func (s *Service) Quarters(w http.ResponseWriter, r *http.Request) {
	limit, ok := httpapi.IntQuery(w, r, "limit", 16)
	if !ok {
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, s.QuartersBody(r.Context(), r.PathValue("symbol"), limit))
}
