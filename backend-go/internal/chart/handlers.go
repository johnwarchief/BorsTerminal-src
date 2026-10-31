package chart

import (
	"net/http"
	"strconv"

	"borsterminal/backend/internal/httpapi"
)

func intQuery(w http.ResponseWriter, r *http.Request, name string, def int) (int, bool) {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return def, true
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		httpapi.UnprocessableAs(w, "int_parsing", []string{"query", name},
			"Input should be a valid integer, unable to parse string as an integer", raw)
		return 0, false
	}
	return v, true
}

func (s *Service) ChartDB(w http.ResponseWriter, r *http.Request) {
	adjustment, ok := intQuery(w, r, "adjustment", 3)
	if !ok {
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, s.chartDBBody(r.Context(), r.PathValue("symbol"), adjustment))
}

func (s *Service) FTS(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK,
		s.analyzeSymbol(r.Context(), r.PathValue("symbol"), r.URL.Query().Get("as_of")))
}

func (s *Service) OrderBook(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.orderBookBody(r.Context(), r.PathValue("symbol")))
}

func (s *Service) KeyLevels(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.keyLevelsBody(r.Context(), r.PathValue("symbol")))
}

func (s *Service) CalendarUpcoming(w http.ResponseWriter, r *http.Request) {
	days, ok := intQuery(w, r, "days", 14)
	if !ok {
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, s.calendarUpcomingBody(days))
}

func (s *Service) CalendarSymbol(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.calendarSymbolBody(r.PathValue("symbol")))
}

func (s *Service) MA(w http.ResponseWriter, r *http.Request) {
	days, ok := intQuery(w, r, "days", 730)
	if !ok {
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, s.maBody(r.Context(), r.PathValue("symbol"), days))
}

func (s *Service) Patterns(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, s.patternsBody(r.Context(), r.PathValue("symbol")))
}
