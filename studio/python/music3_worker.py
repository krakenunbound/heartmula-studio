"""Private WSL inference worker for the local HeartMuLa checkpoint.

The module name remains ``music3_worker`` temporarily because the copied UI
and sidecar import it by that name. Its protocol is model-neutral JSON.
"""
from __future__ import annotations

import gc
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

_PIPE = None
_PIPE_ROOT: str | None = None


def emit(marker: str, payload: dict | None = None) -> None:
    print(marker + ((" " + json.dumps(payload, ensure_ascii=False)) if payload is not None else ""), flush=True)


def load_pipeline(model_root: str):
    global _PIPE, _PIPE_ROOT
    if _PIPE is not None and _PIPE_ROOT == model_root:
        emit("HEARTMULA_PROGRESS", {"progress": 0.03, "message": "Reusing HeartMuLa pipeline"})
        return _PIPE
    import torch
    from heartlib import HeartMuLaGenPipeline

    emit("HEARTMULA_PROGRESS", {"progress": 0.02, "message": "Preparing HeartMuLa pipeline"})
    _PIPE = HeartMuLaGenPipeline.from_pretrained(
        model_root,
        device={"mula": torch.device("cuda"), "codec": torch.device("cuda")},
        dtype={"mula": torch.bfloat16, "codec": torch.float32},
        version="3B",
        # One RTX 3090 cannot hold both models comfortably. The upstream
        # pipeline unloads the language model before codec decoding.
        lazy_load=True,
    )
    _PIPE_ROOT = model_root
    return _PIPE


def run(request: dict) -> None:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("HeartMuLa requires an NVIDIA CUDA GPU.")
    try:
        import gpu_profile
        emit("HEARTMULA_GPU", gpu_profile.apply_to_worker())
    except Exception as error:
        # Memory limits are useful UI telemetry, not a generation prerequisite.
        emit("HEARTMULA_PROGRESS", {"progress": 0.01, "message": f"Starting CUDA ({error})"})

    seed = int(request["seed"])
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    pipe = load_pipeline(str(request["model_root"]))
    output = Path(request["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    emit("HEARTMULA_PROGRESS", {"progress": 0.05, "message": "Generating music with HeartMuLa"})
    started = time.monotonic()
    with torch.inference_mode():
        pipe(
            {"tags": str(request["tags"]), "lyrics": str(request["lyrics"])},
            max_audio_length_ms=int(request["max_audio_length_ms"]),
            save_path=str(output),
            topk=int(request["topk"]),
            temperature=float(request.get("temperature", 1.0)),
            cfg_scale=float(request["cfg_scale"]),
        )
    emit("HEARTMULA_PROGRESS", {"progress": 1.0, "message": "Song ready", "elapsed_seconds": time.monotonic() - started})


def main() -> int:
    emit("HEARTMULA_READY")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            run(json.loads(line))
            emit("HEARTMULA_DONE")
        except BaseException as error:
            traceback.print_exc()
            emit("HEARTMULA_ERROR", {"error": f"{type(error).__name__}: {error}"})
            return 1
        finally:
            gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
