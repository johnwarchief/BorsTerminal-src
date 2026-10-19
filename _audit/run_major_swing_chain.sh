#!/usr/bin/env bash
# _audit/run_major_swing_chain.sh — زنجیرۀ راستی‌آزماییِ مأموریتِ ماژور رویِ یکِ SHA
#
# دو باگی که این نسخه بست (هر دو درِ همین دور رخ داد و درِ سند ثبت شده است):
#  ۱) مسیرِ لاگِ نسبی: نسخهٔ اول بعد ازِ `cd frontend` لاگ را با `_scratch/live/...`
#     می‌نوشت، پس tsc/vitest/lint/build با «No such file or directory» افتادند و
#     EXIT=1 *بی‌اجرایِ فرمان* ثبت شد. حالا همه‌چیز با مسیرِ مطلقِ $LOG است.
#  ۲) تداخلِ دورها: دو زنجیره هم‌زمان درِ یکِ `chain_exits.txt` می‌نوشتند و
#     ۴۰ سوئیت باتری با rc=3221225794 (STATUS_DLL_INIT_FAILED) مردند؛ از لاگِ
#     مشترک نمی‌شد فهمید کدام سطر به کدام SHA است. هر دور حالا پوشۀِ لاگِ خودش را
#     دارد: `_scratch/live/run_<sha>_<زمان>/` و هیچ دوری سطرِ دورِ دیگر را نمی‌بیند.
#
# هیچ گامی «PASS» اعلام نمی‌شود مگر با EXIT=0 درِ لاگِ *همان دور*.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHA="$(git -C "$ROOT" rev-parse HEAD)"
STAMP="$(date +%Y%m%dT%H%M%S)"
LOG="$ROOT/_scratch/live/run_${SHA:0:8}_${STAMP}"
mkdir -p "$LOG" || exit 9
cd "$ROOT" || exit 9
{
  echo "CHAIN_SHA=$SHA"
  echo "CHAIN_START=$(date -Is)"
  echo "branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "LOG_DIR=$LOG"
} | tee "$LOG/chain_head.txt"
: > "$LOG/chain_exits.txt"
EX="$LOG/chain_exits.txt"

echo "== 1) python dev/run_all_tests.py =="
PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 python dev/run_all_tests.py > "$LOG/chain_all_tests.log" 2>&1
echo "ALL_TESTS_EXIT=$?" | tee -a "$EX"

cd "$ROOT/frontend" || exit 9
echo "== 2) npx tsc -b =="
npx tsc -b > "$LOG/chain_tsc.log" 2>&1
echo "TSC_EXIT=$?" | tee -a "$EX"

echo "== 3) npx vitest run =="
npx vitest run > "$LOG/chain_vitest.log" 2>&1
echo "VITEST_EXIT=$?" | tee -a "$EX"

echo "== 4) npm run lint =="
npm run lint > "$LOG/chain_lint.log" 2>&1
echo "LINT_EXIT=$?" | tee -a "$EX"

echo "== 5) npm run build =="
npm run build > "$LOG/chain_build.log" 2>&1
echo "BUILD_EXIT=$?" | tee -a "$EX"

cd "$ROOT"
echo "== 6) گاردهای قرارداد (صریح، جدا از باتری) =="
PYTHONIOENCODING=utf-8 python dev/price_basis_v1070.py > "$LOG/chain_basis.log" 2>&1
echo "BASIS_EXIT=$?" | tee -a "$EX"
PYTHONIOENCODING=utf-8 python dev/db_candle_contract_v1.py > "$LOG/chain_candle.log" 2>&1
echo "CANDLE_EXIT=$?" | tee -a "$EX"
PYTHONIOENCODING=utf-8 python dev/version_anchor_guard.py > "$LOG/chain_anchor.log" 2>&1
echo "ANCHOR_EXIT=$?" | tee -a "$EX"

echo "== 7) سوئیتِ این مأموریت (صریح، برایِ سطرِ جدا درِ سند) =="
PYTHONIOENCODING=utf-8 python dev/major_swing_trend_v1.py > "$LOG/chain_major_swing.log" 2>&1
echo "MAJOR_SUITE_EXIT=$?" | tee -a "$EX"
PYTHONIOENCODING=utf-8 python dev/fts_trend_fixtures_v1075.py > "$LOG/chain_fixtures.log" 2>&1
echo "FIXTURES_EXIT=$?" | tee -a "$EX"
PYTHONIOENCODING=utf-8 python dev/test_rule_map_citations.py > "$LOG/chain_rulemap.log" 2>&1
echo "RULEMAP_EXIT=$?" | tee -a "$EX"

echo "CHAIN_END=$(date -Is)" | tee -a "$EX"
cat "$EX"
