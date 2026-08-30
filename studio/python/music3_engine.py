"""HeartMuLa worker supervision behind the copied Studio's established API."""
from __future__ import annotations

import audioop
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections import deque
from pathlib import Path

from config import HEARTMULA_WORKER_PYTHON, HEARTMULA_WSL_PYTHON, MODEL_ROOT, WORKER_PYTHON as STUDIO_WORKER_PYTHON
import generation_timing

# Compatibility name retained for shared Studio utilities such as Demucs. Its
# Windows runtime is distinct from HeartMuLa's WSL-only Python environment.
WORKER_PYTHON = STUDIO_WORKER_PYTHON

log = logging.getLogger("heartmula.engine")
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_PROCESS: subprocess.Popen[str] | None = None
_LOCK = threading.RLock()
_START_LOCK = threading.Lock()

MODEL_FILES = {
    "heartmula": MODEL_ROOT / "HeartMuLa-oss-3B",
    "heartcodec": MODEL_ROOT / "HeartCodec-oss",
    "tokenizer": MODEL_ROOT / "tokenizer.json",
    "generation_config": MODEL_ROOT / "gen_config.json",
}

# Keep the public checkpoint identity explicit.  The on-disk folder names are
# intentionally stable so existing installs and saved paths continue to work.
MODEL_VARIANT = "HeartMuLa-oss-3B-happy-new-year"
CODEC_VARIANT = "HeartCodec-oss-20260123"


def _worker_path(path: Path) -> str:
    """Translate a Windows path for the project's WSL environment."""
    if os.name != "nt":
        return str(path)
    drive = path.drive.rstrip(":").lower()
    if drive:
        return f"/mnt/{drive}/{path.as_posix()[3:]}"
    return path.as_posix()


def _worker_command(script: Path) -> list[str]:
    if os.name == "nt":
        return ["wsl.exe", "-e", HEARTMULA_WSL_PYTHON, _worker_path(script)]
    return [str(HEARTMULA_WORKER_PYTHON), str(script)]


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if not path.is_dir():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def model_status() -> dict:
    components = []
    total = 0
    for kind, path in MODEL_FILES.items():
        present = path.is_dir() if kind in {"heartmula", "heartcodec"} else path.is_file()
        size = _tree_size(path) if present else 0
        total += size
        components.append({"kind": kind, "path": str(path), "present": present, "size_bytes": size})
    return {
        "root": str(MODEL_ROOT), "ready": all(item["present"] for item in components),
        "present": sum(bool(item["present"]) for item in components), "required": len(components),
        "missing": [item["kind"] for item in components if not item["present"]],
        "size_bytes": total, "components": components,
        "model_variant": MODEL_VARIANT,
        "codec_variant": CODEC_VARIANT,
        "recommended_pair": True,
        "source": "https://huggingface.co/HeartMuLa/HeartMuLa-oss-3B-happy-new-year",
        "codec_source": "https://huggingface.co/HeartMuLa/HeartCodec-oss-20260123",
    }


def runtime_status() -> dict:
    if os.name == "nt":
        wsl_ready = bool(shutil.which("wsl.exe"))
        if wsl_ready:
            try:
                probe = subprocess.run(
                    ["wsl.exe", "-e", "test", "-x", HEARTMULA_WSL_PYTHON],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5, check=False,
                )
                wsl_ready = probe.returncode == 0
            except (OSError, subprocess.SubprocessError):
                wsl_ready = False
        ready = wsl_ready
    else:
        ready = HEARTMULA_WORKER_PYTHON.is_file()
    return {
        "ready": ready,
        "python": str(HEARTMULA_WORKER_PYTHON), "worker_loaded": _alive(),
        "standalone": True, "runtime": "WSL" if os.name == "nt" else "native",
    }


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return env


_GPU_POLICY: dict | None = None


def set_gpu_policy(policy: dict) -> None:
    global _GPU_POLICY
    _GPU_POLICY = policy
    log.info("HeartMuLa VRAM policy: %s", policy)


def gpu_policy() -> dict:
    if _GPU_POLICY:
        return {**_GPU_POLICY, "measured": True}
    import gpu_profile
    return {**gpu_profile.probe(), "measured": False}


def _alive() -> bool:
    return _PROCESS is not None and _PROCESS.poll() is None


def _stop_process(expected: subprocess.Popen[str] | None = None) -> None:
    global _PROCESS
    with _LOCK:
        proc = expected or _PROCESS
        if proc is _PROCESS:
            _PROCESS = None
    if proc is None or proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW, check=False)
    else:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def _start(cancel_event: threading.Event | None = None) -> subprocess.Popen[str]:
    global _PROCESS
    with _START_LOCK:
        with _LOCK:
            if _alive():
                return _PROCESS  # type: ignore[return-value]
        if not runtime_status()["ready"]:
            raise RuntimeError("HeartMuLa WSL runtime is not installed or unavailable.")
        proc = subprocess.Popen(
            _worker_command(Path(__file__).with_name("music3_worker.py")), cwd=str(Path(__file__).parent),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1, env=_env(), creationflags=_NO_WINDOW,
        )
        with _LOCK:
            _PROCESS = proc
        assert proc.stdout is not None
        startup = deque(maxlen=50)
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    _stop_process(proc); raise RuntimeError("cancelled")
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError(f"HeartMuLa worker exited during startup: {' | '.join(startup)}")
                line = line.strip(); startup.append(line); log.info("[worker] %s", line)
                if line == "HEARTMULA_READY":
                    return proc
        except Exception:
            _stop_process(proc)
            raise


def unload() -> dict:
    had_worker = _alive()
    _stop_process()
    return {"cleared": True, "had_worker": had_worker}


def cancel() -> None:
    # Killing the isolated WSL process is the only reliable interruption point
    # while HeartMuLa is sampling frames on CUDA.
    unload()


def count_prompt_tokens(tags: str, lyrics: str) -> dict:
    tokenizer = MODEL_FILES["tokenizer"]
    if not tokenizer.is_file():
        raise RuntimeError("HeartMuLa tokenizer is not installed")
    payload = json.dumps({"tags": tags, "lyrics": lyrics, "tokenizer": _worker_path(tokenizer)}, ensure_ascii=False)
    result = subprocess.run(_worker_command(Path(__file__).with_name("music3_token_count.py")), input=payload,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                            env=_env(), creationflags=_NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Could not count HeartMuLa prompt tokens")
    try:
        counted = json.loads(result.stdout.strip().splitlines()[-1])
        return {"tokens": int(counted["tokens"]), "maximum": int(counted["maximum"])}
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("HeartMuLa tokenizer returned an invalid result") from error


def inspect_wav(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size <= 44:
        raise RuntimeError("HeartMuLa did not produce an audio file")
    with wave.open(str(path), "rb") as handle:
        rate, frames, width, channels = handle.getframerate(), handle.getnframes(), handle.getsampwidth(), handle.getnchannels()
        peak = 0
        while block := handle.readframes(65536):
            peak = max(peak, audioop.max(block, width))
    if frames <= 0 or rate <= 0 or channels <= 0:
        raise RuntimeError("HeartMuLa produced an empty WAV; please try another seed")
    return {"sample_rate": rate, "duration": frames / rate, "peak_pcm": peak, "rms_pcm": 0.0}


def _event(line: str, marker: str) -> str | None:
    token = marker + " "
    return line.split(token, 1)[1].strip() if token in line else None


def generate(job, request: dict, output: Path) -> dict:
    status = model_status()
    if not status["ready"]:
        raise RuntimeError("HeartMuLa model files are missing: " + ", ".join(status["missing"]))
    if not runtime_status()["ready"]:
        raise RuntimeError("HeartMuLa WSL runtime is not installed or unavailable.")
    tags, lyrics = request["generation_tags"], request["rendered_lyrics"]
    payload = {
        "tags": tags, "lyrics": lyrics, "seed": int(request["seed"]),
        "max_audio_length_ms": int(float(request["duration"]) * 1000),
        "cfg_scale": float(request["cfg"]), "topk": int(request.get("top_k", 50)),
        "temperature": 1.0, "output": _worker_path(output), "model_root": _worker_path(MODEL_ROOT),
    }
    profile = generation_timing.predict(request)
    started = time.monotonic(); job.eta_seconds = profile.total_seconds; job.emit()
    proc = _start(job.cancel)
    with _LOCK:
        if job.cancel.is_set() or proc is not _PROCESS or proc.poll() is not None:
            _stop_process(proc); raise RuntimeError("cancelled")
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n"); proc.stdin.flush()
    tail = deque(maxlen=100)
    while True:
        assert proc.stdout is not None
        line = proc.stdout.readline()
        if not line:
            _stop_process(proc); raise RuntimeError("HeartMuLa worker stopped unexpectedly: " + " | ".join(tail))
        line = line.rstrip()
        if not line:
            continue
        tail.append(line); log.info("[worker] %s", line)
        gpu = _event(line, "HEARTMULA_GPU")
        progress = _event(line, "HEARTMULA_PROGRESS")
        error = _event(line, "HEARTMULA_ERROR")
        if gpu:
            try: set_gpu_policy(json.loads(gpu))
            except json.JSONDecodeError: log.warning("Ignoring malformed HeartMuLa GPU event: %s", gpu)
        elif progress:
            try: event = json.loads(progress)
            except json.JSONDecodeError: continue
            job.phase = str(event.get("message") or "Generating with HeartMuLa")
            job.progress = max(0.0, min(1.0, float(event.get("progress", 0.0))))
            job.eta_seconds = max(0.0, profile.total_seconds - (time.monotonic() - started))
            job.emit()
        elif line.strip() == "HEARTMULA_DONE":
            result = inspect_wav(output)
            result["generation_timing"] = {"compose_seconds": time.monotonic() - started, "refine_seconds": 0.0}
            return result
        elif error is not None:
            try: detail = str(json.loads(error).get("error") or error)
            except (json.JSONDecodeError, AttributeError): detail = error
            _stop_process(proc); raise RuntimeError(detail)
        if job.cancel.is_set():
            _stop_process(proc); raise RuntimeError("cancelled")
