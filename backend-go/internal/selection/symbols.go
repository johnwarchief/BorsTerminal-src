package selection

import (
	"context"
	"database/sql"
	"strings"

	"borsterminal/backend/internal/mstat"
	"borsterminal/backend/internal/symbolid"
)

type SymbolItem struct {
	Symbol     string   `json:"symbol"`
	Name       string   `json:"name"`
	SectorName string   `json:"sector_name"`
	Cls        string   `json:"cls"`
	Kind       string   `json:"kind"`
	Price      *float64 `json:"price"`
}

type SymbolsResponse struct {
	Status  string       `json:"status"`
	Count   int          `json:"count"`
	Query   string       `json:"query"`
	Data    []SymbolItem `json:"data"`
	Message string       `json:"message,omitempty"`
}

// SearchSymbols جستجوی نمادها برای افزودن به سبد دارایی بر پایه سهام و صندوق‌ها.
func (s *Service) SearchSymbols(ctx context.Context, q string, limit int) SymbolsResponse {
	term := strings.TrimSpace(q)
	if term == "" {
		return SymbolsResponse{
			Status: "success",
			Count:  0,
			Query:  "",
			Data:   []SymbolItem{},
		}
	}

	capLimit := limit
	if capLimit <= 0 {
		capLimit = 40
	} else if capLimit > 100 {
		capLimit = 100
	}

	nTerm := symbolid.Norm(term)
	kTerm := symbolid.Key(term)

	// واکشی ابزارها از market.db به همراه آخرین قیمت بازار
	query := `
		SELECT i.l_val18, COALESCE(i.l_val30, ''), COALESCE(i.sector_name, ''),
		       i.paper_type, m.p_last, m.p_closing
		FROM instruments i
		LEFT JOIN market_watch m
		       ON m.ins_code = i.ins_code
		      AND m.d_even = (SELECT MAX(d_even) FROM market_watch)
		WHERE i.l_val18 IS NOT NULL AND i.l_val18 <> ''
		ORDER BY length(i.l_val18), i.l_val18
	`

	rows, err := s.marketDB.QueryContext(ctx, query)
	if err != nil {
		return SymbolsResponse{
			Status:  "error",
			Message: err.Error(),
			Data:    []SymbolItem{},
		}
	}
	defer rows.Close()

	var result []SymbolItem
	for rows.Next() {
		var sym, name, sector string
		var paperType sql.NullInt64
		var pLast, pClosing sql.NullFloat64

		if err := rows.Scan(&sym, &name, &sector, &paperType, &pLast, &pClosing); err != nil {
			continue
		}

		kSym := symbolid.Key(sym)
		nName := symbolid.Norm(name)

		// تطابق با نماد یا نام شرکت
		if !strings.Contains(kSym, kTerm) && !strings.Contains(nName, nTerm) {
			continue
		}

		var pt *int64
		if paperType.Valid {
			v := paperType.Int64
			pt = &v
		}

		cls, kind := mstat.Classify(pt, name, sym, sector)
		// فقط سهام و صندوق‌ها قابل نگهداری در سبد هستند
		if cls != mstat.PaperStock && cls != mstat.PaperFund {
			continue
		}

		var price *float64
		if pLast.Valid && pLast.Float64 > 0 {
			v := pLast.Float64
			price = &v
		} else if pClosing.Valid && pClosing.Float64 > 0 {
			v := pClosing.Float64
			price = &v
		}

		result = append(result, SymbolItem{
			Symbol:     sym,
			Name:       strings.TrimSpace(name),
			SectorName: sector,
			Cls:        cls,
			Kind:       kind,
			Price:      price,
		})

		if len(result) >= capLimit {
			break
		}
	}

	if result == nil {
		result = []SymbolItem{}
	}

	return SymbolsResponse{
		Status: "success",
		Count:  len(result),
		Query:  term,
		Data:   result,
	}
}
