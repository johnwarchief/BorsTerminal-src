"""dev/ci_parity_harness.py — CI-parity harness: the guard must pass where `cryptography` is absent.

runnerهای GitHub Actions `cryptography` ندارند (درِ requirements.txt نیست) ⇒ هر
شاخۀ openssl-تنها آنجا می‌دود. این harness هم درِ همین فرایند و هم درِ همهٔ
زیرروندها (CLI که گارد با subprocess صدا می‌زند) ماژول را مسدود می‌کند؛ بی‌بخشِ
زیررونده، آزمون‌های CLI همان‌جا از شاخۀ cryptography رد می‌شدند و باگِ
`genpkey -cipher` دیده نمی‌شد.
"""
import io
import os
import runpy
import sys

import tempfile

# سایتِ ساختگی درِ temp می‌نشیند نه درِ repo: جنریتِ فایلِ importable داخلِ
# مخزن، خودِ یکِ آلودگیِ repo است (و درِ CI هم هیچ‌وقت لازم نمی‌شود).
SITE = tempfile.mkdtemp(prefix="bors-nocrypto-site-")
os.makedirs(SITE, exist_ok=True)
io.open(os.path.join(SITE, "sitecustomize.py"), "w", encoding="utf-8",
        newline="\n").write(
    "import sys\n"
    "class _NoCrypto:\n"
    "    def find_module(self, name, path=None):\n"
    "        return None\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name == 'cryptography' or name.startswith('cryptography.'):\n"
    "            raise ImportError('cryptography is blocked by the CI-parity harness')\n"
    "        return None\n"
    "sys.meta_path.insert(0, _NoCrypto())\n")

os.environ["PYTHONPATH"] = SITE + os.pathsep + os.environ.get("PYTHONPATH", "")


class _Block:
    def find_spec(self, name, path=None, target=None):
        if name == "cryptography" or name.startswith("cryptography."):
            raise ImportError("blocked to simulate the CI runner")
        return None


sys.meta_path.insert(0, _Block())
try:
    import cryptography                      # noqa: F401
    print("HARNESS BROKEN: cryptography still importable")
    sys.exit(9)
except ImportError:
    pass

sys.argv = list(sys.argv[1:]) or ["dev/mobile_manifest_sign_v1079.py"]
runpy.run_path(sys.argv[0], run_name="__main__")
