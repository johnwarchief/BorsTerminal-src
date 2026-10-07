# Market database release contract

The source repository intentionally does not track `market.db.lzma`.

The current baseline is published as the `data-latest` prerelease in `johnwarchief/BorsTerminal`.

Asset:
https://github.com/johnwarchief/BorsTerminal/releases/download/data-latest/market.db.lzma

The companion `market.db.meta.json` contains the byte size and SHA-256 digest. Fresh desktop installs fetch the baseline only when no local copy exists; normal daily operation uses the local SQLite database.
