from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The Studio remains self-contained, but HeartMuLa checkpoints and its Linux
# inference environment live alongside the upstream checkout rather than in
# the copied studio's original model layout.
PROJECT_ROOT = ROOT.parent
MODEL_ROOT = Path(os.environ.get("HEARTMULA_MODEL_ROOT", PROJECT_ROOT / "ckpt")).expanduser()
ENGINE_ROOT = ROOT / "python" / "vendor" / "ComfyUI"
# Kept for the optional Demucs worker used by the existing Studio features.
_studio_runtime = Path(os.environ.get("HEARTMULA_STUDIO_WORKER_PYTHON", ROOT / "python" / "runtime" / "Scripts" / "python.exe")).expanduser()
if not _studio_runtime.is_file():
    # Reuse the existing MiniMax utility runtime; do not install another copy.
    _studio_runtime = Path(r"F:\MiniMaxM3\python\runtime\Scripts\python.exe")
WORKER_PYTHON = _studio_runtime
# HeartMuLa was installed in the project's WSL virtual environment.  The
# controller is normally Windows-native, so music3_engine invokes this through
# wsl.exe and translates only the paths that cross that boundary.
HEARTMULA_WORKER_PYTHON = Path(
    os.environ.get("HEARTMULA_WORKER_PYTHON", PROJECT_ROOT / ".venv" / "bin" / "python")
).expanduser()
HEARTMULA_WSL_PYTHON = os.environ.get(
    "HEARTMULA_WSL_PYTHON", "/mnt/f/Heartmula_music/.venv/bin/python"
)
OUTPUTS_ROOT = ROOT / "outputs"
LIBRARY_ROOT = OUTPUTS_ROOT / "library"
LOGS_ROOT = OUTPUTS_ROOT / "logs"
SIDECAR_HOST = "127.0.0.1"
SIDECAR_PORT = 7784

