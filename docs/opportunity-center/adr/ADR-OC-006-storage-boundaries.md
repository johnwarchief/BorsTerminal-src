# ADR-OC-006 — توپولوژی ذخیره‌سازی و مرزهای Single-Writer

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **پرسش مرتبط:** Q13 (نگهداشت)

## Context

Stage 4 یک نویسندهٔ داده و Snapshotهای نسلی دارد. `market.db`/`codal.db` read-only باز می‌شوند و `user.db` نوشتنی است. OC به دادهٔ پژوهش، نصب بسته، فرصت‌ها و Audit نیاز دارد. اگر این داده‌ها در یک DB یا در `data_dir` Producer قرار گیرند، مرزهای امنیتی و Single-Writer می‌شکنند.

## Decision

1. `market.db`/`codal.db`: فقط Producer می‌نویسد؛ `borsd` و Research فقط read-only از نسل فعال/کپی.
2. `user.db`: دادهٔ شخصی (Watchlist، Portfolio، تنظیمات)؛ فقط `borsd` می‌نویسد؛ هرگز Snapshot/Registry نمی‌شود.
3. `oc_client.db`: فقط `borsd` می‌نویسد؛ نصب‌ها، فرصت‌ها، Revocation، مشاهدات، Audit محلی.
4. `research.db` و Artifact Store: فقط Research/Owner CLI؛ در `BORS_RESEARCH_DIR` خارج از Producer `data_dir`.
5. Registry Blobs: Content-Addressed در `dataDir/oc/registry/`؛ فقط Registry Client می‌نویسد.
6. Producer Allowlist: فقط `market.db` و `codal.db`؛ هر `.db` دیگر باید رد شود (P0).
7. Schema Versioning: `PRAGMA user_version` + Migration Runner + Backup قبل از Migration.
8. Hash chain برای جداول حساس Research/Client Audit.

## Consequences

- دو Migration مستقل (Owner/Client) و دو Backup policy.
- `oc_client.db` قابل بازسازی از Registry است، اما Audit/فرصت‌ها ارزش نگهداری دارند.
- `research.db` قابل انتشار نیست؛ پشتیبان‌گیری آن مسئولیت مالک است.
- Producer Allowlist یک تغییر اجباری در Stage 4 است.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| گذاشتن Research در `user.db` | نقض مرز شخصی و خطر انتشار؛ رد |
| گذاشتن همه در `market.db` | نقض read-only/Single-Writer؛ رد |
| یک DB مشترک Client | تداخل Migration/مالکیت؛ رد |
| فایل JSON برای همه | فقدان تراکنش/Query/Audit؛ رد |

## Evidence

- `backend-go/internal/db/db.go:75-133` — read-only/rwc.
- `backend-go/cmd/bors-producer/pipeline.go:240-265` — Snapshot همهٔ `.db` (باید Allowlist شود).
- `docs/BorsTerminal-Desktop-Migration-Decisions.md:596-606` — Schema/Migration OPEN.
- `04-TECHNICAL-ARCHITECTURE.md` §۷.
