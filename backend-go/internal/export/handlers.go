package export

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"borsterminal/backend/internal/httpapi"
)

type Service struct {
	marketDB *sql.DB
}

func NewService(marketDB *sql.DB) *Service {
	return &Service{
		marketDB: marketDB,
	}
}

type postExportRequest struct {
	Fmt   string `json:"fmt"`
	Title string `json:"title"`
	Rows  any    `json:"rows"`
	Meta  any    `json:"meta"`
}

// Post هندلر صدور خروجی داده‌ها: POST /api/export
func (s *Service) Post(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil || len(strings.TrimSpace(string(body))) == 0 {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "empty body",
		})
		return
	}

	var req postExportRequest
	if err := json.Unmarshal(body, &req); err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "empty body",
		})
		return
	}

	if req.Rows == nil {
		httpapi.WriteJSON(w, http.StatusUnprocessableEntity, map[string]any{
			"detail": "rows باید فهرستِ ردیف‌ها باشد",
		})
		return
	}

	rawRows, ok := req.Rows.([]any)
	if !ok {
		httpapi.WriteJSON(w, http.StatusUnprocessableEntity, map[string]any{
			"detail": "rows باید فهرستِ ردیف‌ها باشد",
		})
		return
	}

	if len(rawRows) > ExportMaxRows {
		httpapi.WriteJSON(w, http.StatusRequestEntityTooLarge, map[string]any{
			"detail": fmt.Sprintf("خروجی از %d ردیف بیشتر است", ExportMaxRows),
		})
		return
	}

	rowsData := make([][]any, 0, len(rawRows))
	maxCols := 0

	for _, item := range rawRows {
		rowList, ok := item.([]any)
		if !ok {
			continue
		}
		if len(rowList) > maxCols {
			maxCols = len(rowList)
		}
		rowsData = append(rowsData, rowList)
	}

	if maxCols > ExportMaxCols {
		httpapi.WriteJSON(w, http.StatusRequestEntityTooLarge, map[string]any{
			"detail": fmt.Sprintf("تعدادِ ستون‌ها از %d بیشتر است", ExportMaxCols),
		})
		return
	}

	var metaData [][2]string
	if req.Meta != nil {
		if rawMeta, ok := req.Meta.([]any); ok {
			for _, item := range rawMeta {
				if pair, ok := item.([]any); ok && len(pair) >= 2 {
					metaData = append(metaData, [2]string{
						fmt.Sprint(pair[0]),
						fmt.Sprint(pair[1]),
					})
				}
			}
		}
	}

	title := strings.TrimSpace(req.Title)
	if title == "" {
		title = "export"
	}

	csvBytes, disposition, _ := BuildCSV(title, rowsData, metaData)

	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", disposition)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(csvBytes)
}

// Get هندلر خروجی داده‌های تابلوی بازار: GET /api/export?view=market&fmt=csv
func (s *Service) Get(w http.ResponseWriter, r *http.Request) {
	view := r.URL.Query().Get("view")
	if view == "" {
		view = "market"
	}
	symbol := r.URL.Query().Get("symbol")

	title := view
	if symbol != "" {
		title = fmt.Sprintf("%s_%s", view, symbol)
	}

	rows, err := QueryMarketExportRows(r.Context(), s.marketDB)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}

	csvBytes, disposition, _ := BuildCSV(title, rows, nil)

	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", disposition)
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(csvBytes)
}
