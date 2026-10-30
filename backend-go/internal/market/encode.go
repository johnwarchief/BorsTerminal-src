package market

import (
	"encoding/json"
	"math"
	"runtime"
	"sort"
	"strconv"
	"sync"
	"unicode/utf8"
)

// boardEncoder همان بدنۀ تابلو را سریال می‌کند، ولی بی بازتابِ encoding/json.
//
// چرا: بدنهٔ `?fields=all` حدود ۸.۷ مگابایت و ۶٬۰۰۰ ردیفِ ۱۳۰ کلیدی است؛
// encoding/json برایِ هر ردیف کلیدها را با reflect می‌شمارد و مرتب می‌کند و
// ۱۲۰ میلی‌ثانیه از ۱۷۶ میلی‌ثانیهٔ بازسازیِ Go را می‌خورد. قراردادِ خروجی
// عینِ json.Marshal است: کلیدهایِ map مرتب (تا etag پایدار بماند)، رشته با
// همان گریزهایِ HTML، و عدد با همان قاعدهٔ 'f'/'e'ِ encoding/json. هر مقداری
// که این‌جا نوعش شناخته نشود به json.Marshal برمی‌گردد؛ پس نبودِ پوشش یعنی
// «کندتر»، نه «خروجیِ ناقص».
type boardEncoder struct {
	buf []byte
	err error
}

func marshalBoard(payload map[string]any) ([]byte, error) {
	e := &boardEncoder{buf: make([]byte, 0, 1<<20)}
	e.value(payload)
	if e.err != nil {
		return nil, e.err
	}
	return e.buf, nil
}

func (e *boardEncoder) value(v any) {
	if e.err != nil {
		return
	}
	switch x := v.(type) {
	case nil:
		e.buf = append(e.buf, "null"...)
	case bool:
		if x {
			e.buf = append(e.buf, "true"...)
		} else {
			e.buf = append(e.buf, "false"...)
		}
	case int:
		e.buf = strconv.AppendInt(e.buf, int64(x), 10)
	case int64:
		e.buf = strconv.AppendInt(e.buf, x, 10)
	case float64:
		e.float(x)
	case string:
		e.str(x)
	case map[string]any:
		e.object(x)
	case []map[string]any:
		e.rows(x)
	case []any:
		e.array(x)
	default:
		e.fallback(v)
	}
}

func (e *boardEncoder) fallback(v any) {
	raw, err := json.Marshal(v)
	if err != nil {
		e.err = err
		return
	}
	e.buf = append(e.buf, raw...)
}

func (e *boardEncoder) object(m map[string]any) {
	// کلیدها برایِ هر map جدا: این تابع بازگشتی است و یک برشِ مشترک، کلیدهایِ
	// والد را وسطِ حلقه با mapِ تودرتو (مثلِ meta) بازنویسی می‌کرد.
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	e.buf = append(e.buf, '{')
	for i, k := range keys {
		if i > 0 {
			e.buf = append(e.buf, ',')
		}
		e.str(k)
		e.buf = append(e.buf, ':')
		e.value(m[k])
		if e.err != nil {
			return
		}
	}
	e.buf = append(e.buf, '}')
}

func (e *boardEncoder) rows(list []map[string]any) {
	order, quotedKeys := rowKeys(list)
	workers := workerCount(len(list))
	if workers <= 1 {
		// ظرفیتِ یک‌باره: بدنهٔ هر ردیف ~۱.۴ کیلوبایت است و رشدِ تدریجیِ برش
		// (۱MB→۲→۴→۸→۱۶) چند ده مگابایت کپی می‌کرد.
		e.reserve(len(list) * 1500)
		e.buf = append(e.buf, '[')
		e.rowsRange(list, order, quotedKeys)
		e.buf = append(e.buf, ']')
		return
	}
	// تکه‌هایِ مستقل موازی پر می‌شوند و به ترتیب به هم می‌چسبند؛ پس بایت‌هایِ
	// خروجی عینِ مسیرِ ترتیبی است و etag تکان نمی‌خورد.
	chunk := (len(list) + workers - 1) / workers
	parts := make([][]byte, 0, workers)
	errs := make([]error, 0, workers)
	var wg sync.WaitGroup
	for start := 0; start < len(list); start += chunk {
		end := start + chunk
		if end > len(list) {
			end = len(list)
		}
		idx := len(parts)
		parts = append(parts, nil)
		errs = append(errs, nil)
		wg.Add(1)
		go func(start, end, idx int) {
			defer wg.Done()
			sub := &boardEncoder{buf: make([]byte, 0, (end-start)*1500)}
			sub.rowsRange(list[start:end], order, quotedKeys)
			parts[idx], errs[idx] = sub.buf, sub.err
		}(start, end, idx)
	}
	wg.Wait()
	total := 0
	for i, part := range parts {
		if errs[i] != nil {
			e.err = errs[i]
			return
		}
		total += len(part)
	}
	e.reserve(total + 2)
	e.buf = append(e.buf, '[')
	for i, part := range parts {
		if i > 0 {
			e.buf = append(e.buf, ',')
		}
		e.buf = append(e.buf, part...)
	}
	e.buf = append(e.buf, ']')
}

// reserve ظرفیتِ لازم را یک‌بار می‌گیرد؛ هیچ بایتی تغییر نمی‌کند.
func (e *boardEncoder) reserve(extra int) {
	if cap(e.buf)-len(e.buf) >= extra {
		return
	}
	grown := make([]byte, len(e.buf), len(e.buf)+extra)
	copy(grown, e.buf)
	e.buf = grown
}

// rowsRange ردیف‌ها را بی قلاب‌هایِ براکت می‌نویسد تا هم مسیرِ ترتیبی و هم
// تکه‌هایِ موازیِ آن یک بدنه بسازند.
func (e *boardEncoder) rowsRange(list []map[string]any, order []string, quotedKeys [][]byte) {
	for i, rec := range list {
		if i > 0 {
			e.buf = append(e.buf, ',')
		}
		e.oneRow(rec, order, quotedKeys)
		if e.err != nil {
			return
		}
	}
}

func (e *boardEncoder) oneRow(rec map[string]any, order []string, quotedKeys [][]byte) {
	e.buf = append(e.buf, '{')
	first := true
	for j, k := range order {
		v, ok := rec[k]
		if !ok {
			continue
		}
		if !first {
			e.buf = append(e.buf, ',')
		}
		first = false
		e.buf = append(e.buf, quotedKeys[j]...)
		e.buf = append(e.buf, ':')
		e.value(v)
		if e.err != nil {
			return
		}
	}
	e.buf = append(e.buf, '}')
}

// workerCount تعدادِ تکه‌هایِ موازی را می‌گوید: رویِ دستهٔ کوچک (گلدن/تست)
// هیچ رشته‌ای باز نمی‌شود و خروجی همان مسیرِ ترتیبی است.
func workerCount(n int) int {
	if n < 1500 {
		return 1
	}
	w := runtime.GOMAXPROCS(0)
	if w > 8 {
		w = 8
	}
	if w < 1 {
		return 1
	}
	return w
}

// rowKeys اجتماعِ کلیدهایِ دسته را یک‌بار مرتب و گریز می‌کند. مرتب‌کردنِ ~۱۳۰
// کلید در هر ردیف ۶٬۰۰۰ بار هزینه داشت؛ این‌جا هر ردیف فقط کلیدهایِ موجودش را
// با همین ترتیبِ پایدار می‌نویسد، پس هیچ کلیدی گم نمی‌شود و etag ثابت می‌ماند.
func rowKeys(list []map[string]any) ([]string, [][]byte) {
	seen := make(map[string]struct{}, 160)
	for _, rec := range list {
		for k := range rec {
			seen[k] = struct{}{}
		}
	}
	order := make([]string, 0, len(seen))
	for k := range seen {
		order = append(order, k)
	}
	sort.Strings(order)
	quotedKeys := make([][]byte, len(order))
	for i, k := range order {
		quotedKeys[i] = quotedKey(k)
	}
	return order, quotedKeys
}

// quotedKey همان گریزِ str را یک‌بار برایِ نامِ کلید می‌سازد؛ json.Marshal رویِ
// رشته هرگز خطا نمی‌دهد.
func quotedKey(k string) []byte {
	if fastStringOK(k) {
		b := make([]byte, 0, len(k)+2)
		b = append(b, '"')
		b = append(b, k...)
		b = append(b, '"')
		return b
	}
	raw, _ := json.Marshal(k)
	return raw
}

func (e *boardEncoder) array(list []any) {
	e.buf = append(e.buf, '[')
	for i, v := range list {
		if i > 0 {
			e.buf = append(e.buf, ',')
		}
		e.value(v)
		if e.err != nil {
			return
		}
	}
	e.buf = append(e.buf, ']')
}

// float عینِ floatEncoderِ encoding/json: 'f' تا وقتی عدد در [1e-6, 1e21) است،
// وگرنه 'e' با همان حذفِ صفرِ پیشروِ توان (e-09 → e-9). NaN/Inf مثلِ
// encoding/json خطاست، نه null.
func (e *boardEncoder) float(f float64) {
	if math.IsNaN(f) || math.IsInf(f, 0) {
		e.err = &json.UnsupportedValueError{Str: strconv.FormatFloat(f, 'g', -1, 64)}
		return
	}
	abs := math.Abs(f)
	format := byte('f')
	if abs != 0 && (abs < 1e-6 || abs >= 1e21) {
		format = 'e'
	}
	e.buf = strconv.AppendFloat(e.buf, f, format, -1, 64)
	if format == 'e' {
		// clean up e-09 to e-9
		n := len(e.buf)
		if n >= 4 && e.buf[n-4] == 'e' && e.buf[n-3] == '-' && e.buf[n-2] == '0' {
			e.buf[n-2] = e.buf[n-1]
			e.buf = e.buf[:n-1]
		}
	}
}

// str رشته را بی json.Marshal می‌نویسد اگر هیچ بایتی گریز لازم نداشته باشد
// (رشته‌هایِ UTF-8ِ معتبر، از جمله فارسی)؛ وگرنه همان json.Marshal تا گریزِ
// کنترلی/HTML و UTF-8ِ نامعتبر دقیقاً مثلِ قبل درست شود.
func (e *boardEncoder) str(s string) {
	if fastStringOK(s) {
		e.buf = append(e.buf, '"')
		e.buf = append(e.buf, s...)
		e.buf = append(e.buf, '"')
		return
	}
	raw, err := json.Marshal(s)
	if err != nil {
		e.err = err
		return
	}
	e.buf = append(e.buf, raw...)
}

// fastStringOK می‌گوید رشته بی هیچ گریزی قابلِ نوشتن است: بایتِ کنترلی،
// «"»، «\» و سه کاراکترِ HTMLِ encoding/json هیچ‌جا نیست، U+2028/U+2029
// (که encoding/json برایِ ایمنیِ JSONP می‌گریزد) نیست، و UTF-8 معتبر است.
func fastStringOK(s string) bool {
	ascii := true
	for i := 0; i < len(s); i++ {
		b := s[i]
		if b < 0x20 || b == '"' || b == '\\' || b == '<' || b == '>' || b == '&' {
			return false
		}
		if b >= utf8.RuneSelf {
			ascii = false
			if b == 0xE2 && i+2 < len(s) && s[i+1] == 0x80 &&
				(s[i+2] == 0xA8 || s[i+2] == 0xA9) {
				return false
			}
		}
	}
	return ascii || utf8.ValidString(s)
}
