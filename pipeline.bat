@echo off
rem ============================================================
rem  pipeline.bat - Anki TTS pipeline (GPT-SoVITS)
rem  Standalone launcher. This .bat can live in any folder.
rem  The GPT-SoVITS engine folder is resolved in this order:
rem    1. env var GPT_SOVITS_ROOT
rem    2. file gptsovits_path.txt next to this .bat (one line = path)
rem    3. this .bat's own folder (if it sits inside GPT-SoVITS)
rem
rem  Double-click: opens interactive menu.
rem  Or call directly, e.g.:
rem    pipeline.bat list
rem    pipeline.bat make-deck --voice madara --query "deck:Arhitektura" --limit 20
rem ============================================================
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem --- locate the GPT-SoVITS engine ---
if defined GPT_SOVITS_ROOT set "ENGINE=%GPT_SOVITS_ROOT%"
if not defined ENGINE if exist "%~dp0app\gptsovits_path.txt" (
    for /f "usebackq delims=" %%i in ("%~dp0app\gptsovits_path.txt") do if not defined ENGINE set "ENGINE=%%i"
)
if not defined ENGINE if exist "%~dp0gptsovits_path.txt" (
    for /f "usebackq delims=" %%i in ("%~dp0gptsovits_path.txt") do if not defined ENGINE set "ENGINE=%%i"
)
if not defined ENGINE if exist "%~dp0runtime\python.exe" set "ENGINE=%~dp0"
rem strip any stray quotes around the path
if defined ENGINE set ENGINE=%ENGINE:"=%

if not exist "%ENGINE%\runtime\python.exe" (
    echo.
    echo  GPT-SoVITS not found. Point to its folder in one of these ways:
    echo    * create gptsovits_path.txt next to pipeline.bat ^(one line = path^)
    echo    * or set the env var GPT_SOVITS_ROOT
    echo    * or run AnkiVoice.exe and pick the folder there ^(saved to config^)
    echo.
    pause
    exit /b 1
)

rem pass the resolved engine to the child so it resolves identically
set "GPT_SOVITS_ROOT=%ENGINE%"

rem --- the pipeline lives in app\ (in the installed app — next to this file) ---
set "PIPELINE=%~dp0app\voice_pipeline.py"
if not exist "%PIPELINE%" set "PIPELINE=%~dp0voice_pipeline.py"

if "%~1"=="" (
    "%ENGINE%\runtime\python.exe" -u "%PIPELINE%"
) else (
    "%ENGINE%\runtime\python.exe" -u "%PIPELINE%" %*
)

echo.
pause
