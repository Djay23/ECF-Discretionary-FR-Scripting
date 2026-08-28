@echo off
setlocal EnableExtensions
rem This file lives in Maintainer\ now, but the build context, the "Data
rem Sheets" populated-check and the workspace resolution all need to see the
rem REPO ROOT (one level up), not this folder.
cd /d "%~dp0.."
title ECF Discretionary FR - Classification Tool (Docker)

set "IMAGE=ecf-discretionary-fr:latest"


rem ------------------------------------------------------------------
rem  Step 1: is Docker installed at all?
rem ------------------------------------------------------------------
where docker >nul 2>&1
if errorlevel 1 goto NODOCKER


rem ------------------------------------------------------------------
rem  Step 2: is Docker Desktop actually running?
rem ------------------------------------------------------------------
docker info >nul 2>&1
if errorlevel 1 goto DOCKERNOTRUNNING


rem ------------------------------------------------------------------
rem  Step 3: find the workspace -- same rule the rest of the tool uses.
rem  1. ECF_WORKSPACE_HOST, if someone has already set it.
rem  2. This folder itself, if it already has a "Data Sheets" folder with
rem     workbooks in it -- an existing install must keep working exactly
rem     where it is.
rem  3. Otherwise, "ECF Classification" on the Desktop, created if needed.
rem ------------------------------------------------------------------
if defined ECF_WORKSPACE_HOST (
    set "WORKSPACE=%ECF_WORKSPACE_HOST%"
    goto HAVEWORKSPACE
)

if exist "Data Sheets\*.xlsx" (
    set "WORKSPACE=%CD%"
    goto HAVEWORKSPACE
)

rem The Desktop is usually redirected into OneDrive on managed machines, so
rem ask the registry for the real location before falling back to a guess.
set "DESKTOP="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul ^| findstr /i "REG_"') do set "DESKTOP=%%B"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"
rem The registry often stores this as "%%USERPROFILE%%\Desktop" rather than a
rem real path. A second expansion pass turns it into one; without this the
rem tool would create a folder literally named "%%USERPROFILE%%".
call set "DESKTOP=%%DESKTOP%%"

set "WORKSPACE=%DESKTOP%\ECF Classification"
if not exist "%WORKSPACE%" (
    mkdir "%WORKSPACE%" 2>nul
    if errorlevel 1 goto WORKSPACEFAIL
)

:HAVEWORKSPACE
rem A trailing backslash right before the closing quote confuses how Windows
rem hands the argument to docker.exe, so strip one if present.
if "%WORKSPACE:~-1%"=="\" set "WORKSPACE=%WORKSPACE:~0,-1%"


rem ------------------------------------------------------------------
rem  Step 4: build the image if this is the first run.
rem ------------------------------------------------------------------
docker image inspect %IMAGE% >nul 2>&1
if not errorlevel 1 goto RUNIT

echo.
echo  ============================================================
echo    FIRST-TIME SETUP
echo  ============================================================
echo.
echo    Building the tool's Docker image. This happens once and can
echo    take a few minutes depending on your internet connection.
echo    Please leave this window open.
echo.
docker build -t %IMAGE% -f "Maintainer\Dockerfile" .
if errorlevel 1 goto BUILDFAIL
echo.
echo    Setup complete.
echo.


rem ------------------------------------------------------------------
rem  Step 5: run it. Same numbered menu as RUN.bat.
rem ------------------------------------------------------------------
:RUNIT
echo.
echo  ============================================================
echo    STARTING THE TOOL
echo  ============================================================
echo.
echo    Your workbooks folder:
echo        %WORKSPACE%
echo.
docker run -it --rm -v "%WORKSPACE%:/data" %IMAGE%
goto FINISH


rem ------------------------------------------------------------------
rem  Problems, explained in plain language.
rem ------------------------------------------------------------------
:NODOCKER
echo.
echo  ============================================================
echo    DOCKER IS NOT INSTALLED
echo  ============================================================
echo.
echo    This tool needs Docker Desktop, which is free.
echo.
echo      1. Go to   https://www.docker.com/products/docker-desktop/
echo      2. Download Docker Desktop for Windows and run the installer.
echo      3. Restart your computer if it asks you to.
echo      4. Start Docker Desktop and wait for the whale icon in the
echo         bottom-right taskbar tray to stop animating -- that means
echo         it is ready.
echo      5. When it finishes, double-click "RUN (Docker).bat" again.
echo.
goto FINISH

:DOCKERNOTRUNNING
echo.
echo  ============================================================
echo    DOCKER IS NOT RUNNING
echo  ============================================================
echo.
echo    Docker Desktop is installed but does not appear to be running,
echo    which is the most common reason this tool won't start.
echo.
echo      1. Open Docker Desktop from the Start menu.
echo      2. Wait for the whale icon in the bottom-right taskbar tray
echo         to stop animating -- that means it is ready.
echo      3. Double-click "RUN (Docker).bat" again.
echo.
goto FINISH

:WORKSPACEFAIL
echo.
echo  ============================================================
echo    COULD NOT CREATE THE WORKING FOLDER
echo  ============================================================
echo.
echo    Tried to create it here:
echo        %WORKSPACE%
echo.
echo    This is usually a permissions problem, or OneDrive has not
echo    finished syncing. Wait for OneDrive to show a green tick, then
echo    double-click "RUN (Docker).bat" again.
echo.
goto FINISH

:BUILDFAIL
echo.
echo  ============================================================
echo    COULD NOT BUILD THE DOCKER IMAGE
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
