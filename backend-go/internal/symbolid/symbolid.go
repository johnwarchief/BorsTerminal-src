// Package symbolid پورتِ symbol_identity.py: تنها تعریفِ «این ردیف مالِ کدام ابزار است».
//
// قرارداد: کلیدِ هویت = یکسان‌سازی ي/ك/ى ← فارسی + حذفِ همهٔ جداسازها و
// فاصله؛ نامزدهای خام از خودِ بانک خوانده می‌شوند (نه جایگشتِ ورودی)؛ و
// پسوندِ رقمیِ خطِ تابلو فقط در دامنهٔ کدال و با گیتِ ISIN باز می‌شود.
//
// کش: پایتون هر اتصال را با (PRAGMA data_version، total_changes) اعتبارسنجی
// می‌کند. Go رویِ market.db نمی‌نویسد، پس data_versionِ یک اتصالِ اختصاصی
// کافی است: نوشتنِ هر اتصالِ دیگر (سینکِ پایتون، حلقهٔ بعدی) آن را تکان می‌دهد.
package symbolid

import (
	"context"
	"database/sql"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"unicode"
)

type Domain string

const (
	Codal Domain = "codal"
	Board Domain = "board"
)

const maxVariants = 48

type source struct{ table, col string }

var domainSources = map[Domain][]source{
	Codal: {{"financial_statements", "symbol"}, {"monthly_sales", "symbol"},
		{"codal_notices", "symbol"}},
	Board: {{"instruments", "l_val18"}, {"price_history", "symbol"},
		{"user_watchlists", "symbol"}},
}

var (
	normReplacer = strings.NewReplacer("\u064a", "\u06cc", "\u0643", "\u06a9",
		"\u0649", "\u06cc")
	sepRe = regexp.MustCompile("[ \u00a0\u200c\u200f\u200e\u202f]+")
)

// Norm فقط عربی←فارسی؛ فاصله‌ها دست‌نخورده (مثلِ symbol_identity.norm).
func Norm(s string) string { return normReplacer.Replace(s) }

// Key کلیدِ هویت؛ رشتهٔ خالی یعنی «هویت نداریم».
func Key(s string) string { return strings.ToLower(sepRe.ReplaceAllString(Norm(s), "")) }

type slot struct {
	byKey      map[string][]string
	byKeyBoard map[string][]string
	isin       map[string]map[string]struct{}
}

func newSlot() *slot {
	return &slot{byKey: map[string][]string{}, byKeyBoard: map[string][]string{},
		isin: map[string]map[string]struct{}{}}
}

// Resolver نقشهٔ هویت را رویِ یک اتصالِ اختصاصی می‌کشد و با data_version تازه می‌کند.
type Resolver struct {
	db    *sql.DB
	mu    sync.Mutex
	conn  *sql.Conn
	dv    int64
	built bool
	s     *slot
}

func New(db *sql.DB) *Resolver { return &Resolver{db: db} }

func (r *Resolver) Close() error {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.conn != nil {
		err := r.conn.Close()
		r.conn = nil
		r.built = false
		return err
	}
	return nil
}

func (r *Resolver) slotFor(ctx context.Context) (*slot, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.conn == nil {
		c, err := r.db.Conn(ctx)
		if err != nil {
			return nil, err
		}
		r.conn = c
	}
	var dv int64
	if err := r.conn.QueryRowContext(ctx, "PRAGMA data_version").Scan(&dv); err != nil {
		dv = -1
	}
	if r.built && r.dv == dv {
		return r.s, nil
	}
	s, err := build(ctx, r.conn)
	if err != nil {
		return nil, err
	}
	r.s, r.dv, r.built = s, dv, true
	return s, nil
}

func build(ctx context.Context, conn *sql.Conn) (*slot, error) {
	s := newSlot()
	for _, dom := range []Domain{Codal, Board} {
		for _, src := range domainSources[dom] {
			if !hasColumn(ctx, conn, src.table, src.col) {
				continue
			}
			rows, err := conn.QueryContext(ctx,
				fmt.Sprintf("SELECT DISTINCT %s FROM %s", src.col, src.table))
			if err != nil {
				continue
			}
			target := s.byKey
			if dom == Board {
				target = s.byKeyBoard
			}
			for rows.Next() {
				var raw sql.NullString
				if err := rows.Scan(&raw); err != nil || !raw.Valid {
					continue
				}
				k := Key(raw.String)
				if k == "" {
					continue
				}
				lst := target[k]
				if !containsStr(lst, raw.String) && len(lst) < maxVariants {
					target[k] = append(lst, raw.String)
				}
			}
			rows.Close()
		}
	}
	rows, err := conn.QueryContext(ctx, "SELECT l_val18, isin FROM instruments")
	if err == nil {
		for rows.Next() {
			var sym, isin sql.NullString
			if err := rows.Scan(&sym, &isin); err != nil || !sym.Valid {
				continue
			}
			k := Key(sym.String)
			if k == "" {
				continue
			}
			seg := strings.ToUpper(strings.TrimSpace(isin.String))
			if strings.HasPrefix(seg, "IR") && len(seg) >= 9 {
				set := s.isin[k]
				if set == nil {
					set = map[string]struct{}{}
					s.isin[k] = set
				}
				set[seg[:9]] = struct{}{}
			}
		}
		rows.Close()
	}
	return s, nil
}

func hasColumn(ctx context.Context, conn *sql.Conn, table, col string) bool {
	rows, err := conn.QueryContext(ctx, fmt.Sprintf("PRAGMA table_info(%s)", table))
	if err != nil {
		return false
	}
	defer rows.Close()
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt sql.NullString
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err != nil {
			return false
		}
		if name == col {
			return true
		}
	}
	return false
}

func containsStr(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

// Variants هر نوشتارِ خامی زیرِ همان کلید؛ خودِ ورودی همیشه هست.
func (r *Resolver) Variants(ctx context.Context, symbol string, domain Domain) ([]string, error) {
	k := Key(symbol)
	if k == "" {
		return nil, nil
	}
	s, err := r.slotFor(ctx)
	if err != nil {
		return nil, err
	}
	src := s.byKeyBoard
	if domain == Codal {
		src = s.byKey
	}
	out := append([]string(nil), src[k]...)
	if symbol != "" && !containsStr(out, symbol) {
		out = append([]string{symbol}, out...)
	}
	if len(out) > maxVariants {
		out = out[:maxVariants]
	}
	return out, nil
}

func trailingDigit(k string) (bool, string) {
	rs := []rune(k)
	if len(rs) < 2 || !unicode.IsDigit(rs[len(rs)-1]) || unicode.IsDigit(rs[len(rs)-2]) {
		return false, k
	}
	return true, string(rs[:len(rs)-1])
}

func (r *Resolver) hasCodalRows(ctx context.Context, conn *sql.Conn, s *slot, k string) bool {
	for _, raw := range s.byKey[k] {
		for _, t := range []string{"financial_statements", "monthly_sales"} {
			var one int
			err := conn.QueryRowContext(ctx,
				fmt.Sprintf("SELECT 1 FROM %s WHERE symbol=? LIMIT 1", t), raw).Scan(&one)
			if err == nil {
				return true
			}
		}
	}
	return false
}

// LineVariants (نامزدها، evidence) برایِ خط‌هایِ رقمیِ تابلو مثلِ «آباد3».
func (r *Resolver) LineVariants(ctx context.Context, symbol string, domain Domain) ([]string, string, error) {
	if domain != Codal {
		return nil, "exact", nil // درِ جهانِ تابلو پسوندِ رقمی هویتِ ابزار است
	}
	k := Key(symbol)
	if len([]rune(k)) < 3 {
		return nil, "exact", nil
	}
	ok, base := trailingDigit(k)
	if !ok || base == "" || base == k {
		return nil, "exact", nil
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.conn == nil {
		c, err := r.db.Conn(ctx)
		if err != nil {
			return nil, "exact", err
		}
		r.conn = c
	}
	if err := r.refreshLocked(ctx); err != nil {
		return nil, "exact", err
	}
	s := r.s
	if !r.hasCodalRows(ctx, r.conn, s, base) {
		return nil, "exact", nil
	}
	mine := s.isin[k]
	theirs := map[string]struct{}{}
	for seg := range s.isin[base] {
		theirs[seg] = struct{}{}
	}
	for kk, segs := range s.isin {
		if kk == base || kk == k {
			continue
		}
		if okk, b := trailingDigit(kk); okk && b == base {
			for seg := range segs {
				theirs[seg] = struct{}{}
			}
		}
	}
	if len(theirs) > 1 {
		return nil, "isin-clash", nil
	}
	if len(mine) > 0 && len(theirs) > 0 && !intersects(mine, theirs) {
		return nil, "isin-clash", nil
	}
	ev := "no-isin"
	if len(mine) > 0 && len(theirs) > 0 {
		ev = "isin-agree"
	}
	var raws []string
	for _, raw := range s.byKey[base] {
		if Key(raw) == base {
			raws = append(raws, raw)
		}
	}
	return raws, ev, nil
}

func intersects(a, b map[string]struct{}) bool {
	for x := range a {
		if _, ok := b[x]; ok {
			return true
		}
	}
	return false
}

// refreshLocked نقشه را اگر data_version عوض شده بازمی‌سازد (قفل باید گرفته باشد).
func (r *Resolver) refreshLocked(ctx context.Context) error {
	var dv int64
	if err := r.conn.QueryRowContext(ctx, "PRAGMA data_version").Scan(&dv); err != nil {
		dv = -1
	}
	if r.built && r.dv == dv {
		return nil
	}
	s, err := build(ctx, r.conn)
	if err != nil {
		return err
	}
	r.s, r.dv, r.built = s, dv, true
	return nil
}

// ClassSiblings خط‌هایِ «کلاس»ِ همان نامِ پایه در تابلو.
func (r *Resolver) ClassSiblings(ctx context.Context, symbol string) ([]string, string, error) {
	k := Key(symbol)
	if k == "" {
		return nil, "unmatched", nil
	}
	s, err := r.slotFor(ctx)
	if err != nil {
		return nil, "unmatched", err
	}
	cands := map[string]struct{}{}
	for kk, raws := range s.byKeyBoard {
		if ok, base := trailingDigit(kk); ok && kk != k && base == k {
			for _, raw := range raws {
				cands[raw] = struct{}{}
			}
		}
	}
	if len(s.byKeyBoard[k]) > 0 {
		return nil, "same-key", nil
	}
	if len(cands) == 0 {
		return nil, "unmatched", nil
	}
	if len(cands) > 1 {
		return nil, "ambiguous", nil
	}
	for raw := range cands {
		return []string{raw}, "no-isin", nil
	}
	return nil, "unmatched", nil
}

// Evidence چگونه به ردیف‌ها رسیدیم (پیش‌فرضِ دامنهٔ تابلو).
func (r *Resolver) Evidence(ctx context.Context, symbol string, domain Domain) (string, error) {
	k := Key(symbol)
	if k == "" {
		return "unmatched", nil
	}
	s, err := r.slotFor(ctx)
	if err != nil {
		return "unmatched", err
	}
	mp := s.byKeyBoard
	if domain == Codal {
		mp = s.byKey
	}
	if len(mp[k]) > 0 {
		return "same-key", nil
	}
	extra, ev, err := r.LineVariants(ctx, symbol, domain)
	if err != nil {
		return "unmatched", err
	}
	if len(extra) > 0 {
		return ev, nil
	}
	if ev == "isin-clash" {
		return ev, nil
	}
	return "unmatched", nil
}

// Pred (شرحِ SQL، پارامترها): col IN (?,…)، یا 1=0 برایِ نمادِ بی‌هویت.
func (r *Resolver) Pred(ctx context.Context, col, symbol string, domain Domain) (string, []any, error) {
	al, err := r.Variants(ctx, symbol, domain)
	if err != nil {
		return "", nil, err
	}
	extra, _, err := r.LineVariants(ctx, symbol, domain)
	if err != nil {
		return "", nil, err
	}
	for _, x := range extra {
		if !containsStr(al, x) {
			al = append(al, x)
		}
	}
	if len(al) == 0 {
		return "1=0", nil, nil
	}
	params := make([]any, len(al))
	for i, x := range al {
		params[i] = x
	}
	return fmt.Sprintf("%s IN (%s)", col, strings.TrimSuffix(strings.Repeat("?,", len(al)), ",")),
		params, nil
}
