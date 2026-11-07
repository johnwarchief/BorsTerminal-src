#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""گیت‌هایِ اعتبارسنجیِ staging برایِ به‌روزرسانیِ خودکارِ کدال — بدونِ شبکه.

`validate_staging(main_db, staging_db, last_good)` فقط با `sqlite3`ِ استاندارد
کار می‌کند و هیچ فایلی نمی‌نویسد: هر دو DB با `mode=ro` باز می‌شوند. نبودِ
جدول/ستون یا خرابیِ DB «خطا/هشدار» در نتیجه است، نه استثنا. mainِ غایب، خراب
یا بدونِ جدول خطاست (fail-closed)، نه هشدار.

دامنهٔ بررسی‌ها: گیت‌هایِ سراسری (وجودِ جدول، پوشش، تکرارِ tracing_no، دورهٔ
آینده، پس‌رفتِ دوره) کلِ جدول را می‌بینند؛ بررسی‌هایِ ردیفی (منفی‌بودنِ درآمد،
gross>revenue، provenance) فقط رویِ ردیف‌هایِ **جدید یا تغییرکرده** نسبت به main
اجرا می‌شوند. مقایسه با tracing_no join می‌شود و «تغییر» یعنی هر ستونِ
`compare` (نه `fetched_at`) فرق کند؛ ردیفِ تاریخیِ خرابِ بدونِ تغییر شکست نمی‌دهد.
اگر main قابلِ اتکا نباشد (نبودِ DB/جدول/ستون)، همهٔ ردیف‌ها بررسی می‌شوند و
خودِ main نیز خطا ثبت می‌کند.

اصلاحِ پلن (مهم): `monthly_sales` ستونِ `gross_profit`، `url` و `publish_date`
ندارد. ستون‌هایِ هر جدول در `TABLE_SPECS` نقش‌بندی شده‌اند و هیچ کوئری‌ای نامِ
ستون را حدس نمی‌زند:

  codal_notices        : provenance = url و publish_date
  financial_statements : revenue/gross_profit، provenance = url و publish_date
  monthly_sales        : monthly_revenue/ytd_revenue، provenance = pdf_url یا
                         excel_url؛ مقایسهٔ gross با revenue رویِ این جدول ممنوع

خروجی: `{"ok": bool, "errors": list[str], "warnings": list[str], "stats": dict}`.
کدهایِ خطا برایِ مصرف‌کنندهٔ پایدار: `main_db_missing`، `main_db_unreadable`،
`main_table_missing:<table>`، `<table>_missing_table`، `<table>_missing_column:<col>`،
`<table>_coverage_drop`، `<table>_duplicate_tracing_no`، `<table>:negative_revenue:<col>`،
`<table>:gross_gt_revenue`، `<table>:missing_provenance`، `future_period:<table>`،
`fs_period_regressed`، `ms_period_regressed`،
`<table>_main_missing_column:period_end`، `main_query_failed:period:<table>`،
`<code>_main_period_unparseable`.
"""
import sqlite3
from datetime import date as _date
from pathlib import Path

TABLES = ("codal_notices", "financial_statements", "monthly_sales")

# نقشِ هر ستون — تنها منبعِ نامِ ستون‌ها در کوئری‌ها.
TABLE_SPECS = {
    "codal_notices": {
        "key": "tracing_no",
        "compare": ("symbol", "title", "url", "publish_date"),
        "provenance": ("url", "publish_date"),
        "provenance_mode": "all",
        "non_negative": (),
        "gross": None,
        "period": None,
    },
    "financial_statements": {
        "key": "tracing_no",
        "compare": ("period_end", "revenue", "gross_profit", "url",
                    "publish_date"),
        "provenance": ("url", "publish_date"),
        "provenance_mode": "all",
        "non_negative": ("revenue",),
        "gross": ("gross_profit", "revenue"),
        "period": "period_end",
    },
    "monthly_sales": {
        "key": "tracing_no",
        "compare": ("period_end", "monthly_revenue", "ytd_revenue",
                    "pdf_url", "excel_url"),
        "provenance": ("pdf_url", "excel_url"),
        "provenance_mode": "any",
        "non_negative": ("monthly_revenue", "ytd_revenue"),
        "gross": None,
        "period": "period_end",
    },
}

_COVERAGE_PCT = 95               # staging باید ≥ ۹۵٪ main باشد
_SAMPLE = 5                      # نمونهٔ tracing_no در پیامِ خطا
# ارقامِ فارسی/عربی → ASCII (برایِ دوره‌هایِ غیرِASCII هم بی‌خطر است).
_DIGITS = str.maketrans(
    "".join(chr(0x06F0 + i) for i in range(10)) +
    "".join(chr(0x0660 + i) for i in range(10)),
    "0123456789" * 2)


def _short(exc, limit=180):
    text = " ".join(str(exc).split())
    return text[:limit] + ("..." if len(text) > limit else "")


def _q(name):
    """شناسهٔ SQLite را نقل‌قول می‌کند (نام‌ها ثابت‌اند، و این لایهٔ دفاعی است)."""
    return '"%s"' % str(name).replace('"', '""')


def _connect_ro(path):
    """اتصالِ فقط‌خواندنی؛ اگر فایل نباشد ساخته نمی‌شود."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("database file not found: %s" % path)
    return sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)


def _columns(conn, table):
    """مجموعهٔ ستون‌ها یا None اگر جدول نباشد/خوانده نشود."""
    if conn is None:
        return None
    try:
        rows = conn.execute("PRAGMA table_info(%s)" % _q(table)).fetchall()
    except sqlite3.Error:
        return None
    return {row[1] for row in rows} if rows else None


def _probe_readable(conn):
    """None اگر DB خوانا باشد، وگرنه پیامِ خطایِ کوتاه."""
    try:
        conn.execute("PRAGMA schema_version").fetchone()
    except sqlite3.Error as exc:
        return _short(exc)
    return None


def _baseline(main, table, spec, main_columns):
    """{tracing_no: tuple(مقادیرِ compare)} از main، یا None اگر قابلِ اتکا نباشد."""
    key = spec["key"]
    fields = spec["compare"]
    if main is None or not main_columns or key not in main_columns:
        return None
    if any(field not in main_columns for field in fields):
        return None
    sql = "SELECT %s FROM %s" % (
        ", ".join([_q(key)] + [_q(field) for field in fields]), _q(table))
    try:
        rows = main.execute(sql).fetchall()
    except sqlite3.Error:
        return None
    return {row[0]: tuple(row[1:]) for row in rows}


def _new_or_changed(baseline, key, values):
    """ردیف جدید است یا یکی از ستون‌هایِ مقایسه‌شده فرق دارد (NULL-safe)."""
    if baseline is None or key is None:
        return True
    prev = baseline.get(key)
    if prev is None:
        return True
    return any((a is None) != (b is None) or (a is not None and a != b)
               for a, b in zip(values, prev))


def _changed_rows(staging, table, spec, staging_columns, baseline):
    """مجموعهٔ tracing_noهایِ جدید/تغییریافته؛ None یعنی همهٔ ردیف‌ها بررسی شوند."""
    if staging is None or not staging_columns or baseline is None:
        return None
    key = spec["key"]
    fields = spec["compare"]
    if key not in staging_columns:
        return None
    if any(field not in staging_columns for field in fields):
        return None
    sql = "SELECT %s FROM %s" % (
        ", ".join([_q(key)] + [_q(field) for field in fields]), _q(table))
    try:
        rows = staging.execute(sql).fetchall()
    except sqlite3.Error:
        return None
    changed = set()
    for row in rows:
        if _new_or_changed(baseline, row[0], tuple(row[1:])):
            changed.add(row[0])
    return changed


def _scoped(keys, changed):
    """فقط ردیف‌هایِ جدید/تغییریافته؛ changed=None یعنی دامنه سراسری است."""
    if changed is None:
        return keys
    return [key for key in keys if key in changed]


def _count(conn, table):
    if conn is None:
        return 0
    try:
        return int(conn.execute("SELECT COUNT(*) FROM %s" % _q(table)).fetchone()[0])
    except sqlite3.Error:
        return None


def _sample(values, limit=_SAMPLE):
    text = ",".join(str(v) for v in values[:limit])
    return text + (",..." if len(values) > limit else "")


def _period_tuple(value):
    """`YYYY/MM/DD` → (سال، ماه، روز)؛ هر چیزِ دیگر None."""
    if value is None:
        return None
    text = str(value).strip().translate(_DIGITS)
    parts = text.split("/")
    if len(parts) != 3:
        return None
    year, month, day = parts
    if len(year) != 4 or len(month) != 2 or len(day) != 2:
        return None
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None
    return int(year), int(month), int(day)


def _leading_year(value):
    """چهار رقمِ نخستِ مقدار (پس از نرمال‌سازیِ ارقام) اگر سالِ کامل باشد."""
    if value is None:
        return None
    text = str(value).strip().translate(_DIGITS)
    if len(text) < 4 or not text[:4].isdigit():
        return None
    if len(text) > 4 and text[4].isdigit():
        return None
    return int(text[:4])


_GDM = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def _g2j(gy, gm, gd):
    """میلادی → جلالی (همان الگوریتمِ jalaali-js که فرانت و ra_parity دارند)."""
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + _GDM[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    return int(jy)


def _period_max_year(now=None):
    """بیشترین سالِ مجازِ دوره = سالِ جلالیِ امروز (نه ۱۴۰۵ِ hard-code).

    گاردِ ۱۴۰۵ در ۱۴۰۶/۰۱/۰۱ (۲۰۲۷-۰۳-۲۱) هر دورهٔ سالمِ تازه را «آینده»
    می‌کرد و اجرایِ روزانهٔ بدونِ‌ناظر را متوقف می‌کرد. `now` برایِ تست تزریق‌شدنی است.
    """
    d = now or _date.today()
    return _g2j(d.year, d.month, d.day)


def _period_scan(conn, table, column, key_expr, max_year=None):
    """(آخرین دوره، ردیف‌هایِ آینده، ردیف‌هایِ بدشکل، خطایِ کوئری)."""
    latest = None
    latest_key = None
    future = []
    unparsed = []
    limit_year = max_year if max_year is not None else _period_max_year()
    try:
        rows = conn.execute(
            "SELECT %s, %s FROM %s WHERE %s IS NOT NULL"
            % (key_expr, _q(column), _q(table), _q(column))).fetchall()
    except sqlite3.Error as exc:
        return None, [], [], _short(exc)
    for key, value in rows:
        if value is None or not str(value).strip():
            continue
        parsed = _period_tuple(value)
        if parsed is None:
            # دورهٔ غیرِکانونیک اما با سالِ آینده (مثلاً 1406/1/1) هم آینده است.
            year = _leading_year(value)
            if year is not None and year > limit_year:
                future.append((key, value))
            else:
                unparsed.append(key)
            continue
        if parsed[0] > limit_year:
            future.append((key, value))
        if latest_key is None or parsed > latest_key:
            latest_key = parsed
            latest = str(value)
    return latest, future, unparsed, None


def _check_duplicates(conn, table, spec, columns, errors):
    key = spec["key"]
    if key not in columns:
        return
    try:
        rows = conn.execute(
            "SELECT %s, COUNT(*) FROM %s GROUP BY %s HAVING COUNT(*) > 1"
            % (_q(key), _q(table), _q(key))).fetchall()
    except sqlite3.Error as exc:
        errors.append("%s_query_failed:duplicate:%s" % (table, _short(exc)))
        return
    if rows:
        errors.append("%s_duplicate_tracing_no:rows=%d sample=%s"
                      % (table, len(rows), _sample([r[0] for r in rows])))


def _check_non_negative(conn, table, spec, columns, column, changed, errors):
    if column not in columns:
        return
    key = spec["key"]
    key_expr = _q(key) if key in columns else "rowid"
    try:
        rows = conn.execute(
            "SELECT %s FROM %s WHERE %s < 0"
            % (key_expr, _q(table), _q(column))).fetchall()
    except sqlite3.Error as exc:
        errors.append("%s_query_failed:negative:%s:%s"
                      % (table, column, _short(exc)))
        return
    scoped = _scoped([row[0] for row in rows], changed)
    if scoped:
        errors.append("%s:negative_revenue:%s:rows=%d sample=%s"
                      % (table, column, len(scoped), _sample(scoped)))


def _check_gross(conn, table, spec, columns, changed, errors):
    pair = spec.get("gross")
    if not pair or any(c not in columns for c in pair):
        return
    gross, revenue = pair
    key = spec["key"]
    key_expr = _q(key) if key in columns else "rowid"
    try:
        rows = conn.execute(
            "SELECT %s FROM %s WHERE %s IS NOT NULL AND %s IS NOT NULL "
            "AND %s > %s"
            % (key_expr, _q(table), _q(gross), _q(revenue),
               _q(gross), _q(revenue))).fetchall()
    except sqlite3.Error as exc:
        errors.append("%s_query_failed:gross:%s" % (table, _short(exc)))
        return
    scoped = _scoped([row[0] for row in rows], changed)
    if scoped:
        errors.append("%s:gross_gt_revenue:rows=%d sample=%s"
                      % (table, len(scoped), _sample(scoped)))


def _check_provenance(conn, table, spec, columns, changed, errors):
    fields = spec["provenance"]
    if any(c not in columns for c in fields):
        return
    joiner = " AND " if spec["provenance_mode"] == "any" else " OR "
    condition = joiner.join(
        "(%s IS NULL OR TRIM(CAST(%s AS TEXT)) = '')" % (_q(c), _q(c))
        for c in fields)
    key = spec["key"]
    key_expr = _q(key) if key in columns else "rowid"
    try:
        rows = conn.execute(
            "SELECT %s FROM %s WHERE %s"
            % (key_expr, _q(table), condition)).fetchall()
    except sqlite3.Error as exc:
        errors.append("%s_query_failed:provenance:%s" % (table, _short(exc)))
        return
    scoped = _scoped([row[0] for row in rows], changed)
    if scoped:
        errors.append("%s:missing_provenance:fields=%s:rows=%d sample=%s"
                      % (table, "+".join(fields), len(scoped),
                         _sample(scoped)))


def _check_periods(conn, table, spec, columns, changed, errors, warnings):
    """آخرین دورهٔ staging را برمی‌گرداند؛ آینده سراسری، بدشکل رویِ ردیف‌هایِ تازه."""
    column = spec.get("period")
    key = spec["key"]
    key_expr = _q(key) if key in columns else "rowid"
    latest, future, unparsed, query_error = _period_scan(
        conn, table, column, key_expr)
    if query_error:
        errors.append("%s_query_failed:period:%s" % (table, query_error))
        return None
    if future:
        errors.append("future_period:%s:rows=%d sample=%s"
                      % (table, len(future), _sample([v for _, v in future])))
    scoped_unparsed = _scoped(unparsed, changed)
    if scoped_unparsed:
        warnings.append("unparseable_period:%s:rows=%d sample=%s"
                        % (table, len(scoped_unparsed), _sample(scoped_unparsed)))
    return latest


def _check_period_regression(main, staging, table, code, main_columns,
                             staging_columns, stats, errors, warnings):
    """MAX(period_end)ِ staging نباید از main عقب‌تر باشد؛ خرابیِ main خطاست."""
    if main is None or main_columns is None:
        return
    if "period_end" not in main_columns:
        errors.append("%s_main_missing_column:period_end" % table)
        return
    if (staging is None or staging_columns is None
            or "period_end" not in staging_columns):
        return
    main_latest, _future, unparsed, query_error = _period_scan(
        main, table, "period_end", "rowid")
    if query_error:
        errors.append("main_query_failed:period:%s:%s" % (table, query_error))
        return
    if unparsed:
        warnings.append("unparseable_period:main:%s:rows=%d"
                        % (table, len(unparsed)))
    if main_latest is None:
        rows = (stats.get(table) or {}).get("main") or 0
        if rows:
            errors.append("%s_main_period_unparseable:rows=%d" % (code, rows))
        return
    staging_latest = stats.get(code + "_latest")
    if staging_latest is None:
        errors.append("%s_period_regressed:main=%s staging=None"
                      % (code, main_latest))
        return
    left = _period_tuple(staging_latest)
    right = _period_tuple(main_latest)
    if left is not None and right is not None and left < right:
        errors.append("%s_period_regressed:main=%s staging=%s"
                      % (code, main_latest, staging_latest))


def _last_good_periods(last_good, stats, warnings):
    for code, keys in (("fs", ("latest_financial_period", "fs_latest")),
                      ("ms", ("latest_monthly_period", "ms_latest"))):
        expected = None
        for key in keys:
            value = last_good.get(key)
            if isinstance(value, str) and value.strip():
                expected = value.strip()
                break
        if expected is None:
            continue
        actual = stats.get(code + "_latest")
        if actual is None:
            warnings.append("last_good_%s_period_missing:last_good=%s staging=None"
                            % (code, expected))
            continue
        left = _period_tuple(actual)
        right = _period_tuple(expected)
        if left is None or right is None:
            warnings.append("last_good_%s_period_unparseable:last_good=%s staging=%s"
                            % (code, expected, actual))
        elif left < right:
            warnings.append("last_good_%s_period_ahead:last_good=%s staging=%s"
                            % (code, expected, actual))


def _last_good_counts(last_good, stats, warnings):
    raw = last_good.get("row_counts")
    counts = {}
    if isinstance(raw, dict):
        for table in TABLES:
            value = raw.get(table)
            if isinstance(value, int) and not isinstance(value, bool):
                counts[table] = value
    if not counts:
        for table in TABLES:
            value = last_good.get(table)
            if isinstance(value, int) and not isinstance(value, bool):
                counts[table] = value
            elif isinstance(value, dict):
                for key in ("staging", "main"):
                    nested = value.get(key)
                    if isinstance(nested, int) and not isinstance(nested, bool):
                        counts[table] = nested
                        break
    for table, expected in counts.items():
        actual = stats.get(table, {}).get("staging")
        if actual is None:
            continue
        if expected > 0 and actual * 100 < expected * _COVERAGE_PCT:
            warnings.append("last_good_count_drop:%s:last_good=%d staging=%d"
                            % (table, expected, actual))


def _check_last_good(last_good, stats, warnings):
    """last_good فقط هشدار می‌دهد؛ شکلِ ناشناخته هم نباید کرش کند."""
    if last_good is None:
        return
    warnings.append("last_good_checked")
    if not isinstance(last_good, dict):
        warnings.append("last_good_unusable:not_a_mapping")
        return
    try:
        _last_good_periods(last_good, stats, warnings)
        _last_good_counts(last_good, stats, warnings)
    except Exception as exc:                      # noqa: BLE001 - دفاعی
        warnings.append("last_good_unusable:%s" % _short(exc))


def spec_missing(table, columns):
    """ستون‌هایی که برایِ checksِ همین جدول لازم‌اند و در staging نیستند."""
    spec = TABLE_SPECS[table]
    needed = [spec["key"]]
    needed.extend(spec["provenance"])
    needed.extend(spec["non_negative"])
    if spec.get("gross"):
        needed.extend(spec["gross"])
    if spec.get("period"):
        needed.append(spec["period"])
    missing = []
    for column in needed:                         # حذفِ تکراری‌ها با حفظِ ترتیب
        if column not in columns and column not in missing:
            missing.append(column)
    return missing


def validate_staging(main_db, staging_db, last_good=None):
    """گیت‌هایِ staging را اجرا می‌کند؛ هرگز صحتِ داده را «فرض» نمی‌کند."""
    errors, warnings = [], []
    stats = {"fs_latest": None, "ms_latest": None}
    main = staging = None
    main_cols, staging_cols = {}, {}
    try:
        try:
            main = _connect_ro(main_db)
        except FileNotFoundError as exc:
            errors.append("main_db_missing:%s" % _short(exc))
        except Exception as exc:                  # noqa: BLE001 - DB ممکن است نباشد
            errors.append("main_db_unreadable:%s" % _short(exc))
        if main is not None:
            problem = _probe_readable(main)
            if problem:
                errors.append("main_db_unreadable:%s" % problem)
                main.close()
                main = None
        try:
            staging = _connect_ro(staging_db)
        except FileNotFoundError as exc:
            errors.append("staging_db_unavailable:%s" % _short(exc))
        except Exception as exc:                  # noqa: BLE001 - DB ممکن است نباشد
            errors.append("staging_db_unreadable:%s" % _short(exc))
        if staging is not None:
            problem = _probe_readable(staging)
            if problem:
                errors.append("staging_db_unreadable:%s" % problem)
                staging.close()
                staging = None

        for table in TABLES:
            spec = TABLE_SPECS[table]
            mcols = _columns(main, table) if main is not None else None
            scols = _columns(staging, table) if staging is not None else None
            main_cols[table] = mcols
            staging_cols[table] = scols

            n_main = 0
            if mcols is not None:
                n_main = _count(main, table)
                if n_main is None:
                    errors.append("%s_main_count_failed" % table)
                    n_main = 0
            n_staging = 0
            if scols is not None:
                n_staging = _count(staging, table)
                if n_staging is None:
                    errors.append("%s_count_failed" % table)
                    n_staging = 0
            stats[table] = {"main": n_main, "staging": n_staging}

            if staging is not None and scols is None:
                errors.append("%s_missing_table" % table)
            if main is not None and mcols is None:
                errors.append("main_table_missing:%s" % table)
            if staging is None or scols is None:
                continue

            if mcols is not None and n_main > 0:
                if n_staging * 100 < n_main * _COVERAGE_PCT:
                    errors.append("%s_coverage_drop:main=%d staging=%d (<%d%%)"
                                  % (table, n_main, n_staging, _COVERAGE_PCT))

            missing = spec_missing(table, scols)
            for column in missing:
                errors.append("%s_missing_column:%s" % (table, column))

            # دامنهٔ ردیفی: فقط ردیف‌هایِ جدید/تغییریافته؛ بقیهٔ گیت‌ها سراسری‌اند.
            baseline = _baseline(main, table, spec, mcols)
            changed = _changed_rows(staging, table, spec, scols, baseline)

            if spec["key"] in scols:
                _check_duplicates(staging, table, spec, scols, errors)

            for column in spec["non_negative"]:
                if column in scols:
                    _check_non_negative(staging, table, spec, scols, column,
                                        changed, errors)

            if spec.get("gross") and all(c in scols for c in spec["gross"]):
                _check_gross(staging, table, spec, scols, changed, errors)

            if all(c in scols for c in spec["provenance"]):
                _check_provenance(staging, table, spec, scols, changed, errors)

            if spec.get("period") and spec["period"] in scols:
                latest = _check_periods(staging, table, spec, scols,
                                        changed, errors, warnings)
                if table == "financial_statements":
                    stats["fs_latest"] = latest
                elif table == "monthly_sales":
                    stats["ms_latest"] = latest

        _check_period_regression(main, staging, "financial_statements", "fs",
                                 main_cols.get("financial_statements"),
                                 staging_cols.get("financial_statements"),
                                 stats, errors, warnings)
        _check_period_regression(main, staging, "monthly_sales", "ms",
                                 main_cols.get("monthly_sales"),
                                 staging_cols.get("monthly_sales"),
                                 stats, errors, warnings)
        _check_last_good(last_good, stats, warnings)
    finally:
        for conn in (main, staging):
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "stats": stats}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("usage: python codal_validation.py MAIN_DB STAGING_DB")
        raise SystemExit(2)
    result = validate_staging(sys.argv[1], sys.argv[2])
    for item in result["errors"]:
        print("ERROR " + item)
    for item in result["warnings"]:
        print("WARN  " + item)
    print("ok=%s stats=%r" % (result["ok"], result["stats"]))
    raise SystemExit(0 if result["ok"] else 1)
