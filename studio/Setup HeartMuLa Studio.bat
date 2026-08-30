@echo off
setlocal
cd /d "%~dp0"

echo Setting up HeartMuLa Studio...
if not exist "python\venv\Scripts\python.exe" py -3.11 -m venv "python\venv"
if errorlevel 1 goto :failed
"python\venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"python\venv\Scripts\python.exe" -m pip install -r "python\requirements.txt"
if errorlevel 1 goto :failed
"python\venv\Scripts\python.exe" -m pip install -e ".."
if errorlevel 1 goto :failed

echo Installing the HeartMuLa GPU runtime...
if not exist "python\runtime\Scripts\python.exe" py -3.11 -m venv "python\runtime"
if errorlevel 1 goto :failed
"python\runtime\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
"python\runtime\Scripts\python.exe" -m pip install "torch==2.10.0" "torchvision==0.25.0" "torchaudio==2.10.0" --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :failed
"python\runtime\Scripts\python.exe" -m pip install -e ".." "torchcodec==0.10.0"
if errorlevel 1 goto :failed

call npm ci
if errorlevel 1 goto :failed
call npm run tauri build -- --no-bundle
if errorlevel 1 goto :failed
copy /y "src-tauri\target\release\heartmula-studio.exe" "HeartMuLa Studio.exe" >nul
echo.
echo Setup complete. HeartMuLa Studio is ready.
pause
exit /b 0

:failed
echo.
echo Setup failed. Review the error above.
pause
exit /b 1
