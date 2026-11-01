package fundamental

// داورِ لایه‌های ۴ و ۵ و دروازه‌های حذف: وکتورهای کامیت‌شده درِ
// `testdata/vectors/` (اوراکلِ پایتون روی فیکچرِ یخ‌زدۀ تسکِ ۱) + جفت‌های
// سنجیده‌شده از تابع‌های پایتون روی یک بانکِ موقتِ ساخته‌شده (برای تابع‌هایی که
// وکتور ندارند: risk_gates / industry_gate / v10_data_gaps / m141_map /
// is_suspended / avg_trade_value_hmt / pub_canon_sql).
//
// هیچ مقدارِ انتظاری این‌جا دست‌نویس نیست: رشته‌های `oracle_sNN` خروجیِ مستقیمِ
// خودِ پایتون‌اند (با \uXXXX تا رقم و «/» درِ کپی‌پیست دزدیده نشوند) و اعداد/
// بولین‌ها از JSONهایِ وکتور خوانده می‌شوند. مقایسه با `internal/parity` است:
// عدد عددی، null/false/0 سخت، آرایه ترتیب‌دار، و کلیدهایِ object دوطرفه
// (کم‌بودن و اضافی بودنِ هر دو خطاست). سقفِ تعداد درِ هر فایل سنجیده می‌شود تا
// وکتورِ بریده‌شده سبز رد نشود.

import (
	"context"
	"database/sql"
	"encoding/json"
	"os"
	"strconv"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/parity"
)

// ── متن‌هایِ سنجیده‌شده از اوراکل (api/fundamental.py و fts_engine.py) ───────
const (
	oracle_s01 = "\u0627\u0644\u0641"
	oracle_s02 = "\u0635\u0646\u062f\u0648\u0642 \u0622\u0632\u0645\u0648\u0646"
	oracle_s03 = "\u062e\u0648\u062f\u0631\u0648"
	oracle_s04 = "\u0633\u06cc\u0645\u0627\u0646"
	oracle_s05 = "\u0628\u06cc\u0645\u0647"
	oracle_s06 = "\u0628\u0627\u0632\u0646\u0634\u0633\u062a\u06af\u06cc"
	oracle_s07 = "\u0646\u0645\u0627\u062f \u062a\u0639\u0644\u06cc\u0642 \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s08 = "\u0635\u0646\u0639\u062a \u0628\u06cc\u0645\u0647 \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s09 = "\u0645\u0627\u062f\u0647 \u06f1\u06f4\u06f1 \u2014 \u0632\u06cc\u0627\u0646 \u0627\u0646\u0628\u0627\u0634\u062a\u0647 \u0628\u06cc\u0634 \u0627\u0632 \u0646\u0635\u0641 \u0633\u0631\u0645\u0627\u06cc\u0647"
	oracle_s10 = "\u0627\u0631\u0632\u0634 \u0628\u0627\u0632\u0627\u0631 (4.00 \u0647\u0645\u062a) \u0632\u06cc\u0631\u0650 \u06a9\u0641\u0650 5.00 \u0647\u0645\u062a"
	oracle_s11 = "\u0627\u0631\u0632\u0634 \u0628\u0627\u0632\u0627\u0631 (0.01 \u0647\u0645\u062a) \u0632\u06cc\u0631\u0650 \u06a9\u0641\u0650 5.00 \u0647\u0645\u062a"
	oracle_s12 = "\u0627\u0631\u0632\u0634 \u0628\u0627\u0632\u0627\u0631 \u0646\u0627\u0645\u0634\u062e\u0635 (\u06a9\u0641 \u0627\u0631\u0632\u0634 \u0628\u0627\u0632\u0627\u0631 \u0642\u0627\u0628\u0644 \u0628\u0631\u0631\u0633\u06cc \u0646\u06cc\u0633\u062a)"
	oracle_s13 = "\u0646\u0642\u062f\u0634\u0648\u0646\u062f\u06af\u06cc (0.0014 \u0647\u0645\u062a) \u0632\u06cc\u0631\u0650 \u06a9\u0641\u0650 2.0000 \u0647\u0645\u062a"
	oracle_s14 = "\u0627\u0631\u0632\u0634 \u0645\u0639\u0627\u0645\u0644\u0627\u062a \u0646\u0627\u0645\u0648\u062c\u0648\u062f (\u067e\u06cc\u0634\u200c\u0634\u0631\u0637 \u0646\u0642\u062f\u0634\u0648\u0646\u062f\u06af\u06cc \u0627\u062d\u0631\u0627\u0632 \u0646\u0634\u062f)"
	oracle_s15 = "\u0646\u0642\u062f\u0634\u0648\u0646\u062f\u06af\u06cc (0.0050 \u0647\u0645\u062a) \u0632\u06cc\u0631\u0650 \u06a9\u0641\u0650 2.0000 \u0647\u0645\u062a"
	oracle_s16 = "Exclude_Industries"
	oracle_s17 = "\u0635\u0646\u0639\u062a \u00ab\u062e\u0648\u062f\u0631\u0648\u00bb \u062f\u0631 \u0641\u0647\u0631\u0633\u062a\u0650 \u0645\u0633\u062a\u062b\u0646\u06cc\u0650 \u067e\u0646\u0644 \u0627\u0633\u062a \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s18 = "Include_Industries"
	oracle_s19 = "\u0635\u0646\u0639\u062a \u00ab\u062e\u0648\u062f\u0631\u0648\u00bb \u062f\u0631 \u0641\u0647\u0631\u0633\u062a\u0650 \u0634\u0627\u0645\u0644\u0650 \u067e\u0646\u0644 \u0646\u06cc\u0633\u062a \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s20 = "\u0635\u0646\u0639\u062a \u00ab\u0628\u06cc\u0645\u0647\u00bb \u062f\u0631 \u0641\u0647\u0631\u0633\u062a\u0650 \u0634\u0627\u0645\u0644\u0650 \u067e\u0646\u0644 \u0646\u06cc\u0633\u062a \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s21 = "\u0635\u0646\u0639\u062a \u00abZZZ\u00bb \u062f\u0631 \u0641\u0647\u0631\u0633\u062a\u0650 \u0634\u0627\u0645\u0644\u0650 \u067e\u0646\u0644 \u0646\u06cc\u0633\u062a \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s22 = "Exclude_Mandatory_Pricing"
	oracle_s23 = "Rank_Only"
	oracle_s24 = "\u0635\u0646\u0639\u062a \u00ab\u2014\u00bb \u062f\u0631 \u0641\u0647\u0631\u0633\u062a\u0650 \u0634\u0627\u0645\u0644\u0650 \u067e\u0646\u0644 \u0646\u06cc\u0633\u062a \u2014 \u062d\u0630\u0641 \u062e\u0648\u062f\u06a9\u0627\u0631"
	oracle_s25 = " AAA , BBB ,,  CCC "
	oracle_s26 = "\u062e\u0648\u062f\u0631\u0648\u060c\u0633\u06cc\u0645\u0627\u0646"
	oracle_s27 = "1a_monetary_growth"
	oracle_s28 = "\u0628\u0627 \u06af\u0631\u0641\u062a\u0646\u0650 \u062f\u06cc\u062a\u0627\u0628\u06cc\u0633 \u062a\u0627\u0632\u0647\u0654 \u06a9\u062f\u0627\u0644 (\u062f\u06a9\u0645\u0647\u0654 \u00ab\u062f\u06cc\u062a\u0627\u0628\u06cc\u0633 \u06a9\u062f\u0627\u0644\u00bb \u062f\u0631 \u062c\u062f\u0648\u0644 \u063a\u0631\u0628\u0627\u0644\u06af\u0631\u06cc) \u06af\u0632\u0627\u0631\u0634\u200c\u0647\u0627\u06cc \u0645\u0627\u0647\u0627\u0646\u0647\u0654 \u062c\u0627\u0627\u0641\u062a\u0627\u062f\u0647 \u0627\u0636\u0627\u0641\u0647 \u0645\u06cc\u200c\u0634\u0648\u062f."
	oracle_s29 = "\u06f1\u0627\u0644\u0641"
	oracle_s30 = "1b_physical_volume"
	oracle_s31 = "\u0628\u0627 \u0647\u0645\u06af\u0627\u0645\u200c\u0633\u0627\u0632\u06cc\u0650 \u06af\u0632\u0627\u0631\u0634 \u0641\u0639\u0627\u0644\u06cc\u062a \u0645\u0627\u0647\u0627\u0646\u0647 (\u0645\u062e\u0631\u062c\u0650 \u0647\u0645\u0627\u0646 \u062f\u0648\u0631\u0647\u0654 \u0633\u0627\u0644 \u0642\u0628\u0644) \u0627\u06cc\u0646 \u0645\u062d\u0648\u0631 \u0633\u0627\u062e\u062a\u0647 \u0645\u06cc\u200c\u0634\u0648\u062f."
	oracle_s32 = "\u06f1\u0628"
	oracle_s33 = "\u0631\u0634\u062f \u0631\u06cc\u0627\u0644\u06cc \u0645\u062d\u0627\u0633\u0628\u0647 \u0646\u0634\u062f \u062a\u0627 \u0631\u0634\u062f \u062a\u0648\u0644\u06cc\u062f\u06cc \u0628\u0631\u0631\u0633\u06cc \u0634\u0648\u062f."
	oracle_s34 = "\u06af\u0632\u0627\u0631\u0634 \u0645\u0627\u0647\u0627\u0646\u0647\u0654 \u0633\u0627\u0644 \u0642\u0628\u0644 \u0644\u0627\u0632\u0645 \u0627\u0633\u062a."
	oracle_s35 = "2_eps_trend"
	oracle_s36 = "\u0627\u06cc\u0646 \u0634\u06a9\u0627\u0641 \u0628\u0627 \u06af\u0631\u0641\u062a\u0646\u0650 \u062f\u06cc\u062a\u0627\u0628\u06cc\u0633\u0650 \u062a\u0627\u0632\u0647\u0654 \u06a9\u062f\u0627\u0644 \u0628\u0633\u062a\u0647 \u0646\u0645\u06cc\u200c\u0634\u0648\u062f: \u0635\u0648\u0631\u062a\u0650 \u0633\u0648\u062f \u0648 \u0632\u06cc\u0627\u0646\u0650 \u063a\u06cc\u0631\u062a\u0644\u0641\u06cc\u0642\u06cc\u0650 \u0622\u0646 \u0633\u0627\u0644\u200c\u0647\u0627 \u0645\u0646\u062a\u0634\u0631 \u0646\u0634\u062f\u0647 \u0627\u0633\u062a."
	oracle_s37 = "\u06f2"
	oracle_s38 = "\u0645\u0628\u0646\u0627\u06cc\u0650 \u063a\u06cc\u0631\u062a\u0644\u0641\u06cc\u0642\u06cc\u0650 \u0633\u0647\u200c\u0633\u0627\u0644\u0647\u0654 \u06a9\u0627\u0645\u0644 \u0645\u0648\u062c\u0648\u062f \u0646\u06cc\u0633\u062a."
	oracle_s39 = "\u0628\u0627 \u06af\u0631\u0641\u062a\u0646\u0650 \u062f\u06cc\u062a\u0627\u0628\u06cc\u0633 \u062a\u0627\u0632\u0647\u0654 \u06a9\u062f\u0627\u0644\u060c \u0635\u0648\u0631\u062a\u200c\u0647\u0627\u06cc \u06f1\u06f2\u0645\u0627\u0647\u0647\u0654 \u0633\u0627\u0644\u200c\u0647\u0627\u06cc \u0642\u062f\u06cc\u0645\u06cc\u200c\u062a\u0631\u0650 \u0647\u0645\u06cc\u0646 \u0646\u0645\u0627\u062f \u0627\u0636\u0627\u0641\u0647 \u0645\u06cc\u200c\u0634\u0648\u062f."
	oracle_s40 = "\u0628\u0627 \u0627\u0646\u062a\u0634\u0627\u0631 \u0635\u0648\u0631\u062a \u06f1\u06f2\u0645\u0627\u0647\u0647\u0654 \u0633\u0627\u0644 \u0645\u0627\u0644\u06cc \u062c\u0627\u0631\u06cc\u060c \u062f\u0627\u0648\u0631\u06cc \u0642\u0637\u0639\u06cc \u0645\u06cc\u0634\u0648\u062f."
	oracle_s41 = "3_gross_margin"
	oracle_s42 = "\u0628\u0627 \u0647\u0645\u06af\u0627\u0645\u200c\u0633\u0627\u0632\u06cc \u06a9\u062f\u0627\u0644 \u0628\u0631\u0631\u0633\u06cc \u0645\u062c\u062f\u062f \u0645\u06cc\u200c\u0634\u0648\u062f."
	oracle_s43 = "\u06f3"
	oracle_s44 = "\u0633\u0648\u062f \u0646\u0627\u062e\u0627\u0644\u0635\u0650 \u0633\u0627\u0644\u0650 \u0645\u0631\u062c\u0639 \u062f\u0631 \u06a9\u062f\u0627\u0644 \u0646\u06cc\u0633\u062a."
	oracle_s45 = "4_sales_to_mcap"
	oracle_s46 = "\u0628\u0627 \u0647\u0645\u06af\u0627\u0645\u200c\u0633\u0627\u0632\u06cc\u0650 \u062a\u0627\u0632\u0647\u0654 \u06a9\u062f\u0627\u0644\u060c \u0633\u062a\u0648\u0646\u0650 \u0648\u0627\u062d\u062f\u0650 \u0647\u0645\u0627\u0646 \u0635\u0648\u0631\u062a\u0650 \u0645\u0627\u0644\u06cc \u067e\u0631 \u0645\u06cc\u200c\u0634\u0648\u062f \u0648 \u0645\u0642\u0627\u06cc\u0633\u0647 \u0628\u0631\u0642\u0631\u0627\u0631 \u0645\u06cc\u200c\u06af\u0631\u062f\u062f."
	oracle_s47 = "\u06f4"
	oracle_s48 = "\u0648\u0627\u062d\u062f\u0650 \u067e\u0648\u0644\u0650 \u0631\u062f\u06cc\u0641\u0650 \u0645\u0631\u062c\u0639\u0650 \u06a9\u062f\u0627\u0644 \u0627\u0639\u0644\u0627\u0645 \u0646\u0634\u062f\u0647\u060c \u067e\u0633 \u0645\u0642\u06cc\u0627\u0633\u0650 \u0627\u06cc\u0646 \u0639\u062f\u062f \u0631\u0627\u0633\u062a\u06cc\u200c\u0622\u0632\u0645\u0627\u06cc\u06cc \u0646\u0634\u062f (\u06af\u06cc\u062a\u0650 \u0648\u0627\u062d\u062f \u0628\u06cc\u200c\u0634\u0627\u0647\u062f \u0627\u062c\u0631\u0627 \u0634\u062f)."
	oracle_s49 = "\u06af\u0632\u0627\u0631\u0634\u200c\u0647\u0627\u06cc \u0645\u0627\u0647\u0627\u0646\u0647\u0654 \u06a9\u0627\u0645\u0644\u0650 \u0647\u0645\u0627\u0646 \u0633\u0627\u0644 \u0645\u0627\u0644\u06cc \u0644\u0627\u0632\u0645 \u0627\u0633\u062a."
	oracle_s50 = "\u0633\u0627\u0644\u0627\u0646\u0647\u200c\u0633\u0627\u0632\u06cc \u00d7\u06f1\u06f2\u00f7\u0645 \u0628\u0627 \u06af\u06cc\u062a\u0650 fts_engine \u0633\u0627\u0632\u06af\u0627\u0631 \u0646\u0634\u062f\u061b \u0641\u0631\u0648\u0634 \u0633\u0627\u0644\u0627\u0646\u0647\u0654 \u06a9\u062f\u0627\u0644 \u062c\u0627\u0646\u0634\u06cc\u0646 \u0634\u062f."
	oracle_s51 = "\u0642\u06cc\u0645\u062a\u200c\u06af\u0630\u0627\u0631\u06cc \u062f\u0633\u062a\u0648\u0631\u06cc \u2014 \u0646\u0631\u062e \u062a\u0648\u0633\u0637 \u0634\u0648\u0631\u0627\u06cc \u0631\u0642\u0627\u0628\u062a/\u062f\u0648\u0644\u062a \u062a\u0639\u06cc\u06cc\u0646 \u0645\u06cc\u0634\u0648\u062f\u061b \u0631\u0634\u062f \u0641\u0631\u0648\u0634 \u0628\u062f\u0648\u0646 \u0645\u062c\u0648\u0632 \u0627\u0641\u0632\u0627\u06cc\u0634 \u0646\u0631\u062e \u0639\u0645\u0644\u0627\u064b \u0645\u0645\u06a9\u0646 \u0646\u06cc\u0633\u062a \u0648 \u0627\u0641\u0632\u0627\u06cc\u0634 \u062d\u0627\u0634\u06cc\u0647 \u0645\u0634\u0645\u0648\u0644 \u0645\u062c\u0648\u0632 \u0627\u0633\u062a. \u0627\u0633\u062a\u0631\u0627\u062a\u0698\u06cc FTS \u0627\u06cc\u0646 \u06af\u0631\u0648\u0647 \u0631\u0627 \u0627\u0632 \u0633\u0628\u062f \u0628\u06cc\u0631\u0648\u0646 \u0645\u06cc\u200c\u06af\u0630\u0627\u0631\u062f."
	oracle_s52 = "\u062f\u0633\u062a\u0648\u0631\u06cc"
	oracle_s53 = "\u0642\u06cc\u0645\u062a\u200c\u06af\u0630\u0627\u0631\u06cc \u062f\u0633\u062a\u0648\u0631\u06cc"
	oracle_s54 = "\u0642\u06cc\u0645\u062a\u200c\u06af\u0630\u0627\u0631\u06cc \u0622\u0632\u0627\u062f / \u0628\u0648\u0631\u0633 \u06a9\u0627\u0644\u0627 / \u0635\u0627\u062f\u0631\u0627\u062a\u200c\u0645\u062d\u0648\u0631 \u2014 \u0646\u0631\u062e \u0627\u0632 \u0628\u0627\u0632\u0627\u0631 \u0645\u06cc\u200c\u0622\u06cc\u062f\u060c \u067e\u0633 \u0631\u0634\u062f \u0641\u0631\u0648\u0634 \u0642\u0627\u0628\u0644\u0650 \u0627\u062a\u06a9\u0627 \u0628\u0647 \u062a\u0648\u0631\u0645 \u0631\u06cc\u0627\u0644\u06cc \u0646\u06cc\u0633\u062a \u0648 \u0628\u0627\u06cc\u062f \u0628\u0627 \u062d\u062c\u0645 \u062b\u0627\u0628\u062a \u0634\u0648\u062f."
	oracle_s55 = "\u0622\u0632\u0627\u062f / \u0628\u0648\u0631\u0633 \u06a9\u0627\u0644\u0627"
	oracle_s56 = "\u0642\u06cc\u0645\u062a\u200c\u06af\u0630\u0627\u0631\u06cc \u0622\u0632\u0627\u062f / \u0628\u0648\u0631\u0633 \u06a9\u0627\u0644\u0627"
	oracle_s57 = "\u0633\u0627\u06cc\u0631 \u0635\u0646\u0627\u06cc\u0639 (\u063a\u06cc\u0631\u062f\u0633\u062a\u0648\u0631\u06cc) \u2014 \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u0628\u0631\u0631\u0633\u06cc \u0645\u0648\u0631\u062f\u06cc\u0650 \u0646\u0631\u062e \u0645\u062d\u0635\u0648\u0644 \u0648 \u0645\u062c\u0648\u0632 \u0627\u0641\u0632\u0627\u06cc\u0634 \u0642\u06cc\u0645\u062a."
	oracle_s58 = "\u0633\u0627\u06cc\u0631 \u0635\u0646\u0627\u06cc\u0639"
	oracle_s59 = "\u062e\u0646\u062b\u06cc \u2014 \u0646\u06cc\u0627\u0632\u0645\u0646\u062f \u0628\u0631\u0631\u0633\u06cc \u0645\u0648\u0631\u062f\u06cc"
	oracle_s60 = "\u0628\u0627\u0646\u0643"
	oracle_s61 = "\u0633\u0631\u0645\u0627\u064a\u0647 \u06af\u0630\u0627\u0631\u064a"
	oracle_s62 = "\u0686\u0646\u062f \u0631\u0634\u062a\u0647 \u0627\u064a"
	oracle_s63 = "\u0635\u0646\u062f\u0648\u0642"
	oracle_s64 = "\u0647\u0644\u062f\u06cc\u0646\u06af"
	oracle_s65 = "\u0634\u0631\u06a9\u062a \u0627\u0644\u0641"
	oracle_s66 = "\u06af\u0631\u0648\u0647 \u067e\u0627\u0631\u0633"
	oracle_s67 = "\u0646\u0647\u0627\u062f\u0647\u0627\u06cc \u0645\u0627\u0644\u06cc \u0648\u0627\u0633\u0637"
	oracle_s68 = "\u0648\u0627\u0633\u0637\u0647 \u06af\u0631\u06cc"
	oracle_s69 = "\u0628\u0627\u0646\u06a9"
	oracle_s70 = "\u0635\u0646\u062f\u0648\u0642 \u0633\u0631\u0645\u0627\u064a\u0647 \u06af\u0630\u0627\u0631\u064a"
	oracle_s71 = "\u0628\u06cc\u0645\u0647 \u0648\u0635\u0646\u062f\u0648\u0642 \u0628\u0627\u0632\u0646\u0634\u062a\u06af\u06cc"
	oracle_s72 = "\u0628\u064a\u0645\u0647\u0648\u0635\u0646\u062f\u0648\u0642 \u0628\u0627\u0632\u0646\u0634\u062a\u06af\u064a"
	oracle_s73 = "\u0628\u064a\u0645\u0647"
	oracle_s74 = "\u0628\u06cc\u0645\u0647 \u0628\u0627\u0631\u0633"
	oracle_s75 = "\u0628\u0627\u0632\u0646\u0634\u062a\u06af\u06cc"
)

// ── زیرساختِ مقایسه ─────────────────────────────────────────────────────────

func ax45Vectors(t *testing.T, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "vectors", name))
	if err != nil {
		t.Fatalf("vectors %s: %v", name, err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("vectors %s: %v", name, err)
	}
	return v
}

// ax45MinList وکتور را می‌خواند و سقفِ تعداد را می‌سنجد: فیکچرِ بریده‌شده نباید
// سبز رد شود.
func ax45MinList(t *testing.T, v map[string]any, key string, min int) []any {
	t.Helper()
	list, ok := v[key].([]any)
	if !ok {
		t.Fatalf("vectors: %q is %T, want array", key, v[key])
	}
	if len(list) < min {
		t.Fatalf("vectors: %q has %d cases, fixture is truncated (min %d)", key, len(list), min)
	}
	return list
}

// ax45Norm مثلِ بدنه‌ای که روی سیم می‌رود: int64 → float64، []string → []any،
// nil → null. بعد از آن `parity.Compare` نوع‌ها را سخت می‌سنجد.
func ax45Norm(t *testing.T, got any) any {
	t.Helper()
	body, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("marshal got: %v", err)
	}
	var v any
	if err := json.Unmarshal(body, &v); err != nil {
		t.Fatalf("unmarshal got: %v", err)
	}
	return v
}

func ax45Check(t *testing.T, label string, want, got any) {
	t.Helper()
	res := parity.Compare(want, got, parity.Options{})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", label, d)
		}
	}
}

func ax45AsMap(v any) map[string]any {
	m, _ := v.(map[string]any)
	return m
}

func ax45AsRows(v any) [][]any {
	list, _ := v.([]any)
	out := make([][]any, 0, len(list))
	for _, r := range list {
		row, _ := r.([]any)
		out = append(out, row)
	}
	return out
}

func ax45F(v any) float64 { f, _ := v.(float64); return f }

// ── ۱) شاخص ۴: ۲۸۰ کیس (۵ annual × ۷ gm × ۴ mcap × exempt∈{F,T}) ────────────

func TestInd4ValuationVectors(t *testing.T) {
	v := ax45Vectors(t, "valuation.json")
	cases := ax45MinList(t, v, "cases", 280)
	annuals := ax45MinList(t, v, "annuals", 5)
	gms := ax45MinList(t, v, "gms", 7)
	th := V10Thresholds(nil)

	seen := map[string]int{}
	for i, c := range cases {
		kase := ax45AsMap(c)
		annual := ax45AsMap(annuals[int(ax45F(kase["annual"]))])
		gm := ax45AsMap(gms[int(ax45F(kase["gm"]))])
		exempt, _ := kase["exempt"].(bool)
		got := ax45Norm(t, Ind4Valuation(annual, gm, kase["mcap"], th, exempt))
		want := kase["out"]
		ax45Check(t, "valuation case "+strconv.Itoa(i), want, got)
		if m := ax45AsMap(want); m != nil {
			switch {
			case exempt:
				seen["exempt"]++
			case m["available"] == true:
				seen["available"]++
				if m["margin_basis"] == "net_margin_proxy" {
					seen["net_margin_proxy"]++
				}
			case m["gap_cause"] == "market_cap":
				seen["no_mcap"]++
			case m["gap_cause"] == "annual_sales":
				seen["no_sales"]++
			}
		}
	}
	// شاخه‌ها باید واقعی خورده باشند، نه اینکه یکِ حالتِ تصادفی سبز شود.
	for _, k := range []string{"exempt", "no_sales", "no_mcap", "net_margin_proxy", "available"} {
		if seen[k] == 0 {
			t.Errorf("valuation branch %q never exercised", k)
		}
	}
	if len(cases) != 280 {
		t.Errorf("valuation cases = %d want 280", len(cases))
	}
}

// ── ۲) لایۀ ۵: فیلترِ صنعت و اضافۀ ind5 ─────────────────────────────────────

// TestSectorFilterVectors — شبکهٔ ورودیِ (mcap/total/gpm/sales_growth) همان چیزی
// است که وکتور را ساخته و درِ `tools/parity/gen_fundamental_vectors.py:201-215`
// ثبت شده؛ JSON فقط `sector`/`cfg`/`out` را نگه داشته (ورودی‌هایِ مقیاس و رشد
// ثبت نشده‌اند)، پس این جدول از همان سورسِ اوراکل خوانده می‌شود — چیزی که
// دست‌نویس می‌شود «ورودی» است، نه رأی؛ رأی ازِ وکتور می‌آید.
func TestSectorFilterVectors(t *testing.T) {
	v := ax45Vectors(t, "sector.json")
	cases := ax45MinList(t, v, "cases", 9)
	inputs := []struct {
		mc, tm float64
		gpm    *float64
		sg     *float64
	}{
		{0, 0, nil, nil}, {0, 0, nil, nil}, {0, 0, nil, nil},
		{0, 0, fP(35.0), fP(45.0)}, {0, 0, fP(35.0), fP(45.0)},
		{0, 0, fP(12.0), fP(90.0)}, {5e12, 1e15, nil, nil},
		{5e12, 1e15, nil, nil}, {0, 0, nil, nil},
	}
	ran := map[string]int{}
	for i, c := range cases {
		kase := ax45AsMap(c)
		sector, _ := kase["sector"].(string)
		in := inputs[i]
		got := ax45Norm(t, SectorFilter(sector, ax45AsMap(kase["cfg"]), in.mc, in.tm,
			in.gpm, in.sg))
		ax45Check(t, "sector case "+strconv.Itoa(i), kase["out"], got)
		if m := ax45AsMap(kase["out"]); m != nil {
			ran[m["verdict"].(string)]++
			if len(m["matched_tokens"].([]any)) > 0 {
				ran["tokens"]++
			}
		}
	}
	for _, k := range []string{"mandatory", "free", "neutral", "tokens"} {
		if ran[k] == 0 {
			t.Errorf("sector branch %q never exercised", k)
		}
	}
}

func fP(v float64) *float64 { return &v }

// TestInd5IndustryAdditions — outlook/regime_label/rule_ref وکتور ندارند؛ داورشان
// متنِ سنجیده‌شده از خودِ اوراکل است (constant‌های بالا).
func TestInd5IndustryAdditions(t *testing.T) {
	for i, c := range []struct {
		sector  string
		verdict string
		outlook string
		regime  string
		label   string
	}{
		{oracle_s03, "mandatory", oracle_s51, oracle_s52, oracle_s53},
		{oracle_s04, "free", oracle_s54, oracle_s55, oracle_s56},
		{"ZZZ", "neutral", oracle_s57, oracle_s58, oracle_s59},
		{oracle_s05, "mandatory", oracle_s51, oracle_s52, oracle_s53},
	} {
		got := ax45AsMap(ax45Norm(t, Ind5Industry(c.sector, nil, 0.0, 0.0, nil, nil)))
		want := map[string]any{"verdict": c.verdict, "outlook": c.outlook,
			"regime_label": c.regime, "rule_ref": "F-05", "label": c.label}
		for k, w := range want {
			if got[k] != w {
				t.Errorf("ind5 case %d key %q = %v want %v", i, k, got[k], w)
			}
		}
	}
}

// ── ۳) سالانۀ‌سازی روی فیکچر (۲۰ کیس: ۵ نماد × exempt/no_exempt/ind4) ───────

func TestAnnualizedSalesVectors(t *testing.T) {
	svc := openService(t)
	defer svc.Close()
	ctx := context.Background()

	ann := ax45Vectors(t, "annualize.json")
	cases := ax45MinList(t, ann, "cases", 20)
	ind := ax45Vectors(t, "indicators.json")
	st := ax45Vectors(t, "statements.json")

	seriesBy := map[string][][]any{}
	for _, e := range ax45MinList(t, ind, "monthly", 5) {
		m := ax45AsMap(e)
		seriesBy[m["symbol"].(string)] = ax45AsRows(m["rows"])
	}
	profBy := map[string]map[string]any{}
	sectorBy := map[string]string{}
	for _, e := range ax45MinList(t, ind, "profile", 5) {
		m := ax45AsMap(e)
		profBy[m["symbol"].(string)] = ax45AsMap(m["out"])
		sectorBy[m["symbol"].(string)], _ = m["sector"].(string)
	}
	refBy := map[string]map[string]any{}
	for _, e := range ax45MinList(t, st, "reference", 5) {
		m := ax45AsMap(e)
		refBy[m["symbol"].(string)] = ax45AsMap(m["out"])
	}

	ran := map[string]int{}
	for i, c := range cases {
		kase := ax45AsMap(c)
		sym, _ := kase["symbol"].(string)
		kind, _ := kase["kind"].(string)
		out := ax45AsMap(kase["out"])
		if kind == "ind4_exempt" {
			na := svc.Ind4Exempt(ctx, sym, sectorBy[sym], true, nil)
			off := svc.Ind4Exempt(ctx, sym, sectorBy[sym], false, nil)
			got := map[string]any{"na": na, "na_false": off}
			ax45Check(t, "ind4_exempt "+sym, out, ax45Norm(t, got))
			if na {
				ran["exempt_true"]++
			} else {
				ran["exempt_false"]++
			}
			continue
		}
		var exempt *bool
		if v, has := kase["exempt"]; has {
			b, _ := v.(bool)
			exempt = &b
		}
		got, err := svc.AnnualizedSales(ctx, sym, refBy[sym], seriesBy[sym], profBy[sym], exempt)
		if err != nil {
			t.Fatalf("annualize %s: %v", sym, err)
		}
		ax45Check(t, "annualize "+strconv.Itoa(i)+" "+sym, out, ax45Norm(t, got))
		if out["na"] == true {
			ran["na"]++
		} else if out["operational_revenue_basis"] == true {
			ran["op_basis"]++
		} else if out["reconciled"] == true {
			ran["reconciled"]++
		} else {
			ran["unverified"]++
		}
	}
	for _, k := range []string{"na", "op_basis", "reconciled", "unverified",
		"exempt_true", "exempt_false"} {
		if ran[k] == 0 {
			t.Errorf("annualize branch %q never exercised", k)
		}
	}
}

// ── ۴) نسخۀ محلیِ ردیفِ مرجع (TODO(unify)) با وکتورهایِ statements.json ──────

func TestA45ReferenceAnnualVectors(t *testing.T) {
	svc := openService(t)
	defer svc.Close()
	ctx := context.Background()
	st := ax45Vectors(t, "statements.json")

	for _, e := range ax45MinList(t, st, "reference", 5) {
		m := ax45AsMap(e)
		sym, _ := m["symbol"].(string)
		got, err := svc.a45ReferenceAnnual(ctx, sym)
		if err != nil {
			t.Fatalf("reference_annual %s: %v", sym, err)
		}
		ax45Check(t, "reference_annual "+sym, m["out"], ax45Norm(t, got))
	}
	// اوراکل این‌ها را با پیش‌فرضِ خودش (require_audit=True، exclude_consolidated
	// =True) ساخته است — همان امضایِ annual_statements.
	for _, e := range ax45MinList(t, st, "annual", 15) {
		m := ax45AsMap(e)
		sym, _ := m["symbol"].(string)
		limit := int(ax45F(m["limit"]))
		got, err := svc.a45AnnualStatements(ctx, sym, true, true, limit)
		if err != nil {
			t.Fatalf("annual_statements %s/%d: %v", sym, limit, err)
		}
		ax45Check(t, "annual_statements "+sym+"/"+strconv.Itoa(limit), m["out"], ax45Norm(t, got))
	}
}

// ── ۵) طبقۀ شرکت (نسخۀ محلیِ company_profile، ۱۷ کیس) ──────────────────────

func TestA45CompanyProfileVectors(t *testing.T) {
	v := ax45Vectors(t, "profile.json")
	cases := ax45MinList(t, v, "cases", 17)
	ran := map[string]int{}
	for i, c := range cases {
		kase := ax45AsMap(c)
		sector, _ := kase["sector"].(string)
		company, _ := kase["company"].(string)
		got := ax45Norm(t, a45CompanyProfile(sector, company))
		ax45Check(t, "profile case "+strconv.Itoa(i), kase["out"], got)
		if m := ax45AsMap(kase["out"]); m != nil {
			ran[m["kind"].(string)]++
		}
	}
	for _, k := range []string{"production", "financial", "service", "fund", "holding"} {
		if ran[k] == 0 {
			t.Errorf("profile class %q never exercised", k)
		}
	}
}

// ── ۶)Matchersِ طبقه (اوراکل، بانک لازم ندارد) ───────────────────────────────

func TestA45ClassMatchersOracle(t *testing.T) {
	for i, c := range []struct {
		sector, company string
		want            bool
	}{
		{"", "", false},
		{oracle_s60, "", true},
		{oracle_s61, "", true},
		{oracle_s62, "", true},
		{oracle_s63, "", false},
		{oracle_s64, oracle_s65, true},
		{"", oracle_s66, false},
		{oracle_s67, "", true},
		{oracle_s68, "", true},
		{oracle_s69, "", true},
		{oracle_s04, "", false},
		{oracle_s03, "", false},
	} {
		if got := a45HoldingClassMatch(c.sector, c.company); got != c.want {
			t.Errorf("holding_class_match %d (%q,%q) = %v want %v", i, c.sector, c.company, got, c.want)
		}
	}
	for i, c := range []struct {
		sector, company string
		want            bool
	}{
		{"", "", false},
		{oracle_s63, "", true},
		{oracle_s70, "", true},
		{oracle_s05, "", false},
		{oracle_s71, "", false},
		{oracle_s72, "", false},
		{"", oracle_s02, true},
		{oracle_s04, "", false},
	} {
		if got := a45FundClassMatch(c.sector, c.company); got != c.want {
			t.Errorf("fund_class_match %d (%q,%q) = %v want %v", i, c.sector, c.company, got, c.want)
		}
	}
	for i, c := range []struct {
		sector string
		want   bool
	}{
		{"", false}, {oracle_s05, true}, {oracle_s73, true}, {oracle_s74, true},
		{oracle_s75, false}, {oracle_s04, false}, {oracle_s06, true},
		{oracle_s03, false},
	} {
		if got := IsInsuranceSector(c.sector); got != c.want {
			t.Errorf("is_insurance_sector %d (%q) = %v want %v", i, c.sector, got, c.want)
		}
	}
}

// ── ۷) دروازۀ صنایعِ دستی + norm_industry_list (اوراکل، بی‌وکتور) ────────────

func TestIndustryGateOracle(t *testing.T) {
	type igCase struct {
		name      string
		cfg       map[string]any
		sector    string
		active    bool
		mode      string
		pass      bool
		matched   []string
		reason    string
		include   []string
		exclude   []string
	}
	cases := []igCase{
		{name: "default|", cfg: map[string]any{}, sector: "", active: false,
			mode: oracle_s22, pass: true},
		{name: "default|ZZZ", cfg: map[string]any{}, sector: "ZZZ", active: false,
			mode: oracle_s22, pass: true},
		{name: "default|" + oracle_s03, cfg: map[string]any{}, sector: oracle_s03,
			active: false, mode: oracle_s22, pass: true},
		{name: "exclude|" + oracle_s03,
			cfg: map[string]any{"industry_mode": oracle_s16, "exclude_industries": oracle_s03},
			sector: oracle_s03, active: true, mode: oracle_s16, pass: false,
			matched: []string{oracle_s03}, reason: oracle_s17, exclude: []string{oracle_s03}},
		{name: "exclude|ZZZ",
			cfg: map[string]any{"industry_mode": oracle_s16, "exclude_industries": oracle_s03},
			sector: "ZZZ", active: true, mode: oracle_s16, pass: true,
			exclude: []string{oracle_s03}},
		{name: "exclude|",
			cfg: map[string]any{"industry_mode": oracle_s16, "exclude_industries": oracle_s03},
			sector: "", active: true, mode: oracle_s16, pass: true,
			exclude: []string{oracle_s03}},
		{name: "include|" + oracle_s03,
			cfg: map[string]any{"industry_mode": oracle_s18,
				"include_industries": []string{oracle_s04}},
			sector: oracle_s03, active: true, mode: oracle_s18, pass: false,
			reason: oracle_s19, include: []string{oracle_s04}},
		{name: "include|" + oracle_s04,
			cfg: map[string]any{"industry_mode": oracle_s18,
				"include_industries": []string{oracle_s04}},
			sector: oracle_s04, active: true, mode: oracle_s18, pass: true,
			matched: []string{oracle_s04}, include: []string{oracle_s04}},
		{name: "include|",
			cfg: map[string]any{"industry_mode": oracle_s18,
				"include_industries": []string{oracle_s04}},
			sector: "", active: true, mode: oracle_s18, pass: false,
			reason: oracle_s24, include: []string{oracle_s04}},
		{name: "nil_mode|", cfg: map[string]any{"industry_mode": nil}, sector: "",
			active: false, mode: oracle_s22, pass: true},
		{name: "rank|", cfg: map[string]any{"industry_mode": oracle_s23}, sector: "",
			active: false, mode: oracle_s23, pass: true},
	}
	for _, c := range cases {
		got := ax45AsMap(ax45Norm(t, IndustryGate(c.sector, c.cfg)))
		want := map[string]any{
			"active": c.active, "mode": c.mode, "pass": c.pass,
			"matched": strList(c.matched), "reason": c.reason,
			"include": strList(c.include), "exclude": strList(c.exclude),
		}
		ax45Check(t, "industry_gate "+c.name, want, got)
	}

	for _, c := range []struct {
		name string
		in   any
		want []string
	}{
		{"nil", nil, nil},
		{"empty", "", nil},
		{"ascii", oracle_s25, []string{"AAA", "BBB", "CCC"}},
		{"comma", oracle_s26, []string{oracle_s03, oracle_s04}},
		{"dupes", []any{oracle_s03, oracle_s03, "", nil, oracle_s05},
			[]string{oracle_s03, oracle_s05}},
		{"list_nil", []any{}, nil},
		{"num", []any{int64(5), int64(0), oracle_s03}, []string{"5", oracle_s03}},
	} {
		got := ax45Norm(t, NormIndustryList(c.in))
		ax45Check(t, "norm_industry_list "+c.name, strList(c.want), got)
	}
}

func strList(xs []string) []any {
	if len(xs) == 0 {
		return []any{}
	}
	out := make([]any, 0, len(xs))
	for _, x := range xs {
		out = append(out, x)
	}
	return out
}

// ── ۸) شکاف‌های داده (اوراکل، بی‌وکتور) ─────────────────────────────────────

func TestV10DataGapsOracle(t *testing.T) {
	gap := func(layer, axis, why, fix string, extra map[string]any) map[string]any {
		m := map[string]any{"layer": layer, "axis": axis, "why": why, "fix": fix}
		for k, v := range extra {
			m[k] = v
		}
		return m
	}
	ind := func(v any) map[string]any { return map[string]any{"indicators": v} }
	s1 := func(monetary, volume map[string]any) map[string]any {
		l1 := map[string]any{}
		if monetary != nil {
			l1["monetary"] = monetary
		}
		if volume != nil {
			l1["volume"] = volume
		}
		return map[string]any{"1": l1}
	}
	for _, c := range []struct {
		name string
		in   map[string]any
		want []map[string]any
	}{
		{"empty", map[string]any{}, nil},
		{"gap1a", ind(s1(map[string]any{"data_gap": true, "reason": "whyA",
			"remediation": ""}, nil)),
			[]map[string]any{gap(oracle_s29, oracle_s27, "whyA", oracle_s28, nil)}},
		{"gap1a_default", ind(s1(map[string]any{"data_gap": true}, nil)),
			[]map[string]any{gap(oracle_s29, oracle_s27, "", oracle_s28, nil)}},
		{"gap1a_fix", ind(s1(map[string]any{"data_gap": true, "reason": "whyB",
			"remediation": "fixB"}, nil)),
			[]map[string]any{gap(oracle_s29, oracle_s27, "whyB", "fixB", nil)}},
		{"gap1b_unavailable", ind(s1(nil, map[string]any{"basis": "unavailable"})),
			[]map[string]any{gap(oracle_s32, oracle_s30, oracle_s33, oracle_s31, nil)}},
		{"gap1b_unavailable_reason",
			ind(s1(nil, map[string]any{"basis": "unavailable", "reason": "whyC"})),
			[]map[string]any{gap(oracle_s32, oracle_s30, "whyC", oracle_s31, nil)}},
		{"gap1b_datagain",
			ind(s1(nil, map[string]any{"basis": "column", "data_gap": true, "reason": "whyD"})),
			[]map[string]any{gap(oracle_s32, oracle_s30, "whyD", oracle_s34, nil)}},
		{"gap1b_bare", ind(s1(nil, map[string]any{"data_gap": true})),
			[]map[string]any{gap(oracle_s32, oracle_s30, "", oracle_s34, nil)}},
		{"na2", map[string]any{"indicators": map[string]any{"2": map[string]any{"na": true}}},
			[]map[string]any{gap(oracle_s37, oracle_s35, oracle_s38, oracle_s36,
				map[string]any{"na": true})}},
		{"gap2", map[string]any{"indicators": map[string]any{"2": map[string]any{
			"na": false, "data_gap": true, "available_periods": 2, "years_required": 3,
			"partial": true, "reason": "whyF"}}},
			[]map[string]any{gap(oracle_s37, oracle_s35, "whyF", oracle_s39, map[string]any{
				"available_periods": 2.0, "required_periods": 3.0, "partial": true})}},
		{"gap2_missing", map[string]any{"indicators": map[string]any{
			"2": map[string]any{"data_gap": true}}},
			[]map[string]any{gap(oracle_s37, oracle_s35, "", oracle_s39, map[string]any{
				"available_periods": 0.0, "required_periods": 3.0, "partial": false})}},
		{"gap2_extra", map[string]any{"indicators": map[string]any{"2": map[string]any{
			"data_gap": true, "available_periods": 0, "years_required": 0,
			"partial": false}}},
			[]map[string]any{gap(oracle_s37, oracle_s35, "", oracle_s39, map[string]any{
				"available_periods": 0.0, "required_periods": 3.0, "partial": false})}},
		{"soft2", map[string]any{"indicators": map[string]any{
			"2": map[string]any{"soft_gap": true, "reason": "whyG"}}},
			[]map[string]any{gap(oracle_s37, oracle_s35, "whyG", oracle_s40, nil)}},
		{"na3", map[string]any{"indicators": map[string]any{"3": map[string]any{"na": true}}},
			[]map[string]any{gap(oracle_s43, oracle_s41, oracle_s44, oracle_s42, nil)}},
		{"na3_fix", map[string]any{"indicators": map[string]any{"3": map[string]any{
			"na": true, "reason": "whyH", "remediation": "fixI"}}},
			[]map[string]any{gap(oracle_s43, oracle_s41, "whyH", "fixI", nil)}},
		{"unit4", map[string]any{"indicators": map[string]any{"4": map[string]any{
			"annual": map[string]any{"unit_unverified": true, "reconciled": true}}}},
			[]map[string]any{gap(oracle_s47, oracle_s45, oracle_s48, oracle_s46, nil)}},
		{"reconcile4", map[string]any{"indicators": map[string]any{"4": map[string]any{
			"annual": map[string]any{"unit_unverified": false, "reconciled": false}}}},
			[]map[string]any{gap(oracle_s47, oracle_s45, oracle_s50, oracle_s49, nil)}},
		{"reconcile_none", map[string]any{"indicators": map[string]any{
			"4": map[string]any{"annual": map[string]any{"reconciled": nil}}}}, nil},
		{"both4", map[string]any{"indicators": map[string]any{"4": map[string]any{
			"annual": map[string]any{"unit_unverified": true, "reconciled": false}}}},
			[]map[string]any{gap(oracle_s47, oracle_s45, oracle_s48, oracle_s46, nil)}},
		{"many", map[string]any{"indicators": map[string]any{
			"1": map[string]any{
				"monetary": map[string]any{"data_gap": true, "reason": "whyJ"},
				"volume":   map[string]any{"basis": "unavailable", "reason": "whyK"}},
			"2": map[string]any{"na": true, "reason": "whyL"},
			"3": map[string]any{"na": true, "reason": "whyM"},
			"4": map[string]any{"annual": map[string]any{"reconciled": false}}}},
			[]map[string]any{
				gap(oracle_s29, oracle_s27, "whyJ", oracle_s28, nil),
				gap(oracle_s32, oracle_s30, "whyK", oracle_s31, nil),
				gap(oracle_s37, oracle_s35, "whyL", oracle_s36, map[string]any{"na": true}),
				gap(oracle_s43, oracle_s41, "whyM", oracle_s42, nil),
				gap(oracle_s47, oracle_s45, oracle_s50, oracle_s49, nil),
			}},
	} {
		got := ax45Norm(t, V10DataGaps(c.in))
		want := []any{}
		for _, m := range c.want {
			want = append(want, m)
		}
		if len(c.want) == 0 {
			want = []any{}
		}
		ax45Check(t, "v10_data_gaps "+c.name, want, got)
	}
}

// ── ۹) متنِ SQLِ «تازۀترینِ انتشار» — سنجیده‌شده از خودِ پایتون ──────────────

func TestGtPubCanonSQLMatchesOracle(t *testing.T) {
	// داور، وکتورِ پایتون‌ساخته است (text.json → pub_canon)؛ دست‌نویسیِ رشته درِ
	// گیت یک‌بار یک `replace` اضافه داشت و گیت را سبز نگه داشت.
	groups, _ := loadVectors(t, "text.json")["pub_canon"].([]any)
	if len(groups) == 0 {
		t.Fatal("vectors/text.json has no pub_canon group")
	}
	for _, raw := range groups {
		row, _ := raw.(map[string]any)
		col, _ := row["col"].(string)
		want, _ := row["canon"].(string)
		wantOrder, _ := row["order"].(string)

		got := gtPubCanonSQL(col)
		if got != want {
			t.Errorf("pub_canon_sql(%q) mismatch\n got: %q\nwant: %q", col, got, want)
		}
		// شمارشِ کدپوینت (پایانۀ رشته درِ پایانه «-» نشان داده می‌شود ولی درِ
		// بانک «/» است — پس فقط شمارشِ کدپوینت مدرک است، نه نمایش).
		// شمارش روی «رون» است نه بایت: رقمِ فارسی/عربی دو بایت است و `len` درِ
		// گو زبانِ گو بایت می‌شمارد (پایتون نویسه).
		runes := []rune(got)
		dash, slash, rep := 0, 0, 0
		for _, r := range runes {
			switch r {
			case '-':
				dash++
			case '/':
				slash++
			}
		}
		for i := 0; i+8 <= len(runes); i++ {
			if string(runes[i:i+8]) == "replace(" {
				rep++
			}
		}
		if dash != 1 || slash != 1 || rep != 21 {
			t.Errorf("pub_canon_sql(%q) codepoints dash=%d slash=%d replace=%d want 1/1/21",
				col, dash, slash, rep)
		}
		if got := gtPubOrderExpr(col); got != wantOrder {
			t.Errorf("pub_order_expr(%q) mismatch\n got: %q\nwant: %q", col, got, wantOrder)
		}
	}
}

// ── ۱۰) گیت‌ها روی بانکِ موقت (راستی‌آزمایی‌نشده با دادهٔ واقعی) ──────────────

// gatesDataJSON همان ردیف‌هایی است که اوراکلِ پایتون روی‌شان سنجید (همان فایل،
// همان ترتیب؛ \u002f و \u002d صریح‌اند تا «/» و «-» با هم اشتباه نشوند).
const gatesDataJSON = "{\"daily\":[[\"IA\",14050101,10000000000.0],[\"IA\",14050102,11000000000.0],[\"IA\",14050103,12000000000.0],[\"IA\",14050104,13000000000.0],[\"IA\",14050105,14000000000.0],[\"IA\",14050106,15000000000.0],[\"IA\",14050107,16000000000.0],[\"IA\",14050108,17000000000.0],[\"IA\",14050001,900000000000.0],[\"IB\",14041201,5000000000.0],[\"IC\",14050108,0.0],[\"ID\",14050107,25000000000.0],[\"ID\",14050108,75000000000.0],[\"IE\",14050101,null],[\"IK\",14050108,10000000000.0]],\"fs\":[[\"TESTA\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,1.0,1.0,1.0,1.0,\"\u0627\u0644\u0641\",\"mrl\",10,\"1405\u002f01\u002f20\",100.0,40.0,1],[\"TESTA\",\"1403\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",9.0,1.0,1.0,1.0,1.0,\"\u0627\u0644\u0641\",\"mrl\",9,\"1404\u002f01\u002f20\",100.0,10.0,1],[\"TESTB\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,1.0,1.0,1.0,1.0,\"\u0628\",\"mrl\",20,\"1405\u002f01\u002f20\",100.0,60.0,1],[\"TESTC\",\"1404\u002f06\u002f31\",6,\"\u062f\u0648\u0631\u0647 6 \u0645\u0627\u0647\u0647\",5.0,null,null,null,null,\"\u067e\",\"mrl\",31,\"1404\u002f07\u002f01\",100.0,5.0,1],[\"TESTC\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,1.0,1.0,1.0,1.0,\"\u067e\",\"mrl\",30,\"1405\u002f01\u002f20\",100.0,45.0,1],[\"TESTD\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,1.0,1.0,1.0,1.0,\"\u062a\",\"mrl\",40,\"1405\u002f01\u002f20\",100.0,50.0,1],[\"TESTE\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,1.0,1.0,1.0,1.0,\"\u062b\",\"mrl\",50,\"1405\u002d01\u002d02\",100.0,90.0,1],[\"TESTE\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,1.0,1.0,1.0,1.0,\"\u062b\",\"mrl\",51,\"1405\u002f\u06f0\u06f1\u002f\u06f0\u06f3 \u06f2\u06f3:\u06f5\u06f3:\u06f5\u06f7\",100.0,20.0,1],[\"TESTF\",null,12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,null,null,null,null,\"\u062c\",\"mrl\",60,\"1405\u002f01\u002f01\",100.0,10.0,1],[\"TESTG\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,null,null,null,null,\"\u0686\",\"mrl\",70,\"1405\u002f01\u002f01\",0.0,10.0,1],[\"TESTH\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,null,null,null,null,\"\u062d\",\"mrl\",80,\"1405\u002f01\u002f01\",100.0,null,1],[\"TESTI\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",3.0,null,null,1.0,0.1,\"\u0635\u0646\u062f\u0648\u0642 \u0622\u0632\u0645\u0648\u0646\",\"mrl\",90,\"1405\u002f01\u002f01\",100.0,80.0,0],[\"TESTJ\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,null,null,null,null,\"\u062b\",null,100,\"\u06f1\u06f4\u06f0\u06f5\u002f\u06f0\u06f2\u002f\u06f0\u06f1\",100.0,30.0,1],[\"TESTJ\",\"1404\u002f12\u002f29\",12,\"\u0633\u0627\u0644\u0627\u0646\u0647\",10.0,null,null,null,null,\"\u062b\",null,101,\"1405\u002d02\u002d03\",100.0,99.0,1]],\"instruments\":[[\"IA\",\"TESTA\",\"TESTA\"],[\"IB\",\"TESTB\",\"TESTB\"],[\"IC\",\"TESTC\",\"TESTC\"],[\"ID\",\"TESTD\",\"TESTD\"],[\"IE\",\"TESTE\",\"TESTE\"],[\"IF\",\"TESTF\",\"TESTF\"],[\"IZ\",\"TESTZ\",\"TESTZ\"],[\"IK\",\"TESTK\",\"TESTK\"]],\"watch\":[[\"IA\",14050101],[\"IB\",14050103],[\"IC\",14050108],[\"ID\",14050105],[\"IE\",14050104],[\"IF\",14050102],[\"IZ\",14050108]]}"

const gatesDDL = "CREATE TABLE financial_statements (symbol TEXT, period_end TEXT, " +
	"period_months INTEGER, title TEXT, revenue REAL, gross_profit REAL, " +
	"operating_profit REAL, net_profit REAL, basic_eps REAL, company_name TEXT, " +
	"unit_norm TEXT, tracing_no INTEGER, publish_date TEXT, capital REAL, " +
	"total_equity REAL, has_operating_sales INTEGER);" +
	"CREATE TABLE monthly_sales (symbol TEXT, year INTEGER, month INTEGER, " +
	"monthly_revenue REAL, ytd_revenue REAL, ytd_revenue_prev REAL, period_end TEXT, " +
	"title TEXT);" +
	"CREATE TABLE codal_notices (symbol TEXT);" +
	"CREATE TABLE instruments (ins_code TEXT, l_val18 TEXT, l_val30 TEXT);" +
	"CREATE TABLE price_history (symbol TEXT);" +
	"CREATE TABLE user_watchlists (symbol TEXT);" +
	"CREATE TABLE daily_prices (ins_code TEXT, d_even INTEGER, q_tot_cap REAL);" +
	"CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER);"

// ax45GatesDB بانکِ موقتِ همان ردیف‌ها را می‌سازد (روی دیسکِ موقت، نه `:memory:`
// — ریزولورِ هویت یک اتصالِ اختصاصی نگه می‌دارد و ویندوز فایل را قفل می‌کند).
//
// dikkat: این دادهٔ ساختگی است. راستی‌آزمایی‌نشده با دادهٔ واقعی.
func ax45GatesDB(t *testing.T) *Service {
	t.Helper()
	var data struct {
		FS          [][]any `json:"fs"`
		Instruments [][]any `json:"instruments"`
		Watch       [][]any `json:"watch"`
		Daily       [][]any `json:"daily"`
	}
	if err := json.Unmarshal([]byte(gatesDataJSON), &data); err != nil {
		t.Fatalf("gates data: %v", err)
	}
	conn, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "gates.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	if _, err := conn.Exec(gatesDDL); err != nil {
		t.Fatal(err)
	}
	mustExec := func(q string, args []any) {
		t.Helper()
		if _, err := conn.Exec(q, args...); err != nil {
			t.Fatal(err)
		}
	}
	for _, r := range data.FS {
		mustExec("INSERT INTO financial_statements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", r)
	}
	for _, r := range data.Instruments {
		mustExec("INSERT INTO instruments VALUES (?,?,?)", r)
	}
	for _, r := range data.Watch {
		mustExec("INSERT INTO market_watch VALUES (?,?)", r)
	}
	for _, r := range data.Daily {
		mustExec("INSERT INTO daily_prices VALUES (?,?,?)", r)
	}
	s := New(conn)
	t.Cleanup(func() { _ = s.Close() })
	return s
}

func TestGatesOnTempDB(t *testing.T) {
	// راستی‌آزمایی‌نشده با دادهٔ واقعی — انتظارها از تابع‌های پایتون روی همین
	// ردیف‌های ساختگی سنجیده شده‌اند (اوراکلِ موقت).
	s := ax45GatesDB(t)
	ctx := context.Background()

	wantSessions := []int64{14050108, 14050107, 14050106, 14050105, 14050104, 14050103,
		14050102, 14050101}
	gotSessions, err := s.gtSessions(ctx)
	if err != nil {
		t.Fatal(err)
	}
	ax45Check(t, "market_sessions", fList(wantSessions), ax45Norm(t, gotSessions))

	m141, err := s.M141Map(ctx)
	if err != nil {
		t.Fatal(err)
	}
	ax45Check(t, "m141_map", map[string]any{
		"testa": true, "testb": false, "testc": true, "testd": true, "teste": true,
		"testf": true, "testi": false, "testj": false,
	}, ax45Norm(t, m141))

	liq, err := s.AvgTradeValueHmt(ctx, 30)
	if err != nil {
		t.Fatal(err)
	}
	ax45Check(t, "avg_trade_value_hmt/30", map[string]any{
		"testa": 1.35, "testd": 5.0, "testk": 1.0}, ax45Norm(t, liq))
	all, err := s.AvgTradeValueHmt(ctx, 99)
	if err != nil {
		t.Fatal(err)
	}
	ax45Check(t, "avg_trade_value_hmt/99", map[string]any{
		"testa": 1.35, "testd": 5.0, "testk": 1.0}, ax45Norm(t, all))

	for _, threshold := range []struct {
		n    int
		want map[string]bool
	}{
		{3, map[string]bool{"TESTA": true, "TESTB": true, "TESTC": false, "TESTD": false,
			"TESTK": false, "TESTZ": false, "TESTNOPE": false}},
		{0, map[string]bool{"TESTA": true, "TESTB": true, "TESTD": true, "TESTK": false,
			"TESTZ": false}},
		{9, map[string]bool{"TESTA": false, "TESTB": false, "TESTD": false, "TESTK": false,
			"TESTZ": false}},
	} {
		for sym, want := range threshold.want {
			got, err := s.IsSuspended(ctx, sym, threshold.n, nil)
			if err != nil {
				t.Fatalf("is_suspended %s/%d: %v", sym, threshold.n, err)
			}
			if got != want {
				t.Errorf("is_suspended(%s, %d) = %v want %v", sym, threshold.n, got, want)
			}
		}
	}
	// یکِ نشست ⇒ داوری نمی‌شود (اوراکل `len(sess) < 2` را بی‌رأی می‌گذارد).
	if got, _ := s.IsSuspended(ctx, "TESTA", 3, []int64{14050108}); got != false {
		t.Errorf("single-session suspension = %v want false", got)
	}

	for sym, want := range map[string]bool{"TESTA": true, "TESTB": false, "TESTC": true,
		"TESTD": true, "TESTK": false, "TESTZ": false, "TESTNOPE": false} {
		got, err := s.M141Hit(ctx, sym, nil)
		if err != nil {
			t.Fatal(err)
		}
		if got != want {
			t.Errorf("m141_hit(%s) = %v want %v", sym, got, want)
		}
	}
	for sym, want := range map[string]float64{"TESTA": 0.00135, "TESTB": 0.0, "TESTC": 0.0,
		"TESTD": 0.005, "TESTK": 0.001, "TESTZ": 0.0} {
		got, err := s.TradeValueHmt(ctx, sym, nil)
		if err != nil {
			t.Fatal(err)
		}
		if got != want {
			t.Errorf("trade_value_hmt(%s) = %v want %v", sym, got, want)
		}
	}
	for sym, want := range map[string]string{"TESTA": oracle_s01, "TESTI": oracle_s02,
		"TESTZ": ""} {
		if got := s.a45CompanyNameOf(ctx, sym); got != want {
			t.Errorf("company_name_of(%s) = %q want %q", sym, got, want)
		}
	}
	for sym, want := range map[string]any{"TESTA": int64(1), "TESTI": int64(0),
		"TESTJ": int64(1), "TESTZ": nil} {
		got := s.a45HasOperatingSales(ctx, sym)
		if !sameScalarPy(got, want) {
			t.Errorf("has_operating_sales(%s) = %#v want %#v", sym, got, want)
		}
	}
	// ind4_exempt — شاهدِ نامی، شاهدِ صورتِ مالی، و نقشۀ ازپیش‌ساخته.
	for sym, want := range map[string]bool{"TESTA": false, "TESTI": true,
		"TESTJ": false, "TESTZ": false} {
		if got := s.Ind4Exempt(ctx, sym, "", true, nil); got != want {
			t.Errorf("ind4_exempt(%s) = %v want %v", sym, got, want)
		}
	}
	for sym, want := range map[string]bool{"TESTA": false, "TESTI": false} {
		if got := s.Ind4Exempt(ctx, sym, "", false, nil); got != want {
			t.Errorf("ind4_exempt(holdings_na=false)(%s) = %v want %v", sym, got, want)
		}
	}
	if got := s.Ind4Exempt(ctx, "TESTZ", "", true, map[string]bool{"testz": true}); !got {
		t.Errorf("ind4_exempt(precomputed in) = false want true")
	}
	if got := s.Ind4Exempt(ctx, "TESTZ", "", true, map[string]bool{"other": true}); got {
		t.Errorf("ind4_exempt(precomputed out) = true want false")
	}
	if got := s.Ind4Exempt(ctx, "TESTZ", "", true, map[string]bool{}); got {
		t.Errorf("ind4_exempt(precomputed empty) = true want false — mapِ خالی یعنی «نقشۀ داده‌شده»")
	}
}

func fList(xs []int64) []any {
	out := make([]any, 0, len(xs))
	for _, x := range xs {
		out = append(out, float64(x))
	}
	return out
}

// sameScalarPy مثلِ مقایسهٔ `row[0] == 0` درِ پایتون: nil با هر عددی برابر نیست.
func sameScalarPy(got, want any) bool {
	if want == nil {
		return got == nil
	}
	i, ok := toI(got)
	j, ok2 := toI(want)
	return ok && ok2 && i == j
}

// ── ۱۱) risk_gates روی همان بانک (اوراکل، بی‌وکتور) ──────────────────────────

func TestRiskGatesOracle(t *testing.T) {
	// راستی‌آزمایی‌نشده با دادهٔ واقعی — انتظارها از fd.risk_gatesِ پایتون روی
	// همین ردیف‌های ساختگی سنجیده شده است.
	s := ax45GatesDB(t)
	ctx := context.Background()
	cases := []struct {
		name   string
		sym    string
		sector string
		mcap   float64
		cfg    map[string]any
		want   []string
	}{
		{"base|TESTA", "TESTA", oracle_s03, 4e13, map[string]any{},
			[]string{oracle_s07}},
		{"base|TESTB", "TESTB", oracle_s04, 9e10, map[string]any{},
			[]string{oracle_s07}},
		{"base|TESTD", "TESTD", oracle_s05, 0.0, map[string]any{},
			[]string{oracle_s08}},
		{"base|TESTZ", "TESTZ", "ZZZ", 8e13, map[string]any{}, nil},
		{"m141on|TESTA", "TESTA", oracle_s03, 4e13, map[string]any{"filter_m141": true},
			[]string{oracle_s07, oracle_s09}},
		{"m141on|TESTD", "TESTD", oracle_s05, 0.0, map[string]any{"filter_m141": true},
			[]string{oracle_s08, oracle_s09}},
		{"mcapfloor|TESTA", "TESTA", oracle_s03, 4e13,
			map[string]any{"mcap_min_hmt": 5.0}, []string{oracle_s07, oracle_s10}},
		{"mcapfloor|TESTB", "TESTB", oracle_s04, 9e10,
			map[string]any{"mcap_min_hmt": 5.0}, []string{oracle_s07, oracle_s11}},
		{"mcapfloor|TESTD", "TESTD", oracle_s05, 0.0,
			map[string]any{"mcap_min_hmt": 5.0}, []string{oracle_s08, oracle_s12}},
		{"liq|TESTA", "TESTA", oracle_s03, 4e13, map[string]any{"min_trade_val": 2.0},
			[]string{oracle_s07, oracle_s13}},
		{"liq|TESTB", "TESTB", oracle_s04, 9e10, map[string]any{"min_trade_val": 2.0},
			[]string{oracle_s07, oracle_s14}},
		{"liq|TESTD", "TESTD", oracle_s05, 0.0, map[string]any{"min_trade_val": 2.0},
			[]string{oracle_s08, oracle_s15}},
		{"all|TESTA", "TESTA", oracle_s03, 4e13,
			map[string]any{"filter_m141": true, "mcap_min_hmt": 5.0, "min_trade_val": 2.0},
			[]string{oracle_s07, oracle_s09, oracle_s10, oracle_s13}},
		{"all|TESTB", "TESTB", oracle_s04, 9e10,
			map[string]any{"filter_m141": true, "mcap_min_hmt": 5.0, "min_trade_val": 2.0},
			[]string{oracle_s07, oracle_s11, oracle_s14}},
		{"all|TESTD", "TESTD", oracle_s05, 0.0,
			map[string]any{"filter_m141": true, "mcap_min_hmt": 5.0, "min_trade_val": 2.0},
			[]string{oracle_s08, oracle_s09, oracle_s12, oracle_s15}},
		{"all|TESTZ", "TESTZ", "ZZZ", 8e13,
			map[string]any{"filter_m141": true, "mcap_min_hmt": 5.0, "min_trade_val": 2.0},
			[]string{oracle_s14}},
		{"excludeind|TESTA", "TESTA", oracle_s03, 4e13,
			map[string]any{"industry_mode": oracle_s16, "exclude_industries": oracle_s03},
			[]string{oracle_s07, oracle_s17}},
		{"includeind|TESTA", "TESTA", oracle_s03, 4e13,
			map[string]any{"industry_mode": oracle_s18,
				"include_industries": []string{oracle_s04}},
			[]string{oracle_s07, oracle_s19}},
		{"includeind|TESTD", "TESTD", oracle_s05, 0.0,
			map[string]any{"industry_mode": oracle_s18,
				"include_industries": []string{oracle_s04}},
			[]string{oracle_s08, oracle_s20}},
		{"includeind|TESTZ", "TESTZ", "ZZZ", 8e13,
			map[string]any{"industry_mode": oracle_s18,
				"include_industries": []string{oracle_s04}},
			[]string{oracle_s21}},
		{"bignum|TESTA", "TESTA", oracle_s03, 4e13,
			map[string]any{"mcap_min_hmt": 0.0001, "min_trade_val": 1e-6},
			[]string{oracle_s07}},
		{"bignum|TESTB", "TESTB", oracle_s04, 9e10,
			map[string]any{"mcap_min_hmt": 0.0001, "min_trade_val": 1e-6},
			[]string{oracle_s07, oracle_s14}},
		{"bignum|TESTD", "TESTD", oracle_s05, 0.0,
			map[string]any{"mcap_min_hmt": 0.0001, "min_trade_val": 1e-6},
			[]string{oracle_s08, oracle_s12}},
		{"bignum|TESTZ", "TESTZ", "ZZZ", 8e13,
			map[string]any{"mcap_min_hmt": 0.0001, "min_trade_val": 1e-6},
			[]string{oracle_s14}},
	}
	for _, c := range cases {
		got, err := s.RiskGates(ctx, c.sym, c.sector, c.mcap, c.cfg, nil, nil, nil)
		if err != nil {
			t.Fatalf("risk_gates %s: %v", c.name, err)
		}
		ax45Check(t, "risk_gates "+c.name, strList(c.want), ax45Norm(t, got))
	}
	// تزریقِ نقشه‌ها (الگوی ضدِN+1ِ واچ‌لیست) نباید رأی را عوض کند.
	m141, err := s.M141Map(ctx)
	if err != nil {
		t.Fatal(err)
	}
	liq, err := s.AvgTradeValueHmt(ctx, 30)
	if err != nil {
		t.Fatal(err)
	}
	got, err := s.RiskGates(ctx, "TESTA", oracle_s03, 4e13,
		map[string]any{"filter_m141": true, "min_trade_val": 2.0}, m141, liq,
		IndustryGate(oracle_s03, map[string]any{}))
	if err != nil {
		t.Fatal(err)
	}
	ax45Check(t, "risk_gates injected",
		strList([]string{oracle_s07, oracle_s09, oracle_s13}), ax45Norm(t, got))
}
