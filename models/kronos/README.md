# Kronos local weights (downloaded 2026-11-06)

Source: Hugging Face Hub, official Kronos repositories by NeoQuasar.

| Repo | Revision (main) | File | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| `NeoQuasar/Kronos-mini` | `f4e68697d9d5aed55cef5c96aabc3376bcad9f81` | `config.json` | 225 | `70daca2cb11e3a979dd6b8ac12ee08e2aace877acf28f5b8dfb4fe5609736201` |
| `NeoQuasar/Kronos-mini` | `f4e68697d9d5aed55cef5c96aabc3376bcad9f81` | `model.safetensors` | 16,440,776 | `a7d5f37e2e9fbd9891f7d7d4f72574512dd1f704fee14223e0a8cd0fbf54197c` |
| `NeoQuasar/Kronos-Tokenizer-2k` | `26966d0035065a0cae0ebad7af8ece35bc1fb51c` | `config.json` | 301 | `0b30a443affb03e05a876a083857de9164f899feb7b4d261da02c485c9a3e3b6` |
| `NeoQuasar/Kronos-Tokenizer-2k` | `26966d0035065a0cae0ebad7af8ece35bc1fb51c` | `model.safetensors` | 15,842,376 | `b97ec46b3b72160509e289183eaf7bdf5f0dac5bb9b49522f6d46638a99a8717` |

Downloaded with:

```sh
curl -L --fail -o models/kronos/Kronos-mini/config.json \
  https://huggingface.co/NeoQuasar/Kronos-mini/resolve/main/config.json
curl -L --fail -o models/kronos/Kronos-mini/model.safetensors \
  https://huggingface.co/NeoQuasar/Kronos-mini/resolve/main/model.safetensors
curl -L --fail -o models/kronos/Kronos-Tokenizer-2k/config.json \
  https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k/resolve/main/config.json
curl -L --fail -o models/kronos/Kronos-Tokenizer-2k/model.safetensors \
  https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k/resolve/main/model.safetensors
```

The two `model.safetensors` SHA-256 values match the Hugging Face LFS
`oid`/sha256 metadata exactly. Parameter count is 4.1M for Kronos-mini; the
on-disk file is larger because weights are stored as float32.

`models/` is git-ignored (`.gitignore` line 64). Do not commit the weights;
re-download with `tools/download_kronos_models.py` or the commands above.

Only Kronos-mini + Tokenizer-2k are downloaded. Kronos-small/base and
Tokenizer-base are not present; the inference engine falls back to mini and
labels `model_fallback_from` when a larger model is requested.
