// Package datatoken نشانکِ «داده عوض شد» برایِ کش‌هایِ درون‌حافظه.
//
// هر سینکِ موفق market_sync.json را بازنویسی می‌کند، و tick_live هر ۵ ثانیه
// ردیف‌ها را در market.db (با WAL) کامیت می‌کند بی‌آنکه آن فایل را دست بزند؛
// پس فقط (mtime_ns, size)ِ market_sync.json کافی نیست و هر سه فایل باید در
// توکن باشند — همان نقشی که revision() و sync_count در پروسۀ پایتون داشتند.
// غایب ⇒ "-"، تا توکن پایدار بماند. فقط os.Stat: نه بازکردنِ SQLite، نه
// خواندنِ محتوا.
package datatoken

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// FileToken نشانکِ (mtime_ns, size)ِ سه فایلِ داده را می‌سازد.
func FileToken(dataDir string) string {
	var b strings.Builder
	for _, name := range []string{"market_sync.json", "market.db", "market.db-wal"} {
		if b.Len() > 0 {
			b.WriteByte('|')
		}
		st, err := os.Stat(filepath.Join(dataDir, name))
		if err != nil {
			b.WriteByte('-')
			continue
		}
		b.WriteString(strconv.FormatInt(st.ModTime().UnixNano(), 10))
		b.WriteByte(':')
		b.WriteString(strconv.FormatInt(st.Size(), 10))
	}
	return b.String()
}
