@echo off
setlocal enabledelayedexpansion
title NutriTool
cd /d "%~dp0"

echo ============================================
echo  NutriTool - starting local server...
echo ============================================
echo.

rem --- locate a Python 3 interpreter (try the launcher, then python, then python3) ---
set "PYCMD="
for %%C in ("py -3" "python" "python3") do (
    if not defined PYCMD (
        %%~C --version >nul 2>nul
        if !errorlevel!==0 (
            %%~C -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >nul 2>nul
            if !errorlevel!==0 set "PYCMD=%%~C"
        )
    )
)

if not defined PYCMD (
    echo [ERROR] Python 3 was not found on this computer.
    echo.
    echo Please install it from https://www.python.org/downloads/
    echo   - During install, check "Add python.exe to PATH".
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo Using Python: %PYCMD%

rem --- check dependencies; only install if something's missing (no silent internet use) ---
%PYCMD% -c "import flask" >nul 2>nul
if not %errorlevel%==0 (
    echo Installing required packages ^(one-time, needs internet^)...
    %PYCMD% -m pip install -r requirements.txt
    if not !errorlevel!==0 (
        echo.
        echo [ERROR] Failed to install required packages.
        echo Check your internet connection and try again, or run manually:
        echo   %PYCMD% -m pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
) else (
    echo Required packages already installed - skipping install.
)

if not defined PORT set "PORT=5000"

rem --- refuse to start if the port is already taken, with a clear message ---
powershell -NoProfile -Command "try { $c = New-Object System.Net.Sockets.TcpClient('127.0.0.1', %PORT%); $c.Close(); exit 1 } catch { exit 0 }" >nul 2>nul
if %errorlevel%==1 (
    echo.
    echo [ERROR] Port %PORT% is already in use on this computer.
    echo Another program ^(maybe another copy of NutriTool^) is already using it.
    echo Close that program, or run with a different port:
    echo   set PORT=5050 ^&^& run.bat
    echo.
    pause
    exit /b 1
)

rem --- open the browser automatically once the server responds (no premature "can't be reached" flash) ---
start "" /B powershell -NoProfile -WindowStyle Hidden -Command "$u='http://localhost:%PORT%/'; for($i=0;$i -lt 60;$i++){try{$c=New-Object System.Net.Sockets.TcpClient('127.0.0.1',%PORT%); if($c.Connected){$c.Close(); Start-Process $u; exit}}catch{}; Start-Sleep -Milliseconds 500}"

echo.
echo Starting server... your browser will open automatically once it's ready.
echo (Leave this window open while using NutriTool. Close it to stop the server.)
echo.

%PYCMD% app.py
set "EXITCODE=%errorlevel%"

if not "%EXITCODE%"=="0" (
    echo.
    echo [ERROR] NutriTool's server stopped unexpectedly ^(exit code %EXITCODE%^).
    echo If this keeps happening, try running it manually to see the full error:
    echo   %PYCMD% app.py
    echo.
    pause
)

endlocal
