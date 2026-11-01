package notifications

import (
	"context"
	"database/sql"
	"fmt"
	"sort"
	"strings"

	"borsterminal/backend/internal/period"
	"borsterminal/backend/internal/symbolid"
)

type Service struct {
	db          *sql.DB
	symResolver *symbolid.Resolver
}

func NewService(db *sql.DB) *Service {
	return &Service{
		db:          db,
		symResolver: symbolid.New(db),
	}
}

func (s *Service) Close() error {
	if s.symResolver != nil {
		return s.symResolver.Close()
	}
	return nil
}


func (s *Service) Sources(ctx context.Context) (map[string]any, error) {
	out := []map[string]any{}
	pubCanon := period.PubCanonSQL("publish_date")
	query := fmt.Sprintf("SELECT COUNT(*), MAX(%s), MAX(fetched_at) FROM codal_notices", pubCanon)

	var (
		count   sql.NullInt64
		newest  sql.NullString
		fetched sql.NullString
	)

	err := s.db.QueryRowContext(ctx, query).Scan(&count, &newest, &fetched)
	if err != nil {
		out = append(out, map[string]any{
			"source":  Source,
			"label":   SourceLabel,
			"rows":    0,
			"state":   "unavailable",
			"message": err.Error(),
		})
	} else {
		n := int(count.Int64)
		state := "empty"
		if n > 0 {
			state = "ok"
		}
		var newestVal any = nil
		if newest.Valid && newest.String != "" {
			newestVal = newest.String
		}
		var fetchedVal any = nil
		if fetched.Valid && fetched.String != "" {
			fetchedVal = fetched.String
		}

		out = append(out, map[string]any{
			"source":         Source,
			"label":          SourceLabel,
			"rows":           n,
			"newest_publish": newestVal,
			"last_fetch":     fetchedVal,
			"state":          state,
		})
	}

	return map[string]any{
		"status":  "ok",
		"sources": out,
		"note": "تک‌منبع: کدالِ خودِ سازمانِ بورس، همان واکشیِ که FTS هم " +
			"از آن تغذیه می‌کند. منبعِ بیرونیِ تازه اضافه نشده است.",
	}, nil
}

type Item struct {
	ID          any     `json:"id"`
	Symbol      *string `json:"symbol"`
	Company     *string `json:"company"`
	Title       string  `json:"title"`
	PublishDate *string `json:"publish_date"`
	SentDate    *string `json:"sent_date"`
	ReceivedAt  *string `json:"received_at"`
	URL         *string `json:"url"`
	Source      string  `json:"source"`
	Occurrences int     `json:"occurrences"`
	Kind        string  `json:"kind"`
	Level       string  `json:"level"`
	Reason      string  `json:"reason"`
	LetterCode  *string `json:"letter_code"`
}

const selectCols = "tracing_no, symbol, company_name, title, letter_code, publish_date, sent_date, url, fetched_at"

func (s *Service) Feed(ctx context.Context, since string, levels []string, limit int, symbol string) (map[string]any, error) {
	wantMap := make(map[string]struct{})
	for _, l := range levels {
		if trimmed := strings.TrimSpace(l); trimmed != "" {
			wantMap[trimmed] = struct{}{}
		}
	}

	symStr := strings.TrimSpace(symbol)
	effLimit := limit
	if effLimit < 1 {
		effLimit = 120
	} else if effLimit > 2000 {
		effLimit = 2000
	}
	dbLimit := effLimit * 3

	var query string
	var args []any

	pubOrder := period.PubOrderExpr("publish_date")

	if symStr != "" {
		pred, pArgs, err := s.symResolver.Pred(ctx, "symbol", symStr, symbolid.Codal)
		if err != nil {
			return nil, err
		}
		query = fmt.Sprintf("SELECT %s FROM codal_notices WHERE %s ORDER BY %s LIMIT ?", selectCols, pred, pubOrder)
		args = append(pArgs, dbLimit)
	} else {
		query = fmt.Sprintf("SELECT %s FROM codal_notices ORDER BY %s LIMIT ?", selectCols, pubOrder)
		args = []any{dbLimit}
	}

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return map[string]any{
			"status":  "error",
			"source":  Source,
			"items":   []any{},
			"message": fmt.Sprintf("جدولِ اطلاعیه‌های کدال درِ این بانک نیست: %s", err.Error()),
		}, nil
	}
	defer rows.Close()

	type rawRow struct {
		tracingNo   any
		symbol      sql.NullString
		companyName sql.NullString
		title       sql.NullString
		letterCode  sql.NullString
		publishDate sql.NullString
		sentDate    sql.NullString
		url         sql.NullString
		fetchedAt   sql.NullString
	}

	var scannedCount int
	var items []*Item
	seen := make(map[string]*Item)
	var dropped int

	for rows.Next() {
		scannedCount++
		var r rawRow
		if err := rows.Scan(
			&r.tracingNo,
			&r.symbol,
			&r.companyName,
			&r.title,
			&r.letterCode,
			&r.publishDate,
			&r.sentDate,
			&r.url,
			&r.fetchedAt,
		); err != nil {
			return nil, err
		}

		pub := ""
		if r.publishDate.Valid {
			pub = r.publishDate.String
		}

		if since != "" && pub != "" && pub < since {
			continue
		}

		symVal := ""
		if r.symbol.Valid {
			symVal = r.symbol.String
		}
		titleVal := ""
		if r.title.Valid {
			titleVal = r.title.String
		}

		k := DedupeKey(symVal, titleVal, pub)
		if existing, ok := seen[k]; ok {
			existing.Occurrences++
			dropped++
			continue
		}

		lcVal := ""
		if r.letterCode.Valid {
			lcVal = r.letterCode.String
		}
		cls := Classify(titleVal, lcVal)
		if len(wantMap) > 0 {
			if _, ok := wantMap[cls.Level]; !ok {
				continue
			}
		}

		var symPtr *string
		if s := strings.TrimSpace(symVal); s != "" {
			symPtr = &s
		}
		var compPtr *string
		if c := strings.TrimSpace(r.companyName.String); r.companyName.Valid && c != "" {
			compPtr = &c
		}
		var pubPtr *string
		if p := strings.TrimSpace(pub); p != "" {
			pubPtr = &p
		}
		var sentPtr *string
		if s := strings.TrimSpace(r.sentDate.String); r.sentDate.Valid && s != "" {
			sentPtr = &s
		}
		var fetchPtr *string
		if f := strings.TrimSpace(r.fetchedAt.String); r.fetchedAt.Valid && f != "" {
			fetchPtr = &f
		}
		var urlPtr *string
		if u := strings.TrimSpace(r.url.String); r.url.Valid && u != "" {
			urlPtr = &u
		}

		item := &Item{
			ID:          r.tracingNo,
			Symbol:      symPtr,
			Company:     compPtr,
			Title:       strings.TrimSpace(titleVal),
			PublishDate: pubPtr,
			SentDate:    sentPtr,
			ReceivedAt:  fetchPtr,
			URL:         urlPtr,
			Source:      Source,
			Occurrences: 1,
			Kind:        cls.Kind,
			Level:       cls.Level,
			Reason:      cls.Reason,
			LetterCode:  cls.LetterCode,
		}

		seen[k] = item
		items = append(items, item)
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	keptLimit := limit
	if keptLimit < 1 {
		keptLimit = 120
	}
	kept := items
	if len(kept) > keptLimit {
		kept = kept[:keptLimit]
	}

	var levelsOut any = nil
	if len(wantMap) > 0 {
		sortedLevels := make([]string, 0, len(wantMap))
		for l := range wantMap {
			sortedLevels = append(sortedLevels, l)
		}
		sort.Strings(sortedLevels)
		levelsOut = sortedLevels
	}

	var sinceOut any = nil
	if since != "" {
		sinceOut = since
	}
	var symbolOut any = nil
	if symStr != "" {
		symbolOut = symStr
	}

	itemResults := make([]any, 0, len(kept))
	for _, it := range kept {
		itemResults = append(itemResults, it)
	}

	return map[string]any{
		"status":            "ok",
		"source":            Source,
		"count":             len(kept),
		"scanned":           scannedCount,
		"merged_duplicates": dropped,
		"levels":            levelsOut,
		"since":             sinceOut,
		"symbol":            symbolOut,
		"items":             itemResults,
	}, nil
}
