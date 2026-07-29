@echo off
setlocal
cd /d "%~dp0"

set "APP_NAME=VimgFind"
set "EXE_NAME=VimgFind.exe"

echo Run: dist\%APP_NAME%\%EXE_NAME%
echo Keep this window open to show errors.
echo.

if not exist "dist\%APP_NAME%\%EXE_NAME%" goto MISSING_EXE

"dist\%APP_NAME%\%EXE_NAME%"
set "RUN_ERROR=%ERRORLEVEL%"
if not "%RUN_ERROR%"=="0" echo Program exited with code: %RUN_ERROR%
goto END

:MISSING_EXE
echo Missing exe. Run build_run.bat first.
set "RUN_ERROR=1"

:END
echo Done.
pause
endlocal
exit /b %RUN_ERROR%
