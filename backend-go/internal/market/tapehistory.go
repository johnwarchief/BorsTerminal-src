package market

import (
	"net/http"

	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/tapehistory"
)

// TapeHistory عینِ get_tape_history درِ api/market.py: هیچ داوریِ تازه‌ای نمی‌سازد
// و همان tape_flag_day را می‌خواند که مسیرِ تابلو نوشته است. `codes` شناسۀ
// پایدار است (نه نامِ نمایشی) و `days` تقویمِ روزهایِ **رصدشده**.
//
// تفاوتِ اعلام‌شده (R7): پایتون پیش از خواندن `tape_flag_history.ensure(conn)`
// را می‌زند و جدولِ نبود را می‌سازد؛ این مسیرِ خواندن چیزی نمی‌سازد و همان
// پاسخِ خالی را بی‌ساختنِ جدول می‌دهد. بدنه یکی است، اثرِ جانبی نه.
// تصحیحِ دورِ بازبینی: جملهٔ «فاز A هرگز user.db را نمی‌نویسد» درست نبود —
// مسیرِ تابلو از همان B1 تاریخچۀ نوار را با Recorder درِ user.db می‌نویسد
// (`service.go:301`)؛ ادعایِ درست و محدودتر همین است که *این* مسیر نمی‌نویسد
// و market.db درِ `db.Open` فقط‌خواندنی است.
func (s *Service) TapeHistory(w http.ResponseWriter, r *http.Request) {
	days, ok := httpapi.IntQuery(w, r, "days", 20)
	if !ok {
		return
	}
	// `codes` هم مثلِ `days` آخرین تکرار را می‌گیرد (قراردادِ starlette).
	codes := tapehistory.ParseCodes(httpapi.StringQuery(r, "codes", ""))
	body := tapehistory.NewReader(s.user, s.recorder.LastErr).
		HistoryFor(r.Context(), codes, tapehistory.ClampDays(days))
	body["status"] = "success"
	// عینِ _ORJ_JSON درِ این مسیر: پاسخِ تاریخچه هرگز کش نمی‌شود.
	w.Header().Set("Cache-Control", "no-store")
	httpapi.WriteJSON(w, http.StatusOK, body)
}
