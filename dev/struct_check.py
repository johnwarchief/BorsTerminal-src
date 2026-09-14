import io, re

h = io.open("archive/legacy_static/index.html", encoding="utf-8").read()
a = io.open("archive/legacy_static/app.js", encoding="utf-8").read()
out = []

# ── تعداد th در thead جدول اسکرینر ──
i = h.find('id="screenerTable"')
thead = h[i:h.find("</thead>", i)]
ths = re.findall(r"<th\b[^>]*>(.*?)</th>", thead, re.S)
out.append("thead th تعداد = %d" % len(ths))
out.append("  " + " | ".join(re.sub(r"\s+", " ", t).strip()[:16] for t in ths))

# ── تعداد td در قالب ردیف اسکرینر (renderScreenerTable) ──
j = a.find("function renderScreenerTable")
body = a[j:a.find("async function openAnalysis", j)]
seg = body[body.find("html += `<tr"):]
seg = seg[:seg.find("`;</tr>`") + 8] if "`;</tr>`" in seg else seg[:seg.find("</tr>`")]
tds = re.findall(r"<td\b", seg)
out.append("")
out.append("tbody td قالب ردیف = %d" % len(tds))
out.append("  " + ("✅ هم‌تعداد با th" if len(tds) == len(ths) else "❌ عدم تطابق ستون‌ها"))
out.append("  ستون وضعیت موجود است: " + ("✅" if "data-selcell" in seg else "❌"))

# ── colspan placeholder ──
cs = re.search(r'screenerTableBody[\s\S]{0,200}?colspan="(\d+)"', h)
out.append("  colspan بارگذاری اولیه = " + (cs.group(1) if cs else "؟")
           + ("  ✅" if cs and cs.group(1) == str(len(ths)) else "  ❌"))

# ── جدول تابلوخوانی: هر دو دکمه بدون شرط ──
k = a.find('class="c-actions"')
blk = a[k - 400:k + 600]
out.append("")
out.append("تابلوخوانی — بلوک عملیات:")
out.append("  دکمه تکنیکال      : " + ("✅" if "gotoChart(" in blk else "❌"))
out.append("  دکمه تحلیل کامل   : " + ("✅" if "openAnalysis(" in blk else "❌"))
out.append("  شرط حذف‌شونده باقی مانده؟ : " + ("❌ بله" if re.search(r"row\.pe > 0 \|\| row\.eps > 0", blk) else "✅ خیر"))
out.append("  «بنیادی ندارد» حذف شد؟    : " + ("✅" if "بنیادی ندارد" not in blk else "❌"))

# ── ارجاع ستون وضعیت در app.js ──
out.append("  SEL.remember در رندر اسکرینر: " + ("✅" if "SEL.remember(data)" in body else "❌"))

# ── نشانه‌های index.html ──
out.append("")
for name, cond in [
    ("نوار تصمیم selBar در techView", 'id="selBar"' in h),
    ("مودال portfolioModal", 'id="portfolioModal"' in h),
    ("دکمهٔ سبد در نوار آمار اسکرینر", "SEL.openPortfolio()" in h),
    ("selection.js ثبت شد", "archive/legacy_static/selection.js?v=9.0.0" in h),
    ("app.js نسخه ۹", "archive/legacy_static/app.js?v=9.0.0" in h),
    ("styles.css نسخه ۹", "styles.css?v=9.0.0" in h),
    ("چک‌باکس صندوق بدون checked", bool(re.search(r'<input[^>]*value="fund"[^>]*>', h)) and "checked" not in re.search(r'<input[^>]*value="fund"[^>]*>', h).group(0)),
]:
    out.append(("  ✅ " if cond else "  ❌ ") + name)

# ── v9.8.1 فاز ۰ — قفل جداسازی دامنهها (interface freeze) ──
# app.js باید فقط مصرفکننده، و فایلهای دامنه باید تعریفکننده بمانند؛
# وگرنه استخراج بیصدا برمیگردد یا یک نسخهٔ دوم در اسکوپ جهانی ساخته میشود.
for _dom, _defs in [("fundamental_ui.js", ["function fmtMcap(",
                                          "async function loadFundamentalData(",
                                          "function fmtBil(",
                                          "function switchModalTab("]),
                    ("portfolio_ui.js", ["const PF_KEY", "let pfState",
                                         "function pfLoad(", "function pfSave(",
                                         "function pfRender(", "async function initPortfolio("])]:
    _src = io.open("archive/legacy_static/" + _dom, encoding="utf-8").read()
    for _d in _defs:
        out.append(("  ✅ " if _d in _src else "  ❌ ") + "%s تعریف میکند: %s" % (_dom, _d))
    for _d in [x.split("(")[0].replace("async function ", "").replace("function ", "")
               for x in _defs]:
        if _d in ("PF_KEY", "pfState"):
            out.append(("  ✅ " if re.search(r"^\s*(const|let)\s+%s\b" % _d, a, re.M)
                        else "  ❌ ") + "app.js دیگر %s را تعریف نمیکند" % _d)
        else:
            out.append(("  ✅ " if not re.search(r"\bfunction\s+%s\s*\(" % _d, a)
                        else "  ❌ ") + "app.js دیگر %s را تعریف نمیکند" % _d)
for _dom in ("fundamental_ui.js", "portfolio_ui.js"):
    out.append(("  ✅ " if "static/%s?v=9.8.1" % _dom in h else "  ❌ ")
               + "%s در index.html ثبت شد" % _dom)

# ── CSS ──
c = io.open("archive/legacy_static/styles.css", encoding="utf-8").read()
out.append("")
for name, cond in [(".sel-bar در CSS", ".sel-bar {" in c), (".sel-btn در CSS", ".sel-btn {" in c),
                   (".sel-accept در CSS", ".sel-accept" in c), (".sel-reject در CSS", ".sel-reject" in c),
                   (".sel-monitor در CSS", ".sel-monitor" in c)]:
    out.append(("  ✅ " if cond else "  ❌ ") + name)

io.open("dev/_struct.txt", "w", encoding="utf-8").write("\n".join(out))
print("ok")
