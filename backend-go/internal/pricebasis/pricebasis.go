// Package pricebasis پورتِ price_basis.py: تنها نقطهٔ انتخابِ ستونِ قیمت.
//
// سه قاعدهٔ قرارداد (docs/CANDLE-CONTRACT.md §۱-ث):
//  1. close هر کندل == ستونِ منتخبِ کاربر؛ هیچ مصرف‌کننده‌ای خودش انتخاب نمی‌کند.
//  2. لنگرِ زنجیرِ تعدیل همیشه closing است و به setting ربطی ندارد.
//  3. اگر ستونِ منتخب در سری نبود، سری صریح به closing می‌رود و دلیلش اعلام
//     می‌شود — یک سری هرگز دو مبنا قاطی نمی‌کند.
package pricebasis

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"sync"
)

const (
	Last    = "last"
	Closing = "closing"
	Default = Last
)

var Allowed = []string{Last, Closing}

// Resolver فایلِ price_basis.json را با امضایِ (mtime,size) کش می‌کند؛ تغییرِ
// فایل در درخواستِ بعدی اثر می‌کند، مثلِ _cacheِ پایتون.
type Resolver struct {
	path string
	mu   sync.Mutex
	sig  string
	val  string
}

func New(path string) *Resolver { return &Resolver{path: path, val: Default} }

func (r *Resolver) Current() string {
	st, err := os.Stat(r.path)
	if err != nil {
		return Default
	}
	sig := fmt.Sprintf("%s|%d|%d", r.path, st.ModTime().UnixNano(), st.Size())
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.sig == sig {
		return r.val
	}
	raw, err := os.ReadFile(r.path)
	if err != nil {
		return Default
	}
	var anyV any
	if err := json.Unmarshal(raw, &anyV); err != nil {
		return Default
	}
	val, _ := anyV.(string)
	if m, ok := anyV.(map[string]any); ok {
		val, _ = m["basis"].(string)
	}
	if val != Last && val != Closing {
		val = Default
	}
	r.sig, r.val = sig, val
	return val
}

// Num معادلِ _num: عددِ مثبتِ متناهی، وگرنه nil. رشته هم پذیرفته می‌شود.
func Num(v any) *float64 {
	switch x := v.(type) {
	case nil:
		return nil
	case float64:
		if x > 0 {
			return &x
		}
	case float32:
		f := float64(x)
		if f > 0 {
			return &f
		}
	case int:
		f := float64(x)
		if f > 0 {
			return &f
		}
	case int64:
		f := float64(x)
		if f > 0 {
			return &f
		}
	case json.Number:
		if f, err := x.Float64(); err == nil && f > 0 {
			return &f
		}
	case string:
		if f, err := strconv.ParseFloat(x, 64); err == nil && f > 0 {
			return &f
		}
	case bool:
		f := 0.0
		if x {
			f = 1
		}
		if f > 0 {
			return &f
		}
	}
	return nil
}

func numKey(c map[string]any, keys ...string) *float64 {
	for _, k := range keys {
		if v, ok := c[k]; ok {
			if n := Num(v); n != nil {
				return n
			}
			return nil // کلید هست ولی عددِ مثبت نیست ⇒ fallback نداریم (get با default)
		}
	}
	return nil
}

func ClosingOf(c map[string]any) *float64 {
	if n := numKey(c, "closing", "close_raw"); n != nil {
		return n
	}
	return Num(c["close"])
}

func LastOf(c map[string]any) *float64 { return Num(c["last"]) }

func CloseOf(c map[string]any, basis string) float64 {
	if basis == "" {
		basis = Default
	}
	if basis == Last {
		if v := LastOf(c); v != nil {
			return *v
		}
	}
	if v := ClosingOf(c); v != nil {
		return *v
	}
	return 0
}

func BasisOfRow(c map[string]any, basis string) string {
	if basis == "" {
		basis = Default
	}
	if basis != Last || LastOf(c) != nil {
		return basis
	}
	return Closing
}

// Meta همان dictِ برگشتیِ apply_basis است.
type Meta struct {
	BasisRequested  string
	BasisApplied    string
	BasisReason     string
	LastMissing     int
	Count           int
	GeometryWidened int
}

func putNum(c map[string]any, key string, v *float64) {
	if v == nil {
		c[key] = nil
		return
	}
	c[key] = *v
}

// ApplyBasis سری را به (closing, last, close) واحد تبدیل می‌کند. با copySeries
// رویِ نسخه‌ها کار می‌کند و نسخه‌ها را برمی‌گرداند (کش‌ها همیشه خام می‌مانند).
func ApplyBasis(candles []map[string]any, copySeries bool, requested string) (Meta, []map[string]any) {
	if requested == "" {
		requested = Default
	}
	out := candles
	if copySeries {
		out = make([]map[string]any, len(candles))
		for i, c := range candles {
			cp := make(map[string]any, len(c)+4)
			for k, v := range c {
				cp[k] = v
			}
			out[i] = cp
		}
	}
	n := len(out)
	missing := 0
	for _, c := range out {
		if LastOf(c) == nil {
			missing++
		}
	}
	applied := requested
	reason := ""
	if requested == Last && missing > 0 {
		applied = Closing
		reason = fmt.Sprintf("last_missing:%d/%d", missing, n)
	}
	widened := 0
	for _, c := range out {
		anchor := ClosingOf(c)
		putNum(c, "closing", anchor)
		var chosen *float64
		if applied == Last {
			chosen = LastOf(c)
		}
		if chosen == nil {
			chosen = anchor
		}
		putNum(c, "close", chosen)
		hi := numKey(c, "high_raw", "high")
		lo := numKey(c, "low_raw", "low")
		op := Num(c["open"])
		if hi != nil && lo != nil && chosen != nil {
			hiRaw, loRaw := *hi, *lo
			putNum(c, "high_raw", hi)
			putNum(c, "low_raw", lo)
			nh, nl := hiRaw, loRaw
			if loRaw > nh {
				nh = loRaw
			}
			if *chosen > nh {
				nh = *chosen
			}
			if loRaw < nl {
				nl = loRaw
			}
			if *chosen < nl {
				nl = *chosen
			}
			if op != nil {
				if *op > nh {
					nh = *op
				}
				if *op < nl {
					nl = *op
				}
			}
			if nh != hiRaw || nl != loRaw {
				widened++
			}
			c["high"], c["low"] = nh, nl
		}
	}
	for _, c := range out {
		c["basis"] = applied
	}
	return Meta{BasisRequested: requested, BasisApplied: applied, BasisReason: reason,
		LastMissing: missing, Count: n, GeometryWidened: widened}, out
}

// ResolvePayload پایانِ هر سری‌دهنده: apply_basis رویِ نسخه‌ها، رنگِ حجم از
// سریِ خام، و متادیتایِ مبنا رویِ پاسخ.
func ResolvePayload(res map[string]any, key string, colors [2]string, requested string) map[string]any {
	cands, _ := res[key].([]map[string]any)
	if len(cands) == 0 {
		return res
	}
	meta, applied := ApplyBasis(cands, true, requested)
	out := make(map[string]any, len(res)+4)
	for k, v := range res {
		out[k] = v
	}
	out[key] = applied
	if vols, ok := res["volumes"].([]map[string]any); ok && len(vols) > 0 {
		byTime := make(map[string]map[string]any, len(cands))
		for _, c := range cands {
			byTime[candleKey(c)] = c
		}
		fixed := make([]map[string]any, len(vols))
		for i, v := range vols {
			vv := make(map[string]any, len(v)+1)
			for k, x := range v {
				vv[k] = x
			}
			if c := byTime[candleKey(vv)]; c != nil {
				o, cl := Num(c["open"]), Num(c["close"])
				if o != nil && cl != nil {
					if *cl >= *o {
						vv["color"] = colors[0]
					} else {
						vv["color"] = colors[1]
					}
				}
			}
			fixed[i] = vv
		}
		out["volumes"] = fixed
	}
	return Stamp(out, meta)
}

func candleKey(c map[string]any) string {
	if s, ok := c["time"].(string); ok && s != "" {
		return s
	}
	if s, ok := c["date"].(string); ok {
		return s
	}
	return ""
}

// Stamp متادیتایِ مبنا را رویِ پاسخ می‌گذارد.
func Stamp(payload map[string]any, meta Meta) map[string]any {
	payload["priceBasis"] = meta.BasisApplied
	payload["priceBasisRequested"] = meta.BasisRequested
	if meta.BasisReason != "" {
		payload["priceBasisReason"] = meta.BasisReason
	}
	payload["priceBasisLastMissing"] = meta.LastMissing
	return payload
}
