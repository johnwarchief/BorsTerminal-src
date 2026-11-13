# جدول قابلیت استفادهٔ داده‌ها برای هر موتور BorsTerminal — Phase 4.9.7

مبتنی بر شواهد کد (file:line). PRICE-ONLY = از Technical DB (کندل رهاورد) قابل تغذیه. NEEDS-FUNDAMENTAL/FLOW = نیازمند CODAL/TSETMC (در آرشیو رهاورد نیست).

| موتور | وجود | دستهٔ نیاز | ورودی واقعی | شواهد | منبع دادهٔ پیشنهادی |
|---|---|---|---|---|---|
| Technical Engine | موجود | PRICE-ONLY | price_history (date,close,volume,last)؛ indicators SMA/EMA/RSI/MACD/Bollinger/ATR؛ adjust_events | backend-go/internal/chart/chartdb.go:465؛ indicators/indicators.go:9-193؛ api/chart.py:3130 | Technical DB (candle + adjustment) |
| FTS (لایهٔ setup/pattern) | موجود | PRICE-ONLY | کندل روزانه؛ W/M با resample؛ trend/fib/jet/choch/point_hunt/double_bottom/range_box/pullback | api/chart.py:5610-5643؛ backend-go/internal/chart/fts_analyze.go:338 | Technical DB |
| FTS (موتور ۵ شاخصهٔ canonical) | موجود | NEEDS-FUNDAMENTAL/FLOW | monthly_sales، financial_statements، instruments(sector/total_shares)، market_watch(p_closing) | fts_engine.py:5-9 | Other Market Data DB (CODAL/TSETMC) |
| Fundamental Analysis | موجود | NEEDS-FUNDAMENTAL/FLOW | monthly_sales، financial_statements، market_watch+instruments(mcap)، codal_notices.publish_date، EPS | api/fundamental.py:509,680,337؛ backend-go/internal/fundamental/axis1.go:387؛ axis2.go:919 | Other Market Data DB (CODAL) |
| Market Intelligence (mstat) | موجود (هم‌نام نیست) | NEEDS-FUNDAMENTAL/FLOW | market_watch، client_type(حقیقی/حقوقی)، blDs(عمق ۵ سطح)، mstat_snap؛ smartmoney buckets | mstat_engine.py:10-22؛ backend-go/internal/mstat/frame.go:244؛ smartmoney.go:25-57 | Other Market Data DB (TSETMC)؛ turnover/breadth از Technical |
| Adaptive Signal Intelligence | یافت نشد (نام) | MIXED | نزدیک‌ترین: confidence_engine (conf_tech از price_history، conf_tape از client_type+market_watch، conf_fund از fts)؛ bot_signals از verdict funnel | confidence_engine.py:7-9؛ bot_signals.py:12-14؛ worker/cadence.go:51 (adaptive polling) | Technical + Other (هر دو) |
| Market Forecasting | موجود | PRICE-ONLY | closes، timestamps، avgDailyValue؛ Kronos neural یا autoregressive Monte-Carlo؛ liquidity guard از value/volume×close | backend-go/internal/prediction/prediction_engine.go:43-49؛ autoregressive_fallback.go:66؛ chart/handlers.go:133-148 | Technical DB |
| Regime Detection | قطعات موجود (رسمی planned) | PRICE-ONLY (قطعات) | candleedge: TRENDING_BULL/BEAR/RANGING از ساختار کندل؛ trend_classify: ATR-normalized slope/MA/pivots؛ regime کلان ۵حالته planned→mstat | backend-go/internal/candleedge/edge_metrics.go:191-196؛ trend_classify.py:9-32؛ docs/ML-ENGINE-ROADMAP.md:127-138 | Technical DB (قطعات)؛ regime کلان→Other |
| Volatility Modeling | مستقل ندارد | PRICE-ONLY | درون موتورهای دیگر: ATR/Bollinger، volatility_amplification(prediction)، annualised_volatility(backtest returns) | indicators.go:161,193؛ prediction_engine.go:38؛ backtest_engine.py:410 | Technical DB |
| Portfolio Management | موجود | MIXED | selection_decisions(weight/price/qty/score/sector)؛ instruments+mstat.Classify(asset class)؛ weight=price×qty؛ verdict بالادست از FTS/funnel | backend-go/internal/selection/portfolio.go:78-86,328-352,227-238 | Technical (قیمت) + Shared (metadata) + verdict بالادست |

## جمع‌بندی
- **موتورهای کاملاً قیمت‌محور** (Technical، FTS-setup، Forecasting، قطعات Regime، Volatility): تماماً از **Technical DB** (کندل + تعدیل + تقویم + metadata نماد) تغذیه می‌شوند — همه از رهاورد موجود است.
- **موتورهای بنیادی/جریان** (Fundamental، mstat/Market Intelligence، confidence/Adaptive Signal، گیت بنیادی FTS): نیازمند **Other Market Data DB** از CODAL/TSETMC — **در آرشیو رهاورد موجود نیست**.
- **Portfolio**: قیمت از Technical + metadata از Shared + verdict بالادست (FTS/funnel) → وابستگی ترکیبی.
- **پیامد**: جداسازی Technical DB فوراً همهٔ موتورهای قیمت‌محور را پوشش می‌دهد؛ تکمیل Other Market Data DB منوط به CODAL/TSETMC (موجود) + استخراج آیندهٔ top-lists رهاورد است.