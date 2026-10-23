# قراردادِ نوشتنِ EasyTrader — بازسازیِ ایستا (Round 11)

**سطحِ قطعیت:** `WRITE_CONTRACT_STATICALLY_RECONSTRUCTED`  
**تأییدِ عملیاتی:** نه — هیچ POSTِ سفارشِ واقعی در این راند اجرا نشد.  
**منبعِ اصلی:** کدِ خودِ وب‌اپِ اول‌طرفی، bundle `main-XW5OZAYT.js`، مشاهدهٔ ۲۰۲۶-۱۰-۲۱.

## ۱) مسیر و پاکت

| مورد | مقدار | شاهد |
| --- | --- | --- |
| Method | `POST` | `createOrder(e)` در کلاینتِ اول‌طرفی |
| Path | `/core/api/v2/order` | `orderUrl + 'v2/order'`؛ `orderUrl = mtsPath + 'core/api/'` |
| Body | `{"order": { … }}` | `httpService.post(..., {body:{order:e}})` |
| Read-back | `GET /core/api/order` | `getOrders()` همان کلاینت |
| Modify | `PUT /core/api/v2/order` با `{modifyOrder: …}` | `updateOrder()` |
| Cancel | `DELETE /core/api/v2/delete-order` با `{orderId, orderFrom}` | `deleteOrder()` |

## ۲) فیلدهایِ `order`

| فیلد | نوع | الزامی | مقدار/معنا | قطعیت | یادداشت |
| --- | --- | --- | --- | --- | --- |
| `symbolIsin` | string | بله | ISINِ ابزار | کلاینتِ اول‌طرفی + نگاشتِ خواندنی | نه `ins_code`، نه نمادِ نمایشی |
| `symbolName` | string | بله | نامِ نمایشی | کلاینتِ اول‌طرفی | سرور ممکن است نادیده بگیرد؛ تأییدنشده |
| `price` | number | بله | قیمت (ریال) | کلاینتِ اول‌طرفی | باید > 0 |
| `quantity` | number | بله | تعدادِ سهم | کلاینتِ اول‌طرفی | باید > 0 |
| `side` | integer | بله | `0=Buy`, `1=Sell`, `3=None` | enumِ کلاینت | `None` برایِ سفارشِ تازه معنا ندارد |
| `validityType` | integer | بله | `0=Day`, `5=Week`, `6=Month`, `1=ValidToDate`, `2=ValidToCancellation`, `3=ExecuteAndRemove`, `99=SharedDueDate` | enumِ کلاینت | کلاینت Week/Month/SharedDueDate را به `ValidToDate` تبدیل می‌کند |
| `validityDate` | string | خیر | تاریخِ اعتبار برایِ نوعِ تاریخ‌دار | کلاینتِ اول‌طرفی | برایِ Day حذف می‌شود |
| `orderModelType` | integer | بله | `1=oms` | enumِ کلاینت | `draft=2`, `ipo=3`, `algorithm=4`, `option=5`, `offline=6` |
| `orderFrom` | integer | بله | `34=OrbisDesktop` برایِ سهام؛ `33=OrbisMobile`؛ `111/110` برایِ آپشن | enumِ کلاینت | برایِ مسیرِ دسکتاپِ سهام 34 |
| `createDateTime` | string | بله | برچسبِ زمانِ محلیِ کلاینت | کلاینتِ اول‌طرفی | هویتِ سفارش نیست؛ برایِ تطبیق استفاده نمی‌شود |
| `commission` | number | خیر | جمعِ کارمزدِ نمایشی | کلاینت؛ معنایِ سرور تأییدنشده | در نبودِ منبعِ تأییدشده حذف می‌شود |
| `totalValue` | number | خیر | جمعِ نمایشی | کلاینت؛ معنایِ سرور تأییدنشده | در نبودِ کارمزدِ تأییدشده حذف می‌شود |
| `id` | string | خیر | شناسهٔ سفارش | create: حذف؛ edit: شناسهٔ فرم | برایِ سفارشِ تازه عمداً حذف می‌شود |

**نمونهٔ ساختاری (مقادیرِ نمایشی، نه سفارشِ واقعی):**

```json
{
  "order": {
    "symbolIsin": "IRO1…",
    "symbolName": "…",
    "price": 1000,
    "quantity": 10,
    "side": 0,
    "validityType": 0,
    "orderModelType": 1,
    "orderFrom": 34,
    "createDateTime": "10/21/2026, 3:00:00 PM"
  }
}
```

## ۳) معنایِ پاسخ

| فیلد | معنا | قطعیت |
| --- | --- | --- |
| `isSuccessful=true` + `id` | درخواست **ثبت شد**؛ نه پذیرش در هسته و نه اجرا | کلاینتِ اول‌طرفی + قراردادِ داخلی |
| `isSuccessful=false` یا `omsError[]` | ردِ صریح؛ `id` دلیلِ زنده‌بودن نیست | کلاینت + تفسیرِ فعلی |
| 2xx بدونِ `isSuccessful` | نامعلوم؛ باید `GET /core/api/order` و OMS را خواند | قراردادِ داخلی |
| 429 | سقفِ اعلامیِ کلاینت: ۱۰۰۰ سفارش در ساعت | پیامِ خودِ کلاینت (نه آزمونِ سرور) |
| timeout/5xx | نامعلوم؛ reconcile، بی‌retry کور | قراردادِ داخلی |

کلاینت پس از `isSuccessful` سفارش را `OnSending` می‌کند و وضعیت را از
`GET /core/api/order`/رویدادهایِ OMS می‌خواند؛ پس «200» به‌تنهایی پذیرش نیست.

## ۴) آنچه هنوز تأییدنشده است

- معنایِ سرور برایِ `commission`/`totalValue` و اینکه آیا بدونِ آن‌ها سفارش
  پذیرفته می‌شود؛ در کدِ ما تا منبعِ تأییدشده حذف می‌شوند.
- قالبِ دقیقِ `createDateTime` در localeهایِ مختلف؛ در کدِ ما قالبِ انگلیسیِ
  مرجع ساخته می‌شود، ولی هویتِ سفارش نیست.
- رفتارِ server با `id`ِ خالی، idempotency رسمی، و semantics پذیرش/اجرای جزئی.
- اعتبارِ `validityType`هایِ غیرِ Day؛ فقط Day در مسیرِ خریدِ این راند استفاده شد.
- هیچ آزمونِ عملیاتیِ POST انجام نشد؛ این سند فقط بازسازیِ ایستا است.

## ۵) شواهدِ اجراییِ مرتبط

- `dev/execution_write_contract_v1147.py` — بدنه، enumها، حذفِ فیلدهایِ
  بی‌منبع، read-only refusal، 2xx=ثبت، duplicate guard، readiness.
- `dev/easytrader_adapter_v1113.py` — قراردادِ آداپتور و تفسیرِ پاسخ.
- `dev/execution_account_sources_v1146.py` — منابعِ حساب و نشتِ صفر.
- `GET /api/execution/readiness` — نمایشِ دروازه‌ها؛ `live_ready=false`.

## ۶) منبعِ تعدادِ قابل‌فروش

در ترافیکِ فقط‌خواندنیِ صفحهٔ پرتفوی، تنها منبعِ سبد
`GET /assetmodule/api/performance` بود؛ فیلدهایِ آن `asset`، میانگین‌ها و
`totalBoughtVolume/totalSoldVolume` را دارد، ولی `quantity`/`free_quantity`/
`sellable_quantity` ندارد. هیچ مسیرِ سهامِ دیگری با شاهدِ کافی دیده نشد؛
بنابراین preflight فروش `sellable=UNKNOWN` و مسدود می‌ماند. `positionFreeQuantity`
که درِ کدِ اول‌طرفی دیده می‌شود مربوط به استراتژی‌هایِ **آپشن** است، نه سهام،
و به سهام تعمیم داده نشد.
