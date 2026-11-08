# Research References — Opportunity Center

> همهٔ منابع بیرونی در **2026-11-08** دسترسی داده شده‌اند. لایهٔ اعتبار هر منبع ذکر شده است.
> ادعای فروشنده (Vendor Claim) از رفتار مستندشده (Official Docs) و از مشاهدهٔ مستقل (Independent) جدا می‌شود.

## لایه‌های اعتبار

| لایه | معنا |
|---|---|
| **Official Docs** | مستند رسمی محصول/نهاد؛ رفتار قابل استناد، اما ممکن است بازاریابی باشد. |
| **Peer-reviewed / Primary** | مقالهٔ داوری‌شده یا منبع اولیهٔ علمی. |
| **Secondary** | خبر/رسانه/دانشنامه؛ برای زمینه و تاریخ مفید، نه اثبات فنی. |
| **Vendor Claim** | ادعای خود محصول؛ بدون بازتولید پذیرفته نمی‌شود. |
| **Repo Evidence** | کد/داده/سند همین مخزن در مبنا `da6d6177`. |

---

## ۱) منابع بیرونی

| ID | منبع | ناشر/نویسنده | سال | نشانی | کاربرد | لایه |
|---|---|---|---|---|---|---|
| R1 | QuantConnect LEAN | QuantConnect | — | https://github.com/quantconnect/lean | معماری موتور و داده | Official Docs |
| R2 | Walk-Forward Optimization | QuantConnect | — | https://www.quantconnect.com/docs/v2/writing-algorithms/optimization/walk-forward-optimization | WF مستند | Official Docs |
| R3 | Research Guide | QuantConnect | — | https://www.quantconnect.com/docs/v1/key-concepts/research-guide | انضباط پژوهش و Overfitting | Official Docs |
| R4 | Composer | Composer | — | https://www.composer.trade/ | Symphony، کتابخانه و اجرای خودکار | Vendor Claim (دسترسی خودکار 403) |
| R5 | Portfolio Visualizer | Portfolio Visualizer | — | https://www.portfoliovisualizer.com/backtest-portfolio · https://www.portfoliovisualizer.com/faq | منشأ داده، فرضی، بهینه‌سازی وزن | Official Docs |
| R6 | Strategy Tester / Pine | TradingView | — | https://www.tradingview.com/pine-script-docs/concepts/strategies/ | Repaint/Lookahead، کمیسیون/اسلیپیج | Official Docs |
| R7 | Deep Backtesting | TradingView | — | https://www.tradingview.com/support/solutions/43000666265-how-deep-backtesting-works/ | محدودیت‌های بک‌تست عمیق | Official Docs |
| R8 | MT5 Strategy Tester | MetaQuotes | — | https://www.metatrader5.com/en/automated-trading/strategy-tester | Forward period، مدل پرشدن | Official Docs |
| R9 | MT5 Optimization | MetaQuotes | — | https://www.metatrader5.com/en/terminal/help/algotrading/strategy_optimization | ژنتیک/ brute force و ریسک | Official Docs |
| R10 | vectorbt Upgrade | vectorbt | — | https://vectorbt.dev/getting-started/upgrade/ | Split و Heatmap در PRO | Official Docs |
| R11 | QuantRocket Machine Learning | QuantRocket | — | https://www.quantrocket.com/machine-learning/ | WF برای ML | Official Docs |
| R12 | QuantRocket Docs | QuantRocket | — | https://www.quantrocket.com/docs/ | داده و Credential محلی | Official Docs |
| R13 | Rahavard365 Wiki — Replay | Rahavard365 | — | https://rahavard365.com/wiki/10617/ | Replay دستی، بدون مستند بک‌تست خودکار | Official Docs |
| R14 | Allen & Karjalainen, “Using genetic algorithms to find technical trading rules” | JFE | 1999 | https://www.sciencedirect.com/science/article/pii/S0304405X9800052X | GP و نبود edge پس از هزینه در OOS | Peer-reviewed |
| R15 | Koza, *Genetic Programming* | MIT Press | 1992 | https://mitpress.mit.edu/9780262527910/genetic-programming/ | زمینهٔ GP | Primary |
| R16 | Schmidt & Lipson, “Distilling free-form natural laws…” | Science | 2009 | https://www.science.org/doi/10.1126/science.1165893 | Symbolic Regression در علوم | Peer-reviewed |
| R17 | Cranmer et al., “Discovering symbolic models…” | NeurIPS | 2020 | https://arxiv.org/abs/2006.11287 | اسطوره‌زدایی/توان SR | Peer-reviewed |
| R18 | Cranmer, PySR | arXiv | 2023 | https://arxiv.org/abs/2305.01582 | پیاده‌سازی SR | Preprint |
| R19 | Bailey et al., “Pseudo-mathematics and financial charlatanism” | Notices AMS | 2014 | https://www.ams.org/notices/201405/rnoti-p458.pdf | تعداد آزمایش و شانس | Peer-reviewed |
| R20 | Bailey & López de Prado, “The Deflated Sharpe Ratio” | JPM | 2014 | https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf | DSR | Peer-reviewed |
| R21 | Bailey et al., “The Probability of Backtest Overfitting” | J. Computational Finance | 2017 | https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf | PBO/CSCV | Peer-reviewed |
| R22 | Harvey, Liu & Zhu, “…and the Cross-Section of Expected Returns” | RFS | 2016 | https://academic.oup.com/rfs/article/29/1/5/1843824 | آستانهٔ آزمون و Factor Zoo | Peer-reviewed |
| R23 | Sullivan, Timmermann & White, “Data-Snooping…” | Journal of Finance | 1999 | https://www.jstor.org/stable/222500 | Reality Check در قواعد تکنیکال | Peer-reviewed |
| R24 | White, “A Reality Check for Data Snooping” | Econometrica | 2000 | https://onlinelibrary.wiley.com/doi/abs/10.1111/1468-0262.00152 | RC/SPA | Peer-reviewed |
| R25 | Pardo, *The Evaluation and Optimization of Trading Strategies* | Wiley | 2008 | https://onlinelibrary.wiley.com/doi/book/10.1002/9781119196969 | Walk-Forward | Primary |
| R26 | Arnott, Harvey & Markowitz, “A Backtesting Protocol…” | JFDS | 2019 | https://people.duke.edu/~charvey/Research/Published_Papers/G138_A_backtesting_protocol.pdf | پروتکل بک‌تست | Peer-reviewed |
| R27 | Israel, Kelly & Moskowitz, “Can Machines ‘Learn’ Finance?” | JOIM | 2020 | https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking-2Q19-Can-Machines-Learn-Finance.pdf | محدودیت ML مالی | Industry Research |
| R28 | Gu, Kelly & Xiu, “Empirical Asset Pricing via Machine Learning” | RFS | 2020 | https://academic.oup.com/rfs/article/33/5/2223/5758276 | ML و R² خارج‌نمونه | Peer-reviewed |
| R29 | Lo, Mamaysky & Wang, “Foundations of Technical Analysis” | Journal of Finance | 2000 | https://www.nber.org/papers/w7613 | الگوهای تکنیکال | Peer-reviewed |
| R30 | La Malfa et al., “Distilling Financial Models by Symbolic Regression” | Discovery Science | 2021 | https://dl.acm.org/doi/10.1007/978-3-030-95470-3_38 | شکنندگی SR در مالی | Peer-reviewed |
| R31 | Alpha-GPT | arXiv | 2023 | https://arxiv.org/abs/2308.00016 | LLM alpha mining | Preprint |
| R32 | AlphaAgent | arXiv/ACM | 2025 | https://arxiv.org/abs/2502.16789 | LLM alpha mining | Preprint |
| R33 | R&D-Agent-Quant | arXiv | 2025 | https://arxiv.org/abs/2505.15155 | LLM research agent | Preprint |
| R34 | AlphaForge | arXiv | 2024 | https://arxiv.org/abs/2406.18394 | ترکیب عامل/تولید | Preprint |
| R35 | Brock, Lakonishok & LeBaron, “Simple Technical Trading Rules…” | Journal of Finance | 1992 | https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1992.tb04681.x | شواهد اولیهٔ قواعد تکنیکال | Peer-reviewed |
| R36 | خبر تغییر دامنه — SEO | سازمان بورس | — | https://service.seo.ir/news/72635 | دامنهٔ نوسان (متناقض با منابع دیگر) | Official/Secondary |
| R37 | دستورالعمل معاملات بورس | بورس تهران | — | https://www.parsianbroker.com/Files/ParsianBroker/Media/ParsianBroker/Parsian-Broker/قوانین%20و%20مقررات%20معاملات/دستور-العمل-معاملات-در-بورس.pdf | اولویت قیمت/زمان و صف | Official (PDF) |
| R38 | دستورالعمل معاملات — نسخهٔ NIBB | NIBB | — | https://nibb.ir/menu/detail/2205/?langid=1065 | مادهٔ ۱۴ و قواعد صف | Secondary |
| R39 | دامنهٔ نوسان | خانِ سرمایه | — | https://khanesarmaye.com/swing-range/ | دامنهٔ ۷٪/۱۰٪/۳٪ و صندوق‌ها | Secondary |
| R40 | کارمزد و مالیات | خانِ سرمایه | — | https://khanesarmaye.com/transaction-fees/ | کارمزد خرید/فروش + مالیات | Secondary |
| R41 | تسویه | خانِ سرمایه | — | https://khanesarmaye.com/trade-settlement/ | T+2 سهام/ETF | Secondary |
| R42 | ساعات معاملات | خانِ سرمایه | — | https://khanesarmaye.com/stock-exchange-trading-hours/ | ساعات و حراج | Secondary |
| R43 | کارمزد و مالیات | ManafinTech | — | https://manafintech.com/blog/trading-fees-and-taxes/ | مصوبهٔ ۶۱۴۳۶ و نرخ‌های نامتقارن | Secondary |
| R44 | دامنهٔ صندوق‌های اهرمی | Borna | — | https://borna.news/fa/news/2411811 | دامنهٔ ۶٪ صندوق اهرمی | Secondary |
| R45 | ساعات معاملات | IRNA | — | https://www.irna.ir/news/86172345 | ساعت ۰۹:۰۰–۱۲:۳۰ از ۱۴۰۵-۰۶-۱۶ | Secondary |
| R46 | Reopening 2026 | Al Jazeera | 2026 | https://www.aljazeera.com/economy/2026/5/20/controlled-reopening-ends-irans-lengthy-stock-market-shutdown | توقف طولانی و بازگشایی کنترل‌شده | Secondary |
| R47 | T+2 | Finextra | 2018 | https://www.finextra.com/pressarticle/72400/tehran-stock-exchange-moves-t2 | تسویهٔ T+2 | Secondary |
| R48 | تغییر دامنه | دنیای اقتصاد | — | https://donya-e-eqtesad.com/ | تاریخ تغییر دامنه | Secondary |
| R49 | توقف و Circuit Breaker | Agah | — | https://pedia.agah.com/article/what-is-circuit-breaker-trading | توقف/بازگشایی | Secondary |
| R50 | دامنهٔ ±۳٪ | IRNA | — | https://www.irna.ir/news/85588578/ | دامنهٔ ۱۴۰۴ | Secondary |
| R51 | Tehran Stock Exchange | Wikipedia | — | https://en.wikipedia.org/wiki/Tehran_Stock_Exchange | تعداد شرکت‌ها (زمینه) | Secondary |
| R52 | 50 million stakeholders | Amwaj | 2021 | https://amwaj.media/article/how-iran-created-50m-new-market-stakeholders | ساختار خرده‌فروش | Secondary |

> **هشدار دسترسی:** Composer در 2026-11-08 به Fetch خودکار 403 داد؛ ادعاهای آن از متن ایندکس‌شده نقل شده و **Vendor Claim** است. رهاورد ۳۶۵ فقط صفحهٔ عمومی Replay در دسترس بود؛ هیچ مدرک عمومی از بک‌تست/WF خودکار پیدا نشد.

---

## ۲) شواهد مخزن (مبنا `da6d6177`)

| ID | مسیر | چه چیزی را ثابت می‌کند | لایه |
|---|---|---|---|
| S1 | `frontend-v2/src/app/App.tsx:11-24` | مسیرهای زندهٔ پوستهٔ v2 | تأییدشده |
| S2 | `frontend-v2/src/app/shell/Sidebar.tsx:11-27` | گروه «کشف فرصت» و مقاصد غیرفعال | تأییدشده |
| S3 | `backend-go/internal/httpapi/routes.json` | ۱۴۲ مسیر Python در فهرست | تأییدشده |
| S4 | `backend-go/internal/httpapi/server.go` | الگوی 501 برای مسیرهای پورت‌نشده | تأییدشده |
| S5 | `backend-go/internal/db/db.go:67-130` | `market.db`/`codal.db` فقط‌خواندنی؛ `user.db` نوشتنی | تأییدشده |
| S6 | `backend-go/internal/tsetmc/lock.go` | قفل تک‌نویسندهٔ producer | تأییدشده |
| S7 | `backend-go/cmd/borsd`، `cmd/bors-producer` | دو باینری هدف | تأییدشده |
| S8 | `backtest_engine.py:67-99` | `BarView` و پروتکل `Strategy`/`Signal` | تأییدشده |
| S9 | `backtest_engine.py:287-338` | اجرای سیگنال دیروز در بازگشایی امروز | تأییدشده |
| S10 | `trade_sim.py:53-58` | CostModel پیش‌فرض ۳۰bp/۱۰bp/۲٪ | تأییدشده |
| S11 | `trade_sim.py:190-297` | منطق پرشدن، دامنه، سقف حجم، نبود صف/T+2 | تأییدشده |
| S12 | `mstat_engine.py:82-102` | گیت ساعت/روز معاملاتی | تأییدشده |
| S13 | `docs/research/STRATEGY-FTS-READ-ONLY-AUDIT-2026-10-17.md:284-310` | شکاف‌های DSL/ذخیره‌سازی/بولینگر/سیگنال ژورنال | سند |
| S14 | `docs/plans/strategy-unification-plan.md:9-36` | سه موتور داوری و چهار استور | سند |
| S15 | `docs/research/MULTI-ALGORITHM-PLATFORM-ARCHITECTURE.md` | هفت مؤلفه، Slot Grammar، ExperimentManifest، DSR/RC | سند |
| S16 | `docs/research/LOCAL-ALGORITHMIC-LEARNING-ARCHITECTURE.md` | هفت لایه، Feature Store، PIT، پایش drift، فازبندی | سند |
| S17 | `docs/research/ALGORITHMIC-RESEARCH-ENGINE-SPEC.md` | سه‌لایهٔ موتور، قرارداد سیگنال، ۵ استراتژی، WF | سند |
| S18 | `docs/fts-notes/OWNER_RULINGS.md` | رأی‌های مالک دربارهٔ FTS | مالک |
| S19 | `docs/FTS-RULE-ALGORITHM-MAP.md` | نگاشت قاعده → الگوریتم → ترسیم | سند |
| S20 | `docs/CANDLE-CONTRACT.md` | قرارداد کندل و لنگر تعدیل | سند |
| S21 | `docs/RAHAVARD-CANDLE-ADJUSTMENT-PARITY-1405-07-20.md` | سنجش تعدیل و شکاف‌ها | سنجیده |
| S22 | `docs/TSETMC-DATA-GAP-MATRIX.md` | شکاف‌های داده (صف، توقف، PIT) | سنجیده |
| S23 | `docs/TAPE_FILTERS_VS_SOURCES_1405-07-18.md:51` | هم‌ارزی `allowed_*` با `psGelSta*` | سنجیده |
| S24 | `docs/STAGE2-FINAL-ACCEPTANCE-AND-STAGE3-READINESS.md` | پذیرش Stage 2 و آمادگی Stage 3 | سند |
| S25 | `docs/STAGE3-GO-DATA-PRODUCERS-FINAL-REPORT.md` | بستن Stage 3 | سند |
| S26 | `BorsTerminal-Desktop-Migration-Decisions.md` | تصمیم‌های مرجع مهاجرت (بند ۱۰ افزوده شد) | مالک |
| S27 | `docs/ML-ENGINE-ROADMAP.md` | ML بلندمدت؛ FTS جایگزین نمی‌شود | سند |
| S28 | `docs/research/STRATEGY-TREE-5PAGES-2026-10-19.md` | درخت پنج‌صفحه‌ای (خارج از محدوده) | سند |
| S29 | `docs/README.md` | تقدم منابع و هشدار اسناد تاریخ‌دار | سند |
| S30 | `DESIGN.md` | هویت بصری و قرارداد پذیرش | مالک/سند |

---

## ۳) تعارض‌ها و چیزهای نامعلوم

| موضوع | تعارض/شکاف | تصمیم این فاز |
|---|---|---|
| دامنهٔ نوسان | ۷٪/۱۰٪/۳٪/۶٪/۲٪ در منابع مختلف؛ تاریخ اعمال روشن نیست | استفاده از فیلد هر نشست؛ درصد ثابت ممنوع؛ تاریخ‌گذاری لازم |
| کارمزد | ۳۰bp کد؛ ۰٫۳۷۱٪ خرید و ۰٫۸۸۰٪ فروش در سند پژوهشی؛ ۰٫۳۴۵۶٪/۰٫۳۵۳۶٪+۰٫۵٪ مالیات در منبع دیگر؛ ۰٫۴۶۴٪/۰٫۹۶۴٪ در منبع سوم | مدل نامتقارن و تاریخ‌دار؛ آستانه رأی مالک (Q3) |
| ساعت معاملات | کد ۰۸:۵۵–۱۳:۰۰؛ منبع رسمی/خبری ۰۹:۰۰–۱۲:۳۰ از ۱۴۰۵-۰۶-۱۶؛ پیش‌حراج/حراج پایانی متفاوت | گیت کد و منبع رسمی جدا ثبت شوند؛ استراتژی درون‌روزی خارج از دامنه |
| تسویه | T+2 سهام/ETF؛ T+1 بدهی | قفل نقدی T+2 در مدل اجرا؛ جزئیات در فاز ۲ |
| PIT بنیادی | `publish_date` در داده هست اما فیلتر `<= as_of` در کوئری FTS نیست؛ `as_of` رابط، زمان منبع است نه برش بازپخش | لایهٔ PIT پیش‌نیاز اعتبارسنجی بنیادی |
| صف | عمق تاریخی و Order ID وجود ندارد؛ اسنپ‌شات ۵ سطح | پیش‌فرض «عدم پرشدن در صف قفل»؛ مدل تهاجمی ممنوع |
| مالیات/توقف/نماد | تاریخچهٔ توقف و Alias کامل نیست | ثبت رویداد به‌صورت Forward؛ ادعای تاریخی ممنوع |
| رهاورد | بک‌تست خودکار عمومی مستند نشده | هیچ ادعای اعتبارسنجی رهاورد پذیرفته نشود |
| Composer | دسترسی خودکار 403 | فقط ادعای فروشنده؛ در جدول با برچسب مشخص |

---

## ۴) نگاشت منبع به ادعاهای کلیدی

| ادعا | منابع |
|---|---|
| Walk-forward در LEAN/MT5 مستند است | R2، R8، R25 |
| تعدیل آزمون‌های مکرر در محصولات بررسی‌شده مستند نیست | R1–R13 (نبود شاهد)؛ R19–R24 (روش‌ها) |
| GP بدون هزینه در OOS مزیت پایدار ندارد | R14 |
| Symbolic Regression در مالی شکننده است | R16، R17، R30 |
| ML مالی signal-to-noise پایین دارد | R27، R28 |
| LLM alpha mining نوپاست | R31–R33 |
| تعداد آزمایش، DSR/PBO را تعیین می‌کند | R19، R20، R21، R24 |
| صف بر اساس قیمت سپس زمان است | R37، R38 |
| کارمزد نامتقارن و تاریخ‌دار است | R40، R43 |
| T+2 وجود دارد | R41، R47 |
| دامنهٔ نوسان رژیمی و متناقض است | R36، R39، R44، R48، R50 |
| بک‌تست فعلی خوش‌بینانه است | S10، S11، S22 |
| Strategy/Experiment/Opportunity وجود ندارد | S13، S14، بازبینی schema |
| FTS کانونیکال و رأی‌محور است | S18، S19، S26 |
| Stage 3 کامل و Stage 4 در جریان است | S24، S25، `git` |
