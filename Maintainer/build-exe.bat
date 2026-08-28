@echo off
setlocal EnableExtensions
rem This file lives in Maintainer\ now. .venv, Engine_1_and_2 and the spec's
rem relative paths (engine_sources()) all resolve from the REPO ROOT, so move
rem there before doing anything else.
cd /d "%~dp0.."
title ECF Classification - build the .exe

rem ------------------------------------------------------------------
rem  For the maintainer only. Builds "ECF Classification.exe" -- the
rem  single file end users double-click, with no Python install needed.
rem  Uses the project's own .venv, so run RUN.bat at least once first
rem  (or set the venv up yourself) before running this.
rem ------------------------------------------------------------------

set "VPY=.venv\Scripts\python.exe"

if exist "%VPY%" goto CHECKPYINSTALLER
echo.
echo  ============================================================
echo    NO .venv FOUND
echo  ============================================================
echo.
echo    Run RUN.bat once first to create the project's Python
echo    environment, then run build-exe.bat again.
echo.
goto FINISH

:CHECKPYINSTALLER
"%VPY%" -c "import PyInstaller" >nul 2>&1
if not errorlevel 1 goto BUILD
echo.
echo    Installing PyInstaller into the project's environment...
"%VPY%" -m pip install --quiet pyinstaller
if errorlevel 1 goto PIPFAIL

:BUILD
echo.
echo  ============================================================
echo    BUILDING "ECF Classification.exe"
echo  ============================================================
echo.
echo    This packages the tool and its Python dependencies (pandas,
echo    numpy, openpyxl) into one file. The ML layer is deliberately
echo    excluded -- it was removed from the pipeline. Takes a minute
echo    or two.
echo.

rem  --workpath/--distpath keep PyInstaller's scratch folders inside
rem  Maintainer instead of dropping "build" and "dist" at the top level,
rem  where staff opening this in SharePoint would see them and wonder
rem  which one to click.
"%VPY%" -m PyInstaller --noconfirm ^
    --workpath "Maintainer/build" ^
    --distpath "Maintainer/dist" ^
    "Maintainer\ECF Classification.spec"
if errorlevel 1 goto BUILDFAIL

rem Copy the built exe to the REPO ROOT -- that's the file staff double-click
rem and the one START HERE.txt names, sitting beside Data Sheets/, Taxonomy/
rem and Final Review/. Overwrite any previous copy.
copy /y "Maintainer\dist\ECF Classification.exe" "ECF Classification.exe" >nul
if errorlevel 1 goto COPYFAIL

echo.
echo  ============================================================
echo    DONE
echo  ============================================================
echo.
echo    The finished file is now at the top level of this folder:
echo.
echo        ECF Classification.exe
echo.
echo    Hand THAT ONE FILE to staff (or hand over the whole folder --
echo    it's ready for SharePoint as-is). They double-click it --
echo    nothing to install, no Python, no Docker, no admin rights
echo    needed. On first run it creates its working folders on their
echo    Desktop (or reuses ones already sitting next to the .exe).
echo.
goto FINISH

:PIPFAIL
echo.
echo    Could not install PyInstaller. Check the internet connection
echo    (or company firewall/proxy) and try again.
echo.
goto FINISH

:BUILDFAIL
echo.
echo    The build failed. Scroll up for the PyInstaller error. A
echo    "module not found" error at RUN time (not here) usually means
echo    a hidden import needs to be added to "ECF Classification.spec".
echo.
goto FINISH

:COPYFAIL
echo.
echo    PyInstaller succeeded, but the file could not be copied from
echo    dist\ECF Classification.exe to the top level of this folder --
echo    usually because it's open (e.g. still running) or read-only.
echo    Close it and copy dist\ECF Classification.exe there by hand.
echo.
goto FINISH

:FINISH
echo.
pause
endlocal
