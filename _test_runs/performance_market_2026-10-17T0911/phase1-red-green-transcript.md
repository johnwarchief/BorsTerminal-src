# قرمز‑سبز: `dev/funnel_body_cache_v1.py` رویِ `ff6b2fb` (۳ سبز، ۸ قرمز)

همراه با ریتم‌هایِ قبلِ تغییر درِ همان فایل. raw: `phase1-before.log` (بیرونِ git).

```
### BEFORE: 5s rhythm
  +  0.00s 200   2074.2 ms xc=      as_of=1792238955 etag=
  +  7.08s 200   1150.0 ms xc=      as_of=1792238955 etag=
  + 13.23s 200   1641.3 ms xc=      as_of=1792238968 etag=
  + 19.87s 200   1123.6 ms xc=      as_of=1792238968 etag=
  + 26.00s 200   2205.6 ms xc=      as_of=1792238981 etag=
  + 33.20s 200   1456.2 ms xc=      as_of=1792238981 etag=
  + 39.66s 200   3380.2 ms xc=      as_of=1792238996 etag=
  + 48.04s 200   2079.1 ms xc=      as_of=1792239003 etag=
  + 55.12s 200   1285.4 ms xc=      as_of=1792239003 etag=
  + 61.41s 200   2182.8 ms xc=      as_of=1792239017 etag=
rhythm 5.0s x 10 polls -> HIT 0 / MISS 10 ; distinct bodies 1 (as_of 6)
### BEFORE: 20s rhythm
  +  0.00s 200   1331.9 ms xc=      as_of=1792239017 etag=
  + 21.33s 200   2006.8 ms xc=      as_of=1792239046 etag=
  + 43.34s 200   3095.1 ms xc=      as_of=1792239069 etag=
  + 66.44s 200   1766.8 ms xc=      as_of=1792239091 etag=
  + 88.21s 200   1954.1 ms xc=      as_of=1792239113 etag=
  +110.17s 200   3242.5 ms xc=      as_of=1792239136 etag=
rhythm 20.0s x 6 polls -> HIT 0 / MISS 6 ; distinct bodies 1 (as_of 6)
### BEFORE: openapi
openapi 200 73566b
### BEFORE: funnel guard (expect RED = red-green proof)
FAIL ۱ هر دو درخواست ۲۰۰ و بدنهٔ غیرخالی‌اند  ← {'http': (200, 200), 'bytes': (7489027, 7489048)}
FAIL ۲ بدنهٔ کش‌شده با بدنهٔ تازه بایت‌به‌بایت یکی است  ← {'first_bytes_differ_at': 7489026}
FAIL ۳ سرِ کش از MISS به HIT رفت (همان کلید، بی‌بازسازی)  ← {'X-Cache': (None, None)}
FAIL ۴ درخواستِ گرم واقعاً ارزان‌تر است (<۳۰۰ms)  ← 1108.9 ms
FAIL ۵ etagِ درست ⇒ ۳۰۴ با صفر بایت  ← {'http': 200, 'bytes': 7489048, 'xc': None}
FAIL ۶ etagِ نادرست ⇒ ۲۰۰ِ کامل، نه ۳۰۴ (کش کهنه را تازه اعلام نمی‌کند)  ← {'http': 200, 'bytes': 7489048}
FAIL ۷ کلیدِ متفاوت بدنهٔ خودش را دارد (etag مشترک نیست)  ← {'http': 200, 'etag_same_as_trend': True}
ok   ۸ `status_matrix` و `universe` درِ هر دو پاسخ یکی است
ok   ۹ `timeline` درِ پاسخِ فهرست نمی‌آید (همان `_strip`ِ پیشین)
ok   ۱۰ presetِ ناشناخته همان خطایِ پیشین را می‌دهد و بدنهٔ کش نمی‌شود
FAIL ۱۱ پس ازِ خطا، همان کلیدِ درست بدنهٔ درست را می‌گیرد  ← {'http': 200, 'bytes': 7489048}

نتیجه: 3 سبز، 8 قرمز
```
