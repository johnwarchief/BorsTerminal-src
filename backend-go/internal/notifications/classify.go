package notifications

import (
	"regexp"
	"strings"
)

const (
	Source      = "codal"
	SourceLabel = "کدال (سازمانِ بورس)"

	LevelHigh        = "high"
	LevelMedium      = "medium"
	LevelLow         = "low"
	LevelUnclassfied = "unclassified"
)

type kindRule struct {
	kind   string
	reason string
	level  string
	re     *regexp.Regexp
}

var kindRules = []kindRule{
	{
		kind:   "statements",
		reason: "صورتهایِ مالیِ دوره (ورودیِ EPS/حاشیه/رشدِ پنج‌شاخصه)",
		level:  LevelHigh,
		re:     regexp.MustCompile(`(?i)صورته?ا?ی مالی|صورتهایِ مالی|صورت\x{200c}های مالی|صورت\x{200f}مسئولیت`),
	},
	{
		kind:   "assembly",
		reason: "مجمعِ عمومی (وتویِ زمان‌بندیِ ورود درِ قیف)",
		level:  LevelHigh,
		re:     regexp.MustCompile(`(?i)آگهی دعوت|اعلانیه? دعوت|برگزاری مجمع|دعوت به مجمع|زمان\s*مجمع`),
	},
	{
		kind:   "capital",
		reason: "افزایشِ سرمایه (مبنایِ سهم و ارزشِ بازار)",
		level:  LevelHigh,
		re:     regexp.MustCompile(`(?i)افزایش\s*سرمایه`),
	},
	{
		kind:   "dividend",
		reason: "تقسیمِ سود / سودِ نقدی (مبنایِ قیمت)",
		level:  LevelHigh,
		re:     regexp.MustCompile(`(?i)تقسیم\s*سود|سود\s*نقدی|تقسیم\s*مبلغ`),
	},
	{
		kind:   "ipo",
		reason: "عرضهٔ اولیه / پذیرش",
		level:  LevelHigh,
		re:     regexp.MustCompile(`(?i)عرضه\s*اولیه|پذیرش\s*نظر|پذیرش\s*شده`),
	},
	{
		kind:   "maturity",
		reason: "سررسیدِ اوراق/صکوک",
		level:  LevelHigh,
		re:     regexp.MustCompile(`(?i)سررسید|اخزا|صکوک|اوراق`),
	},
	{
		kind:   "monthly",
		reason: "گزارشِ فعالیتِ ماهانه (مبنایِ رشدِ فروشِ ۱۲ماهه)",
		level:  LevelMedium,
		re:     regexp.MustCompile(`(?i)گزارش\s*فعالیت|فعالیت\s*ماهانه`),
	},
	{
		kind:   "production",
		reason: "گزارشِ تولیدِ هفته/ماه (کمکیِ همان محورِ فروش)",
		level:  LevelMedium,
		re:     regexp.MustCompile(`(?i)گزارش\s*تولید|تولید\s*ماهانه|تولید\s*هفتگی`),
	},
	{
		kind:   "governance",
		reason: "مدیریت/حاکمیت — افشا، خبری از پنج محور نیست",
		level:  LevelLow,
		re:     regexp.MustCompile(`(?i)هیئت\s*مدیره|مدیر\s*عامل|سرمایه\s*گذار|انتشار|اصلاحیه|لغو|به\s*تعویق`),
	},
}

var normTitleRepl = strings.NewReplacer(
	"\u200c", " ",
	"\u064a", "\u06cc",
	"\u0643", "\u06a9",
)

var whitespaceRe = regexp.MustCompile(`\s+`)

func NormTitle(title string) string {
	t := normTitleRepl.Replace(title)
	t = whitespaceRe.ReplaceAllString(t, " ")
	return strings.ToLower(strings.TrimSpace(t))
}

type Classification struct {
	Kind       string  `json:"kind"`
	Level      string  `json:"level"`
	Reason     string  `json:"reason"`
	LetterCode *string `json:"letter_code"`
}

func Classify(title, letterCode string) Classification {
	var letter *string
	if lc := strings.TrimSpace(letterCode); lc != "" {
		letter = &lc
	}

	t := title
	for _, rule := range kindRules {
		if rule.re.MatchString(t) {
			return Classification{
				Kind:       rule.kind,
				Level:      rule.level,
				Reason:     rule.reason,
				LetterCode: letter,
			}
		}
	}

	return Classification{
		Kind:  "other",
		Level: LevelUnclassfied,
		Reason: "هیچ‌کدام از داورهایِ موجودِ برنامه این عنوان را نشناخت؛ " +
			"این «کم‌اهمیت» نیست، «بی‌طبقه» است.",
		LetterCode: letter,
	}
}

func DedupeKey(symbol, title, publishDate string) string {
	sym := strings.TrimSpace(symbol)
	normT := NormTitle(title)
	pub := strings.TrimSpace(publishDate)
	if len(pub) > 10 {
		pub = pub[:10]
	}
	return sym + "|" + normT + "|" + pub
}
