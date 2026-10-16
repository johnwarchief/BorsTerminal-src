# گزارش زنده‌سنجی «مجمع» از API عمومی TSETMC (cdn.tsetmc.com)

> **Snapshot منبع مجمع:** این بررسی به درخواست‌ها و داده‌های برداشت‌شده در ۲۰۲۶-۱۰-۰۸ مربوط است. وجود فیلد یا نتیجه برای نمادهای نمونه، پوشش کامل یا صحت همان فیلدها در نشست بعدی را ثابت نمی‌کند؛ قبل از بستن باگ مجمع، با کد و دادهٔ تازه تطبیق بدهید.


تاریخ اجرا: ۲۰۲۶-۱۰-۰۸ (امروز). هر درخواست واقعی با status/bytes/sha256 در
`_audit/tsetmc_assembly_probe_evidence.json` ثبت شده است. چیزی که در این فایل نیست،
صریحاً «UNVERIFIED» است.

## نمادهای انتخابی (از `_audit/live_rows.json`، ۵۸۶۵ ردیف)

| نقش | نماد | insCode |
| --- | --- | --- |
| بزرگ تولیدی | فولاد | 46348559193224090 |
| بزرگ تولیدی | ذوب | 71483646978964608 |
| بانک | وبملت | 778253364357513 |
| سرمایه‌گذاری | وساپا | 37614886280396031 |
| ETF | ثروت | 27812005859539773 |
| صفِ صفر/توقف‌خورده (ردیف بی‌معامله) | قاروم | 10831074117626896 |
| دیگر | شتران | 51617145873056483 |
| دیگر | خودرو | 65883838195688438 |

## تکلیف ۱ — `Instrument/IsInstrument` و کلیدهای مجمع

- `Instrument/IsInstrument?insCode=…&_pt=…` → **HTTP 404، بدنه ۰ بایت** برای هر ۸ نماد؛
  نسخهٔ مسیری (`IsInstrument/{code}`) هم **404**. این اندپوینت امروز وجود ندارد.
- کلیدهای `maxam`, `lMaxam`, `cMaxam`, `devidDate`, `divCash`, `farDiv`, `prevNext`,
  `shareHolderMeetingDate`, `shareHolderMeetingDecisionDate`, `navmIC`, `statTakeh`,
  `isManager`, `memo`, `dPS`: **در هیچ پاسخِ ۲۰۰ِ این اجرا حضور نداشتند** (جست‌وجوی
  کلیدهایِ مسطح‌شده روی هر پاسخِ JSON). ادعای تاریخیِ `maxam` ⇒ **تأیید نشد**.
- اندپوینتِ واقعیِ صفحهٔ نماد: `Instrument/GetInstrumentInfo/{insCode}` → **200 (~۱ کیلوبایت)**.
  کلیدهایِ برگشتی (عیناً): `eps.epsValue, eps.estimatedEPS, eps.sectorPE, eps.psr, sector, staticThreshold, minWeek, maxWeek, minYear, maxYear, qTotTran5JAvg, kAjCapValCpsIdx, dEven, topInst, faraDesc, contractSize, nav, underSupervision, etfIssuedUnit, etfUnitDeven, cValMne, lVal18, cSocCSAC, lSoc30, yMarNSC, yVal, insCode, lVal30, lVal18AFC, flow, cIsin, zTitad, baseVol, instrumentID, cgrValCot, cComVal, lastDate, sourceID, flowTitle, cgrValCotTitle` — **هیچ کلیدِ مجمعی ندارد**.

## تکلیف ۲ — `ClosingPrice/GetMarketWatch`

`market=0&showTraded=false&withBestLimits=true` → **200، ۳۹۲۴ ردیف**. ردیف‌ها ۴۴ کلید دارند
(`lva, lvc, insCode, pmd, pcl, py, pe, eps, qtj, ztt, blDs, dEven, hEven, iClose, yClose, …`).
کلیدِ مجمع‌محورِ غیرخالی: **هیچ** — جدولِ بسامد خالی است (در evidence: `task2.assembly_candidates={}`
شمارشِ غیرخالیِ هر ۴۴ کلید هم هست). یعنی تابلو هیچ پرچمِ مجمعی حمل نمی‌کند.

## تکلیف ۳ — کاندیداها (وضعیت واقعی)

| مسیر | status | bytes | نتیجه |
| --- | --- | --- | --- |
| `Instrument/InstrumentInfo?instrument=` | 404 | 0 |attempt—not-endpoint |
| `Instrument/InstrumentInfoFull?instrument=` | 404 | 0 | attempt |
| `Dashboard/GetInstrumentInfo?instrument=` | 200 | 824 | بدنه = HTMLِ اپِ SPA (فالبک)، نه JSON ⇒ **غیرقابل‌استفاده** |
| `Dashboard/GetDividendDatesByInsCode?insCode=` | 200 | 824 | همان HTMLِ فالبک ⇒ غیرقابل‌استفاده |
| `Dashboard/GetDividendDatesBySymbol?symbol=` | 200 | 824 | همان HTML ⇒ غیرقابل‌استفاده |
| `News/GetNewsByInstrument?instrument=&rows=20` | 200 | 824 | همان HTML ⇒ غیرقابل‌استفاده |
| `Karbasta/GetByInstrument?instrument=` | 200 | 824 | همان HTML ⇒ غیرقابل‌استفاده |
| `Meeting/GetMeetings` | 200 | 824 | همان HTML ⇒ غیرقابل‌استفاده |
| `Council/GetDecisions` | 200 | 824 | همان HTML ⇒ غیرقابل‌استفاده |
| `Announcement/GetByInstrument?instrument=` | 200 | 824 | همان HTML ⇒ غیرقابل‌استفاده |
| `Instrument/GetInstrumentInfo/{insCode}` (شکلِ مسیری) | **200** | ~980 | JSONِ مجاز؛ بدونِ کلیدِ مجمع |
| `MarketData/GetInstrumentState/{insCode}/{dEven}` | **200** | 166/324 | `instrumentState[]: cEtaval, cEtavalTitle, underSupervision, realHeven, hEven` — وضعیتِ نماد (شتران در 20261007 دو ردیف `cEtaval:"IS"` = توقف؛ سایر «A ») |
| `Msg/GetMsgByInsCode/{insCode}` | **200** | 0.1–3.5MB | `msg[]: tseMsgIdn, dEven, hEven, tseTitle, tseDesc, flow` — اطلاعیه‌های «برگزاری مجمع»، «توقف/بازگشایی نماد پس از مجمع» (متنِ فارسی، نه فیلدِ ساخت‌یافته) |
| `Codal/GetPreparedDataByInsCode/{count}/{insCode}` | **200** | ~30–60KB | `preparedData[]: id, symbol, name, title, sentDateTime_Gregorian, publishDateTime_Gregorian, publishDateTime_DEven, mainTableRowID, hasHtml/Excel/PDF/XMLReport, attachmentID, contentType, fileName, fileExtension, tracingNo` — **آینهٔ CDNِ کدال؛ تنها منبعِ واقعیِ اطلاعیهٔ مجمع در این اجرا** |
| `Instrument/GetInstrumentShareChange/{insCode}` | **200** | ~0.2–1.9KB | `instrumentShareChange[]: dEven, insCode, numberOfShareOld, numberOfShareNew, lVal18AFC` — تغییرِ ساختارِ سرمایه (ساخت‌یافته) |
| `ClosingPrice/GetPriceAdjustList/{insCode}` | **200** | ~1.5KB | `priceAdjust[]: dEven, pClosing, pClosingNotAdjusted, corporateTypeCode(null در همهٔ نمونه‌ها)` |
| `ClosingPrice/GetClosingPriceInfo/{insCode}` | **200** | 620B | کلیدهایِ قیمت/وضعیت؛ `finalLastDate=20261007` — بدونِ DPS |
| `Codal/GetStatementContentByInsCode/{insCode}` | 404 | 0 | attempt |
| `Fund/GetETFByInsCode/{insCode}` | **500** | 0 | attempt (خطای سرور) |
| `ClosingPrice/GetInstrumentCalendar?insCode=&fromDate=` (شکلِ کوئری) | 404 | 0 | attempt |
| `tsev2/data/instinfofast.aspx` روی cdn/www | 200 | 824 | همان HTMLِ فالبک ⇒ میروث قدیمی روی CDN مرده |
| `old.tsetmc.com/tsev2/data/instinfofast.aspx` | 200 | 0 | بدنهٔ خالی |
| `StaticData/GetInstrumentList` | 404 | 0 | attempt |

## تکلیف ۴ — نگاشتِ داده‌ای که واقعاً هست (`Codal/GetPreparedDataByInsCode`)

| کلید خام | معنا | مثال (از پاسخ‌های این اجرا) | مفهوم UI |
| --- | --- | --- | --- |
| `title` | عنوان اطلاعیه | «آگهی ثبت تصمیمات مجمع عادی سالیانه دوره 12 ماهه منتهی به 1404-12-29» | آگهی/تصمیم مجمع — **تنها با regex روی متن** |
| `title` (شامل «معرفی /تغییر در ترکیب اعضای هیئت مدیره/مدیر عامل») | تغییر هیئت‌مدیره | وبملت 2026-09-16 | تغییرات هیئت‌مدیره (عنوان، نه دادهٔ ساخت‌یافته) |
| `publishDateTime_Gregorian` / `publishDateTime_DEven` | زمان/تاریخ انتشار | 2026-09-15T11:51:55 / 20260915 | asOf |
| `sentDateTime_Gregorian` | زمان ارسال | — | asOf |
| `tracingNo`, `hasPDFReport/hasHtmlReport` | ارجاع و پیوست | — | لینک جزئیات (DPS واقعی داخل فایلِ «تصمیمات» است، نه JSON) |
| `instrumentShareChange[].numberOfShareOld/New + dEven` | تغییر سرمایه | وساپا ۷ ردیف | افزایش سرمایه (تاریخ + نسبت محاسبه‌شدنی) |
| `msg[].tseTitle/dEven` («بازگشايي نماد … پس از برگزاری مجمع»، «توقف نماد») | وضعیت اجرا/بازگشایی | شتران 20260729 | وضعیت مجمع |
| `instrumentState[].cEtaval` («A »/«IS») + `underSupervision` | وضعیت صف | شتران IS در 20261007 | وضعیت نماد |

**زنده یا EOD؟** اطلاعیه‌ها در لحظهٔ انتشار در کدال در این CDN می‌آیند: تازه‌ترینِ وساپا
2026-09-30، وبملت 2026-09-16، گزارش ماهانهٔ فولاد منتهی به 1405-06-31 با انتشار اوایل مهر —
یعنی **سوب‌روز، تقریباً زنده**. `dEven`های GetInstrumentState/GetClosingPriceInfo
(`finalLastDate=20261007`) **EOD/در-session**اند. **DPS عددی، «نوع مجمع» به‌صورت فیلد،
`eventDate` ساخت‌یافته و دادهٔ ساخت‌یافتهٔ هیئت‌مدیره:Absent — از هیچ پاسخِ ۲۰۰ این اجرا قابل‌استخراج نیستند.**

## جدول نمادها (TSETMC)

| نماد | insCode | کلیدهایِ مجمعِ TSETMC | مقدار | تاریخ | منبع | وضعیت |
| --- | --- | --- | --- | --- | --- | --- |
| فولاد | 46348559193224090 | بدونِ کلیدِ ساخت‌یافته | «تصمیمات مجمع عمومی عادی سالیانه …(اصلاحیه)» | 2026-08-16 | Codal/GetPreparedDataByInsCode | تصمیمِ مجمع موجود؛ ۱۸ اطلاعیهٔ مجمع‌دار در ۱۰۰ آخر |
| ذوب | 71483646978964608 | — | «آگهی ثبت تصمیمات مجمع عادی سالیانه» | 2026-09-15 | Codal/GetPreparedDataByInsCode | ۱۶ اطلاعیه؛ بازگشاییِ پسِ مجمع: Msg dEven 20260805 |
| وبملت | 778253364357513 | — | «معرفی /تغییر در ترکیب اعضای هیئت مدیره/مدیر عامل» | 2026-09-16 | Codal/GetPreparedDataByInsCode | تصمیم مجمع 2026-07-29؛ هیئت‌مدیره فقط عنوان |
| وساپا | 37614886280396031 | — | «آگهی ثبت تصمیمات مجمع عمومی فوق العاده (بجز تغییرات سرمایه)» | 2026-09-06 | Codal/GetPreparedDataByInsCode | ۱۳ اطلاعیه؛ shareChange ۷ ردیف |
| ثروت | 27812005859539773 | — | «آگهی دعوت به مجمع صندوق سرمایه گذاری در تاریخ 1400-05-24» | 2021-08-04 | Codal/GetPreparedDataByInsCode | feed صندوق تا ۲۰۲۱ (۱۹ ردیف)؛ Msg بدونِ مجمع |
| قاروم | 10831074117626896 | — | «آگهی ثبت تصمیمات مجمع عادی سالیانه» | 2025-12-23 | Codal/GetPreparedDataByInsCode | بازگشایی Msg 20251129؛ ۳۶ اطلاعیهٔ مجمع‌دار |
| شتران | 51617145873056483 | cEtaval="IS" (توقف) | «خلاصه تصمیمات مجمع عمومی عادی به طور فوق العاده» | 2026-08-03 | GetPreparedData + GetInstrumentState | توقف/بازگشاییِ مجمعی در Msg (20260726/20260729) |
| خودرو | 65883838195688438 | — | «آگهی ثبت تصمیمات مجمع عمومی فوق العاده (بجز تغییرات سرمایه)» | 2026-09-13 | Codal/GetPreparedDataByInsCode | ۱۵ اطلاعیه؛ shareChange ۶ ردیف |

## تکلیف ۶ — مقایسه با کدالِ محلی

`codal.db` در ریشهٔ worktree **وجود ندارد**؛ `_audit/codal_snapshot.db` بررسی شد (همین محتوا).

| منبع | ردیف کل | عنوانِ «مجمع» | «دعوت» | «مصوبات» | «بازگشایی» | دامنهٔ تاریخِ مجمع‌ها |
| --- | --- | --- | --- | --- | --- | --- |
| `market.db → codal_notices` | 36350 | 301 (0.8٪) | 100 | 1 | 1 | همه publish_date=1405/06/01 (بَچِ یک‌روزه) |
| `_audit/codal_snapshot.db` | 36187 | 301 | 100 | 1 | 1 | همان |

تازه‌ترین اطلاعیهٔ محلیِ هر نماد (LIKE '%مجمع%'): فولاد ۰، وبملت ۰، وساپا ۰، ثروت ۰، قاروم ۰،
شتران ۰، خودرو ۰؛ ذوب: یک ردیف ولی مربوط به «ذوب سهام» (ETF)، نه ذوب. در ۸/۸ نمادِ بزرگ،
میزانِ اطلاعیه‌هایِ ذخیرۀ محلی ۱۴ تا ۶۶ ردیف است، همگی از جنسِ گزارشِ ماهانه/صورتِ مالی —
و تازه‌ترین publish_date محلی ۱۴۰۵/۰۶/۱۳ (≈۴ روز کهنه‌تر از امروز).
نتیجه: **همین حالا کدالِ ذخیره‌شده در برنامه برچسبِ مجمع نمی‌دهد؛ اطلاعیه‌هایِ مجمع عملاً از
synk بیرون‌اند** (فقط یک بَچِ ۳۰۱ ردیفی). در مقابلِ همان data روی CDN با ۱۳–۳۶ ردیف مجمع در
۱۰۰ اطلاعیهٔ آخر هر نماد، زنده و سوب‌روز، در دسترس است. `market.db` جدول‌های `tsetmc_messages`
(۱۵۰۱ ردیف، ۶ ردیفِ «مجمع») و `share_change_events` (۳۴۸۰) را هم از همین اندپوینت‌ها پر می‌کند.

## تکلیف ۵ — رفتارِ نرخ (۱۰ GET پشت‌سرهم، بدونِ مکث)

| اندپوینت | statusها | زمان هر فراخوانی | بایت |
| --- | --- | --- | --- |
| `ClosingPrice/GetMarketWatch` | ۱۰×200 | 538–963ms | 4.01MB |
| `Codal/GetPreparedDataByInsCode/50/فولاد` | ۱۰×200 | 111–286ms | 30.1KB |

هیچ 403/429 دیده نشد (اولین فراخوانیِ بلاک: ندارد). توصیه: چکِ مجمعیِ هر نماد (۳۰KB) با
بازه ≥۳۰ ثانیه و فقط برایِ نمادهایِ انتخابی؛ GetMarketWatch (۴MB) حداکثر هر ۱–۲ دقیقه؛
سراسریِ all-symbol هر چند دقیقه یک‌بار با صف.

## رأی نهاییِ هر درخواست

| مفهوم | حکم |
| --- | --- |
| آگهی دعوت به مجمع | **available** — عنوان در `Codal/GetPreparedDataByInsCode` (متن؛ فیلدِ ساخت‌یافته نیست) |
| تاریخ مجمع (eventDate) | **UNVERIFIED ساخت‌یافته** — فقط داخلِ متنِ عنوان («در تاریخ …»)؛ parse لازم |
| وضعیت مجمع (توقف/بازگشایی) | **available به‌صورت استنتاجی** — `Msg/GetMsgByInsCode` + `cEtaval` در `GetInstrumentState` |
| تصمیم مجمع | **available** — عنوان «تصمیمات مجمع…»؛ decisionDate ≈ تاریخِ انتشار آن اطلاعیه (proxy) |
| نوع مجمع (عادی/فوق‌العاده) | **available به‌صورت regex روی عنوان**؛ فیلد جداگانه: absent |
| DPS | **absent-from-TSETMC** در هر پاسخِ JSON این اجرا؛ عددِ سود در فایل‌هایِ پیوست (hasPDFReport) است ⇒ از CDN فقط با دانلودِ گزارش |
| افزایش سرمایه | **available** — `GetInstrumentShareChange` (ساخت‌یافته) + `GetPriceAdjustList` |
| تغییرات هیئت‌مدیره | فقط **عنوانِ اطلاعیه** («معرفی /تغییر در ترکیب اعضای هیئت مدیره»)؛ دادهٔ ساخت‌یافته: absent |
| `maxam`/`IsInstrument` | **absent** — اندپوینت 404؛ کلید در هیچ پاسخی دیده نشد |

## AssemblyEvent پیشنهادی

`AssemblyEvent{insCode, symbol, eventType, eventDate, status, decisionDate, source, asOf}`
- insCode/symbol: TSETMC (تابلو/GetInstrumentInfo) — پر می‌شود.
- eventType (invited|decided؛ عادی|فوق‌العاده|عادی‌سالیانه): **derive** از `preparedData.title`.
- eventDate: از متنِ «آگهی دعوت…» (parse) — در غیر این صورت **null** (حدس نزنید).
- status (suspended-for-assembly|reopened): از `msg.tseTitle` + `cEtaval` — derive.
- decisionDate: proxy = `publishDateTime_Gregorian`ِ اطلاعیهٔ «تصمیمات مجمع…» — علامت‌دار به‌عنوانِ proxy.
- DPS/درصد افزایش سرمایه: DPS **از هیچ‌کدام پر نمی‌شود** (مگر دانلودِ فایلِ اطلاعیه)؛ نسبتِ سرمایه از shareChange.
- source: `tsetmc-cdn:preparedData|msg|shareChange|state`؛ asOf: publishDateTime_DEven/dEven.

## تلاش‌هایِ ناموفق (attempt-not-endpoint)

`Instrument/IsInstrument` (کوئری و مسیر) 404 · `Instrument/InstrumentInfo` 404 ·
`Instrument/InstrumentInfoFull` 404 · `Dashboard/*`, `News/*`, `Karbasta/*`, `Meeting/GetMeetings`,
`Council/GetDecisions`, `Announcement/*`: 200 ولی HTMLِ SPA (824B) — نه اندپوینت ·
`Codal/GetStatementContentByInsCode/{ins}` 404 · `Fund/GetETFByInsCode/{ins}` **500** ·
`ClosingPrice/GetInstrumentCalendar` (شکلِ کوئری) 404 · `StaticData/GetInstrumentList` 404 ·
`tsev2/instinfofast.aspx`: 200 HTML/200 خالی. هیچ‌کدام در گزارش بالا به‌عنوان منبع استفاده نشده‌اند.
