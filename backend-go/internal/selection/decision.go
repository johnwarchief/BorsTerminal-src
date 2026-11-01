package selection

import (
	"context"
	"fmt"
	"strings"
	"time"
)

var allowedStatuses = map[string]bool{
	"accept":  true,
	"reject":  true,
	"monitor": true,
	"pending": true,
}

var keepIfAbsent = []string{
	"name", "asset_kind", "price", "qty", "score", "pricing_mode", "sector",
}

type PostDecisionResponse struct {
	Status      string       `json:"status"`
	Decision    *DecisionRow `json:"decision,omitempty"`
	Symbol      string       `json:"symbol,omitempty"`
	SavedStatus string       `json:"saved_status,omitempty"`
	Message     string       `json:"message,omitempty"`
}

type DeleteDecisionResponse struct {
	Status  string `json:"status"`
	Deleted int64  `json:"deleted"`
	Message string `json:"message,omitempty"`
}

// SaveDecision ثبت یا به‌روزرسانی تصمیم روی یک نماد.
func (s *Service) SaveDecision(ctx context.Context, payload map[string]any) PostDecisionResponse {
	if len(payload) == 0 {
		return PostDecisionResponse{
			Status:  "error",
			Message: "بدنهٔ درخواست خالی است — کلیدهای symbol و status لازم‌اند",
		}
	}

	symRaw, _ := payload["symbol"].(string)
	symbol := strings.TrimSpace(symRaw)
	if symbol == "" {
		return PostDecisionResponse{
			Status:  "error",
			Message: "نماد ارسال نشده",
		}
	}

	stRaw, _ := payload["status"].(string)
	status := strings.ToLower(strings.TrimSpace(stRaw))
	if !allowedStatuses[status] {
		return PostDecisionResponse{
			Status:  "error",
			Message: "وضعیت نامعتبر: " + status,
		}
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	// اگر وضعیت pending باشد، تصمیم حذف می‌شود (بازگشت به بررسی‌نشده)
	if status == "pending" {
		_, err := s.userDB.ExecContext(ctx, "DELETE FROM selection_decisions WHERE symbol = ?", symbol)
		if err != nil {
			return PostDecisionResponse{
				Status:  "error",
				Message: err.Error(),
			}
		}
		return PostDecisionResponse{
			Status:      "success",
			Decision:    nil,
			Symbol:      symbol,
			SavedStatus: status,
		}
	}

	// استخراج مقادیر جدید از payload
	name := getString(payload, "name", 120)
	reason := getString(payload, "reason", 200)
	note := getString(payload, "note", 500)
	stopLoss := getString(payload, "stop_loss", 120)
	assetKind := getString(payload, "asset_kind", 10)
	pricingMode := getString(payload, "pricing_mode", 20)
	sector := getString(payload, "sector", 80)

	weightPct := getFloat(payload, "weight_pct")
	price := getFloat(payload, "price")
	qty := getFloat(payload, "qty")
	score := getInt(payload, "score")

	nowStr := time.Now().Format("2006-01-02T15:04:05")

	// Patch-semantics: خواندن رکورد قبلی برای فیلدهایی که در payload ارسال نشده‌اند
	var prev DecisionRow
	row := s.userDB.QueryRowContext(ctx, `
		SELECT symbol, name, status, reason, note, stop_loss, asset_kind,
		       weight_pct, price, qty, score, pricing_mode, sector, updated_at
		FROM selection_decisions
		WHERE symbol = ?
	`, symbol)

	existed := false
	if err := row.Scan(
		&prev.Symbol, &prev.Name, &prev.Status, &prev.Reason, &prev.Note, &prev.StopLoss,
		&prev.AssetKind, &prev.WeightPct, &prev.Price, &prev.Qty, &prev.Score,
		&prev.PricingMode, &prev.Sector, &prev.UpdatedAt,
	); err == nil {
		existed = true
	}

	if existed {
		if _, ok := payload["name"]; !ok || payload["name"] == nil || payload["name"] == "" {
			name = prev.Name
		}
		if _, ok := payload["asset_kind"]; !ok || payload["asset_kind"] == nil || payload["asset_kind"] == "" {
			assetKind = prev.AssetKind
		}
		if _, ok := payload["pricing_mode"]; !ok || payload["pricing_mode"] == nil || payload["pricing_mode"] == "" {
			pricingMode = prev.PricingMode
		}
		if _, ok := payload["sector"]; !ok || payload["sector"] == nil || payload["sector"] == "" {
			sector = prev.Sector
		}
		if _, ok := payload["price"]; !ok || payload["price"] == nil || payload["price"] == "" {
			price = prev.Price
		}
		if _, ok := payload["qty"]; !ok || payload["qty"] == nil || payload["qty"] == "" {
			qty = prev.Qty
		}
		if _, ok := payload["score"]; !ok || payload["score"] == nil || payload["score"] == "" {
			score = prev.Score
		}
	}

	// درج یا به‌روزرسانی
	query := `
		INSERT INTO selection_decisions (
			symbol, name, status, reason, note, stop_loss, asset_kind,
			weight_pct, price, qty, score, pricing_mode, sector, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(symbol) DO UPDATE SET
			name = excluded.name,
			status = excluded.status,
			reason = excluded.reason,
			note = excluded.note,
			stop_loss = excluded.stop_loss,
			asset_kind = excluded.asset_kind,
			weight_pct = excluded.weight_pct,
			price = excluded.price,
			qty = excluded.qty,
			score = excluded.score,
			pricing_mode = excluded.pricing_mode,
			sector = excluded.sector,
			updated_at = excluded.updated_at
	`

	_, err := s.userDB.ExecContext(ctx, query,
		symbol, name, status, reason, note, stopLoss, assetKind,
		weightPct, price, qty, score, pricingMode, sector, nowStr,
	)
	if err != nil {
		return PostDecisionResponse{
			Status:  "error",
			Message: err.Error(),
		}
	}

	savedRow := &DecisionRow{
		Symbol:      symbol,
		Name:        name,
		Status:      status,
		Reason:      reason,
		Note:        note,
		StopLoss:    stopLoss,
		AssetKind:   assetKind,
		WeightPct:   weightPct,
		Price:       price,
		Qty:         qty,
		Score:       score,
		PricingMode: pricingMode,
		Sector:      sector,
		UpdatedAt:   nowStr,
	}

	return PostDecisionResponse{
		Status:      "success",
		Decision:    savedRow,
		Symbol:      symbol,
		SavedStatus: status,
	}
}

// RemoveDecision پاک کردن تصمیم یک نماد.
func (s *Service) RemoveDecision(ctx context.Context, symbol string) DeleteDecisionResponse {
	cleanSym := strings.TrimSpace(symbol)
	if cleanSym == "" {
		return DeleteDecisionResponse{
			Status:  "error",
			Message: "symbol is required",
		}
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	res, err := s.userDB.ExecContext(ctx, "DELETE FROM selection_decisions WHERE symbol = ?", cleanSym)
	if err != nil {
		return DeleteDecisionResponse{
			Status:  "error",
			Message: err.Error(),
		}
	}

	n, _ := res.RowsAffected()
	return DeleteDecisionResponse{
		Status:  "success",
		Deleted: n,
	}
}

func getString(p map[string]any, key string, maxLen int) string {
	v, ok := p[key]
	if !ok || v == nil {
		return ""
	}
	s := strings.TrimSpace(fmt.Sprint(v))
	if maxLen > 0 && len(s) > maxLen {
		return s[:maxLen]
	}
	return s
}

func getFloat(p map[string]any, key string) float64 {
	v, ok := p[key]
	if !ok || v == nil || v == "" {
		return 0
	}
	switch val := v.(type) {
	case float64:
		return val
	case float32:
		return float64(val)
	case int:
		return float64(val)
	case int64:
		return float64(val)
	}
	var f float64
	_, _ = fmt.Sscanf(fmt.Sprint(v), "%f", &f)
	return f
}

func getInt(p map[string]any, key string) int {
	v, ok := p[key]
	if !ok || v == nil || v == "" {
		return 0
	}
	switch val := v.(type) {
	case int:
		return val
	case int64:
		return int(val)
	case float64:
		return int(val)
	}
	var i int
	_, _ = fmt.Sscanf(fmt.Sprint(v), "%d", &i)
	return i
}
