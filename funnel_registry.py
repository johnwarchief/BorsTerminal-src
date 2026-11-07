# -*- coding: utf-8 -*-
"""funnel_registry.py — تک‌منبعِ «کدام فیلترها و کدام presetها» درِ قیف FTS.

چرا این فایل هست: تا پیش از این، فهرستِ فیلترهایِ قیف یک آرایۀ پنج‌تاییِ
hardcoded درِ فرانت بود (`ftsFunnel.ts` → `FILE_FILTERS`)، درحالی‌که بک‌اند
هفت فیلترِ canonical می‌سازد (`tape_flags.py`: دو تایِ آخر `f_smart` و
`f_legal` از دو فایلِ «ورود پول هوشمند»). هیچ‌جا هم نوشته نشده بود هر عدد
از کدام سطرِ کدام فایل آمده — یعنی «رجیستری» نداشتیم، فقط یک فهرست.

قواعدِ این ماژول:
  • هیچ آستانه‌ای اینجا اختراع نمی‌شود. هر `value` یا از ثابتِ `tape_flags`
    برمی‌دارد یا عددِ عینِ فایلِ منبع است؛ منبعِ هر عدد در فیلدِ `source`
    نوشته شده (فایل:سطر). چیزی که منبع ندارد در `note` می‌آید و `status`
    فیلتر را `unverified` می‌کند.
  • متنِ فایل‌ها درِ این ماژول *کپی* نمی‌شود؛ اثرِ انگشتیِ sha256شان پین شده
    تا گاردِ `dev/funnel_registry_v1.py` با بازنویسیِ فایل منبع قرمز شود.
    (باندلِ خودِ txtها درِ EXE لازم نیست: آنچه درِ Trace دیده می‌شود همین
    hash و نشانیِ فایل است، نه متنش.)
  • `configurable=True` فقط جایی است که جزوه صریحاً گفته این عدد دستِ کاربر
    است (ضریبِ حجمِ الگوی ساعت، دامنهٔ حجمِ مشکوک). بقیه قفل‌اند — فیلترِ
    canonical عوض‌شدنی نیست، فقط parameterهایِ مجاز.
  • ترتیبِ `FILTERS` همان ترتیبِ رجیستری درِ Workspace است؛ ترتیبِ `chain` درِ
    هر preset همان ترتیبِ اجراست (اشتراکِ ترتیبی، نه OR).

این ماژول فقط *تعریف* است: هیچ داوری‌ای نمی‌کند. اجرایِ زنجیره درِ موتورِ
قیف (مرحلۀ E) است و حکمِ بنیادی درِ `fts_engine`/`api.fundamental` می‌ماند.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

import tape_flags as TF

REGISTRY_VERSION = "1"


# ── تعاریف ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class FilterParam:
    """یک عددِ فیلتر، با منبعش. `value_text` برایِ ساختارهایِ غیرعددی."""
    param_id: str
    label: str
    source: str
    value: float | None = None
    value_text: str = ""
    unit: str = ""
    configurable: bool = False
    min_value: float | None = None
    max_value: float | None = None
    note: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "param_id": self.param_id, "label": self.label, "source": self.source,
            "value": self.value, "value_text": self.value_text or None,
            "unit": self.unit, "configurable": self.configurable,
            "min": self.min_value, "max": self.max_value, "note": self.note or None,
        }


@dataclass(frozen=True)
class FunnelFilter:
    filter_id: str
    name: str
    description: str
    source_file: str
    source_sha256: str
    formula_version: str
    backend_impl: str
    params: tuple[FilterParam, ...]
    test_refs: tuple[str, ...] = ()
    # 'backend' = پرچمِ بک‌اند برایِ کلِ تابلو ساخته می‌شود.
    # 'backend-partial' = بعضی قیدهایِ فایل هنوز درِ بانک سنجیده نمی‌شوند (درِ note).
    availability: str = "backend"
    status: str = "canonical"
    note: str = ""

    def param(self, param_id: str) -> FilterParam:
        for p in self.params:
            if p.param_id == param_id:
                return p
        raise KeyError(f"{self.filter_id}.{param_id}")

    def as_json(self) -> dict[str, Any]:
        return {
            "filter_id": self.filter_id, "name": self.name,
            "description": self.description, "source_file": self.source_file,
            "source_hash": self.source_sha256, "formula_version": self.formula_version,
            "backend_impl": self.backend_impl, "availability": self.availability,
            "status": self.status, "note": self.note or None,
            "params": [p.as_json() for p in self.params],
            "test_refs": list(self.test_refs),
        }


@dataclass(frozen=True)
class FunnelPreset:
    preset_id: str
    label: str
    chain: tuple[str, ...]
    technical_gate: str
    source: str
    # ترتیبِ مراحل: `tape_first` = رفتارِ امروزِ canonical (تابلو ← تکنیکال ← …)؛
    # `tech_first` = استراتژیِ تازه: تکنیکال ← تابلو ← بنیادی ← تحویل
    flow: str = "tape_first"
    status: str = "canonical"
    note: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id, "label": self.label,
            "chain": list(self.chain), "technical_gate": self.technical_gate,
            "flow": self.flow,
            "source": self.source, "status": self.status, "note": self.note or None,
        }


@dataclass(frozen=True)
class TechFilter:
    """یک شرطِ تکنیکال که **از ستونِ ساخته‌شدۀ `funnel_tech_scan`** خوانده می‌شود.

    چرا ستون، نه محاسبۀ دوم: `_fts_analyze_symbol` داوریِ رسمی را یک بار برایِ کل
    جوامع ساخته (funnel_tech_scan.py:1-34)؛ دوباره‌حساب‌کردنش درِ قیف همان «دو
    داورِ تکنیکال» را می‌ساخت که ممیزیِ قیف به‌عنوانِ عیبِ اول رد کرد. پس اینجا هیچ
    فرمولِ تازه‌ای نیست و هیچ آستانه‌ای اختراع نمی‌شود — `expect` فقط می‌گوید کدام
    مقدارِ همان ستون «خورده شد» است.

    role:
      gate  ⇒ اجباری، خاموش‌شدنی نیست (وتوی هفتگی — رأیِ ۱۲)
      entry ⇒ انتخابی، اشتراکِ منطقی (عبور = خوردنِ همهٔ انتخاب‌شده‌ها)
      risk  ⇒ انتخابی، حذف‌کننده (نمادِ دارایِ آن شاهدِ خروج رد می‌شود)
    origin:
      chart ⇒ سطرِ خودِ چارت ۳/جزوه آن را می‌گوید
      program ⇒ خودِ برنامه آن را ساخته و منبعِ جزوه‌ای ندارد ⇒ درِ رابط «شاهدِ
                برنامه‌ای» برچسب می‌گیرد و هرگز قاعدۀ جزوه جا می‌زند
    """
    filter_id: str
    name: str
    description: str
    role: str
    column: str
    expect: dict[str, str]
    source: str
    origin: str
    note: str = ""
    # هر شرط می‌تواند پارامترهایِ خودش را داشته باشد (آستانه، بازه، منبعِ عدد).
    # تا پیش از این فقط فیلترهایِ تابلو پارامتر داشتند؛ رأیِ مالک ۲۰۲۶-۱۰-۱۸
    # می‌گوید «هر فیلتر باید تنظیماتِ مربوط به خودش را داشته باشد» — پس همان
    # `FilterParam` اینجا هم می‌آید، با همان قاعده: بی‌منبع، عدد نمی‌گذاریم.
    params: tuple[FilterParam, ...] = ()

    def param(self, param_id: str) -> FilterParam | None:
        for p in self.params:
            if p.param_id == param_id:
                return p
        return None

    def as_json(self) -> dict[str, Any]:
        return {"filter_id": self.filter_id, "name": self.name,
                "description": self.description, "role": self.role,
                "column": self.column, "expect": dict(self.expect),
                "source": self.source, "origin": self.origin, "note": self.note or None,
                "params": [p.as_json() for p in self.params]}


# ── هفت فیلترِ canonical از docs/*.txt ────────────────────────────────────
# تنها ارجاع‌هایِ واقعی: فایلی که درِ دیسک هست و همان filter_id را می‌سنجد.
# `tools/tape_formula_parity.py` پاریتیِ تمام‌ست با متنِ فایل است (هر هفت فیلتر)؛
# بقیه درِ پایین فهرست می‌شوند. `dev/funnel_registry_v1.py` وجودِ هر مسیر را می‌سنجد.
_TESTS = ("tools/tape_formula_parity.py",)

FILTERS: tuple[FunnelFilter, ...] = (
    FunnelFilter(
        filter_id="f_clock",
        name="الگوی ساعت",
        description="آخرین روی پایانیِ ۲٪، حجمِ بیشتر از میانگینِ نشست‌ها و تعدادِ معامله.",
        source_file="docs/الگوی ساعت.txt",
        source_sha256="6637192e4d10a73d",
        formula_version="txt-1",
        backend_impl="tape_flags.clock_flag",
        test_refs=_TESTS + ("dev/tape_filters_v1034.py", "tools/tape_parity_fuzz.py", "dev/test_mainwatch_flags_v1.py", "frontend/src/__tests__/tape-fuzz-parity.spec.ts", "frontend/src/__tests__/tape-patterns.spec.tsx"),
        params=(
            FilterParam("clock_delta", "فاصلۀ آخرین از پایانی", "docs/الگوی ساعت.txt:1 `(pl)>=(pc)*1.02`",
                        value=TF.CLOCK_DELTA, unit="کسر",
                        note="تعارضِ X-1: چارت ۳ و FTS_SPEC.md:73 عددِ ۱٪ را می‌آورند؛ رأی ۱۸ «گد رو عین فرمول‌ها بکن» ⇒ همان ۱٫۰۲."),
            FilterParam("vol_mult", "ضریبِ حجم", "docs/الگوی ساعت.txt:1 `(tvol)>1*(Σ[ih][0..29]/30)`",
                        value=1.0, unit="×میانگین", configurable=True, min_value=1.0, max_value=5.0,
                        note="جزوه صریحاً این عدد را دستِ کاربر گذاشته: «می توانیم عدد 1 را به 3 یا 5 تغییر دهیم» (jozve…1-24.md:610-611)."),
            FilterParam("min_trades", "حداقلِ تعدادِ معامله", "docs/الگوی ساعت.txt:1 `(tno)>30`",
                        value=float(TF.CLOCK_TRADES), unit="معامله"),
            FilterParam("base_sessions", "پنجرةٔ میانگینِ حجم", "docs/الگوی ساعت.txt:1 Σ[ih][0..29]",
                        value=float(TF.VOL_BASE_SESSIONS), unit="نشست",
                        note="رأی ۱۸ بند ۲: مبناء از month_avg_vol به همین Σ/۳۰ عوض شد. انحرافِ ثبت‌شده: بانکِ ما نشستِ بی‌معامله را ندارد، پس تقسیم بر شمارِ نشستِ *موجود* (کفِ ۱۰) می‌شود."),
        ),
    ),
    FunnelFilter(
        filter_id="f_susp",
        name="حجم مشکوک",
        description="حجمِ همین نشست سه برابرِ میانگینِ سی نشست، با حداقلِ تعدادِ معامله.",
        source_file="docs/حجم مشکوک.txt",
        source_sha256="b8a185c4168be33e",
        formula_version="txt-1",
        backend_impl="tape_flags.suspicious_flag",
        test_refs=_TESTS + ("dev/tape_filters_v1034.py", "tools/tape_parity_fuzz.py", "dev/test_mainwatch_flags_v1.py", "frontend/src/__tests__/tape-fuzz-parity.spec.ts", "frontend/src/__tests__/tape-patterns.spec.tsx"),
        params=(
            FilterParam("vol_mult", "ضریبِ حجم", "docs/حجم مشکوک.txt:1 `(tvol)>3*(Σ[ih][0..29]/30)`",
                        value=TF.SUSP_VOL_MULT, unit="×میانگین", configurable=True,
                        min_value=2.5, max_value=5.0,
                        note="دامنه از جزوه: «(tvol)>2.5 یا (tvol)>5» (jozve…1-24.md:615-618)."),
            FilterParam("min_trades", "حداقلِ تعدادِ معامله", "docs/حجم مشکوک.txt:1 `(tno)>50`",
                        value=float(TF.SUSP_TRADES), unit="معامله"),
            FilterParam("base_sessions", "پنجرةٔ میانگینِ حجم", "docs/حجم مشکوک.txt:1",
                        value=float(TF.VOL_BASE_SESSIONS), unit="نشست"),
        ),
    ),
    FunnelFilter(
        filter_id="f_jet",
        name="فیلتر جت",
        description="حجمِ سنگین + قدرتِ خریدارِ حقیقی + شکستنِ سقفِ ایستای هشت پنجره.",
        source_file="docs/فیلتر جت.txt",
        source_sha256="e93cab46073567c0",
        formula_version="txt-1",
        backend_impl="tape_flags.jet_flag",
        test_refs=_TESTS + ("dev/tape_filters_v1034.py", "tools/tape_parity_fuzz.py", "frontend/src/__tests__/tape-fuzz-parity.spec.ts", "frontend/src/__tests__/tape-patterns.spec.tsx"),
        params=(
            FilterParam("vol_mult", "ضریبِ حجم", "docs/فیلتر جت.txt:1 `(tvol)>3*(Σ…/30)`",
                        value=TF.JET_VOL_MULT, unit="×میانگین"),
            FilterParam("buyer_power", "سرانۀ سفارشِ خرید به فروشِ حقیقی",
                        "docs/فیلتر جت.txt:1 `Buy_I_Volume/Buy_CountI >= 1.5*Sell_I_Volume/Sell_CountI`",
                        value=TF.JET_BUYER_POWER, unit="×"),
            FilterParam("resistance_ladder", "پنجره‌هایِ سقفِ ایستا",
                        "docs/فیلتر جت.txt:1 [ih][59,49,39,29,19,9,5,2].PriceMax",
                        value_text=",".join(str(k) for k in TF.JET_LADDER), unit="نشستِ پیش"),
            FilterParam("min_trades", "حداقلِ تعدادِ معامله", "docs/فیلتر جت.txt:1 `(tno)>1 && (tno)>100`",
                        value=float(TF.JET_MIN_TRADES), unit="معامله",
                        note="تعارضِ X-3 / پرسشِ Q-2: رأی ۱۷ می‌گوید جزوه و چارت ۳ چنین کفی ندارند و رأی ۱۸ آن را برایِ بجِ تابلو نگه داشته؛ درِ قیف هنوز رأیِ صریح ندارد."),
        ),
    ),
    FunnelFilter(
        filter_id="f_roobi",
        name="کف روبی صف فروش",
        description="قیمت رویِ آستانۀ مجاز پایین چسبیده و صفِ خریدِ سنگین همان‌جا نشسته است.",
        source_file="docs/کف روبی صف فروش.txt",
        source_sha256="053a12a7c96b6e4f",
        formula_version="txt-1",
        backend_impl="tape_flags.roobi_flag",
        test_refs=_TESTS + ("dev/tape_filters_v1034.py", "tools/tape_parity_fuzz.py", "frontend/src/__tests__/tape-fuzz-parity.spec.ts", "frontend/src/__tests__/tape-patterns.spec.tsx"),
        availability="backend-partial",
        params=(
            FilterParam("plp_max", "سقفِ درصدِ آخرین", "docs/کف روبی صف فروش.txt:1 `(plp)<-1`",
                        value=TF.ROOBI_MAX_CHANGE, unit="٪"),
            FilterParam("zd1_min", "حداقلِ تعدادِ سفارشِ سطرِ اولِ خرید", "docs/کف روبی صف فروش.txt:1 `(zd1)>1`",
                        value=float(TF.ROOBI_ZD1_MIN), unit="سفارش"),
            FilterParam("qd1_min", "حداقلِ حجمِ سفارشِ سطرِ اولِ خرید", "docs/کف روبی صف فروش.txt:1 `(qd1)>100`",
                        value=float(TF.ROOBI_QD1_MIN), unit="سهم",
                        note="رأی ۱۸ بندِ انحرافِ ۲: ستونِ qd1 تازه به daily_prices آمده؛ تا نبودش این قید سنجیده نمی‌شود و جانشینِ حدسی هم نمی‌خواهد."),
        ),
        note="تقریبِ جزوه: «(tno)>200» به‌جایِ کف‌روبیِ سخت (jozve…1-24.md:616) — ثبت‌شده، فعلاً درِ کد نیست.",
    ),
    FunnelFilter(
        filter_id="f_noqteh",
        name="نقطه زنی",
        description="قیمت پایانی زیرِ ۳٪ از کمینۀ ماه، با حجمِ بیشتر از میانگین و حداقلِ تعدادِ معامله.",
        source_file="docs/نقطه زنی.txt",
        source_sha256="e5d4fd99a6811443",
        formula_version="txt-1",
        backend_impl="tape_flags.noqteh_flag",
        test_refs=_TESTS + ("dev/tape_filters_v1034.py", "tools/tape_parity_fuzz.py", "frontend/src/__tests__/tape-fuzz-parity.spec.ts"),
        params=(
            FilterParam("max_dist", "سقفِ فاصلۀ تا کفِ ماه", "docs/نقطه زنی.txt:1 `(cfield2)<3`",
                        value=TF.NOQTEH_MAX_DIST, unit="٪"),
            FilterParam("low_window", "پنجرةٔ کمینه", "docs/نقطه زنی.txt حلقۀ `n=1; n<29`",
                        value=float(TF.LOW_BASE_SESSIONS), unit="نشست",
                        note="تعارضِ X-4 / پرسشِ Q-3: کرانِ `dist>=0` درِ v1.0.33 بی‌رأی وارد شده بود و رأی ۲۰ آن را پس داد."),
            FilterParam("vol_mult", "ضریبِ حجم", "docs/نقطه زنی.txt:1 `(tvol)>1*(Σ…/30)`",
                        value=1.0, unit="×میانگین"),
            FilterParam("min_trades", "حداقلِ تعدادِ معامله", "docs/نقطه زنی.txt:1 `(tno)>5`",
                        value=float(TF.NOQTEH_TRADES), unit="معامله"),
        ),
    ),
    FunnelFilter(
        filter_id="f_smart",
        name="ورود پول هوشمند",
        description="حجمِ ۱٫۵ برابرِ میانگین با سرانۀ سفارشِ خریدِ حقیقیِ بیشتر از فروش، رویِ روندِ صعودیِ همان نشست.",
        source_file="docs/ورود پول هوشمند.txt",
        source_sha256="590e52a23c78166f",
        formula_version="txt-1",
        backend_impl="tape_flags.smart_money_flag",
        test_refs=_TESTS + ("dev/tape_filters_v1034.py", "dev/tape_smartmoney_v1074.py", "dev/test_mainwatch_flags_v1.py"),
        availability="backend-partial",
        params=(
            FilterParam("vol_mult", "ضریبِ حجم", "docs/ورود پول هوشمند.txt:1 `(tvol)>1.5*(Σ…/30)`",
                        value=TF.SMART_VOL_MULT, unit="×میانگین"),
            FilterParam("buyer_power_ge", "سرانۀ خرید ≥ سرانۀ فروشِ حقیقی",
                        "docs/ورود پول هوشمند.txt:1", value=TF.SMART_BP_GE, unit="×"),
        ),
        note="سطرهایِ ۲ و ۳ همان فیلتر با مبناءهایِ [is5]/[is6]اند؛ آن آرایه درِ بانکِ ما ذخیره نمی‌شود، پس آن دو variant سنجیده **نمی‌شوند** (نه جانشینِ حدسی). فایل هیچ qidِ تعدادِ معاملۀ دیگری ندارد و اضافه نشده است.",
    ),
    FunnelFilter(
        filter_id="f_legal",
        name="پول هوشمند و کد به کد حقوقی به حقیقی",
        description="همان چهار قیدِ «ورود پول هوشمند» + خریدِ حقوقی و فروشِ حقیقیِ هر دو بالایِ نصفِ حجمِ نشست.",
        source_file="docs/ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt",
        source_sha256="92adf93e9d5e1df4",
        formula_version="txt-1",
        backend_impl="tape_flags.legal_to_retail_flag",
        test_refs=_TESTS + ("dev/tape_smartmoney_v1074.py", "dev/test_mainwatch_flags_v1.py"),
        availability="backend-partial",
        params=(
            FilterParam("legal_share", "سهمِ هر دو طرف از حجمِ نشست",
                        "docs/…کد به کد…txt:1 `Buy_I_Volume>0.5*(tvol) && Sell_N_Volume>0.5*(tvol)`",
                        value=TF.LEGAL_SHARE_OF_TVOL, unit="سهمِ tvol"),
        ),
        note="قیدهایِ فایل «حقوقی می‌خرد / حقیقی می‌فروشد» را می‌خواهد؛ نامِ فایل «حقوقی به حقیقی» است و ما عیناً از متنِ فایل پیروی می‌کنیم، نه از نام.",
    ),
)

BY_ID: dict[str, FunnelFilter] = {f.filter_id: f for f in FILTERS}

#: فیلترهایی که درِ هیچ منبعی فرمول ندارند و عمداً درِ رجیستری نیستند.
UNIMPLEMENTED_FILTERS: dict[str, str] = {
    "خشک کردن": "نام درِ FTS_CHART3_extracted_text.txt (بلوکِ روندگیر) هست، فرمول هیچ‌جا نیست ⇒ NOT FOUND",
}

# ── فیلترهای تکنیکال (از ستون‌های funnel_tech_scan؛ بی‌فرمولِ تازه) ─────────
C3 = "docs/fts-notes/FTS_CHART3_extracted_text.txt"
TECH_FILTERS: tuple[TechFilter, ...] = (
    TechFilter("t_weekly_up", "روند هفتگی صعودی",
               "وتوی رسمی: نزولی یا خنثی هفتگی ⇒ رد؛ فقط صعودی ادامه می‌دهد.",
               "gate", "tech_trend_w", {"equals": "up"},
               f"{C3}:31-33", "chart",
               "رأیِ ۱۲: هم نزولی و هم خنثی هفتگی reject است. خاموش‌شدنی نیست."),
    TechFilter("t_daily_up", "روند روزانۀ صعودی",
               "روزانه هم صعودی باشد (شاخۀ پولبک/جت).",
               "entry", "tech_trend_d", {"equals": "up"}, f"{C3}:34", "chart"),
    TechFilter("t_setup_jet", "ستاپ جت",
               "عبور از سقفِ ایستا با حجم و قدرتِ خریدار، از همان داورِ `jet`ِ تحلیل.",
               "entry", "tech_jet", {"truthy": "1"}, f"{C3}:36,142", "chart"),
    TechFilter("t_setup_fib_33_40", "ناحیۀ فیبوناتچی ۳۳–۴۰",
               "قیمت در کمربندِ اولِ اصلاحِ موج است — درِ روند صعودی، موجی که "
               "به این ناحیه رسیده برایِ بررسیِ ورود می‌ایستد.",
               "entry", "tech_fib_zone", {"equals": "33-40"},
               f"{C3}:38 · jozve_FTS_handwritten_pages_1-24.md:529 · "
               "transcription_p10-p18.md:300", "chart",
               "کمربندِ اصلیِ ورودِ جزوه؛ رأیِ مالک ۱۴۰۵-۰۷-۲۷: «۳۳ تا ۴۰ یک نیاز "
               "اصلی است، با نزدیک ۳۰٪ یا ۶۱٫۸–۷۰ ادغام نشود». شاهدِ داوری "
               "(عمقِ اصلاح و نقاطِ موج) از ستون‌هایِ tech_fib_* خوانده می‌شود.",
               (FilterParam("fib_lo", "کفِ کمربند (٪ اصلاح)",
                            "docs/fts-notes/jozve_FTS_handwritten_pages_1-24.md:529 «رن فیبو 33 تا 40»",
                            value=33.0, unit="٪",
                            note="مقیاسِ سنجش لگاریتمی است، نه خطی (جزوه ص ۹: «Fib levels on log»)."),
                FilterParam("fib_hi", "سقفِ کمربند (٪ اصلاح)",
                            "docs/fts-notes/jozve_FTS_handwritten_pages_1-24.md:529",
                            value=40.0, unit="٪"))),
    TechFilter("t_setup_fib_618_70", "ناحیۀ فیبوناتچی ۶۱٫۸–۷۰",
               "قیمت در کمربندِ دومِ اصلاحِ موج است (پلۀ دومِ ورود).",
               "entry", "tech_fib_zone", {"equals": "61.8-70"},
               f"{C3}:38 · jozve_FTS_handwritten_pages_1-24.md:739 «یک پله ورود در 60-70»",
               "chart", "کمربندِ دوم؛ جدا از ۳۳–۴۰ شمرده و گزارش می‌شود.",
               (FilterParam("fib_lo", "کفِ کمربند (٪ اصلاح)",
                            "docs/fts-notes/jozve_FTS_handwritten_pages_1-24.md:739",
                            value=61.8, unit="٪"),
                FilterParam("fib_hi", "سقفِ کمربند (٪ اصلاح)",
                            "docs/fts-notes/jozve_FTS_handwritten_pages_1-24.md:739",
                            value=70.0, unit="٪"))),
    TechFilter("t_setup_choch", "CHoCH صعودی",
               "شکستِ آخرین کف در روندِ نزولی (تغییرِ ساختارِ صعودی).",
               "entry", "tech_choch_bull", {"truthy": "1"}, f"{C3}:39", "chart"),
    TechFilter("t_setup_double_bottom", "کف دوقلو",
               "دو کف تا ۱٫۵٪، با شکستِ آخرین سقف.",
               "entry", "tech_double_bottom", {"truthy": "1"}, f"{C3}:42", "chart"),
    TechFilter("t_setup_range_break", "شکستِ باکس/رنج",
               "خروجِ معتبر از جعبهٔ رِنج — سازۀ خودِ برنامه، سطرِ مستقلِ جزوه ندارد.",
               "entry", "tech_range_break", {"truthy": "1"}, "program: api/chart.py range_box",
               "program"),
    TechFilter("t_hourglass_accelerate", "ساعت‌شنی: خریدِ شتابان",
               "قیمت هفتگی نسبت به MA52 در حالتِ انتخابی و RSI هفتگی در اشباع فروش.",
               "entry", "tech_hourglass_action", {"equals": "ACCELERATE_BUY_2X_4X"},
               f"{C3}:141 · OWNER_RULINGS.md رأیِ ۲۴", "chart",
               "دورۀ RSI و سطحِ اشباع از تنظیمِ فعالِ موتور خوانده می‌شود، نه از عددِ ثابت."),
    TechFilter("t_risk_third_peak", "شاهدِ سقفِ سوم",
               "نزدیکی به خطِ روند در سومینِ سقف (هفتگی ۱۰٪ / روزانۀ ۵٪).",
               "risk", "tech_exit_signals", {"signal": "third_peak"}, f"{C3}:45", "chart"),
    TechFilter("t_risk_divergence", "شاهدِ واگراییِ RSI",
               "سقفِ بالاتر در قیمت و پایین‌تر در RSI(14).",
               "risk", "tech_exit_signals", {"signal": "rsi_divergence"},
               "docs/fts-notes/transcription_p10-p18.md:39-40 · " + C3 + ":46", "chart"),
    TechFilter("t_risk_rsi_rollover", "شاهدِ چرخشِ RSI از اشباع",
               "RSI از منطقۀ اشباع برگشته است.",
               "risk", "tech_exit_signals", {"signal": "rsi_rollover"},
               "program: api/chart.py _fts_exit_layer4", "program"),
    TechFilter("t_risk_ma14_trail", "شاهدِ خروجِ MA14",
               "دو بدنۀ متوالی زیر MA14 (لایۀ ۱ خروج).",
               "risk", "tech_exit_signals", {"signal": "ma14_trail"},
               f"{C3}:49-50 · FTS-TREND-CLASSIFIER-AUDIT-1405-07-13.md:39", "chart",
               "خودِ ممیزی «MISMATCH منبع/کد» را ثبت کرده: جزوه یک کندلِ کامل می‌خواهد."),
    TechFilter("t_risk_channel_break", "شاهدِ شکستِ کانال",
               "قیمت از کانالِ روند بیرون آمده است.",
               "risk", "tech_exit_signals", {"signal": "channel_break"},
               "program: api/chart.py exit engine", "program"),
    TechFilter("t_risk_double_top", "شاهدِ سقفِ دوقلو",
               "سقفِ دوقلو در سازۀ خروج.",
               "risk", "tech_exit_signals", {"signal": "double_top"}, f"{C3}:43", "chart"),
    TechFilter("t_risk_hs_break", "شاهدِ شکستِ خطِ گردنِ سروشانه",
               "سروشانه با خطِ گردنِ شکسته‌شده.",
               "risk", "tech_exit_signals", {"signal": "hs_break"}, f"{C3}:44", "chart"),
)

TECH_BY_ID: dict[str, TechFilter] = {f.filter_id: f for f in TECH_FILTERS}
TECH_GATE_IDS = tuple(f.filter_id for f in TECH_FILTERS if f.role == "gate")
TECH_ENTRY_IDS = tuple(f.filter_id for f in TECH_FILTERS if f.role == "entry")
TECH_RISK_IDS = tuple(f.filter_id for f in TECH_FILTERS if f.role == "risk")


# ── presetها ──────────────────────────────────────────────────────────────
# گیتِ تکنیکالِ پیش‌فرض همان داورِ رسمیِ روند است (هفتگی داورِ جهت، روزانه
# داورِ ورود) که درِ `_fts_analyze_candles` (api/chart.py:2791، شاخه‌ها :2840-2891)
# ساخته می‌شود.
# «none» یعنی این استراتژی هیچ دروازۀ تحمیلی‌شدنی ندارد. رأیِ مالک
# ۱۴۰۵-۰۷-۲۷: «قواعد، آستانه‌ها و گیت‌های هفتگی و روزانۀ استراتژی قدیمی را
# خودکار به استراتژی جدید منتقل نکن». بی‌این نشان، `technical_gate` تهی را موتور
# همان `TREND_GATE` همیشگی می‌خواند و «خاموش‌کردن» فقط در ظاهر می‌ماند.
NO_GATE = "none"

TREND_GATE = "trend_matrix"
HOURGLASS_GATE = "hourglass_ma52_rsi5_weekly"

PRESETS: tuple[FunnelPreset, ...] = (
    FunnelPreset(
        preset_id="swing", label="شخص نوسان‌گیر (زیر ۳ ماه)",
        chain=("f_clock", "f_jet", "f_susp"), technical_gate=TREND_GATE,
        source="FTS_CHART3_extracted_text.txt بلوکِ «فیلتر / نوسانگیر»: ساعت + جت + حجم مشکوک",
        note="سطرِ «مهندسی معکوس ۱-تابلو خوانی فیلتر حجم مشکوک الگوی ساعت کف روبی ۲-تکنیکال ۳-بنیادی» ترتیبِ دیگری می‌دهد؛ چارت ۳ مرجعِ چیدمان است و همان نگه داشته شده.",
    ),
    FunnelPreset(
        preset_id="trend", label="شخص روندگیر (بالای ۳ ماه)",
        chain=("f_roobi", "f_noqteh"), technical_gate=TREND_GATE,
        source="FTS_CHART3_extracted_text.txt بلوکِ روندگیر: کف روبی + نقطه زنی (ورود در کف سوم یا پنجم) · jozve…1-24.md:584",
        note="جزوه: «روندگیر: به حجم مشکوک نیازی ندارد» (jozve…1-24.md:540) — پس حجم مشکوک درِ این preset نیست.",
    ),
    FunnelPreset(
        preset_id="hourglass", label="استراتژی ساعت شنی (۳ تا ۱۰ ساله)",
        chain=(), technical_gate=HOURGLASS_GATE,
        source="jozve_FTS_handwritten_pages_25-34.md:74 «MA = 52 تایم هفتگی ؛ RSI = 5 تایم هفتگی» · :66 «در تایم هفتگی یا بالاتر فقط کار می‌کند» · چارت ۳ سطر ۱۴",
        status="unverified",
        note="هیچ فیلترِ تابلویی درِ هیچ منبعی برایش نیامده، پس زنجیره‌اش تهی است. کدِ پیشِ این دور `f_roobi,f_clock` را قرض می‌گرفت که بی‌منبع است ⇒ حذف شد و منتظرِ رأیِ مالک (Q-1) است. خودِ سیگنال درِ api/chart.py:2767-2790 پیاده است.",
    ),
    FunnelPreset(
        preset_id="tech_first", label="تکنیکال اول (غربالِ نموداری پیش از تابلو)",
        chain=(), technical_gate=NO_GATE, flow="tech_first",
        source="مأموریتِ مالک ۱۴۰-۰۷-۲۶: «تکنیکال ← تابلوخوانی ← بنیادی ← تحویل»",
        note="فیلترهایِ این مسیر از ستون‌های funnel_tech_scan خوانده می‌شوند. "
             "تصحيحِ رأیِ ۱۴۰۵-۰۷-۲۷: وتوی هفتگی دیگر خودکار تحمیل نمی‌شود؛ "
             "شرطِ هفتگی و روزانه درِ `STRATEGY_SETTINGS[tech_first]` انتخاب "
             "می‌شوند و پیش‌فرضِ هر قاعدۀ تأییدنشده «اعمال‌نشدن» است.",
    ),
    FunnelPreset(
        preset_id="custom", label="مسیر سفارشی (انتخاب دستی)",
        chain=(), technical_gate=TREND_GATE,
        source="مأموریتِ مالک ۱۴۰۵-۰۷-۱۶ بند ۴: کاربر از کلِ رجیستری می‌چیند",
        note="زنجیره‌ای که کاربر می‌سازد؛ هیچ فیلتری به‌عنوانِ پیش‌فرض تحمیل نمی‌شود.",
    ),
)

PRESET_BY_ID: dict[str, FunnelPreset] = {p.preset_id: p for p in PRESETS}


# ── کمکی‌ها ────────────────────────────────────────────────────────────────
def filter_ids() -> tuple[str, ...]:
    return tuple(f.filter_id for f in FILTERS)


def get_filter(filter_id: str) -> FunnelFilter:
    return BY_ID[filter_id]


def get_preset(preset_id: str) -> FunnelPreset:
    return PRESET_BY_ID[preset_id]


def tech_filter_ids() -> tuple[str, ...]:
    return tuple(f.filter_id for f in TECH_FILTERS)


def get_tech_filter(filter_id: str) -> TechFilter:
    return TECH_BY_ID[filter_id]


def resolve_tech_chain(preset_id: str, custom: Iterable[str] | None = None
                       ) -> tuple[str, ...]:
    """زنجیرۀ فیلترهایِ تکنیکال. گیتِ هفتگی همیشه داخلش است، حتی اگر کاربر نخواهد.

    انتخابِ ناشناخته KeyError می‌دهد (بی‌صدا رد نمی‌شود) و بی‌انتخاب، فقط گیت
    می‌ماند ⇒ داوری با امروزِ `technical_stage` یکی می‌شود.
    """
    chosen = tuple(custom or ())
    for fid in chosen:
        if fid not in TECH_BY_ID:
            raise KeyError(f"فیلترِ تکنیکالِ ناشناخته: {fid}")
    return TECH_GATE_IDS + tuple(f for f in chosen if f not in TECH_GATE_IDS)


def preset_chain(preset_id: str, custom: Iterable[str] | None = None) -> tuple[str, ...]:
    """زنجیرۀ اجراییِ یک preset. برایِ custom همان چیدستِ کاربر است.

    فیلترِ ناشناخته بی‌صدا رد نمی‌شود: KeyError می‌دهد تا UI گمراه نشود.
    """
    p = get_preset(preset_id)
    if p.preset_id != "custom":
        return p.chain
    chain = tuple(custom or ())
    for fid in chain:
        if fid not in BY_ID:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
    return chain


# ── تنظیماتِ مستقلِ هر استراتژی ───────────────────────────────────────────
@dataclass(frozen=True)
class StrategySetting:
    """یک پیچِ تنظیمیِ *همین* استراتژی — با پیش‌فرض، دامنه، معنا و اثرش.

    سه قاعده که این ساختار برایِ آن نوشته شد (رأیِ مالک ۱۴۵-۰۷-۲۷):
      • «هر فیلتر باید تنظیماتِ مربوط به خودش را داشته باشد» ⇒ `owner` می‌گوید
        این پیچ مالِ کدام فیلتر یا کدام گام است.
      • «تغییرِ تنظیم باید واقعاً درِ موتور اثر بگذارد» ⇒ `effect` نامِ همان
        نقطۀ اجرا را می‌برد؛ تنظیمی که خواننده ندارد اینجا جایی ندارد.
      • «قاعدۀ تأییدنشده را پیش‌فرضِ اجباری مکن» ⇒ `default` برایِ هر چیزی که
        رأیِ صریحِ مالک ندارد `off` است، نه «همان قاعدۀ قدیمی».
    """
    setting_id: str
    label: str
    owner: str            # filter_id یا "stage:technical"
    description: str
    choices: tuple[tuple[str, str], ...]
    default: str
    source: str
    effect: str

    def as_json(self) -> dict[str, Any]:
        return {"setting_id": self.setting_id, "label": self.label, "owner": self.owner,
                "description": self.description,
                "choices": [{"value": v, "label": t} for v, t in self.choices],
                "default": self.default, "source": self.source, "effect": self.effect}


STRATEGY_SETTINGS: dict[str, tuple[StrategySetting, ...]] = {
    "tech_first": (
        StrategySetting(
            "weekly_mode", "شرطِ روند هفتگی", "stage:technical",
            "سرنوشتِ نمادی که هفتگی‌اش صعودی نیست.",
            (("off", "اعمال نشود (هیچ وتویی ازِ هفتگی نمی‌آید)"),
             ("require_up", "فقط صعودی قبول است (قاعدۀ استراتژی کلاسیک، رأیِ ۱۲)"),
             ("reject_down", "نزولی ⇒ رد؛ خنثی و بی‌داده ⇒ رد نیست")),
            "off",
            "رأیِ مالک ۱۴۵-۰۷-۲۷: «شرط‌هایی مانند روند هفتگی خنثی یا نزولی ⇒ رد "
            "را بدون تعریف و تأیید برای استراتژی جدید اعمال نکن»",
            "technical_stage → `weekly_mode`"),
        StrategySetting(
            "daily_mode", "شرطِ روند روزانه", "stage:technical",
            "آیا روزانۀ صعودی هم لازم باشد.",
            (("off", "اعمال نشود"),
             ("require_up", "روزانه هم صعودی باشد (شاخۀ پولبک/جت)")),
            "off",
            "رأیِ مالک ۱۴۰۵-۰۷-۲۷: «الزام به صعودی‌بودن هم‌زمان هفتگی و روزانه "
            "بدون تعریف اعمال نشود»",
            "technical_stage → `daily_mode`"),
        StrategySetting(
            "clock_delta_pct", "آستانۀ الگوی ساعت", "f_clock",
            "اختلافِ آخرین از پایانی چقدر باشد تا «الگوی ساعت» بخورد.",
            (("1", "۱٪ — متنِ چارت ۳ و FTS_SPEC:73"),
             ("2", "۲٪ — متنِ فایلِ «الگوی ساعت» و پاریتیِ سطر‌به‌سطرِ سایت")),
            "1",
            "رأیِ مالک ۱۴۰۵-۰۷-۲۷: «برای اجرای اولیهٔ استراتژی جدید، ۱٪ پیش‌فرض "
            "قابل تغییر باشد؛ این فقط پیش‌فرض همین استراتژی است»",
            "funnel_engine._tape_miss → f_clock (به‌جای TF.CLOCK_DELTA)"),
    ),
}


def settings_defaults(preset_id: str) -> dict[str, str]:
    return {st.setting_id: st.default for st in STRATEGY_SETTINGS.get(preset_id, ())}


def validate_settings(preset_id: str, given: dict[str, Any] | None) -> dict[str, str]:
    """تنظیماتِ درخواستی را به همان چارچوبِ تعریف‌شده برمی‌گرداند.

    انتخابِ ناشناخته بی‌صدا اصلاح نمی‌شود: KeyError. پیش‌فرضِ هر پیچ هم از خودِ
    تعریف خوانده می‌شود، نه ازِ یک جایِ دوم.
    """
    defs = STRATEGY_SETTINGS.get(preset_id)
    if not defs:
        return {}
    allowed = {st.setting_id: {v for v, _ in st.choices} for st in defs}
    out = settings_defaults(preset_id)
    for k, v in (given or {}).items():
        if k not in allowed:
            raise KeyError(f"تنظیمِ ناشناخته برایِ «{preset_id}»: {k}")
        v = str(v)
        if v not in allowed[k]:
            raise KeyError(f"مقدارِ «{v}» برایِ «{k}» مجاز نیست ({', '.join(sorted(allowed[k]))})")
        out[k] = v
    return out


def _fingerprint() -> str:
    """اثرِ انگشتیِ کلِ تعاریف — همان چیزی که درِ Trace باید مهر شود.

    هر تغییرِ عدد، منبع یا ترتیبِ زنجیره نسخه را عوض می‌کند، پس یک تصمیمِ
    ثبت‌شده درِ گذشته با نسخهٔ امروزِ قوانین اشتباه گرفته نمی‌شود.
    """
    h = hashlib.sha256()
    for f in FILTERS:
        h.update(f.filter_id.encode())
        h.update(f.source_sha256.encode())
        h.update(f.formula_version.encode())
        for p in f.params:
            h.update(f"{p.param_id}={p.value if p.value is not None else p.value_text}".encode())
    for t in TECH_FILTERS:
        h.update(f"{t.filter_id}:{t.role}:{t.column}:{sorted(t.expect.items())}".encode())
        for p in t.params:
            h.update(f"{t.filter_id}/{p.param_id}={p.value}".encode())
    # پیش‌فرضِ هر پیچِ تنظیمی هم قاعدۀ داوری است؛ اگر جابه‌جا شد، نسخه باید عوض شود.
    for pid, sts in sorted(STRATEGY_SETTINGS.items()):
        for st in sts:
            h.update(f"{pid}/{st.setting_id}={st.default}".encode())
    for p in PRESETS:
        h.update(f"{p.preset_id}:{'>'.join(p.chain)}:{p.technical_gate}:{p.flow}".encode())
    return h.hexdigest()[:12]


RULESET_VERSION = _fingerprint()


def as_json() -> dict[str, Any]:
    """پایبارِ کاملِ رجیستری — همان چیزی که /api/funnel/registry می‌دهد."""
    return {
        "registry_version": REGISTRY_VERSION,
        "ruleset_version": RULESET_VERSION,
        "filters": [f.as_json() for f in FILTERS],
        "presets": [p.as_json() for p in PRESETS],
        "unimplemented_filters": dict(UNIMPLEMENTED_FILTERS),
        "technical_filters": [t.as_json() for t in TECH_FILTERS],
        "strategy_settings": {k: [st.as_json() for st in v]
                              for k, v in sorted(STRATEGY_SETTINGS.items())},
        "technical_filter_groups": {"gate": list(TECH_GATE_IDS), "entry": list(TECH_ENTRY_IDS),
                                    "risk": list(TECH_RISK_IDS)},
        "gates": {
            "technical": [TREND_GATE, HOURGLASS_GATE],
            # دروازۀ بنیادی: سه شاخصِ اول بلاکر، دو تایِ آخر فقط شاهد.
            # اجرایِ این حکم مرحلۀ E است؛ اینجا فقط تعریفِ خواسته است.
            "fundamental": "mandatory_i1_i2_i3_supporting_i4_i5",
        },
    }
