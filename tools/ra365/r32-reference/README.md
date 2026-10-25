# tools/ra365/r32-reference — Rahavard reference intelligence

Round 32A. Brings Rahavard365 reference data into a versioned pack, infers the
effective adjustment factor per instrument from raw-vs-adjusted evidence, and
ledgers every unmatched paired date under one stable key.

Owner's work only: nothing here edits `adjustment_engine.py`,
`corporate_ledger.py`, `price_basis.py`, `candle_contract.py`, `api/chart.py`
or any UI file. Nothing here writes to a database or fetches the network on its
own — the capture driver is the one component that talks to Rahavard, and only
inside the owner's own browser session.

## The pack

```
reference-pack/
  manifest.json              what is inside, hashes, counts, pack_id
  coverage.json              per-series rows/first/last/status, shortfall vs the declared universe
  bars.ndjson.gz             one record per (symbol, timeframe, adjust, basis, date)
  factor_segments.ndjson.gz  one record per inferred factor interval
  factor_segments_frozen.ndjson.gz   the R30 step boundaries, kept apart and labelled
  mismatch_map.ndjson.gz     one record per unmatched paired date
  *-summary.json             per-tool summaries
```

Local location: `D:/BorsTerminal-tmp/ra365_round32/reference-pack/`
(never committed; the reference OHLC is the owner's subscription).

## The contract

Schemas are versioned in `r32_schema.py`:

| record | schema | required |
| --- | --- | --- |
| bar | `ra365-reference-bar/1` | symbol_id, timeframe, date, adjust, source_id |
| factor segment | `ra365-factor-segment/1` | symbol_id, timeframe, segment_index, date_from, date_to |
| mismatch | `ra365-mismatch/1` | symbol_id, timeframe, date, price_basis, cause |

Two rules hold everywhere:

- **A field that the source did not supply is named in the row's `unavailable`
  array** and is never estimated. A bar with no volume has `volume: null` and
  `"volume"` in `unavailable`; a segment with no single scalar has
  `factor: null` and `"factor"` in `unavailable`.
- **The stable key is `symbol_id | timeframe | date | price_basis`**
  (`r32_schema.mismatch_key`). Everything lookup-able is keyed by it.

`pack_id` is a hash over the file list (path, sha256, rows). Two builds of the
same input with the same `--generated-at` produce the same `pack_id`; the
wall-clock timestamp is recorded beside it and never folded into it.

## Capture from Rahavard365 (authorized, owner session)

```bash
# 1. open an Edge window with a real CDP port, then log in THERE
node tools/ra365/r32-reference/capture_rahavard.mjs --launch --probe-auth
#    exit 3 = the session is not authenticated; log in and re-run

# 2. capture
node capture_rahavard.mjs --symbols symbols.json --out D:/.../rahavard-export.json \
     --types type0,type7 --res D,W,M --countback 400 --marks
```

`symbols.json` is `[{"asset_id": 453, "symbol": "..."}, ...]`. The driver
issues the same same-origin `fetch` the product's own chart page issues
(`/api/v2/chart/bars`, ticker
`exchange.asset:{id}:real_close:type0|type7`). It never reads, prints or stores
a cookie, token, password or account id.

**If the browser route is unavailable**, export any CSV with the columns
`date, symbol, open, high, low, close, volume, adjust, basis, timeframe` and
import it with `--kind rahavard-csv`. Anything the export does not carry must be
left blank: a blank cell becomes `unavailable`, not a zero.

## Run

```bash
# whole pack, from the evidence that is in git, one command
python tools/ra365/r32-reference/run_pipeline.py \
  --pack D:/BorsTerminal-tmp/ra365_round32/reference-pack \
  --artifacts artifacts/ra365/r32a --generated-at 2026-10-25T00:00:00Z

# or a single step
python import_reference.py --in <export|ledger> --kind auto --out <dir>
python infer_factor_segments.py --in <ledger> --kind candle-diverge --out <dir>
python build_mismatch_ledger.py --mode ledger --in <ledger> --kind parity-diverge --out <dir>
python build_mismatch_ledger.py --mode disposition \
    --families artifacts/ra365/r30/attribution/families.csv --out <dir>
python pack.py --dir <dir> --require bars.ndjson.gz,coverage.json
python verify_pack.py --dir <dir>
```

`import_reference.py --kind auto` sniffs the export shape. The frozen ledgers it
understands: `candle-diverge` (product raw beside reference adjusted),
`parity-diverge` (the four named arms), `steps` (the R30 factor-chain
boundaries).

## Factor inference

`factor(t) = reference_adjusted(t) / product_raw(t)` — the multiplier the
reference applied to the raw series, the same convention as the R31 witness
(`factor = H_type7 / H_type0`).

For each instrument the tool finds the scalar the largest number of
(session, field) pairs agree on, keeps every session where at least
`--min-fields` fields follow it as that factor's evidence, splits the evidence
into date-contiguous intervals, and repeats on what is left. A field that does
not follow the scalar is named in `dissent_fields` rather than averaged away.

Causes, in the order they are tested:

| cause | meaning |
| --- | --- |
| `insufficient_evidence` | fewer than `--min-run` sessions support the scalar |
| `no_single_scalar` | open/high/low disagree: not a factor, so it belongs to the data/model ledger |
| `single_scalar_with_dissent` | the body fields agree; one field (usually close) follows a different definition |
| `exact_single_scalar` | raw × factor reproduces every agreeing field exactly |
| `single_scalar_with_rounding` | every agreeing field is within one price unit |
| `single_scalar` | one scalar fits, with a residual above tolerance |

Every threshold is a tool parameter, printed with the run and swept for
sensitivity in `sensitivity`. **They are not methodology rulings.** A ratio
break is a computational witness only: `event_attribution` stays
`unattributed` unless independent event evidence is supplied.

## Tests

```bash
for t in dev/ra365/r32-reference/test_r32_*.py; do python "$t"; done
```

164 checks across the schema, the gzip determinism, both export parsers, the
frozen-ledger adapters, the estimator, the ledger and the end-to-end importer.

These are not yet in `dev/run_all_tests.py`'s `SUITES` list — that file is
outside this round's ownership. Registering one line there is a follow-up for
its owner.