@echo off
setlocal
cd /d "%~dp0"
if exist "HeartMuLa Studio.exe" (
  start "" "HeartMuLa Studio.exe"
) else (
  echo HeartMuLa Studio is not built yet. Run "Setup HeartMuLa Studio.bat" first.
  pause
)
