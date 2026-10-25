-- Round 30 session-anomaly migration (isolated DB only; do not apply to the operational DB in this mission)
-- source: artifacts/ra365/r30/cross-section-gaps.csv via tools/session_anomaly_scan.py
-- rule: official_symbols==0 AND product_only_steps>=10 AND median_abs_ratio_deviation<=0.02
INSERT OR REPLACE INTO session_anomalies(d_even,gap_symbols,official_symbols,product_only_steps,median_abs_ratio_deviation,cause,evidence,built_at) VALUES (20230328,31,0,32,0.015967,'MARKET_WIDE_SESSION_DIFFERENCE','gap_symbols=31;official=0;steps=32;mad=0.015967','2026-10-25');
