package codal

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// NoticeSummary خلاصه اطلاعات یک اطلاعیه کشف‌شده کدال.
type NoticeSummary struct {
	TracingNo   int64  `json:"tracing_no"`
	Symbol      string `json:"symbol"`
	Title       string `json:"title"`
	LetterCode  string `json:"letter_code"`
	PublishDate string `json:"publish_date"`
	SentDate    string `json:"sent_date"`
	URL         string `json:"url"`
	CompanyName string `json:"company_name,omitempty"`
}

// codalLetter ساختار دریافت اطلاعیه از پاسخ JSON وب‌سرویس جستجوی کدال.
type codalLetter struct {
	TracingNo       any    `json:"TracingNo"`
	Symbol          string `json:"Symbol"`
	CompanyName     string `json:"CompanyName"`
	Title           string `json:"Title"`
	LetterCode      string `json:"LetterCode"`
	PublishDateTime string `json:"PublishDateTime"`
	SentDateTime    string `json:"SentDateTime"`
	Url             string `json:"Url"`
	PdfUrl          string `json:"PdfUrl"`
	ExcelUrl        string `json:"ExcelUrl"`
}

type codalSearchResponse struct {
	Page    int           `json:"Page"`
	Total   int           `json:"Total"`
	Letters []codalLetter `json:"Letters"`
}

// EnsureSchema ایجاد جداول استاندارد codal_notices و pipeline_cursor در دیتابیس کدال در صورت عدم وجود.
func EnsureSchema(db *sql.DB) error {
	ddl := `
	CREATE TABLE IF NOT EXISTS codal_notices (
		tracing_no INTEGER PRIMARY KEY,
		symbol TEXT,
		company_name TEXT,
		title TEXT,
		letter_code TEXT,
		publish_date TEXT,
		sent_date TEXT,
		url TEXT,
		fetched_at TEXT,
		pdf_url TEXT,
		excel_url TEXT
	);
	CREATE INDEX IF NOT EXISTS ix_codal_symbol ON codal_notices(symbol);
	CREATE INDEX IF NOT EXISTS ix_codal_date ON codal_notices(publish_date DESC);

	CREATE TABLE IF NOT EXISTS pipeline_cursor (
		key TEXT PRIMARY KEY,
		value TEXT,
		previous TEXT,
		updated_at TEXT,
		note TEXT
	);
	`
	_, err := db.Exec(ddl)
	return err
}

// DiscoverFeed واکشی فید سراسری جستجوی کدال برای دسته مشخص‌شده (۱ برای صورت‌های مالی، ۳ برای گزارش فعالیت ماهانه)
// همراه با صفحه‌بندی، مدیریت نشانک پایدار در pipeline_cursor، عدم ذخیره و بازگشت موارد تکراری، و درج اتمیک در codal_notices.
func DiscoverFeed(ctx context.Context, client *PoliteClient, db *sql.DB, category int) ([]NoticeSummary, error) {
	if client == nil {
		client = NewPoliteClient()
	}

	if err := EnsureSchema(db); err != nil {
		return nil, fmt.Errorf("ensure schema: %w", err)
	}

	cursorKey := fmt.Sprintf("notice_scan_tn_cat%d", category)

	// ۱. خواندن نشانک پیشین (watermark) از pipeline_cursor
	var watermark int64
	var oldCursorVal string
	err := db.QueryRowContext(ctx, "SELECT value FROM pipeline_cursor WHERE key = ?", cursorKey).Scan(&oldCursorVal)
	if err == nil && oldCursorVal != "" {
		if wm, parseErr := strconv.ParseInt(strings.TrimSpace(oldCursorVal), 10, 64); parseErr == nil {
			watermark = wm
		}
	}

	var discovered []NoticeSummary
	maxSeenTracingNo := watermark
	newestPublishDate := ""

	const maxPages = 50 // سقف احتیاطی صفحات در یک دور کشف

	for page := 1; page <= maxPages; page++ {
		if err := ctx.Err(); err != nil {
			return nil, err
		}

		reqURL := buildSearchURL(client.BaseURL(), category, page)
		body, statusCode, err := client.Get(ctx, reqURL)
		if err != nil {
			return nil, fmt.Errorf("fetch page %d: %w", page, err)
		}
		if statusCode != 200 {
			return nil, fmt.Errorf("codal api returned status %d on page %d", statusCode, page)
		}

		var searchResp codalSearchResponse
		if err := json.Unmarshal(body, &searchResp); err != nil {
			return nil, fmt.Errorf("decode json page %d: %w", page, err)
		}

		if len(searchResp.Letters) == 0 {
			// پایان فید
			break
		}

		allKnownOnPage := true
		var pageNewNotices []NoticeSummary

		// تراکنش برای درج دسته‌ای اطلاعیه‌های همین صفحه
		tx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return nil, fmt.Errorf("begin tx page %d: %w", page, err)
		}

		stmt, err := tx.PrepareContext(ctx, `
			INSERT INTO codal_notices (
				tracing_no, symbol, company_name, title, letter_code,
				publish_date, sent_date, url, fetched_at, pdf_url, excel_url
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			ON CONFLICT(tracing_no) DO NOTHING;
		`)
		if err != nil {
			_ = tx.Rollback()
			return nil, fmt.Errorf("prepare insert notice: %w", err)
		}

		nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")

		for _, item := range searchResp.Letters {
			tn, parseErr := parseTracingNo(item.TracingNo)
			if parseErr != nil || tn <= 0 {
				continue
			}

			if tn > maxSeenTracingNo {
				maxSeenTracingNo = tn
			}

			// اگر شماره پیگیری اطلاعیه کوچک‌تر یا مساوی نشانک باشد، پیش‌تر دیده شده است
			if watermark > 0 && tn <= watermark {
				continue
			}

			// بررسی وجود در پایگاه داده
			var exists int
			_ = tx.QueryRowContext(ctx, "SELECT 1 FROM codal_notices WHERE tracing_no = ?", tn).Scan(&exists)
			if exists == 1 {
				continue
			}

			allKnownOnPage = false

			pubDate := foldDigits(item.PublishDateTime)
			sentDate := foldDigits(item.SentDateTime)
			rawURL := normalizeURL(item.Url)
			pdfURL := normalizeURL(item.PdfUrl)
			excelURL := normalizeURL(item.ExcelUrl)
			sym := strings.TrimSpace(item.Symbol)
			comp := strings.TrimSpace(item.CompanyName)
			title := strings.TrimSpace(item.Title)
			lCode := strings.TrimSpace(item.LetterCode)

			_, execErr := stmt.ExecContext(ctx, tn, sym, comp, title, lCode, pubDate, sentDate, rawURL, nowStr, pdfURL, excelURL)
			if execErr != nil {
				_ = stmt.Close()
				_ = tx.Rollback()
				return nil, fmt.Errorf("insert notice %d: %w", tn, execErr)
			}

			if pubDate > newestPublishDate {
				newestPublishDate = pubDate
			}

			summary := NoticeSummary{
				TracingNo:   tn,
				Symbol:      sym,
				CompanyName: comp,
				Title:       title,
				LetterCode:  lCode,
				PublishDate: pubDate,
				SentDate:    sentDate,
				URL:         rawURL,
			}
			pageNewNotices = append(pageNewNotices, summary)
		}

		_ = stmt.Close()

		if err := tx.Commit(); err != nil {
			return nil, fmt.Errorf("commit page %d notices: %w", page, err)
		}

		discovered = append(discovered, pageNewNotices...)

		// پیش بردن اتمیک نشانک پس از تکمیل کامل و موفق این صفحه
		if maxSeenTracingNo > watermark {
			updateCursor(ctx, db, cursorKey, strconv.FormatInt(maxSeenTracingNo, 10), fmt.Sprintf("category %d discovery", category))
		}
		if newestPublishDate != "" {
			updateCursor(ctx, db, "notice_newest_date", newestPublishDate, "تازه‌ترین تاریخ انتشار دیده‌شده")
		}

		// اگر تمام اطلاعیه‌های این صفحه قبلاً دیده شده بودند، به مرز داده‌های پیشین رسیده‌ایم
		if allKnownOnPage && watermark > 0 {
			break
		}
	}

	return discovered, nil
}

// buildSearchURL ساخت آدرس فراخوانی جستجوی کدال با پارامترهای مشخص.
func buildSearchURL(baseURL string, category int, page int) string {
	q := url.Values{}
	q.Set("Category", strconv.Itoa(category))
	q.Set("PageNumber", strconv.Itoa(page))
	q.Set("Audited", "true")
	q.Set("AuditorRef", "-1")
	q.Set("Childs", "true")
	q.Set("CompanyState", "-1")
	q.Set("CompanyType", "-1")
	q.Set("Consolidatable", "true")
	q.Set("IsNotAudited", "false")
	q.Set("Length", "-1")
	q.Set("LetterType", "-1")
	q.Set("Mains", "true")
	q.Set("NotAudited", "true")
	q.Set("NotConsolidatable", "true")
	q.Set("Publisher", "false")
	q.Set("ReportingType", "-1")
	q.Set("TracingNo", "-1")
	q.Set("search", "false")
	q.Set("FromDate", "1400/01/01")

	return fmt.Sprintf("%s/api/search/v2/q?%s", baseURL, q.Encode())
}

// updateCursor ذخیره نشانک در pipeline_cursor با حفظ مقدار قبلی.
func updateCursor(ctx context.Context, db *sql.DB, key, value, note string) {
	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05")
	query := `
	INSERT INTO pipeline_cursor (key, value, previous, updated_at, note)
	VALUES (?, ?, NULL, ?, ?)
	ON CONFLICT(key) DO UPDATE SET
		previous = pipeline_cursor.value,
		value = excluded.value,
		updated_at = excluded.updated_at,
		note = excluded.note;
	`
	_, _ = db.ExecContext(ctx, query, key, value, nowStr, note)
}

// foldDigits تبدیل ارقام فارسی و عربی به ارقام انگلیسی (ASCII).
func foldDigits(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		switch {
		case r >= '۰' && r <= '۹':
			b.WriteRune('0' + (r - '۰'))
		case r >= '٠' && r <= '٩':
			b.WriteRune('0' + (r - '٠'))
		default:
			b.WriteRune(r)
		}
	}
	return strings.TrimSpace(b.String())
}

// normalizeURL یکسان‌سازی آدرس و تبدیل آدرس‌های نسبی به آدرس کامل کدال.
func normalizeURL(u string) string {
	u = strings.TrimSpace(u)
	if u == "" {
		return ""
	}
	if strings.HasPrefix(u, "/") {
		return "https://codal.ir" + u
	}
	return u
}

// parseTracingNo تجزیه امن شماره پیگیری از فرمت‌های مختلف JSON.
func parseTracingNo(v any) (int64, error) {
	switch val := v.(type) {
	case float64:
		return int64(val), nil
	case int64:
		return val, nil
	case int:
		return int64(val), nil
	case json.Number:
		return val.Int64()
	case string:
		clean := foldDigits(val)
		return strconv.ParseInt(clean, 10, 64)
	default:
		return 0, fmt.Errorf("unknown tracing_no type: %T", v)
	}
}
