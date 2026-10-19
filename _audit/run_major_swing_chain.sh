#!/usr/bin/env bash
# _audit/run_major_swing_chain.sh — زنجیرۀ راستی‌آزماییِ مأموریتِ ماژور رویِ یکِ SHA
#
# چرا این فایل درِ `_audit/` است (نه `_scratch/`): نسخهٔ اولِ همین اسکریپت بعد از
# `cd frontend` مسیرِ *نسبی* لاگ را نگه داشت و هر چهار گامِ فرانت با
# «No such file or directory» افتادند — یعنی EXIT=1 که هیچ وقت آن فرمان‌ها را
# اجرا نکرده بود. اسکریپتِ tracked این اشکال را با مسیر مطلق ندارد و متنِ این
# توضیح خودش شاهدِ رفع است.
#
# هیچ گامی «PASS» اعلام نمی‌شود مگر با EXIT=0 درِ لاگ. خروجی‌ها به
# `_scratch/live/` می‌روند (خارج از Git) و سندِ نهایی از همین لاگ‌ها عدد می‌خواند.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/_scratch/live"
mkdir -p "$LOG"
cd "$ROOT" || exit 9
{
  echo "CHAIN_SHA=$(git rev-parse HEAD)"
  echo "CHAIN_START=$(date -Is)"
  echo "branch=$(git rev-parse --abbrev-ref HEAD)"
} | tee "$LOG/chain_head.txt"
: > "$LOG/chain_exits.txt"

echo "== 1) python dev/run_all_tests.py =="
PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 python dev/run_all_tests.py > "$LOG/chain_all_tests.log" 2>&1
echo "ALL_TESTS_EXIT=$?" | tee -a "$LOG/chain_exits.txt"

cd "$ROOT/frontend" || exit 9
echo "== 2) npx tsc -b =="
npx tsc -b > "$LOG/chain_tsc.log" 2>&1
echo "TSC_EXIT=$?" | tee -a "$LOG/chain_exits.txt"

echo "== 3) npx vitest run =="
npx vitest run > "$LOG/chain_vitest.log" 2>&1
echo "VITEST_EXIT=$?" | tee -a "$LOG/chain_exits.txt"

echo "== 4) npm run lint =="
npm run lint > "$LOG/chain_lint.log" 2>&1
echo "LINT_EXIT=$?" | tee -a "$LOG/chain_exits.txt"

echo "== 5) npm run build =="
npm run build > "$LOG/chain_build.log" 2>&1
echo "BUILD_EXIT=$?" | tee -a "$LOG/chain_exits.txt"

cd "$ROOT"
echo "== 6) گاردهای قراردادِ مبنایِ قیمت و کندل (صریح، جدا از باتری) =="
PYTHONIOENCODING=utf-8 python dev/price_basis_v1070.py > "$LOG/chain_basis.log" 2>&1
echo "BASIS_EXIT=$?" | tee -a "$LOG/chain_exits.txt"
PYTHONIOENCODING=utf-8 python dev/db_candle_contract_v1.py > "$LOG/chain_candle.log" 2>&1
echo "CANDLE_EXIT=$?" | tee -a "$LOG/chain_exits.txt"
PYTHONIOENCODING=utf-8 python dev/version_anchor_guard.py > "$LOG/chain_anchor.log" 2>&1
echo "ANCHOR_EXIT=$?" | tee -a "$LOG/chain_exits.txt"

echo "CHAIN_END=$(date -Is)" | tee -a "$LOG/chain_exits.txt"
cat "$LOG/chain_exits.txt"
