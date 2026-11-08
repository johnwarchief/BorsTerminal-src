package codal

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode"

	"golang.org/x/net/html"
)

// MonthlyReportData ساختار داده‌ای استخراج‌شده از گزارش فعالیت ماهانه کدال.
type MonthlyReportData struct {
	TracingNo   int64   `json:"tracing_no"`
	Symbol      string  `json:"symbol"`
	PeriodEnd   string  `json:"period_end"`
	Year        int     `json:"year"`
	Month       int     `json:"month"`
	Revenue     float64 `json:"revenue"`
	YTDRevenue  float64 `json:"ytd_revenue"`
	PrevRevenue float64 `json:"prev_revenue"`
	PrevYTD     float64 `json:"prev_ytd"`
	Volume      float64 `json:"volume"`
	YTDVolume   float64 `json:"ytd_volume"`
	Unit        string  `json:"unit"`
}

// FinancialStatementData ساختار داده‌ای استخراج‌شده از صورت‌های مالی کدال.
type FinancialStatementData struct {
	TracingNo        int64   `json:"tracing_no"`
	Symbol           string  `json:"symbol"`
	PeriodEnd        string  `json:"period_end"`
	Months           int     `json:"months"`
	Revenue          float64 `json:"revenue"`
	GrossProfit      float64 `json:"gross_profit"`
	OperatingProfit  float64 `json:"operating_profit"`
	NetProfit        float64 `json:"net_profit"`
	Assets           float64 `json:"assets"`
	Liabilities      float64 `json:"liabilities"`
	Equity           float64 `json:"equity"`
	Capital          float64 `json:"capital"`
	RetainedEarnings float64 `json:"retained_earnings"`
	EPS              float64 `json:"eps"`
	IsAudited        bool    `json:"is_audited"`
	IsConsolidated   bool    `json:"is_consolidated"`
	UnitNorm         float64 `json:"unit_norm"`
}

// TableGrid نمای جدولی دوبعدی سلول‌ها (ردیف -> ستون -> مقدار رشته‌ای)
type TableGrid map[int]map[int]string

type tableInfo struct {
	Description string
	Grid        TableGrid
}

type codalJSONCell struct {
	RowSequence    int `json:"rowSequence"`
	ColumnSequence int `json:"columnSequence"`
	Value          any `json:"value"`
}

type codalJSONTable struct {
	Description string          `json:"description"`
	Cells       []codalJSONCell `json:"cells"`
}

type codalJSONSheet struct {
	SheetId any              `json:"sheetId"`
	Title   string           `json:"title"`
	Tables  []codalJSONTable `json:"tables"`
}

type codalJSONDatasource struct {
	Sheets          []codalJSONSheet `json:"sheets"`
	Period          any              `json:"period"`
	PeriodEndToDate any              `json:"periodEndToDate"`
}

func stringify(v any) string {
	if v == nil {
		return ""
	}
	switch val := v.(type) {
	case string:
		return val
	case float64:
		return strconv.FormatFloat(val, 'f', -1, 64)
	default:
		return fmt.Sprint(v)
	}
}

var (
	reDatasource = regexp.MustCompile(`(?s)var\s+datasource\s*=\s*(\{.*?\});`)
	reDateLoose  = regexp.MustCompile(`(?:^|[^\d])(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})(?:[^\d]|$)`)
	reMonths     = regexp.MustCompile(`(?:دوره\s*)?([0-9]+|یک|دو|سه|چهار|پنج|شش|نه|دوازده)\s*ماهه`)

	fsSideKeys = map[string]bool{
		"total_liabilities": true,
		"total_equity":      true,
		"capital":           true,
		"retained_earnings": true,
	}

	// الگوهای رتبه‌بندی‌شده استخراج اقلام صورت‌های مالی طبق قرارداد کدال و FTS
	fsPatterns = map[string][]string{
		"revenue": {
			`^جمعدرآمدهایعملیاتی`,
			`^جمعدرآمدها$`,
			`^درآمدهایعملیاتی$`,
			`^درآمدعملیاتی`,
			`^فروشخالص`,
			`^مبلغفروش`,
			`^بهایفروش`,
			`^جمعفروش`,
			`^درآمدهعملیاتی`,
			`^فروش$`,
			`^درآمد`,
		},
		"gross_profit": {
			`سود\(?زیان\)?ناخالص`,
			`سودناخالص`,
			`سودوزیانناخالص`,
		},
		"operating_profit": {
			`سود\(?زیان\)?عملیات`,
			`سودعملیاتی`,
			`سودوزیانعملیاتی`,
		},
		"net_profit": {
			`^سود\(?زیان\)?خالص$`,
			`^سودخالص$`,
			`^زیانخالص$`,
			`سود\(?زیان\)?قابلتخصیصبهصاحبان`,
			`سود\(?زیان\)?خالص`,
			`سودخالص`,
			`سودوزیانخالص`,
			`^زیانخالص`,
		},
		"total_assets": {
			`^جمعداراییها$`,
			`^جمعداراییها`,
			`کلداراییها`,
			`مجموعداراییها`,
			`^جمعدارایی`,
			`^مجموعدارایی`,
		},
		"total_liabilities": {
			`^جمعبدهیها$`,
			`^جمعبدیها`,
			`کلبدهیها`,
			`مجموعبدهیها`,
			`^جمعبدهی`,
			`^مجموعبدهی`,
		},
		"total_equity": {
			`^جمعحقوقصاحبانسهام$`,
			`حقوقصاحبانسهام`,
			`کلحقوقصاحبانسهام`,
			`^جمعحقوقمالکانه`,
			`^حقوقمالکانه$`,
		},
		"capital": {
			`^سرمایه$`,
			`سرمایهپرداخته`,
			`محل تامین سرمایه`,
			`سرمایهثبتشده`,
		},
		"retained_earnings": {
			`سود\(?زیان\)?انباشته`,
			`سودانباشته`,
			`سودوزیانانباشته`,
			`اندوختهسرمایه`,
			`زیانانباشته`,
		},
		"basic_eps": {
			`سود\(?زیان\)?خالصهرسهم`,
			`سود\(?زیان\)?خالصهرسهمپایه`,
			`epsخالصهرسهم`,
			`سودخالصهرسهم`,
			`درآمدهرسهم`,
			`سود\(?زیان\)پایههرسهم`,
		},
	}

	fsCompiled = make(map[string][]*regexp.Regexp)
)

func init() {
	for key, pats := range fsPatterns {
		for _, p := range pats {
			fsCompiled[key] = append(fsCompiled[key], regexp.MustCompile(p))
		}
	}
}

// matchPatternWithExclusions تطبیق برچسب با الگوی رتبه‌بندی شده همراه با استثنائات تجاری
func matchPatternWithExclusions(key string, idx int, pat *regexp.Regexp, label string) bool {
	if !pat.MatchString(label) {
		return false
	}
	// استثنائات اختصاصی
	switch key {
	case "revenue":
		if idx == len(fsCompiled["revenue"])-1 { // آخرین الگو: ^درآمد
			if strings.Contains(label, "سودسهام") || strings.Contains(label, "سرمایهگذاری") {
				return false
			}
		}
	case "total_assets":
		if strings.HasPrefix(label, "جمعداراییهای") || strings.HasPrefix(label, "مجموعداراییهای") {
			return false
		}
	case "total_liabilities":
		if strings.HasPrefix(label, "جمعبدهیهای") || strings.HasPrefix(label, "مجموعبدهیهای") {
			return false
		}
	}
	return true
}

// normalizeLabel پاک‌سازی نویسه‌های فاصله، نیم‌فاصله، و یکسان‌سازی ي/ك عربی.
func normalizeLabel(s string) string {
	s = foldDigits(s)
	s = strings.ReplaceAll(s, "\u200c", "")
	s = strings.ReplaceAll(s, "ي", "ی")
	s = strings.ReplaceAll(s, "ك", "ک")
	s = strings.ReplaceAll(s, "ة", "ه")

	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		if !unicode.IsSpace(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

// parseNumericValue تبدیل رشته حاوی اعداد فارسی/انگلیسی، با یا بدون ویرگول و پرانتز (منفی).
func parseNumericValue(s string) (float64, bool) {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" || s == "—" {
		return 0, false
	}
	folded := foldDigits(s)
	folded = strings.ReplaceAll(folded, ",", "")
	folded = strings.ReplaceAll(folded, "،", "")
	folded = strings.ReplaceAll(folded, "\u200c", "")
	folded = strings.ReplaceAll(folded, "\u200e", "")
	folded = strings.ReplaceAll(folded, "\u200f", "")
	folded = strings.TrimSpace(folded)

	isNegative := false
	if strings.HasPrefix(folded, "(") && strings.HasSuffix(folded, ")") {
		isNegative = true
		folded = strings.TrimSpace(folded[1 : len(folded)-1])
	} else if strings.HasPrefix(folded, "-") {
		isNegative = true
		folded = strings.TrimSpace(folded[1:])
	}

	val, err := strconv.ParseFloat(folded, 64)
	if err != nil {
		return 0, false
	}
	if isNegative {
		val = -val
	}
	return val, true
}

// extractTablesFromHTML استخراج جداول از طریق datasource و در صورت عدم وجود از طریق تگ‌های <table> HTML.
func extractTablesFromHTML(htmlBytes []byte) ([]tableInfo, string) {
	var tables []tableInfo
	var periodEnd string

	// ۱. بررسی وجود var datasource = {...} در اسکریپت صفحه
	match := reDatasource.FindSubmatch(htmlBytes)
	if len(match) > 1 {
		var ds codalJSONDatasource
		if err := json.Unmarshal(match[1], &ds); err == nil {
			if ds.PeriodEndToDate != nil {
				periodEnd = canonicalizePeriod(stringify(ds.PeriodEndToDate))
			}
			for _, sheet := range ds.Sheets {
				for _, tbl := range sheet.Tables {
					grid := make(TableGrid)
					for _, c := range tbl.Cells {
						if _, ok := grid[c.RowSequence]; !ok {
							grid[c.RowSequence] = make(map[int]string)
						}
						grid[c.RowSequence][c.ColumnSequence] = stringify(c.Value)
					}
					tables = append(tables, tableInfo{
						Description: tbl.Description,
						Grid:        grid,
					})
				}
			}
		}
	}

	// اگر جداول از datasource استخراج شدند، برگردان
	if len(tables) > 0 {
		return tables, periodEnd
	}

	// ۲. استخراج مستقیم جداول از ساختار درخت DOM با استفاده از golang.org/x/net/html
	doc, err := html.Parse(bytes.NewReader(htmlBytes))
	if err != nil {
		return nil, periodEnd
	}

	var walkTable func(n *html.Node)
	walkTable = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "table" {
			grid := parseHTMLTableNode(n)
			if len(grid) > 0 {
				tables = append(tables, tableInfo{
					Grid: grid,
				})
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walkTable(c)
		}
	}
	walkTable(doc)

	return tables, periodEnd
}

// parseHTMLTableNode پیمایش نود <table> و تبدیل سطرها و ستون‌ها با احتساب rowspan و colspan.
func parseHTMLTableNode(tableNode *html.Node) TableGrid {
	grid := make(TableGrid)
	occupied := make(map[int]map[int]bool)

	rowIndex := 0

	var findRows func(n *html.Node)
	findRows = func(n *html.Node) {
		if n.Type == html.ElementNode && n.Data == "tr" {
			rowIndex++
			if _, ok := grid[rowIndex]; !ok {
				grid[rowIndex] = make(map[int]string)
			}

			colIndex := 1
			for cell := n.FirstChild; cell != nil; cell = cell.NextSibling {
				if cell.Type == html.ElementNode && (cell.Data == "td" || cell.Data == "th") {
					for occupied[rowIndex] != nil && occupied[rowIndex][colIndex] {
						colIndex++
					}

					rowSpan := 1
					colSpan := 1
					for _, attr := range cell.Attr {
						if strings.EqualFold(attr.Key, "rowspan") {
							if v, err := strconv.Atoi(attr.Val); err == nil && v > 1 {
								rowSpan = v
							}
						}
						if strings.EqualFold(attr.Key, "colspan") {
							if v, err := strconv.Atoi(attr.Val); err == nil && v > 1 {
								colSpan = v
							}
						}
					}

					cellText := extractNodeText(cell)

					for r := rowIndex; r < rowIndex+rowSpan; r++ {
						if occupied[r] == nil {
							occupied[r] = make(map[int]bool)
						}
						for c := colIndex; c < colIndex+colSpan; c++ {
							occupied[r][c] = true
						}
					}

					for c := colIndex; c < colIndex+colSpan; c++ {
						grid[rowIndex][c] = cellText
					}

					colIndex += colSpan
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			findRows(c)
		}
	}

	findRows(tableNode)
	return grid
}

func extractNodeText(n *html.Node) string {
	var sb strings.Builder
	var walk func(*html.Node)
	walk = func(node *html.Node) {
		if node.Type == html.TextNode {
			sb.WriteString(node.Data)
		}
		for c := node.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(n)
	return strings.TrimSpace(sb.String())
}

// canonicalizePeriod استخراج و تبدیل تاریخ به فرمت استاندارد YYYY/MM/DD.
func canonicalizePeriod(raw string) string {
	raw = foldDigits(raw)
	match := reDateLoose.FindStringSubmatch(raw)
	if len(match) < 4 {
		return ""
	}
	year, errY := strconv.Atoi(match[1])
	month, errM := strconv.Atoi(match[2])
	day, errD := strconv.Atoi(match[3])
	if errY != nil || errM != nil || errD != nil {
		return ""
	}
	if month < 1 || month > 12 || day < 1 || day > 31 {
		return ""
	}
	return fmt.Sprintf("%04d/%02d/%02d", year, month, day)
}

// parsePeriodEndFromTitle استخراج دوره منتهی به از عنوان اطلاعیه.
func parsePeriodEndFromTitle(title string) string {
	idx := strings.Index(title, "منتهی به")
	if idx != -1 {
		title = title[idx+len("منتهی به"):]
	}
	return canonicalizePeriod(title)
}

// parsePeriodMonthsFromTitle استخراج تعداد ماه‌های دوره (مثلا ۳، ۶، ۹، ۱۲ ماهه).
func parsePeriodMonthsFromTitle(title string) int {
	norm := foldDigits(title)
	match := reMonths.FindStringSubmatch(norm)
	if len(match) > 1 {
		token := match[1]
		switch token {
		case "1", "یک":
			return 1
		case "2", "دو":
			return 2
		case "3", "سه":
			return 3
		case "4", "چهار":
			return 4
		case "5", "پنج":
			return 5
		case "6", "شش":
			return 6
		case "9", "نه":
			return 9
		case "12", "دوازده":
			return 12
		default:
			if v, err := strconv.Atoi(token); err == nil {
				return v
			}
		}
	}
	if strings.Contains(title, "سال مالی") || strings.Contains(title, "سالانه") {
		return 12
	}
	return 0
}

// ExtractMonthlySales استخراج ساختاریافته جدول فعالیت ماهانه نماد از HTML یا datasource.
func ExtractMonthlySales(htmlContent []byte, notice NoticeSummary) (*MonthlyReportData, error) {
	tables, dsPeriod := extractTablesFromHTML(htmlContent)
	if len(tables) == 0 {
		return nil, fmt.Errorf("no tables found in monthly report HTML for %s (tracing %d)", notice.Symbol, notice.TracingNo)
	}

	periodEnd := dsPeriod
	if periodEnd == "" {
		periodEnd = parsePeriodEndFromTitle(notice.Title)
	}

	var year, month int
	if periodEnd != "" {
		parts := strings.Split(periodEnd, "/")
		if len(parts) >= 2 {
			year, _ = strconv.Atoi(parts[0])
			month, _ = strconv.Atoi(parts[1])
		}
	}

	data := &MonthlyReportData{
		TracingNo: notice.TracingNo,
		Symbol:    notice.Symbol,
		PeriodEnd: periodEnd,
		Year:      year,
		Month:     month,
	}

	// پیمایش جداول جهت پیدا کردن جدول تولید و فروش ماهانه
	for _, tbl := range tables {
		grid := tbl.Grid
		var rowKeys []int
		for r := range grid {
			rowKeys = append(rowKeys, r)
		}
		sort.Ints(rowKeys)
		if len(rowKeys) < 2 {
			continue
		}

		// شناسایی دو سطر هدر (یک سطر برای گروه‌های زمانی و یک سطر برای زیرستون‌های مبلغ/تعداد)
		var subRow, grpRow int
		for _, hr := range rowKeys[:min(4, len(rowKeys))] {
			for _, v := range grid[hr] {
				nv := normalizeLabel(v)
				if strings.Contains(nv, "مبلغفروش") {
					subRow = hr
				}
				if strings.Contains(nv, "دورهیکماهه") || strings.Contains(nv, "ازابتدایسالمالی") {
					grpRow = hr
				}
			}
		}

		if subRow == 0 || grpRow == 0 {
			// جدول فروش پیدا نشد، ادامه به جدول بعدی
			continue
		}

		// نگاشت گروه‌های زمانی ستون‌ها
		grpCols := make([]int, 0)
		for c, v := range grid[grpRow] {
			if strings.TrimSpace(v) != "" {
				grpCols = append(grpCols, c)
			}
		}
		sort.Ints(grpCols)

		getGroupOf := func(ci int) string {
			g := ""
			for _, gc := range grpCols {
				if gc <= ci {
					g = normalizeLabel(grid[grpRow][gc])
				} else {
					break
				}
			}
			return g
		}

		var mcols, vmcols []int
		var vunitCol int

		// گام اول: شناسایی ستون‌های دوره یک ماهه (فروش و حجم) و ستون واحد
		for ci, val := range grid[subRow] {
			nv := normalizeLabel(val)
			grp := getGroupOf(ci)

			if strings.Contains(nv, "مبلغفروش") && strings.Contains(grp, "دورهیکماهه") {
				mcols = append(mcols, ci)
			}
			if (strings.Contains(nv, "تعدادفروش") || strings.Contains(nv, "مقدارفروش")) && strings.Contains(grp, "دورهیکماهه") {
				vmcols = append(vmcols, ci)
			}
			if nv == "واحد" {
				vunitCol = ci
			}
		}

		sort.Ints(mcols)
		sort.Ints(vmcols)

		minMcol := 0
		if len(mcols) > 0 {
			minMcol = mcols[0]
		}
		minVmcol := 0
		if len(vmcols) > 0 {
			minVmcol = vmcols[0]
		}

		// گام دوم: شناسایی ستون‌های تجمیعی از ابتدای سال مالی (ستون‌های بعد از دوره یک ماهه جاری)
		var ycols, vycols []int
		for ci, val := range grid[subRow] {
			nv := normalizeLabel(val)
			grp := getGroupOf(ci)

			if strings.Contains(nv, "مبلغفروش") && strings.Contains(grp, "ازابتدایسالمالی") {
				if minMcol == 0 || ci > minMcol {
					ycols = append(ycols, ci)
				}
			}
			if (strings.Contains(nv, "تعدادفروش") || strings.Contains(nv, "مقدارفروش")) && strings.Contains(grp, "ازابتدایسالمالی") {
				if minVmcol == 0 || ci > minVmcol {
					vycols = append(vycols, ci)
				}
			}
		}

		if vunitCol == 0 {
			for ci, val := range grid[grpRow] {
				if normalizeLabel(val) == "واحد" {
					vunitCol = ci
					break
				}
			}
		}

		sort.Ints(ycols)
		sort.Ints(vycols)

		var mcol, ycol, mcolPrev, ycolPrev int
		if len(mcols) > 0 {
			mcol = mcols[0]
			if len(mcols) > 1 {
				mcolPrev = mcols[1]
			}
		}
		if len(ycols) > 0 {
			ycol = ycols[0]
			if len(ycols) > 1 {
				ycolPrev = ycols[1]
			}
		}

		var vmcol, vycol int
		if len(vmcols) > 0 {
			vmcol = vmcols[0]
		}
		if len(vycols) > 0 {
			vycol = vycols[0]
		}

		// یافتن سطر جمع
		var totalRow int
		for _, r := range rowKeys {
			lab := normalizeLabel(grid[r][1])
			if lab == "جمع" || lab == "جمعکل" {
				totalRow = r
				break
			}
		}
		if totalRow == 0 {
			for _, r := range rowKeys {
				lab := normalizeLabel(grid[r][1])
				if strings.HasPrefix(lab, "جمع") {
					totalRow = r
					break
				}
			}
		}

		if totalRow == 0 {
			continue
		}

		// استخراج مقادیر ریالی فروش
		if mcol > 0 {
			if v, ok := parseNumericValue(grid[totalRow][mcol]); ok {
				data.Revenue = v
			}
		}
		if ycol > 0 {
			if v, ok := parseNumericValue(grid[totalRow][ycol]); ok {
				data.YTDRevenue = v
			}
		}
		if mcolPrev > 0 {
			if v, ok := parseNumericValue(grid[totalRow][mcolPrev]); ok {
				data.PrevRevenue = v
			}
		}
		if ycolPrev > 0 {
			if v, ok := parseNumericValue(grid[totalRow][ycolPrev]); ok {
				data.PrevYTD = v
			}
		}

		// استخراج حجم فروش
		extractVol := func(col int) float64 {
			if col == 0 {
				return 0
			}
			if v, ok := parseNumericValue(grid[totalRow][col]); ok && v > 0 {
				return v
			}
			// در صورت خالی بودن سطر جمع، محاسبه مجموع سطرهای محصول
			var sum float64
			for _, r := range rowKeys {
				if r == totalRow || r == subRow || r == grpRow {
					continue
				}
				lab := normalizeLabel(grid[r][1])
				if lab == "" || strings.HasPrefix(lab, "جمع") || strings.HasPrefix(lab, "مجموع") {
					continue
				}
				if v, ok := parseNumericValue(grid[r][col]); ok {
					sum += v
				}
			}
			return sum
		}

		data.Volume = extractVol(vmcol)
		data.YTDVolume = extractVol(vycol)

		// استخراج واحد حجم از اولین سطر داده‌ای غیرخالی
		if vunitCol > 0 {
			for _, r := range rowKeys {
				if r == totalRow || r == subRow || r == grpRow {
					continue
				}
				u := strings.TrimSpace(grid[r][vunitCol])
				uNorm := normalizeLabel(u)
				if u != "" && uNorm != "واحد" {
					data.Unit = uNorm
					break
				}
			}
		}

		// در صورت استخراج موفق فروش ماه یا تجمعی، خروج
		if data.Revenue > 0 || data.YTDRevenue > 0 {
			return data, nil
		}
	}

	// حالت پشتیبان برای بانک‌ها و بیمه‌ها (فروش ندارد بلکه درآمدهای محقق‌شده دارد)
	for _, tbl := range tables {
		grid := tbl.Grid
		var rowKeys []int
		for r := range grid {
			rowKeys = append(rowKeys, r)
		}
		sort.Ints(rowKeys)
		if len(rowKeys) < 2 {
			continue
		}

		var mcol, ycol int
		for _, hr := range rowKeys[:min(3, len(rowKeys))] {
			for ci, val := range grid[hr] {
				nv := normalizeLabel(val)
				if strings.Contains(nv, "درآمد") && strings.Contains(nv, "محقق") && strings.Contains(nv, "طیدوره") {
					mcol = ci
				}
				if strings.Contains(nv, "جمعدرآمد") && strings.Contains(nv, "ابتدای") {
					ycol = ci
				}
			}
			if mcol > 0 && ycol > 0 {
				break
			}
		}

		if mcol > 0 || ycol > 0 {
			var sm, sy float64
			for _, r := range rowKeys {
				lab := normalizeLabel(grid[r][1])
				if strings.HasPrefix(lab, "سرفصل") || strings.HasPrefix(lab, "جمع") {
					continue
				}
				if mcol > 0 {
					if v, ok := parseNumericValue(grid[r][mcol]); ok {
						sm += v
					}
				}
				if ycol > 0 {
					if v, ok := parseNumericValue(grid[r][ycol]); ok {
						sy += v
					}
				}
			}
			data.Revenue = sm
			data.YTDRevenue = sy
			return data, nil
		}
	}

	return data, nil
}

// ExtractFinancialStatements استخراج اقلام ترازنامه و سود و زیان از صفحات شیت‌های صورت مالی.
func ExtractFinancialStatements(sheets map[string][]byte, notice NoticeSummary) (*FinancialStatementData, error) {
	if len(sheets) == 0 {
		return nil, fmt.Errorf("no sheets provided for financial statements extraction: %s (tracing %d)", notice.Symbol, notice.TracingNo)
	}

	isAudited := strings.Contains(notice.Title, "حسابرسی شده") && !strings.Contains(notice.Title, "حسابرسی نشده")
	isConsolidated := strings.Contains(notice.Title, "تلفیقی") && !strings.Contains(notice.Title, "غیرتلفیقی")
	periodMonths := parsePeriodMonthsFromTitle(notice.Title)

	var detectedPeriod string
	out := make(map[string]float64)
	rank := make(map[string]int)
	refusedRank := make(map[string]int)
	unitNorm := 1.0

	// پیمایش شیت‌ها: شیت‌های سود و زیان پیش از شیت‌های ترازنامه پردازش می‌شوند
	// دقیقا مطابق با رفتار targets = [("income", ...), ("balance", ...)] در codal_fetcher.py
	var sheetKeys []string
	for k := range sheets {
		sheetKeys = append(sheetKeys, k)
	}
	sort.Slice(sheetKeys, func(i, j int) bool {
		ki, kj := strings.ToLower(sheetKeys[i]), strings.ToLower(sheetKeys[j])
		isIncI := strings.Contains(ki, "inc") || strings.Contains(ki, "سود") || ki == "1"
		isIncJ := strings.Contains(kj, "inc") || strings.Contains(kj, "سود") || kj == "1"
		if isIncI != isIncJ {
			return isIncI
		}
		return ki < kj
	})

	for _, sheetKey := range sheetKeys {
		content := sheets[sheetKey]
		tables, dsPeriod := extractTablesFromHTML(content)
		if detectedPeriod == "" && dsPeriod != "" {
			detectedPeriod = dsPeriod
		}

		for _, tbl := range tables {
			if strings.Contains(tbl.Description, "میلیون ریال") {
				unitNorm = 1000000.0
			}

			grid := tbl.Grid
			var rowKeys []int
			for r := range grid {
				rowKeys = append(rowKeys, r)
			}
			sort.Ints(rowKeys)

			for _, r := range rowKeys {
				label := normalizeLabel(grid[r][1])

				// شناسایی برچسب ستون راست در ترازنامه‌های دوبل کناری (col 3, 4, 5)
				var rlabel string
				var rcol int
				for _, c := range []int{3, 4, 5, 6} {
					val := normalizeLabel(grid[r][c])
					if val != "" {
						for key, pats := range fsCompiled {
							for idx, p := range pats {
								if matchPatternWithExclusions(key, idx, p, val) {
									rlabel = val
									rcol = c
									break
								}
							}
							if rlabel != "" {
								break
							}
						}
					}
					if rlabel != "" {
						break
					}
				}

				if label == "" && rlabel == "" {
					continue
				}

				for key, pats := range fsCompiled {
					bestRank := -1
					isSide := false

					if label != "" {
						for i, p := range pats {
							if matchPatternWithExclusions(key, i, p, label) {
								bestRank = i
								break
							}
						}
					}

					if bestRank == -1 && rlabel != "" && fsSideKeys[key] {
						for i, p := range pats {
							if matchPatternWithExclusions(key, i, p, rlabel) {
								bestRank = i
								isSide = true
								break
							}
						}
					}

					if bestRank == -1 {
						continue
					}

					currentRank, hasRank := rank[key]
					if hasRank && currentRank <= bestRank {
						continue
					}

					if refRank, refused := refusedRank["!"+key]; refused && refRank <= bestRank {
						continue
					}

					// استخراج ستون‌های عددی این سطر
					var cols []int
					for c := range grid[r] {
						cols = append(cols, c)
					}
					sort.Ints(cols)

					var valCols []int
					if isSide && rcol > 0 {
						for _, ci := range cols {
							if ci > rcol {
								valCols = append(valCols, ci)
							}
						}
					} else {
						for _, ci := range cols {
							if ci > 1 {
								if rcol > 0 && ci >= rcol {
									break
								}
								valCols = append(valCols, ci)
							}
						}
					}

					var chosenVal float64
					found := false
					for _, ci := range valCols {
						if v, ok := parseNumericValue(grid[r][ci]); ok && v != 0 {
							chosenVal = v
							found = true
							break
						}
					}

					if !found {
						if key == "revenue" {
							if hasRank && bestRank < currentRank {
								delete(out, key)
								delete(rank, key)
							}
							refusedRank["!"+key] = bestRank
						}
						continue
					}

					out[key] = chosenVal
					rank[key] = bestRank
				}
			}
		}
	}

	periodEnd := detectedPeriod
	if periodEnd == "" {
		periodEnd = parsePeriodEndFromTitle(notice.Title)
	}

	res := &FinancialStatementData{
		TracingNo:        notice.TracingNo,
		Symbol:           notice.Symbol,
		PeriodEnd:        periodEnd,
		Months:           periodMonths,
		Revenue:          out["revenue"],
		GrossProfit:      out["gross_profit"],
		OperatingProfit:  out["operating_profit"],
		NetProfit:        out["net_profit"],
		Assets:           out["total_assets"],
		Liabilities:      out["total_liabilities"],
		Equity:           out["total_equity"],
		Capital:          out["capital"],
		RetainedEarnings: out["retained_earnings"],
		EPS:              out["basic_eps"],
		IsAudited:        isAudited,
		IsConsolidated:   isConsolidated,
		UnitNorm:         unitNorm,
	}

	return res, nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
