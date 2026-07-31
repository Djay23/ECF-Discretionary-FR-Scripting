@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ECF Discretionary FR - Classification Tool

set "VENV=.venv"
set "VPY=%VENV%\Scripts\python.exe"

if exist "%VPY%" goto CHECKDEPS


rem ------------------------------------------------------------------
rem  First run on this computer: build the private Python environment.
rem ------------------------------------------------------------------
echo.
echo  ============================================================
echo    FIRST-TIME SETUP
echo  ============================================================
echo.
echo    Setting this tool up on this computer. This happens once
echo    and takes a minute or two. Please leave this window open.
echo.

set "BASEPY="
py -3 --version >nul 2>&1
if not errorlevel 1 set "BASEPY=py -3"
if defined BASEPY goto MAKEVENV

python --version >nul 2>&1
if not errorlevel 1 set "BASEPY=python"
if defined BASEPY goto MAKEVENV
goto NOPYTHON

:MAKEVENV
echo    Creating the environment...
%BASEPY% -m venv "%VENV%"
if errorlevel 1 goto VENVFAIL

echo    Installing required components...
"%VPY%" -m pip install --upgrade pip --quiet
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto DEPSFAIL
echo.
echo    Setup complete.
echo.


rem ------------------------------------------------------------------
rem  Normal start.
rem ------------------------------------------------------------------
:CHECKDEPS
"%VPY%" -c "import pandas, numpy, openpyxl" >nul 2>&1
if not errorlevel 1 goto START
echo.
echo    Some components are missing. Reinstalling them...
echo.
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto DEPSFAIL

:START
"%VPY%" "Tools\launcher.py"
goto FINISH


rem ------------------------------------------------------------------
rem  Problems, explained in plain language.
rem ------------------------------------------------------------------
:NOPYTHON
echo.
echo  ============================================================
echo    PYTHON IS NOT INSTALLED
echo  ============================================================
echo.
echo    This tool needs Python, which is free.
echo.
echo      1. Go to   https://www.python.org/downloads/
echo      2. Click the big yellow "Download Python" button.
echo      3. Run the installer.
echo      4. IMPORTANT: tick "Add python.exe to PATH" on the first
echo         screen before clicking Install.
echo      5. When it finishes, double-click RUN.bat again.
echo.
goto FINISH

:VENVFAIL
echo.
echo  ============================================================
echo    SETUP COULD NOT CREATE ITS ENVIRONMENT
echo  ============================================================
echo.
echo    This usually means the folder is read-only, or OneDrive has
echo    not finished syncing. Wait for OneDrive to show a green tick,
echo    then double-click RUN.bat again.
echo.
echo    If it keeps happening, send a photo of this window to whoever
echo    maintains this tool.
echo.
goto FINISH

:DEPSFAIL
echo.
echo  ============================================================
echo    COULD NOT DOWNLOAD THE REQUIRED COMPONENTS
echo  ============================================================
echo.
echo    This is almost always the internet connection or a company
echo    firewall blocking the download.
echo.
echo    Check you are online and try again. If you are on the office
echo    network or VPN, it may need to be allowed by IT.
echo.
goto FINISH

:FINISH
echo.
pause
endlocal
