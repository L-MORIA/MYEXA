@echo off
rem Test harness for the provider-detection block used in run.bat.
set MYEXA_PROVIDER=
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "try { $h = Invoke-RestMethod 'http://localhost:3005/api/health?deep=true'; $h.active_provider } catch { '' }"`) do set MYEXA_PROVIDER=%%a
echo DETECTED=[%MYEXA_PROVIDER%]
if "%MYEXA_PROVIDER%"=="searxng" (
    echo NOTE BRANCH PRINTED
) else (
    echo NOTE BRANCH SKIPPED
)
