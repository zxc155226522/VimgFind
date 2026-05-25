@echo off
setlocal
cd /d "%~dp0"

set "APP_NAME=VimgFind"
set "EXE_NAME=VimgFind.exe"
set "PYTHON=python"
set "RUN_ERROR=0"

if exist "env\Scripts\python.exe" set "PYTHON=env\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"

echo [1/4] Stop old process: %EXE_NAME%
taskkill /F /IM "%EXE_NAME%" >nul 2>nul

echo [2/4] Check PyInstaller
"%PYTHON%" -m PyInstaller --version >nul 2>nul
if errorlevel 1 goto INSTALL_PYINSTALLER
goto BUILD_EXE

:INSTALL_PYINSTALLER
echo Installing PyInstaller...
"%PYTHON%" -m pip install pyinstaller
if errorlevel 1 goto PIP_ERROR

:BUILD_EXE
echo [3/4] Build %EXE_NAME%
"%PYTHON%" -m PyInstaller --noconfirm --clean --console --name "%APP_NAME%" --icon "config\favicon.ico" --collect-all ttkbootstrap --collect-all tkinterdnd2 "main.py"
if errorlevel 1 goto BUILD_ERROR

if not exist "dist\%APP_NAME%\%EXE_NAME%" goto MISSING_EXE

echo [4/4] Run new exe
echo Keep this window open to show errors.
"dist\%APP_NAME%\%EXE_NAME%"
set "RUN_ERROR=%ERRORLEVEL%"
if not "%RUN_ERROR%"=="0" echo Program exited with code: %RUN_ERROR%
goto END

:PIP_ERROR
echo Failed to install PyInstaller.
goto FAIL

:BUILD_ERROR
echo Build failed.
goto FAIL

:MISSING_EXE
echo Missing output: dist\%APP_NAME%\%EXE_NAME%
goto FAIL

:FAIL
set "RUN_ERROR=1"

:END
echo Done.
pause
endlocal
exit /b %RUN_ERROR%
