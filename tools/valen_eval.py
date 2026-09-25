"""داورِ تصویری UI — با Valen (Qwen3.5-2B + decision head) روی یک اسکرین‌شات رأی می‌دهد.

این فایل با پایتونِ محیطِ جدا (`E:\\bors-ui-qa\\venv`) اجرا می‌شود، نه با پایتونِ
محیطِ ریلیز؛ torch/transformers عمداً بیرونِ `requirements.txt` نگه داشته شده‌اند.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

VAL_HOME = Path(os.environ.get("VALEN_HOME", r"E:\bors-ui-qa\Valen"))
DEFAULT_CHECKPOINT = VAL_HOME / "models" / "Valen-Preview-0923"

# کنسول ویندوز cp1252 است؛ بی‌این خط، کلیدهای فارسیِ گزینه‌ها در حالت --serve
# به سوروگیت تبدیل و JSON مخرب می‌شود.
for _stream in (sys.stdin, sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="strict")

_loaded: dict = {}


def _ensure_loaded(checkpoint: str, device: str):
    if "model" in _loaded:
        return _loaded

    from valen.data.schema import read_jsonl
    from valen.modeling.factory import build_compiler, build_model, get_backend, normalize_model_config
    from valen.modeling.factory import backend_for_model  # noqa: F401  (imported for parity with inference CLI)
    from valen.training.checkpoint import load_checkpoint
    from valen.evaluation.inference import predict

    os.chdir(VAL_HOME)
    config = json.loads((Path(checkpoint) / "config.json").read_text(encoding="utf-8"))
    config = normalize_model_config(config)
    config["device"] = device
    model = build_model(config)
    load_checkpoint(checkpoint, model)
    backend = get_backend(config["architecture"])
    _loaded.update(
        config=config,
        model=model,
        backend=backend,
        predict=predict,
        read_jsonl=read_jsonl,
        build_compiler=build_compiler,
    )
    return _loaded


def _record(image: str, questions: dict) -> dict:
    prompt = next(iter(questions.values()))["instructions"]
    return {
        "group_id": "ui-qa",
        "request": {
            "state": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": str(Path(image).resolve())}},
                        ],
                    }
                ]
            },
            "questions": questions,
        },
    }


def judge(checkpoint: str, device: str, image: str, questions: dict) -> dict:
    state = _ensure_loaded(checkpoint, device)
    # یک دایرکتوری ثابت: build_compiler پردازندهٔ HF را می‌سازد، پس media_root نباید
    # در هر فراخوانی عوض شود وگرنه در حالت --serve هر پرسش چند ثانیه هزینه دارد.
    workdir = VAL_HOME / "output" / "ui_qa"
    workdir.mkdir(parents=True, exist_ok=True)
    data = workdir / "req.jsonl"
    with data.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(_record(image, questions), ensure_ascii=False) + "\n")
    records = state["read_jsonl"](data, candidate_fn=state["backend"].candidates)
    if "compiler" not in state:
        state["compiler"] = state["build_compiler"](state["config"], workdir)
    out = state["predict"](state["model"], state["compiler"].compile(records[0]))
    return out["answers"]


def _questions_from_args(args) -> dict:
    criteria = {}
    for item in args.choice or []:
        key, _, text = item.partition("=")
        criteria[key.strip()] = text.strip()
    if not criteria:
        raise SystemExit("--choice حداقل یک گزینه لازم است (قالب: key=description)")
    kind = args.kind if args.kind != "auto" else ("choice" if len(criteria) > 1 else "noul")
    question = {"type": kind, "instructions": args.question}
    if kind != "noul":
        question["criteria"] = criteria if kind == "choice" else list(criteria.values())
    return {"ui": question}


def main() -> int:
    parser = argparse.ArgumentParser(description="Valen UI judge")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--image")
    parser.add_argument("--question", default="")
    parser.add_argument("--choice", action="append", metavar="KEY=TEXT")
    parser.add_argument("--kind", default="auto", choices=["auto", "choice", "score", "noul"])
    parser.add_argument("--serve", action="store_true", help="یک مدل بارگذاری کن و از stdin خطی بخوان")
    args = parser.parse_args()

    if args.serve:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            try:
                questions = req.get("questions") or {
                    "ui": {
                        "type": req.get("kind", "choice"),
                        "instructions": req["question"],
                        "criteria": req["criteria"],
                    }
                }
                answers = judge(args.checkpoint, args.device, req["image"], questions)
                resp = {"id": req.get("id"), "ok": True, "answers": answers}
            except Exception as exc:  # noqa: BLE001
                resp = {"id": req.get("id"), "ok": False, "error": f"{type(exc).__name__}: {exc}"}
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        return 0

    if not args.image:
        parser.error("--image لازم است (یا --serve)")
    answers = judge(args.checkpoint, args.device, args.image, _questions_from_args(args))
    json.dump(answers.get("ui", answers), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
