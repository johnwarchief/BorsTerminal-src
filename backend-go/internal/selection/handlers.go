package selection

import (
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"

	"borsterminal/backend/internal/httpapi"
)

type Service struct {
	marketDB *sql.DB
	userDB   *sql.DB
	mu       sync.Mutex
}

func NewService(marketDB, userDB *sql.DB) *Service {
	return &Service{
		marketDB: marketDB,
		userDB:   userDB,
	}
}

// Symbols هندلر جستجوی نمادها برای سبد دارایی: GET /api/selection/symbols?q=...&limit=...
func (s *Service) Symbols(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	limitStr := r.URL.Query().Get("limit")
	limit := 40
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	res := s.SearchSymbols(r.Context(), q, limit)
	httpapi.WriteJSON(w, http.StatusOK, res)
}

// Portfolio هندلر دریافت اطلاعات جامع سبد دارایی: GET /api/selection/portfolio
func (s *Service) Portfolio(w http.ResponseWriter, r *http.Request) {
	res := s.GetPortfolio(r.Context())
	httpapi.WriteJSON(w, http.StatusOK, res)
}

// PostDecision هندلر ثبت یا به‌روزرسانی تصمیم: POST /api/selection/decision
func (s *Service) PostDecision(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil || len(strings.TrimSpace(string(body))) == 0 {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "بدنهٔ درخواست خالی است — کلیدهای symbol و status لازم‌اند",
		})
		return
	}

	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "بدنهٔ درخواست خالی است — کلیدهای symbol و status لازم‌اند",
		})
		return
	}

	res := s.SaveDecision(r.Context(), payload)
	httpapi.WriteJSON(w, http.StatusOK, res)
}

// DeleteDecision هندلر حذف تصمیم نماد: DELETE /api/selection/decision/{symbol}
func (s *Service) DeleteDecision(w http.ResponseWriter, r *http.Request) {
	sym := r.PathValue("symbol")
	if sym == "" {
		// اگر PathValue خالی بود، از انتهای Path می‌خوانیم
		parts := strings.Split(r.URL.Path, "/")
		if len(parts) > 0 {
			sym = parts[len(parts)-1]
		}
	}
	decodedSym, err := url.PathUnescape(sym)
	if err == nil && decodedSym != "" {
		sym = decodedSym
	}

	res := s.RemoveDecision(r.Context(), sym)
	httpapi.WriteJSON(w, http.StatusOK, res)
}
