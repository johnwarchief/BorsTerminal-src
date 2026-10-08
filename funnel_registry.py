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
    status: str = "canonical"
    note: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id, "label": self.label,
            "chain": list(self.chain), "technical_gate": self.technical_gate,
            "source": self.source, "status": self.status, "note": self.note or None,
        }


# ── هفت فیلترِ canonical از docs/*.txt ────────────────────────────────────
_TESTS = ("dev/test_tape_flags_v1059.py", "tools/tape_formula_parity.py")

FILTERS: tuple[FunnelFilter, ...] = (
    FunnelFilter(
        filter_id="f_clock",
        name="الگوی ساعت",
        description="آخرین روی پایانیِ ۲٪، حجمِ بیشتر از میانگینِ نشست‌ها و تعدادِ معامله.",
        source_file="docs/الگوی ساعت.txt",
        source_sha256="6637192e4d10a73d",
        formula_version="txt-1",
        backend_impl="tape_flags.clock_flag",
        test_refs=_TESTS + ("frontend/src/__tests__/tape-fuzz-parity.spec.ts",),
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
        test_refs=_TESTS,
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
        test_refs=_TESTS,
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
        test_refs=_TESTS,
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
        test_refs=_TESTS,
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
        test_refs=_TESTS,
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
        test_refs=_TESTS,
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

# ── presetها ──────────────────────────────────────────────────────────────
# گیتِ تکنیکالِ پیش‌فرض همان داورِ رسمیِ روند است (هفتگی داورِ جهت، روزانه
# داورِ ورود) که درِ api/chart.py:2703-2747 ساخته می‌شود.
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
    for p in PRESETS:
        h.update(f"{p.preset_id}:{'>'.join(p.chain)}:{p.technical_gate}".encode())
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
        "gates": {
            "technical": [TREND_GATE, HOURGLASS_GATE],
            # دروازۀ بنیادی: سه شاخصِ اول بلاکر، دو تایِ آخر فقط شاهد.
            # اجرایِ این حکم مرحلۀ E است؛ اینجا فقط تعریفِ خواسته است.
            "fundamental": "mandatory_i1_i2_i3_supporting_i4_i5",
        },
    }
