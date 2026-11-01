package funnel

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"borsterminal/backend/internal/httpapi"
)

// Registry هندلر بازگرداندن رجیستری قیف: GET /api/funnel/registry
func (s *Service) Registry(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(RegistryRawBytes())
}

// GetFunnel هندلر دریافت ارزیابی قیف: GET /api/funnel?preset=...&chain=...&fund_mode=...
func (s *Service) GetFunnel(w http.ResponseWriter, r *http.Request) {
	preset := r.URL.Query().Get("preset")
	chainStr := r.URL.Query().Get("chain")
	var chain []string
	if chainStr != "" {
		for _, c := range strings.Split(chainStr, ",") {
			if strings.TrimSpace(c) != "" {
				chain = append(chain, strings.TrimSpace(c))
			}
		}
	}
	fundMode := r.URL.Query().Get("fund_mode")
	logic := r.URL.Query().Get("logic")

	res, err := s.Evaluate(r.Context(), preset, chain, fundMode, logic)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, res)
}

type postFunnelRequest struct {
	Preset     string   `json:"preset"`
	Chain      []string `json:"chain"`
	FundMode   string   `json:"fund_mode"`
	Logic      string   `json:"logic"`
	DropSuffix *bool    `json:"drop_suffix"`
}

// PostFunnel هندلر اجرای ارزیابی قیف با پارامترهای بدنه: POST /api/funnel
func (s *Service) PostFunnel(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	var req postFunnelRequest
	if err == nil && len(strings.TrimSpace(string(body))) > 0 {
		_ = json.Unmarshal(body, &req)
	}

	res, err := s.Evaluate(r.Context(), req.Preset, req.Chain, req.FundMode, req.Logic)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, res)
}

// Trace هندلر خط زمان و ردپای یک نماد: GET /api/funnel/trace?symbol=...&preset=...
func (s *Service) Trace(w http.ResponseWriter, r *http.Request) {
	sym := r.URL.Query().Get("symbol")
	preset := r.URL.Query().Get("preset")

	res, err := s.GetTrace(r.Context(), sym, preset)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, res)
}
