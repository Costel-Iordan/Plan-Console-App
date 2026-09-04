@echo off
rem ============================================================
rem  PLAN CONSOLE LAUNCHER
rem  1. Runs plan-console.py that sits NEXT TO this file.
rem  2. Tries "py" first, then "python" (two Python installers).
rem  3. If Python is missing, it says so instead of flashing away.
rem ============================================================

rem --- Step 1: is the "py" launcher installed? ---
where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0plan-console.py"
    goto end
)

rem --- Step 2: is "python" installed AND real? ---
rem The Microsoft Store installs a fake python.exe stub in WindowsApps
rem that only opens the Store. Require "python --version" to succeed
rem before trusting it.
where python >nul 2>nul
if %errorlevel%==0 (
    python --version >nul 2>nul
    if not errorlevel 1 (
        python "%~dp0plan-console.py"
        goto end
    )
)

rem --- Step 3: neither found — explain instead of dying silently ---
echo.
echo  Python was not found on this computer.
echo.
echo  Fix: install Python from https://www.python.org/downloads/
echo  and TICK the box "Add python.exe to PATH" during setup,
echo  then double-click this file again.
echo.
pause
exit /b 1

:end
rem keep the window open ONLY if Python crashed (an error was printed)
if errorlevel 1 pause