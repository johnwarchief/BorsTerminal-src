import sys
import sqlite3
import json

sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect("market.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

SYMBOLS_20 = [
    "فولاد", "فملی", "شستا", "شپنا", "شبندر",
    "شتران", "خودرو", "خساپا", "وبملت", "وتجارت",
    "وبصادر", "فارس", "تاپیکو", "کگل", "کچاد",
    "وغدیر", "ومعادن", "وامید", "رمپنا", "پارس"
]

print("Scanning 20 symbols in market.db...")
results = []
for sym in SYMBOLS_20:
    # Try multiple match strategies: exact l_val18, trimmed, arabic kaf/yeh
    sym_ar = sym.replace('ک', 'ك').replace('ی', 'ي')
    sym_fa = sym.replace('ك', 'ک').replace('ي', 'ی')
    
    rows = cur.execute("""
        SELECT ins_code, l_val18, l_val30, isin 
        FROM instruments 
        WHERE TRIM(l_val18) IN (?, ?, ?) OR TRIM(l_val30) LIKE ? OR TRIM(l_val30) LIKE ?
        ORDER BY updated_at DESC
    """, (sym, sym_ar, sym_fa, f"{sym}%", f"{sym_ar}%")).fetchall()
    
    ins_code = None
    l_val18 = None
    l_val30 = None
    if rows:
        ins_code = rows[0]["ins_code"]
        l_val18 = rows[0]["l_val18"]
        l_val30 = rows[0]["l_val30"]
    
    # Check candles in price_history
    ph_count = cur.execute("SELECT count(*) FROM price_history WHERE symbol IN (?, ?, ?)", (sym, sym_ar, sym_fa)).fetchone()[0]
    
    # Check adjust_events
    ae_rows = cur.execute("SELECT count(*), min(date), max(date) FROM adjust_events WHERE symbol IN (?, ?, ?)", (sym, sym_ar, sym_fa)).fetchone()
    ae_count = ae_rows[0]
    ae_min = ae_rows[1]
    ae_max = ae_rows[2]
    
    # Check share_change_events
    sc_count = 0
    sc_min = None
    sc_max = None
    if ins_code:
        sc_rows = cur.execute("SELECT count(*), min(d_even), max(d_even) FROM share_change_events WHERE ins_code=?", (ins_code,)).fetchone()
        sc_count = sc_rows[0]
        sc_min = sc_rows[1]
        sc_max = sc_rows[2]
        
    # Check price_adjust_events
    pa_count = 0
    pa_min = None
    pa_max = None
    if ins_code:
        pa_rows = cur.execute("SELECT count(*), min(d_even), max(d_even) FROM price_adjust_events WHERE ins_code=?", (ins_code,)).fetchone()
        pa_count = pa_rows[0]
        pa_min = pa_rows[1]
        pa_max = pa_rows[2]

    results.append({
        "symbol": sym,
        "matched_l_val18": l_val18,
        "matched_name": l_val30,
        "ins_code": ins_code,
        "price_history_bars": ph_count,
        "adjust_events": ae_count,
        "adjust_events_range": f"{ae_min}..{ae_max}",
        "share_changes": sc_count,
        "share_changes_range": f"{sc_min}..{sc_max}",
        "price_adjusts": pa_count,
        "price_adjusts_range": f"{pa_min}..{pa_max}",
    })

print(f"{'نماد':<8} | {'کد ابزار':<18} | {'کندل':<6} | {'adj_events':<10} | {'share_chg':<10} | {'price_adj':<10}")
print("-" * 75)
for r in results:
    print(f"{r['symbol']:<8} | {str(r['ins_code']):<18} | {r['price_history_bars']:<6} | {r['adjust_events']:<10} | {r['share_changes']:<10} | {r['price_adjusts']:<10}")

with open("_audit/20_symbols_real_audit.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
