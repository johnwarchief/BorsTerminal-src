# گزارش جامع نهایی — Opportunity Center (فازهای ۱ تا ۴)

> **تاریخ:** 2026-11-08 · **شاخه:** `mission/opportunity-center-design-2026-11-08` · **مبنا:** `da6d6177` (نوک Stage 3) · **مبنای معماری:** Stage 4 پذیرفته‌شده `11f4b128` (ادغام‌شده در `9c3676d4`)
> **وضعیت:** طراحی فازهای ۱ تا ۴ تکمیل شد. هیچ کد Runtime، API عملیاتی، مدل AI، تغییر FTS، انتشار نسخه یا ادغام در `main` انجام نشد.
> **حکم:** `PHASE4_DESIGN_COMPLETE_RUNTIME_NOT_STARTED`

---

## ۱) خلاصهٔ اجرایی

این مأموریت یک طرح کامل برای «مرکز فرصت / آزمایشگاه فرصت» تولید کرد: از کشف محصول و مدل استراتژی تا رابط کاربری قابل‌بازبینی و معماری فنی روی واقعیت پذیرفته‌شدهٔ Stage 4. خروجی، سند طراحی است، نه پیاده‌سازی. هر ادعای مربوط به رفتار امروزِ کد با مسیر و خط مشخص شده و هر انتخاب طراحی که هنوز تأیید مالک ندارد، صریح «پیشنهادی» یا «نیازمند رأی» مانده است.

سه نتیجهٔ اصلی:

1. **مرز مالکیت روشن شد:** آموزش، تکامل، تأیید و انتشار Stable فقط در Research Workbench مالک انجام می‌شود؛ کلاینت سه کاربر فقط نسخه‌های تأییدشده را می‌بیند و Lab آن فقط‌خواندنی است.
2. **زنجیرهٔ اعتماد و توزیع تعریف شد:** `oc.strategy/1` → `oc.bundle/1` → `oc.approval/1` → `oc.registry/1` با امضای Minisign، نصب اتمیک، Rollback، حالت آفلاین و Revocation. Registry خصوصی روی GitHub Private Releases است و هیچ سرور دائمی یا هزینهٔ میزبانی مستمر مفروض نیست.
3. **شکاف‌های Stage 4 پنهان نشدند:** «اعمال نسل» با «سرو نسل» یکی نیست؛ Producer هر `.db` را اسنپ‌شات می‌کند؛ چند مسیر Sync/Update پاسخ موفق بدون انجام کار می‌دهند. این‌ها به‌عنوان دروازه‌های P0 ثبت شده‌اند، نه فرض‌های نادرست.

---

## ۲) خروجی‌های تحویل‌شده

| فاز | سند / مصنوع | وضعیت | شاهد |
|---|---|---|---|
| ۱ — Product Discovery | `01-PRODUCT-DISCOVERY.md` | تکمیل‌شده | چشم‌انداز، کاربر، Job، مدل مفهومی، دامنه، روش‌های تولید، پژوهش رقابتی |
| ۲ — Strategy Intelligence | `02-STRATEGY-INTELLIGENCE.md` | تکمیل‌شده | مدل استراتژی، تولید، ارزیابی، اعتبارسنجی، چرخهٔ عمر، قیدهای ایران، قرارداد FTS |
| ۳ — UX & Product Experience | `03-UX-AND-PRODUCT-EXPERIENCE.md`، `PRODUCT-REQUIREMENTS.md`، `prototype/` | تکمیل‌شده | ۹ اسکرین‌شات در ۱۳۶۶×۷۶۸ و ۱۹۲۰×۱۰۸۰؛ صفر خطای صفحه |
| ۴ — Technical Architecture | `04-TECHNICAL-ARCHITECTURE.md` | تکمیل‌شده | ۲۳ بخش؛ نمودار زمینه/Container/توالی/چرخهٔ عمر؛ مدل داده، Registry، امنیت، شکست/بازیابی، Q1–Q19 |
| تصمیم‌ها | `adr/ADR-OC-001..014` + `DECISION-LOG.md` | تکمیل‌شده | ۱۴ ADR؛ ۶۳ تصمیم ثبت‌شده (`OC-D-001..063`) |
| الزامات | `PRODUCT-REQUIREMENTS.md` | تکمیل‌شده | ۶۵ FR + ۱۴ NFR با شناسهٔ پایدار |
| نقشهٔ راه | `IMPLEMENTATION-ROADMAP.md` | تکمیل‌شده | P0–P6 با Gate، وابستگی و معیار پذیرش |
| پرسش‌های باز | `OPEN-QUESTIONS.md` | تکمیل‌شده | Q1–Q19؛ تفکیک «حل ساختاری» از «رأی مالک» |
| گزارش نهایی | همین سند | تکمیل‌شده | جمع‌بندی شواهد، ریسک‌ها و مرزهای راستی‌آزمایی |

Prototype مستقل است و خارج از Runtime می‌ماند. اسکرین‌شات‌ها در `prototype/evidence/` و اسکریپت بازتولید در `prototype/_screenshot.mjs` است؛ هیچ فایل دمو در بستهٔ تولید قرار نمی‌گیرد.

---

## ۳) مبنا، کنترل نسخه و جداسازی

| مورد | مقدار | توضیح |
|---|---|---|
| مبنای فازهای ۱–۳ | `da6d6177` | نوک Stage 3 |
| مبنای معماری فاز ۴ | `11f4b128` | Stage 4 پذیرفته‌شده |
| ادغام در شاخهٔ طراحی | `9c3676d4` (`--no-ff`) | Stage 4 بدون بازنویسی تاریخچه وارد شد |
| شاخهٔ مأموریت | `mission/opportunity-center-design-2026-11-08` | مستقل از `main` |
| Stage 4 Worktree | دست‌نخورده | هیچ فایل یا تغییر uncommitted آن لمس نشد |
| `main` | بدون تغییر | هیچ Merge یا Release انجام نشد |

**قاعدهٔ حاکم:** اگر شواهد کد با گزارش پذیرش Stage 4 تعارض داشت، شواهد کد ثبت می‌شد و تعارض به‌صورت شکاف P0 نوشته می‌شد؛ نه اینکه گزارش پذیرش نادیده گرفته شود و نه اینکه شکاف پنهان بماند.

---

## ۴) تصمیم‌های محصول

| موضوع | تصمیم | مرجع |
|---|---|---|
| مسئله | «الان چه چیزی مهم است، چرا، و چقدر قابل‌اعتماد؟» نه فهرست سیگنال | `01` |
| دو لنز | یک پوسته، دو لنز: فرصت (Today/Inspector) و پژوهش (Library/Lab/Compare/Monitor) | `03` §۲ |
| Today | فقط فرصت‌های حاصل از نسخهٔ Approved؛ هر ردیف به Validation و Approval پیوند دارد | FR-OC-001 |
| رتبه‌بندی | قابل‌توضیح، بدون امتیاز مرکب؛ کلید فعال و دلیل قابل‌بازکردن | FR-OC-003، OC-D-024 |
| FTS | کانونیکال و مصرف‌شده؛ بازپیاده‌سازی ممنوع؛ قواعدش به سایر استراتژی‌ها تحمیل نمی‌شود | `01` §۶، ADR-OC-008 |
| تعداد استراتژی | ثابت نیست؛ عدد چهار فقط مثال اولیه بود | قید مأموریت |
| Backtest | به‌تنهایی اثبات اعتبار یا سودآوری نیست | FR-OC-031، Phase 2 §۵ |
| Approved | مجوز استفاده در کشف فرصت است، نه مجوز معاملهٔ واقعی | FR-OC-015 |
| Kronos | متعلق به Technical Intelligence؛ وارد Strategy Intelligence نمی‌شود | OC-D-050 |
| دادهٔ شخصی | Watchlist/Portfolio/Workspace محلی می‌ماند؛ صفر Telemetry | OC-D-045، NFR-OC-010 |

---

## ۵) هوش استراتژی (فاز ۲)

- **مدل نسخه:** استراتژی = فرضیهٔ ابطال‌پذیر + یونیورس + افق + پنج اسلات تایپ‌شده (رژیم، ستاپ، تأیید، خروج، اندازه) + شرایط ابطال. نسخه تغییرناپذیر است؛ هر تغییر نسخهٔ تازه می‌سازد.
- **چرخهٔ عمر:** `draft → backtested → out-of-sample → paper → approved → suspended → deprecated → retired`. Approved فقط با Validation سبز و اقدام انسانی مالک.
- **تولید:** موتور فقط کاندید می‌سازد؛ هر کاندید موفق یا ناموفق در Trial Registry ثبت می‌شود. بودجهٔ جست‌وجو و سقف کاندیدها پیش از اجرا قفل می‌شود.
- **اعتبارسنجی:** Holdout یک‌بارمصرف با Access Log؛ `insufficient_evidence` حکم رسمی است؛ آستانه‌ها پیش از دیدن نتیجه ثبت می‌شوند.
- **FTS:** به‌عنوان استراتژی کانونیکال با Ruleset و Data Hash مصرف می‌شود؛ در مقایسه، ابعاد بک‌تست FTS «مقایسهٔ مستقیم مجاز نیست» می‌گیرند، نه صفر.
- **قیدهای ایران:** فقط خرید، سهام/ETF نقدی، هزینه/T+2/صف در پروتکل آزمون؛ مشتقه و فروش استقراضی خارج از نسخهٔ اول.

---

## ۶) تجربهٔ محصول و Prototype (فاز ۳)

| مسیر | هدف | وضعیت Prototype |
|---|---|---|
| `/today` | میز فرصت + Inspector | ساخته و اسکرین‌شات شد |
| `/research/library` | کتابخانهٔ استراتژی و نسخه‌ها | ساخته و اسکرین‌شات شد |
| `/research/lab/:id/:version` | شواهد اعتبارسنجی | ساخته و اسکرین‌شات شد؛ در کلاینت فقط‌خواندنی |
| `/research/compare` | مقایسهٔ نام‌دار ۲ تا ۴ استراتژی | ساخته و اسکرین‌شات شد |
| `/research/monitor` | پایش نسخه‌های Approved/Paper | ساخته و اسکرین‌شات شد |
| `/fts-screen` | سطح کانونیکال FTS | در IA ثبت شد؛ صفحهٔ مستقل می‌ماند |

**اصلاح مرز فاز ۴:** کنترل‌های «اجرای آزمایش» و «تأیید» در Prototype صرفاً مرجع دیداری سمت مالک‌اند. در محصول کلاینت، Lab فقط شواهد اجرای ثبت‌شده را نشان می‌دهد؛ حالت‌های `queued/running/failed` و لغو اجرا فقط در Research Workbench مالک وجود دارند (OC-D-044، OC-D-058).

**اندازه‌گیری:** ۹ اسکرین‌شات در `prototype/evidence/`؛ در ۱۳۶۶ پنل پیکربندی تا آستانهٔ ۱۲۸۰px کنار نتایج می‌ماند؛ هیچ سرریز افقی گزارش نشد. این سنجش، «بازبینی دیداری Prototype» است و ادعای انطباق WCAG یا پذیرش دیداری مالک نیست.

---

## ۷) معماری فنی (فاز ۴)

### ۷.۱) دو صفحه و مرز اعتماد

| صفحه | محیط | مسئولیت | چه چیزی ندارد |
|---|---|---|---|
| **Research & Approval Plane** | Python روی سیستم مالک | تولید/تکامل، اجرای آزمایش، اعتبارسنجی، تأیید، امضا، انتشار | در بستهٔ کلاینت نیست |
| **Client Runtime Plane** | Go + Tauri روی سه دستگاه | Today، Inspector، Library/Lab فقط‌خواندنی، Compare، Monitor، پایش | اجرا، تأیید، انتشار، تغییر آستانه |

مرز با فرآیند، کلید و شبکه جدا می‌شود، نه با قرارداد UI. حتی اگر کلاینت بخواهد، کلید APPROVAL را ندارد و مسیر انتشار در آن وجود ندارد.

### ۷.۲) زنجیرهٔ اعتماد

```text
oc.strategy/1   تعریف نسخه، اسلات‌ها، ابطال، وابستگی به Primitiveها
      ↓
oc.bundle/1     Strategy + Validation Evidence + Manifest + Runtime Compatibility
      ↓ (Minisign با APPROVAL_KEY روی Hash بسته)
oc.approval/1   تأیید مالک: دامنه، زمان، نسخه، سیاست اعتبارسنجی، امضا
      ↓
oc.registry/1   ایندکس امضاشده: نسخه‌های Stable، Hash، Revocation، Sequence
      ↓
Client Install  دانلود → Verify امضا و Hash → Staging → Switch اتمیک → Pointer
```

چهار نقش کلید جدا هستند: `DATA_KEY` (اسنپ‌شات داده)، `APP_KEY` (به‌روزرسانی برنامه)، `APPROVAL_KEY` (تأیید استراتژی؛ آفلاین و فقط مالک)، `REGISTRY_KEY` (ایندکس توزیع). یک کلید مشترک، شعاع انفجار را به همهٔ دارایی‌ها گسترش می‌دهد و رد شده است (ADR-OC-004).

### ۷.۳) جریان Research تا Runtime

1. مالک دادهٔ Snapshot را با `DATA_KEY` دریافت و Hash آن را ثبت می‌کند.
2. Research Workbench نسخه را با Primitiveهای ثبت‌شده اجرا می‌کند؛ خروجی اجرا، `run_id`، Manifest و شواهد است.
3. Validation Policy امضاشده اعمال می‌شود؛ تا `approval_enabled=false` است، هیچ نسخهٔ جدیدی Stable نمی‌شود.
4. مالک بسته را می‌سازد و با `APPROVAL_KEY` امضا می‌کند.
5. ایندکس Registry با `REGISTRY_KEY` امضا و در GitHub Private Releases منتشر می‌شود.
6. کلاینت ایندکس را می‌خواند، بسته را دانلود و اعتبارسنجی می‌کند، در Staging می‌نویسد و پس از تأیید کامل، Pointer را اتمیک جابه‌جا می‌کند.

هیچ AI یا اتوماسیونی کلید APPROVAL را در اختیار ندارد؛ پس «انتشار خودکار» از نظر فنی ممکن نیست، نه فقط ممنوع (OC-D-049).

### ۷.۴) Registry خصوصی و توزیع

- **v1:** GitHub Private Releases + ایندکس امضاشده. سه کاربر با Fine-grained PAT خواندنی و قابل Revoke. هیچ سرور دائمی، دیتابیس مرکزی یا هزینهٔ میزبانی مستمر لازم نیست.
- **Transport:** رابط `RegistryTransport` تا در آینده بدون تغییر Runtime به S3/سرور خصوصی جابه‌جا شود.
- **آفلاین:** آخرین نسخهٔ تأییدشده با برچسب `offline_verified` اجرا می‌شود؛ Revocation در اولین Sync اعمال می‌شود. ادعای تازگی یا Revocation بدون اتصال مجاز نیست.
- **Anti-Rollback:** ایندکس یک `sequence` یکنوا دارد؛ کلاینت نسخهٔ پایین‌تر از Sequence دیده‌شده را رد می‌کند مگر با تأیید صریح مالک.
- **Export/Import:** بستهٔ آفلاین امضاشده برای انتقال دستی؛ همان زنجیرهٔ Verify.
- **جزئیات:** ADR-OC-003/004/005؛ `04` §۱۰.

### ۷.۵) Runtime و API

| سطح | قرارداد |
|---|---|
| Today | `GET /api/oc/today` با `as_of`، `data_state`، `freshness`، `ranking_policy_id` و صفحه‌بندی |
| استراتژی/نسخه | `GET /api/oc/strategies`، `/api/oc/strategies/{id}/versions` |
| Lab | `GET /api/oc/versions/{id}/evidence` — فقط شواهد ثبت‌شده؛ بدون POST اجرا |
| Compare | `GET /api/oc/compare?ids=...` با ابعاد نام‌دار و `incomparable_reason` |
| Monitor | `GET /api/oc/monitor` با وضعیت، آخرین بررسی و هشدار |
| Job | `POST /api/oc/jobs` فقط در Workbench مالک؛ پاسخ باید `job_id` واقعی بدهد |
| FTS | `/api/fts-screen` سطح کانونیکال مستقل؛ Today همان Envelope را مصرف می‌کند |

**قاعدهٔ صداقت:** پاسخ `200` بدون `job_id`/`as_of`/`data_state` ممنوع است. مسیرهایی که کار انجام نمی‌دهند نباید «آغاز شد» بدهند. این مستقیماً از شکاف مشاهده‌شده در `internal/sync/handlers.go` آمده است.

### ۷.۶) ذخیره‌سازی

| Store | مالک | نوشتن | محتوا |
|---|---|---|---|
| `market.db` / `codal.db` | Producer | فقط Producer | دادهٔ خام؛ کلاینت فقط‌خواندنی |
| Generations (`gens/gen_*`) | Client | فقط نصب‌کنندهٔ اتمیک | Snapshotهای امضاشده؛ سرو از نسل فعال |
| `oc_client.db` | Client | Runtime (Read Model) | فرصت‌ها، شواهد Stable، وضعیت پایش — بدون دادهٔ شخصی |
| `user.db` | کاربر | فقط API کاربر | Watchlist، Portfolio، Workspace؛ هرگز در Sync بازنویسی نمی‌شود |
| `research.db` | مالک | فقط Research Workbench | Trial Registry، اجراها، Holdout، شواهد — خارج از `data_dir` Producer |

Producer فقط باید `market.db` و `codal.db` را Snapshot کند. پیمایش فعلی همهٔ `.db`ها خطر انتشار `research.db` یا دیتابیس شخصی را دارد (OC-D-053).

### ۷.۷) شکست، بازیابی و حالت آفلاین

| شکست | رفتار |
|---|---|
| قطع شبکه در دانلود | بستهٔ ناقص دور ریخته می‌شود؛ نسخهٔ فعال دست‌نخورده می‌ماند |
| Hash/امضای نامعتبر | نصب رد می‌شود؛ رویداد امنیتی ثبت می‌شود؛ نسخهٔ قبلی ادامه می‌دهد |
| Crash هنگام Switch | Pointer اتمیک است؛ راه‌اندازی بعدی یکی از دو نسل معتبر را می‌بیند |
| Revocation | در Sync بعدی اعمال می‌شود؛ نسخهٔ پس‌گرفته‌شده از Today خارج می‌شود |
| دادهٔ کهنه | `data_state=stale` و «رتبهٔ جاری» ادعا نمی‌شود؛ آخرین نسخهٔ معتبر با برچسب آفلاین |
| Schema ناسازگار | Migration صریح با نسخه؛ نبود مسیر ⇒ توقف، نه نوشتن تخریبی |
| Registry در دسترس نیست | آخرین ایندکس معتبر + `offline_verified`؛ بدون ادعای تازگی |

نگهداشت N-1 نسخهٔ فعال برای Rollback فوری؛ حذف نسخه‌ها فقط پس از تأیید Sync و بدون حذف شواهد.

---

## ۸) تعیین تکلیف Q1 تا Q14

| پرسش | تصمیم مهندسی | وضعیت | مرجع |
|---|---|---|---|
| Q1 — آستانهٔ Approved | `oc.validation_policy/1` امضاشده؛ `approval_enabled=false` تا امضای مالک؛ Candidate Profile فاز ۲ فقط پیشنهاد | ساختار Accepted؛ اعداد و امضا مالک | ADR-OC-009، `04` §۱۸.۱ |
| Q2 — یونیورس | دامنهٔ کامل با فیلتر نقدشوندگی؛ دامنهٔ نهایی تابع داده | پیش‌فرض؛ مالک | `04` §۱۸.۴ |
| Q3 — کارمزد/صف/T+2 | مدل هزینه در پروتکل آزمون؛ مقدار در Policy | پیش‌فرض؛ مالک | `02` §۵ |
| Q4 — مبنای بازده | مبنای total-return سازگار با FTS؛ جزئیات در Policy | پیش‌فرض؛ مالک | `02` §۴ |
| Q5 — جایگاه FTS | `/fts-screen` سطح کانونیکال مستقل؛ Today مصرف‌کنندهٔ `fts.envelope/1`؛ بدون غربالگری موازی | معماری Accepted؛ تأیید محصول مالک | ADR-OC-008، `04` §۱۸.۲ |
| Q6 — دامنهٔ تولید | قالب + عامل انسانی؛ جست‌وجو/ML فقط پژوهشی و پشت پرچم | پیش‌فرض | `04` §۱۸.۴ |
| Q7 — نقش AI | فقط پیشنهاد فرضیه؛ هیچ امتیاز/تأیید AI در مسیر نهایی | Accepted | ADR-OC-002 |
| Q8 — سقف منابع | تعاملی ≤۲ دقیقه، دسته‌ای ≤۳۰ دقیقه، قابل‌لغو، صف جدا | پیشنهادی | `04` §۱۸.۴ |
| Q9 — دادهٔ تاریخی | ثبت رو به جلو؛ بک‌فیل مأموریت جدا؛ بدون ادعای بک‌تست صف تاریخی | پیش‌فرض | `04` §۱۸.۴ |
| Q10 — اختیار تأیید | تک‌مالک + Audit امضاشده؛ سه کاربر فقط مصرف‌کننده | Accepted | ADR-OC-002 |
| Q11 — رتبه‌بندی | `oc.ranking_policy/1` امضاشده و Lexicographic؛ بدون وزن/Score؛ ترتیب پیشنهادی v1: تازگی → اعتبار استراتژی → پوشش شواهد → نقدشوندگی → زمان سیگنال → نماد | ساختار Accepted؛ ترتیب مالک | ADR-OC-010، `04` §۱۸.۳ |
| Q12 — ابزارها | سهام/ETF نقدی، فقط خرید؛ مشتقه و فروش استقراضی خارج | پیش‌فرض؛ مالک | `04` §۱۸.۴ |
| Q13 — نگهداشت | Append-Only؛ حذف خودکار ممنوع؛ آرشیو فشرده با حفظ Manifest | Accepted | ADR-OC-006 |
| Q14 — اعلان | فقط درون‌برنامه؛ بدون کانال بیرونی/Telemetry | Accepted | ADR-OC-012 |

**نکتهٔ صداقت:** Q1 و Q11 «حل ساختاری» شده‌اند، نه «حل عددی». هیچ آستانه یا ترتیب نهایی اختراع نشده است. Q5 از نظر معماری حل شده اما جایگاه محصولی آن (`/fts-screen` در ناوبری) منتظر تأیید مالک است.

---

## ۹) پرسش‌های تازهٔ فاز ۴ (Q15–Q19)

| پرسش | پیش‌فرض معماری | اثر | وضعیت |
|---|---|---|---|
| Q15 — دامنهٔ دادهٔ GPU | Opt-in صریح برای هر Job؛ بدون دادهٔ شخصی؛ Scope Hash و Audit | P6 | نیازمند رأی مالک |
| Q16 — دسترسی Registry | Fine-grained PAT خواندنی در OS Keychain؛ قابل Revoke | Onboarding سه کاربر | پیش‌فرض |
| Q17 — آفلاین/Revocation | آخرین نسخهٔ معتبر با `offline_verified`؛ Revocation در اولین Sync | امنیت/صداقت وضعیت | نیازمند سیاست مالک |
| Q18 — نگهداری کلید | کلیدهای جدا؛ Approval آفلاین/رمزدار؛ چرخش با Key Transition | امنیت انتشار | پیش‌فرض امنیتی |
| Q19 — Entitlement | v1: همهٔ Stableها برای هر سه کاربر؛ بدون تفکیک | مدل دسترسی | پیش‌فرض؛ مالک |

هیچ‌کدام مانع P0–P4 نیستند؛ Q15 مانع P6 و Q17 مانع سیاست قطعی آفلاین است.

---

## ۱۰) یافته‌های تأییدشده و راستی‌آزمایی‌نشده

### ۱۰.۱) تأییدشده در کد (با مسیر)

| یافته | شاهد | اثر بر طراحی |
|---|---|---|
| `borsd` از `dataDir/market.db` باز می‌کند | `backend-go/cmd/borsd/main.go:50` | Generation Resolver باید در P0 اضافه شود |
| `ActiveDBPath` مصرف‌کنندهٔ تولیدی ندارد | `backend-go/internal/snapshot/applier.go:96`؛ جست‌وجوی کل مخزن فقط همان تعریف | «اعمال نسل» با «سرو نسل» یکی نیست |
| Producer همهٔ `.db`ها را اسنپ‌شات می‌کند | `backend-go/cmd/bors-producer/pipeline.go:250-264` | Producer Allowlist در P0 |
| Sync مسیرها پیام «شروع شد» می‌دهند | `backend-go/internal/sync/handlers.go:107,118,130` | API Honesty؛ ممنوعیت 200 بدون Job |
| بخشی از مسیرهای FTS/بنیادی 501 هستند | `backend-go/internal/httpapi/server.go:245` | مسیرهای ناقص نباید در UI «موفق» دیده شوند |
| Ruleset فنی FTS در Python `"6"` و در Go `"3"` است | `api/chart.py:3896`؛ `backend-go/internal/chart/fts_swings.go:20` | دروازهٔ Parity و تک‌منبع‌سازی Ruleset |
| Tauri یک URL خارجی بار می‌کند، نه باندل داخلی | `frontend/src-tauri/src/lib.rs:123-131` | مرز امنیتی کانال محلی باید صریح باشد |
| Updater تعبیه شده اما JS آن را مصرف نمی‌کند | `frontend/src-tauri/tauri.conf.json:31-35`؛ `frontend-v2/src/shared/api/http.ts:3,19-29` | آرتیفکت استراتژی از App Updater جدا می‌شود |

### ۱۰.۲) راستی‌آزمایی‌نشده (ادعا نمی‌شود)

- پذیرش دیداری مالک برای Prototype و معماری.
- انطباق WCAG 2.1 AA؛ فقط بازبینی دستی Prototype انجام شده است.
- عملکرد واقعی Research Workbench، Registry و نصب اتمیک؛ هیچ‌کدام پیاده‌سازی نشده‌اند.
- رفتار سه کاربر واقعی روی سه دستگاه؛ فقط طراحی دسترسی انجام شده است.
- کفایت دادهٔ تاریخی برای بک‌تست صف/عمق سفارش.
- صحت Ruleset فنی FTS تا زمانی که Parity روی مجموعهٔ مرجع اجرا نشود.
- امنیت کانال محلی Tauri↔Go؛ در اسناد مهاجرت `OPEN` است و Phase 4 فقط الزاماتش را ثبت کرده است.

---

## ۱۱) ریسک‌ها

| ریسک | احتمال/اثر | کاهش |
|---|---|---|
| سرو دادهٔ قدیمی به‌جای نسل فعال | بالا/بالا | Generation Resolver در P0؛ تست یکپارچهٔ Apply→Serve |
| انتشار `research.db` یا دادهٔ شخصی در Snapshot | متوسط/بالا | Producer Allowlist؛ مسیر جدا برای Research |
| پذیرش «200 = انجام شد» در UI | بالا/متوسط | API Honesty؛ Job ID واقعی؛ تست قرارداد |
| واگرایی FTS Python/Go | بالا/بالا | Parity Gate؛ Ruleset تک‌منبع؛ Replay |
| Overfitting و سوءاستفاده از Backtest | متوسط/بالا | Holdout قفل‌شده، Trial Registry، DSR/PBO، `insufficient_evidence` |
| گم‌شدن کلید APPROVAL یا چرخش نادرست | کم/بحرانی | کلید آفلاین، Backup، Key Transition + App Update |
| وابستگی به GitHub برای توزیع | متوسط/متوسط | `RegistryTransport` قابل‌تعویض؛ Export/Import آفلاین |
| پیچیدگی سه کاربر و Revocation | متوسط/متوسط | PAT محدود، ایندکس امضاشده، Sequence و Revocation صریح |
| ابهام آستانه‌های Q1/Q11 | بالا/متوسط | `approval_enabled=false`؛ انتشار Stable تا امضای مالک متوقف |

---

## ۱۲) نقشهٔ راه P0–P6

| مرحله | محتوا | Gate خروج |
|---|---|---|
| **P0 — پایهٔ اعتماد** | Generation Resolver؛ Producer Allowlist؛ Schema Migration؛ Local API Token؛ API Honesty؛ قرارداد «بدون Python در بستهٔ کلاینت» | Today از نسل فعال سرو می‌شود؛ هیچ `.db` غیرمجاز Snapshot نمی‌شود؛ 200 بدون Job ممنوع |
| **P1 — قرارداد و Registry** | `oc.strategy/1`، `oc.bundle/1`، `oc.approval/1`، `oc.registry/1`؛ Verify/Install/Rollback | نصب اتمیک و Rollback با بستهٔ آزمایشی امضاشده |
| **P2 — Research Workbench** | Trial Registry، Holdout، اجرا/لغو، Validation Policy، Export | اجرای بازتولیدپذیر با Manifest کامل |
| **P3 — FTS و Today** | Adapter/Envelope، Parity Gate، Today Read Model | Parity سبز؛ Today فقط Approved |
| **P4 — Runtime سه کاربر** | Client Install، Lab فقط‌خواندنی، Compare/Monitor، Offline | سه دستگاه، بدون دادهٔ شخصی بیرونی |
| **P5 — Policy، مقایسه، پایش** | Q1/Q11 پس از امضای مالک؛ Ranking/Validation نهایی؛ پایش Drift | Stable جدید فقط با امضای مالک |
| **P6 — تولید/AI/GPU** | جست‌وجوی پژوهشی، مدل‌های پیشنهادی، GPU موقت با Opt-in | هیچ خروجی AI بدون تأیید مالک منتشر نمی‌شود |

وابستگی: P0 → P1 → P2/P3 → P4 → P5 → P6. P2 و P3 می‌توانند موازی پیش بروند. جزئیات در `IMPLEMENTATION-ROADMAP.md`.

---

## ۱۳) معیار پذیرش

### ۱۳.۱) پذیرش طراحی (این فاز)

- [x] همهٔ فازهای ۱–۴ سند دارند و به هم ارجاع می‌دهند.
- [x] معماری روی `11f4b128` بنا شده و شکاف‌های Stage 4 ثبت شده‌اند.
- [x] ADRها برای تصمیم‌های ساختاری وجود دارند (`ADR-OC-001..014`).
- [x] Q1–Q14 تعیین تکلیف شده‌اند؛ موارد مالکانه صریحاً «نیازمند رأی» مانده‌اند.
- [x] Prototype در ۱۳۶۶ و ۱۹۲۰ با شواهد تصویری بازبینی شده است.
- [x] هیچ کد Runtime، تغییر FTS، انتشار یا Merge به `main` انجام نشده است.

### ۱۳.۲) پذیرش پیاده‌سازی (فازهای بعد)

- Generation Resolver: Today دقیقاً از نسل فعال سرو شود؛ تست Apply→Restart→Query.
- Producer Allowlist: فقط `market.db`/`codal.db` در Snapshot؛ تست منفی با `research.db`.
- Registry: Verify امضا/Hash، نصب اتمیک، Rollback، آفلاین و Revocation با تست‌های خرابکاری.
- FTS Parity: مقایسهٔ Ruleset/خروجی روی مجموعهٔ مرجع؛ هیچ Stub/501 در مسیر Today.
- امنیت: Local API Token، عدم نشت کلید، تست نفوذ کانال محلی.
- UI: Today فقط Approved؛ Lab کلاینت بدون کنترل اجرا/تأیید؛ اندازه‌گیری WCAG.
- سه کاربر: Onboarding/Revoke PAT؛ صفر دادهٔ شخصی در شبکه.

---

## ۱۴) شواهد و فرمان‌های بازتولید

```bash
# وضعیت شاخه و مبنا
git log --oneline -5
git merge-base --is-ancestor 11f4b128 HEAD && echo "Stage4 base OK"

# شمارش مصنوعات طراحی
ls docs/opportunity-center/adr/ADR-OC-*.md | wc -l          # انتظار: 14
grep -c '^| OC-D-' docs/opportunity-center/DECISION-LOG.md   # انتظار: 63
grep -c '^| FR-OC-' docs/opportunity-center/PRODUCT-REQUIREMENTS.md  # انتظار: 65
grep -c '^| NFR-OC-' docs/opportunity-center/PRODUCT-REQUIREMENTS.md # انتظار: 14
ls docs/opportunity-center/prototype/evidence/*.png | wc -l  # انتظار: 9

# گارد فارسی و فاصله‌های اضافی (پس از Stage)
python dev/persian_glyph_guard.py
git diff --cached --check
```

**شواهد Prototype:** `1366x768-today.png`، `1366x768-detail.png`، `1366x768-library.png`، `1366x768-lab.png`، `1920x1080-today.png`، `1920x1080-library.png`، `1920x1080-lab.png`، `1920x1080-compare.png`، `1920x1080-monitor.png`.

**شواهد Stage 4 (به‌نقل از گزارش پذیرش):** Run `42508665247`، تگ `v1.0.98`، ۶ دارایی، KeyID `830BF752EF10076`، دانلود 91,547,928 بایت، `user.db` با SHA-256 یکسان. این اعداد در این مأموریت دوباره اندازه‌گیری نشدند و به‌عنوان «سند» نقل می‌شوند.

---

## ۱۵) مرزها و اعلام صریح

1. **هیچ Runtime پیاده‌سازی نشد.** همهٔ کدهای مسیر Opportunity Center، Registry، Research Workbench و Generation Resolver طراحی شده‌اند، نه ساخته.
2. **هیچ استراتژی‌ای تأیید یا منتشر نشد.** `approval_enabled=false` است و کلید APPROVAL در این مأموریت استفاده نشد.
3. **`main` دست‌نخورده است.** هیچ Merge، Tag یا Release انجام نشد.
4. **Stage 4 دست‌نخورده است.** Worktree و فایل‌های uncommitted آن لمس نشدند.
5. **هیچ آستانهٔ روش‌شناسی اختراع نشد.** Q1 و Q11 ساختار دارند، اما اعداد و ترتیب نهایی مالک‌اند.
6. **Prototype دمو است.** داده‌های آن ساختگی‌اند و هرگز در بستهٔ تولید قرار نمی‌گیرند.
7. **ادعای انطباق یا پذیرش دیداری نداریم.** تصاویر و اندازه‌ها ارائه شده‌اند؛ رأی مالک لازم است.

**گام بعدی پیشنهادی:** تأیید مالک روی Q1/Q5/Q11 و سپس شروع P0 (Generation Resolver، Producer Allowlist، Schema Migration، Local API Token، API Honesty). تا آن زمان، هیچ انتشار Stable جدیدی مجاز نیست.
