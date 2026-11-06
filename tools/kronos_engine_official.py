#!/usr/bin/env python3
"""Kronos local CPU inference (official implementation, no simulation).

This replaces the earlier hand-rolled NumPy sampler, which skipped the
tokenizer encoder/decoder, the dependency-aware layer and true autoregression
and therefore could not honestly be labelled "Kronos".

It runs the official model code from https://github.com/shiyu-coder/Kronos
(MIT, commit 67b630e67f6a18c9e9be918d9b4337c960db1e9a), vendored under
tools/kronos_vendor/model, against the local safetensors weights in
models/kronos. No network access is required at inference time.

CLI is compatible with the Go prediction engine:
    python tools/kronos_inference.py --stdin
    python tools/kronos_inference.py --model mini --horizon 12 --closes 1,2,3
Output JSON keeps the forecast_steps/p10/p50/p90 schema; extra fields are
diagnostics and are ignored by the Go decoder.

If the current interpreter has no torch (system Python 3.14 on this machine),
the script re-executes itself with the local .venv-kronos interpreter.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MODELS_DIR = os.path.join(REPO_ROOT, "models", "kronos")
VENDOR_DIR = os.path.join(REPO_ROOT, "tools", "kronos_vendor")
VENV_PYTHONS = [
    os.path.join(REPO_ROOT, ".venv-kronos", "Scripts", "python.exe"),
    os.path.join(REPO_ROOT, "venv_kronos", "Scripts", "python.exe"),
]

MODEL_MAP: Dict[str, Dict[str, Any]] = {
    "mini": {"model": "Kronos-mini", "tokenizer": "Kronos-Tokenizer-2k", "max_context": 2048},
    "small": {"model": "Kronos-small", "tokenizer": "Kronos-Tokenizer-base", "max_context": 512},
    "base": {"model": "Kronos-base", "tokenizer": "Kronos-Tokenizer-base", "max_context": 512},
}
MODEL_ALIASES = {
    "Kronos-mini": "mini",
    "Kronos-small": "small",
    "Kronos-base": "base",
}

ENGINE_NAME = "kronos-official-torch"
UPSTREAM_COMMIT = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"


def _ensure_torch_runtime() -> None:
    """Re-exec into the local venv when the system interpreter lacks torch."""
    try:
        import torch  # noqa: F401
        return
    except Exception:
        pass

    if os.environ.get("KRONOS_NO_REEXEC") == "1":
        raise SystemExit(
            "torch is not importable in this interpreter and KRONOS_NO_REEXEC=1"
        )

    current = os.path.normcase(os.path.abspath(sys.executable))
    for candidate in VENV_PYTHONS:
        if not os.path.isfile(candidate):
            continue
        if os.path.normcase(os.path.abspath(candidate)) == current:
            continue
        os.execv(candidate, [candidate, os.path.abspath(__file__), *sys.argv[1:]])

    raise SystemExit(
        "torch is not importable and no local venv was found. "
        "Create one with: uv venv --python 3.12 .venv-kronos && "
        "uv pip install --python .venv-kronos/Scripts/python.exe "
        "--index-url https://download.pytorch.org/whl/cpu --no-deps torch==2.9.1 && "
        "uv pip install --python .venv-kronos/Scripts/python.exe "
        "--index-url https://download.pytorch.org/whl/cpu numpy typing-extensions "
        "filelock fsspec sympy networkx jinja2 tqdm setuptools. "
        "einops is vendored in tools/kronos_vendor."
    )


_ensure_torch_runtime()

import numpy as np  # noqa: E402
import torch  # noqa: E402

if VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)

from model.kronos import (  # noqa: E402
    Kronos,
    KronosTokenizer,
    sample_from_logits,
)


_TORCH_DTYPES = {
    "F64": torch.float64,
    "F32": torch.float32,
    "F16": torch.float16,
    "BF16": torch.bfloat16,
    "I64": torch.int64,
    "I32": torch.int32,
    "I16": torch.int16,
    "I8": torch.int8,
    "U8": torch.uint8,
    "BOOL": torch.bool,
}


def _load_safetensors_torch(path: str) -> Dict[str, torch.Tensor]:
    """Minimal safetensors reader (no safetensors package needed).

    Reads the documented header + little-endian tensor payload directly. Only
    the formats present in the Kronos checkpoints are supported.
    """
    with open(path, "rb") as handle:
        header_len = struct.unpack("<Q", handle.read(8))[0]
        header = json.loads(handle.read(header_len).decode("utf-8"))
        payload = handle.read()

    tensors: Dict[str, torch.Tensor] = {}
    for name, info in header.items():
        if name == "__metadata__":
            continue
        dtype = _TORCH_DTYPES.get(info["dtype"])
        if dtype is None:
            raise ValueError(f"unsupported safetensors dtype {info['dtype']} for {name}")
        start, end = info["data_offsets"]
        raw = payload[start:end]
        tensor = torch.frombuffer(bytearray(raw), dtype=dtype).reshape(tuple(info["shape"]))
        tensors[name] = tensor.clone()
    return tensors


_MODEL_CACHE: Dict[str, Tuple[Kronos, KronosTokenizer, Dict[str, Any]]] = {}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_model_key(model_key: str) -> Tuple[str, Optional[str]]:
    key = MODEL_ALIASES.get(model_key, model_key).lower()
    if key not in MODEL_MAP:
        key = "mini"
    requested = key
    spec = MODEL_MAP[key]
    model_dir = os.path.join(MODELS_DIR, spec["model"])
    tokenizer_dir = os.path.join(MODELS_DIR, spec["tokenizer"])
    if os.path.isfile(os.path.join(model_dir, "model.safetensors")) and os.path.isfile(
        os.path.join(tokenizer_dir, "model.safetensors")
    ):
        return key, None
    # Keep the Go path working when only the mini weights are present.
    fallback = "mini"
    spec = MODEL_MAP[fallback]
    if os.path.isfile(os.path.join(MODELS_DIR, spec["model"], "model.safetensors")) and os.path.isfile(
        os.path.join(MODELS_DIR, spec["tokenizer"], "model.safetensors")
    ):
        return fallback, requested
    raise FileNotFoundError(
        "Kronos weights are missing under models/kronos. Expected "
        f"{os.path.join(MODELS_DIR, 'Kronos-mini', 'model.safetensors')} and "
        f"{os.path.join(MODELS_DIR, 'Kronos-Tokenizer-2k', 'model.safetensors')}. "
        "Run tools/download_kronos_models.py first."
    )


def load_kronos(model_key: str = "mini") -> Tuple[Kronos, KronosTokenizer, Dict[str, Any]]:
    """Loads the official model + tokenizer from the local safetensors files."""
    key, fallback_from = _resolve_model_key(model_key)
    if key in _MODEL_CACHE:
        model, tokenizer, meta = _MODEL_CACHE[key]
        meta = dict(meta)
        meta["fallback_from"] = fallback_from
        return model, tokenizer, meta

    spec = MODEL_MAP[key]
    model_dir = os.path.join(MODELS_DIR, spec["model"])
    tokenizer_dir = os.path.join(MODELS_DIR, spec["tokenizer"])
    model_cfg = _load_json(os.path.join(model_dir, "config.json"))
    tokenizer_cfg = _load_json(os.path.join(tokenizer_dir, "config.json"))

    started = time.perf_counter()
    tokenizer = KronosTokenizer(**tokenizer_cfg)
    tokenizer.load_state_dict(
        _load_safetensors_torch(os.path.join(tokenizer_dir, "model.safetensors")),
        strict=True,
    )
    tokenizer.eval()

    model = Kronos(**model_cfg)
    model.load_state_dict(
        _load_safetensors_torch(os.path.join(model_dir, "model.safetensors")),
        strict=True,
    )
    model.eval()
    load_ms = (time.perf_counter() - started) * 1000.0

    meta = {
        "model_key": key,
        "model_id": f"NeoQuasar/{spec['model']}",
        "tokenizer_id": f"NeoQuasar/{spec['tokenizer']}",
        "model_dir": model_dir,
        "tokenizer_dir": tokenizer_dir,
        "model_config": model_cfg,
        "tokenizer_config": tokenizer_cfg,
        "max_context": spec["max_context"],
        "load_ms": load_ms,
        "fallback_from": fallback_from,
        "upstream_commit": UPSTREAM_COMMIT,
        "engine": ENGINE_NAME,
    }
    _MODEL_CACHE[key] = (model, tokenizer, meta)
    return model, tokenizer, meta


def _now_ts() -> int:
    return int(time.time())


def _time_features(timestamps: Sequence[int]) -> np.ndarray:
    """minute, hour, weekday, day, month -- same order as Kronos TemporalEmbedding."""
    rows: List[List[float]] = []
    for ts in timestamps:
        moment = _dt.datetime.fromtimestamp(int(ts), tz=_dt.timezone.utc)
        rows.append(
            [
                float(moment.minute),
                float(moment.hour),
                float(moment.weekday()),
                float(moment.day),
                float(moment.month),
            ]
        )
    return np.asarray(rows, dtype=np.float32)


def _ohlcv_from_closes(closes: Sequence[float]) -> np.ndarray:
    """Deterministic OHLCV+amount proxy for closes-only callers.

    The Go prediction engine currently only supplies closes. Kronos expects six
    channels (O, H, L, C, V, amount); inventing per-bar OHLC is not the same as
    passing real candles, so every response records input.kind =
    "closes-derived OHLCV". Callers that have real candles should pass
    `ohlcv` in the JSON payload.
    """
    close = np.asarray(closes, dtype=np.float32)
    if close.size == 0:
        return np.zeros((0, 6), dtype=np.float32)
    open_ = np.concatenate([[close[0]], close[:-1]]).astype(np.float32)
    high = np.maximum(open_, close) * 1.002
    low = np.minimum(open_, close) * 0.998
    volume = (1_000_000.0 + (np.arange(close.size) % 7) * 100_000.0).astype(np.float32)
    amount = volume * (open_ + high + low + close) / 4.0
    return np.stack([open_, high, low, close, volume, amount], axis=-1)


def _generate_paths(
    tokenizer: KronosTokenizer,
    model: Kronos,
    x: np.ndarray,
    x_stamp: np.ndarray,
    y_stamp: np.ndarray,
    max_context: int,
    pred_len: int,
    clip: float,
    temperature: float,
    top_k: int,
    top_p: float,
    sample_count: int,
    seed: int,
) -> np.ndarray:
    """Official autoregressive loop, returning every sample path.

    Adapted from Kronos auto_regressive_inference (MIT, upstream commit
    recorded above). The only change is that the sample paths are returned
    instead of being averaged, so P10/P50/P90 can be computed honestly.
    """
    torch.manual_seed(seed)
    with torch.no_grad():
        x_t = torch.from_numpy(np.asarray(x, dtype=np.float32))
        x_t = torch.clip(x_t, -clip, clip)
        x_stamp_t = torch.from_numpy(np.asarray(x_stamp, dtype=np.float32))
        y_stamp_t = torch.from_numpy(np.asarray(y_stamp, dtype=np.float32))

        x_t = x_t.unsqueeze(1).repeat(1, sample_count, 1, 1).reshape(-1, x_t.size(1), x_t.size(2))
        x_stamp_t = (
            x_stamp_t.unsqueeze(1)
            .repeat(1, sample_count, 1, 1)
            .reshape(-1, x_stamp_t.size(1), x_stamp_t.size(2))
        )
        y_stamp_t = (
            y_stamp_t.unsqueeze(1)
            .repeat(1, sample_count, 1, 1)
            .reshape(-1, y_stamp_t.size(1), y_stamp_t.size(2))
        )

        x_token = tokenizer.encode(x_t, half=True)
        initial_seq_len = x_t.size(1)
        batch_size = x_token[0].size(0)
        total_seq_len = initial_seq_len + pred_len
        full_stamp = torch.cat([x_stamp_t, y_stamp_t], dim=1)

        generated_pre = x_token[0].new_empty(batch_size, pred_len)
        generated_post = x_token[1].new_empty(batch_size, pred_len)

        pre_buffer = x_token[0].new_zeros(batch_size, max_context)
        post_buffer = x_token[1].new_zeros(batch_size, max_context)
        buffer_len = min(initial_seq_len, max_context)
        if buffer_len > 0:
            start_idx = max(0, initial_seq_len - max_context)
            pre_buffer[:, :buffer_len] = x_token[0][:, start_idx : start_idx + buffer_len]
            post_buffer[:, :buffer_len] = x_token[1][:, start_idx : start_idx + buffer_len]

        for step in range(pred_len):
            current_seq_len = initial_seq_len + step
            window_len = min(current_seq_len, max_context)
            if current_seq_len <= max_context:
                input_pre = pre_buffer[:, :window_len]
                input_post = post_buffer[:, :window_len]
            else:
                input_pre = pre_buffer
                input_post = post_buffer

            context_end = current_seq_len
            context_start = max(0, context_end - max_context)
            current_stamp = full_stamp[:, context_start:context_end, :].contiguous()

            s1_logits, context = model.decode_s1(input_pre, input_post, current_stamp)
            sample_pre = sample_from_logits(
                s1_logits[:, -1, :],
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                sample_logits=True,
            )
            s2_logits = model.decode_s2(context, sample_pre)
            sample_post = sample_from_logits(
                s2_logits[:, -1, :],
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                sample_logits=True,
            )

            generated_pre[:, step] = sample_pre.squeeze(-1)
            generated_post[:, step] = sample_post.squeeze(-1)

            if current_seq_len < max_context:
                pre_buffer[:, current_seq_len] = sample_pre.squeeze(-1)
                post_buffer[:, current_seq_len] = sample_post.squeeze(-1)
            else:
                pre_buffer.copy_(torch.roll(pre_buffer, shifts=-1, dims=1))
                post_buffer.copy_(torch.roll(post_buffer, shifts=-1, dims=1))
                pre_buffer[:, -1] = sample_pre.squeeze(-1)
                post_buffer[:, -1] = sample_post.squeeze(-1)

        full_pre = torch.cat([x_token[0], generated_pre], dim=1)
        full_post = torch.cat([x_token[1], generated_post], dim=1)
        context_start = max(0, total_seq_len - max_context)
        z = tokenizer.decode(
            [
                full_pre[:, context_start:total_seq_len].contiguous(),
                full_post[:, context_start:total_seq_len].contiguous(),
            ],
            half=True,
        )
        z = z.reshape(-1, sample_count, z.size(1), z.size(2))
        return z.cpu().numpy()[0]


def forecast_kronos(
    symbol: str,
    closes: Sequence[float],
    timestamps: Sequence[int],
    horizon: int = 12,
    model_key: str = "mini",
    samples: int = 20,
    lookback: int = 128,
    top_p: float = 0.9,
    temperature: float = 1.0,
    top_k: int = 0,
    seed: int = 42,
    ohlcv: Optional[Sequence[Sequence[float]]] = None,
    device: str = "cpu",
) -> Dict[str, Any]:
    if horizon < 1:
        horizon = 1
    if samples < 1:
        samples = 1
    if lookback < 10:
        lookback = 10

    closes_arr = np.asarray(closes, dtype=np.float32)
    if closes_arr.size < 10:
        return {
            "symbol": symbol,
            "generated_at": int(timestamps[-1]) if timestamps else 0,
            "historical_end": int(timestamps[-1]) if timestamps else 0,
            "horizon": horizon,
            "model_used": MODEL_MAP.get(MODEL_ALIASES.get(model_key, model_key), MODEL_MAP["mini"])["model"],
            "is_liquid": True,
            "forecast_steps": [],
            "upside_probability": 0.5,
            "volatility_amplification": 0.0,
            "error": "series_too_short",
        }

    if ohlcv is not None:
        raw = np.asarray(ohlcv, dtype=np.float32)
        if raw.ndim != 2 or raw.shape[1] != 6 or raw.shape[0] != closes_arr.size:
            raise ValueError("ohlcv must be a [bars,6] array aligned with closes")
        input_kind = "ohlcv"
    else:
        raw = _ohlcv_from_closes(closes_arr)
        input_kind = "closes-derived OHLCV"

    if not timestamps:
        last = _now_ts()
        timestamps = [last - (len(closes_arr) - 1 - i) * 86400 for i in range(len(closes_arr))]
    if len(timestamps) != len(closes_arr):
        raise ValueError("timestamps length must match closes length")

    original_len = len(closes_arr)
    start = max(0, original_len - lookback)
    raw_win = raw[start:]
    ts_win = [int(x) for x in timestamps[start:]]
    last_close = float(closes_arr[-1])
    last_ts = int(ts_win[-1])

    dt_seconds = 86400
    if len(ts_win) >= 2:
        candidate = ts_win[-1] - ts_win[-2]
        if candidate > 0:
            dt_seconds = candidate

    mean = np.mean(raw_win, axis=0)
    std = np.std(raw_win, axis=0)
    x = (raw_win - mean) / (std + 1e-5)
    x = np.clip(x, -5.0, 5.0)[None, :, :]

    x_stamp = _time_features(ts_win)[None, :, :]
    future_ts = [last_ts + (h + 1) * dt_seconds for h in range(horizon)]
    y_stamp = _time_features(future_ts)[None, :, :]

    model, tokenizer, meta = load_kronos(model_key)
    torch.set_grad_enabled(False)

    started = time.perf_counter()
    paths_norm = _generate_paths(
        tokenizer,
        model,
        x,
        x_stamp,
        y_stamp,
        max_context=int(meta["max_context"]),
        pred_len=horizon,
        clip=5.0,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        sample_count=samples,
        seed=seed,
    )
    inference_ms = (time.perf_counter() - started) * 1000.0

    # paths_norm: [samples, total_seq, 6]
    paths = paths_norm[:, -horizon:, :] * (std + 1e-5) + mean
    close_paths = paths[:, :, 3]

    forecast_steps = []
    for step in range(horizon):
        step_prices = close_paths[:, step]
        p10 = round(float(np.percentile(step_prices, 10)), 2)
        p50 = round(float(np.percentile(step_prices, 50)), 2)
        p90 = round(float(np.percentile(step_prices, 90)), 2)
        if p50 < p10:
            p50 = p10
        if p90 < p50:
            p90 = p50
        forecast_steps.append(
            {
                "step_index": step + 1,
                "timestamp": int(future_ts[step]),
                "p10": p10,
                "p50": p50,
                "p90": p90,
            }
        )

    upside_prob = round(float(np.mean(close_paths[:, -1] > last_close)), 4)
    recent = closes_arr[max(0, len(closes_arr) - min(60, len(closes_arr))) :]
    hist_vol = float(np.std(np.diff(np.log(np.maximum(recent, 1e-4))))) if recent.size > 2 else 0.0
    path_vols = []
    for path in close_paths:
        rets = np.diff(np.log(np.maximum(path, 1e-4)))
        if rets.size:
            path_vols.append(float(np.std(rets)))
    vol_amp = round(
        float(np.mean([v > hist_vol for v in path_vols])) if path_vols else 0.0,
        4,
    )

    model_spec = MODEL_MAP[meta["model_key"]]
    return {
        "symbol": symbol,
        "generated_at": last_ts,
        "historical_end": last_ts,
        "horizon": horizon,
        "model_used": model_spec["model"],
        "requested_model": model_key,
        "model_fallback_from": meta["fallback_from"],
        "engine": f"{ENGINE_NAME} ({UPSTREAM_COMMIT[:12]})",
        "device": device,
        "is_liquid": True,
        "input": {
            "kind": input_kind,
            "bars_total": original_len,
            "bars_used": int(x.shape[1]),
            "normalization": "per-column mean/std, clip=5",
        },
        "sampling": {
            "paths": samples,
            "top_p": top_p,
            "temperature": temperature,
            "top_k": top_k,
            "seed": seed,
        },
        "forecast_steps": forecast_steps,
        "upside_probability": upside_prob,
        "volatility_amplification": vol_amp,
        "timings_ms": {
            "model_load": round(float(meta["load_ms"]), 3) if meta["load_ms"] else 0.0,
            "inference": round(inference_ms, 3),
        },
        "output_shape": {
            "paths": [int(paths.shape[0]), int(paths.shape[1]), int(paths.shape[2])],
            "quantiles": [horizon, 3],
        },
    }


def _process_memory() -> Dict[str, int]:
    if os.name != "nt":
        return {}
    import ctypes
    from ctypes import wintypes

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    psapi = ctypes.WinDLL("psapi.dll")
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    kernel32 = ctypes.WinDLL("kernel32.dll")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    ok = psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    if not ok:
        return {}
    return {
        "rss_current_bytes": int(counters.WorkingSetSize),
        "rss_peak_bytes": int(counters.PeakWorkingSetSize),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Kronos official CPU inference")
    parser.add_argument("--symbol", type=str, default="FOOLAD")
    parser.add_argument("--model", type=str, default="mini", choices=["mini", "small", "base"])
    parser.add_argument("--horizon", type=int, default=12)
    parser.add_argument("--samples", type=int, default=20, help="Monte Carlo paths for P10/P50/P90")
    parser.add_argument("--lookback", type=int, default=128, help="Historical bars fed to the model")
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=0, help="0 keeps torch default")
    parser.add_argument("--stats", action="store_true", help="Add process RSS to the JSON output")
    parser.add_argument("--closes", type=str, default="")
    parser.add_argument("--timestamps", type=str, default="")
    parser.add_argument("--json-input", type=str, default="")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    closes: List[float] = []
    timestamps: List[int] = []
    ohlcv = None
    symbol = args.symbol
    horizon = args.horizon
    model_key = args.model
    samples = args.samples
    lookback = args.lookback

    payload: Optional[Dict[str, Any]] = None
    if args.stdin or args.json_input == "-":
        payload = json.loads(sys.stdin.read())
    elif args.json_input:
        if os.path.exists(args.json_input):
            payload = _load_json(args.json_input)
        else:
            payload = json.loads(args.json_input)

    if payload is not None:
        symbol = payload.get("symbol", symbol)
        horizon = int(payload.get("horizon", horizon))
        model_key = payload.get("model", model_key)
        samples = int(payload.get("samples", samples))
        lookback = int(payload.get("lookback", lookback))
        closes = [float(x) for x in payload.get("closes", [])]
        timestamps = [int(x) for x in payload.get("timestamps", [])]
        if payload.get("ohlcv"):
            ohlcv = payload["ohlcv"]
    elif args.closes:
        closes = [float(x.strip()) for x in args.closes.split(",") if x.strip()]
        if args.timestamps:
            timestamps = [int(x.strip()) for x in args.timestamps.split(",") if x.strip()]
    else:
        now = 1730500000
        closes = [100.0 * (1.0 + 0.005 * i + 0.02 * __import__("math").sin(i / 3.0)) for i in range(40)]
        timestamps = [now - (40 - 1 - i) * 86400 for i in range(40)]
        lookback = min(lookback, 40)

    if args.threads > 0:
        torch.set_num_threads(args.threads)

    started = time.perf_counter()
    result = forecast_kronos(
        symbol=symbol,
        closes=closes,
        timestamps=timestamps,
        horizon=horizon,
        model_key=model_key,
        samples=samples,
        lookback=lookback,
        top_p=args.top_p,
        temperature=args.temperature,
        seed=args.seed,
        ohlcv=ohlcv,
    )
    wall_ms = (time.perf_counter() - started) * 1000.0
    result["timings_ms"]["total"] = round(wall_ms, 3)
    if args.stats:
        result["process"] = _process_memory()

    out_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(out_json)
        print(f"Written forecast to {args.out}", file=sys.stderr)
    else:
        print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
