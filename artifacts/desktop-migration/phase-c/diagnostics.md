# Phase C diagnostic experiments (n=1 each)

These were single cold runs on the same 1-core/4 GB host and the same Edge
fallback protocol. They are recorded to justify the chosen fix, not as a
statistical baseline (n=1, no median/p95).

| Experiment | Board | Chart | Fundamental |
|---|---:|---:|---:|
| Baseline (screener warm at startup) | 65,901 ms median (n=3) | 88,193 ms | 90,418 ms |
| Skip screener warm entirely | 43,975 ms | 68,510 ms | 70,979 ms |
| Screener at lowest priority only | 53,398 ms | 81,654 ms | 83,911 ms |
| Lowest priority + wait for first board publish (shipped) | 44,654 ms | 69,285 ms | 71,717 ms |
| Shipped code, cold baseline (n=3) | 45,928 ms median | 67,045 ms | 69,143 ms |
| Shipped code, warm baseline (n=3) | 45,975 ms median | 64,728 ms | 67,314 ms |

Interpretation: the scan is real work and must still run; the win comes from
serializing it behind the first usable board and yielding CPU priority. The
shipped variant is within ~1 s of skipping the warm work, so the cache remains
warm without the startup penalty.
