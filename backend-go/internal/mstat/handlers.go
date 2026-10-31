package mstat

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/marketphase"
)

// qlast همان Query(...)ِ FastAPI برایِ پارامترِ تکراری: آخرین مقدار برنده است
// (?group=a&group=b ⇒ b)؛ url.Values.Get اولین را می‌داد.
func qlast(r *http.Request, name string) (string, bool) {
	vals, ok := r.URL.Query()[name]
	if !ok || len(vals) == 0 {
		return "", false
	}
	return vals[len(vals)-1], true
}

// qstr همان Query(...)ِ FastAPI: نبودِ پارامتر ⇒ default، ولی ?group= تهی
// می‌ماند (FastAPI مقدارِ تهی را با نبودن یکی نمی‌کند؛ ?group= دستهٔ ناشناخته
// است و صفر ردیف می‌دهد). مقدارِ تکراری ⇒ آخرین (qlast).
func qstr(r *http.Request, name, def string) string {
	if v, ok := qlast(r, name); ok {
		return v
	}
	return def
}

// panelKey کلیدِ کش را با طول‌پیشوندِ هر جزء می‌سازد. joinِ ساده با «|» دو تاپلِ
// متفاوت را یکسان می‌کرد (group=a&industry=b|c با group=a|b&industry=c) و
// درخواستِ دوم بدنهٔ اول را از کش می‌خورد؛ طولِ هر جزء مرز را یکتا می‌کند.
func panelKey(name string, parts ...string) string {
	var b strings.Builder
	b.WriteString(strconv.Itoa(len(name)))
	b.WriteByte(':')
	b.WriteString(name)
	for _, p := range parts {
		b.WriteByte('|')
		b.WriteString(strconv.Itoa(len(p)))
		b.WriteByte(':')
		b.WriteString(p)
	}
	return b.String()
}

// fastBool همان مجموعهٔ رشته‌ایِ Pydantic است، نه strconv.ParseBool.
// TrimSpace عمداً نیست: Pydantic «" true "» را با 422 رد می‌کند.
func fastBool(v string) (bool, bool) {
	switch strings.ToLower(v) {
	case "1", "t", "true", "y", "yes", "on":
		return true, true
	case "0", "f", "false", "n", "no", "off":
		return false, true
	}
	return false, false
}

func writePanel(w http.ResponseWriter, body map[string]any) {
	httpapi.WriteJSON(w, http.StatusOK, body)
}

// پنل‌ها یک‌بار به‌صورتِ تابعِ بدنه تعریف می‌شوند تا مسیرِ تک‌پنلی و board
// عیناً یک کلیدِ کش و یک محاسبه بگیرند (همان قانونِ _panel/_mstat_call).
func (s *Service) summaryBody() map[string]any {
	return s.Call("summary", func() (map[string]any, error) {
		return summaryPanel(s.db, s.clock())
	}, Options{StaleOK: true})
}

func (s *Service) histogramBody(group string) map[string]any {
	return s.Call(panelKey("histogram", group), func() (map[string]any, error) {
		return histogramPanel(s.db, group)
	}, Options{StaleOK: true})
}

func (s *Service) thermometerBody(group string) map[string]any {
	return s.Call(panelKey("thermometer", group), func() (map[string]any, error) {
		return thermometerPanel(s.db, group)
	}, Options{StaleOK: true})
}

func (s *Service) depthBody(group string) map[string]any {
	return s.Call(panelKey("depth", group), func() (map[string]any, error) {
		return depthPanel(s.db, group)
	}, Options{StaleOK: true})
}

func (s *Service) clientSplitBody(tab string) map[string]any {
	return s.Call(panelKey("clientsplit", tab), func() (map[string]any, error) {
		return clientSplitPanel(s.db, tab)
	}, Options{StaleOK: true})
}

func (s *Service) marketSnapshotBody() map[string]any {
	return s.Call("market-snapshot", func() (map[string]any, error) {
		return marketSnapshotPanel(s.db, s.clock())
	}, Options{StaleOK: true})
}

func (s *Service) phaseBody() map[string]any {
	// stale_ok=False: تنها فیلدی که میانِ دو ساختِ یکسانِ حالتِ بانک فرق می‌کند
	// clock_now است، پس پنلِ ارزان درِ انقضا درون‌خطی ساخته می‌شود.
	return s.Call("phase", func() (map[string]any, error) {
		return phasePanel(s.db, s.clock())
	}, Options{StaleOK: false})
}

func (s *Service) industriesBody() map[string]any {
	return s.Call("industries", func() (map[string]any, error) {
		return industriesPanel(s.db)
	}, Options{StaleOK: true})
}

func (s *Service) timelineBody(mode string) map[string]any {
	return s.Call(panelKey("timeline", mode), func() (map[string]any, error) {
		return timelinePanel(s.db, mode)
	}, Options{StaleOK: true})
}

func (s *Service) phasesBody() map[string]any {
	return s.Call("phases", func() (map[string]any, error) {
		return phasesPanel(s.db)
	}, Options{StaleOK: true})
}

func (s *Service) smartMoneyBody() map[string]any {
	return s.Call("smart-money", func() (map[string]any, error) {
		return smartMoneyPanel(s.db, s.clock(), s.memo)
	}, Options{StaleOK: true})
}

func (s *Service) Summary(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.summaryBody())
}

func (s *Service) Histogram(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.histogramBody(qstr(r, "group", "all")))
}

func (s *Service) Thermometer(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.thermometerBody(qstr(r, "group", "all")))
}

func (s *Service) Depth(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.depthBody(qstr(r, "group", "all")))
}

func (s *Service) ClientSplit(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.clientSplitBody(qstr(r, "tab", "all")))
}

func (s *Service) MarketSnapshot(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.marketSnapshotBody())
}

func (s *Service) Phase(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.phaseBody())
}

func (s *Service) SmartMoney(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.smartMoneyBody())
}

// Board همان mstat_board: ترکیبِ ده پنل از همان کش، بی‌کشِ سطحِ خودش.
// source از هر پنل حذف می‌شود (همان _panel) و فقط در سطحِ board می‌ماند.
func (s *Service) Board(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "eq_all")
	limit := 60
	if raw, ok := qlast(r, "limit"); ok {
		v, err := strconv.Atoi(raw)
		if err != nil {
			httpapi.UnprocessableAs(w, "int_parsing", []string{"query", "limit"},
				"Input should be a valid integer, unable to parse string as an integer", raw)
			return
		}
		limit = v
	}
	writePanel(w, s.boardBody(group, limit))
}

func (s *Service) boardBody(group string, limit int) map[string]any {
	panel := func(body map[string]any) map[string]any {
		delete(body, "source")
		return body
	}
	return map[string]any{
		"status": "ok", "source": mstatSource,
		"summary":     panel(s.summaryBody()),
		"thermometer": panel(s.thermometerBody(group)),
		"histogram":   panel(s.histogramBody(group)),
		"depth":       panel(s.depthBody(group)),
		"clientsplit": panel(s.clientSplitBody("all")),
		"mainwatch":   panel(s.mainwatchBody(group, "", "clock", true, limit)),
		"industries":  panel(s.industriesBody()),
		"smartmoney":  panel(s.smartMoneyBody()),
		"timeline":    panel(s.timelineBody("cum")),
		"phases":      panel(s.phasesBody()),
	}
}

func (s *Service) Mainwatch(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "eq_all")
	industry := qstr(r, "industry", "")
	sortKey := qstr(r, "sort", "clock")
	desc := true
	if raw, ok := qlast(r, "desc"); ok {
		v, ok := fastBool(raw)
		if !ok {
			httpapi.UnprocessableAs(w, "bool_parsing", []string{"query", "desc"},
				"Input should be a valid boolean, unable to interpret input", raw)
			return
		}
		desc = v
	}
	limit := 120
	if raw, ok := qlast(r, "limit"); ok {
		v, err := strconv.Atoi(raw)
		if err != nil {
			httpapi.UnprocessableAs(w, "int_parsing", []string{"query", "limit"},
				"Input should be a valid integer, unable to parse string as an integer", raw)
			return
		}
		limit = v
	}
	writePanel(w, s.mainwatchBody(group, industry, sortKey, desc, limit))
}

func (s *Service) mainwatchBody(group, industry, sortKey string, desc bool, limit int) map[string]any {
	key := panelKey("mainwatch", group, industry, sortKey,
		strconv.FormatBool(desc), strconv.FormatInt(int64(limit), 10))
	return s.Call(key, func() (map[string]any, error) {
		return mainwatchPanel(s.db, s.flags, group, industry, sortKey, desc, limit)
	}, Options{StaleOK: true})
}

func (s *Service) Industries(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.industriesBody())
}

func (s *Service) Timeline(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.timelineBody(qstr(r, "mode", "cum")))
}

func (s *Service) Phases(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.phasesBody())
}

// phasePanel همان dict(MP.from_db(conn), status="ok"). Phase خودش Status ندارد
// (پایتون هم آن را در session_phase می‌گذارد، نه در موتورِ فاز)، پس این‌جا
// می‌نشیند و تستِ مسیر تنها نگهبانِ آن است.
func phasePanel(db *sql.DB, now time.Time) (map[string]any, error) {
	ph := marketphase.FromDB(db, now)
	raw, err := json.Marshal(ph)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	out["status"] = "ok"
	return out, nil
}
