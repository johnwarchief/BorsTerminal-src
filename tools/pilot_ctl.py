"""داورِ جریانی jev-pilot — فقط شرحِ کوتاه می‌پذیرد، نه کد.

تصمیمِ مالک (۲۰۲۶-۰۹-۲۶): هیچ متنِ کدی به api.typesafe.ai فرستاده نمی‌شود.
این ابزار همان را به‌صورت مکانیکی اعمال می‌کند؛ اگر متن بوی کد بدهد، رد می‌کند.

    python pilot_ctl.py stuck  --history failures.txt
    python pilot_ctl.py guard  --action "delete E:/bors-ui-qa" --state "..."
    python pilot_ctl.py arbitrate --context "..." --option "a=شرح" --option "b=شرح"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

MAX_CHARS = 1200

# نشانه‌های کد. فارسی/انگلیسیِ توضیحی نباید هیچ‌کدام را داشته باشد.
CODE_MARKERS = [
    re.compile(r"[{};]"),
    re.compile(r"^\s*(import|from|def|class|const|let|var|function|return|export)\b", re.M),
    re.compile(r"</?[a-zA-Z-]+>"),
    re.compile(r"=>|&&|\|\||\bself\.|\bthis\."),
]


def _refuse_if_code(text: str, field: str) -> str:
    text = text.strip()
    if len(text) > MAX_CHARS:
        raise SystemExit(f"refused: {field} is {len(text)} chars (max {MAX_CHARS}) — summarise it")
    for pattern in CODE_MARKERS:
        if pattern.search(text):
            raise SystemExit(
                f"refused: {field} looks like source code ({pattern.pattern!r}). "
                "Owner policy: describe the option in prose; never send code."
            )
    return text


def _pilot():
    from jev_pilot import JevPilot

    return JevPilot()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stuck", "guard", "arbitrate"])
    ap.add_argument("--history", help="path to a newline file of step summaries")
    ap.add_argument("--action")
    ap.add_argument("--state", default="")
    ap.add_argument("--context", default="")
    ap.add_argument("--option", action="append", default=[], metavar="KEY=PROSE")
    args = ap.parse_args()

    if not (os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")):
        raise SystemExit("TYPESAFE_API_KEY is not set (key file is intentionally not used)")

    pilot = _pilot()

    if args.mode == "stuck":
        steps = Path(args.history).read_text(encoding="utf-8").splitlines() if args.history else []
        steps = [_refuse_if_code(s, f"step {i}") for i, s in enumerate(steps)]
        r = pilot.check_stuck(steps)
        out = {"is_stuck": r.is_stuck, "confidence": r.confidence, "risk": r.risk_score}
    elif args.mode == "guard":
        r = pilot.guard(_refuse_if_code(args.action or "", "action"),
                        _refuse_if_code(args.state, "state"))
        out = {"allowed": r.allowed, "danger": r.danger_score, "kind": r.action_type,
               "error": r.error}
    else:
        candidates = {}
        for item in args.option:
            key, _, prose = item.partition("=")
            candidates[key.strip()] = _refuse_if_code(prose, f"option {key.strip()}")
        if not candidates:
            raise SystemExit("--option at least twice is required")
        r = pilot.arbitrate(_refuse_if_code(args.context, "context"), candidates)
        out = {"winner": r.winner, "confidence": r.confidence,
               "probabilities": {k: round(v, 3) for k, v in r.probabilities.items()},
               "risk": r.risk_score}

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
