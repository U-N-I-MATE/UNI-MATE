@echo off
chcp 65001 >nul
title UNI MATE
cd /d "%~dp0"

REM ============================================================
REM  UNI MATE - mo nhu mot app tren Windows (ban sao cua "UNI MATE.app" ben Mac).
REM  Double-click: server tu chay nen (khong cua so den) roi dashboard tu mo
REM  thanh CUA SO RIENG (Edge/Chrome che do --app: khong thanh dia chi, co o
REM  rieng tren taskbar). Tu khoi dong cung may: unimate-autostart.bat install.
REM ============================================================

REM Cong chay: bien UNIMATE_PORT neu co, khong thi dong UNIMATE_PORT=... trong .env, khong thi 8688.
if "%UNIMATE_PORT%"=="" for /f "tokens=1,* delims==" %%a in ('findstr /r /b /c:"UNIMATE_PORT=[0-9]" ".env" 2^>nul') do set "UNIMATE_PORT=%%b"
if "%UNIMATE_PORT%"=="" set UNIMATE_PORT=8688
set "URL=http://127.0.0.1:%UNIMATE_PORT%"

REM Server dang chay roi thi KHONG khoi dong lai (start-unimate.vbs se kill instance
REM cu truoc - double-click lan hai ma restart thi mat het viec dang chay do).
REM Chi mo cua so.
curl -sf -m 2 -o nul %URL%/health 2>nul
if %errorlevel%==0 goto :open

echo Dang bat UNI MATE (chay nen, log o server\unimate.log)...
wscript //nologo start-unimate.vbs

REM Cho server len (toi da ~45 giay) roi moi mo - mo som chi thay trang trang.
REM May thieu curl (Windows cu): khong tham do duoc thi cho 8 giay roi mo dai.
where curl >nul 2>&1
if not %errorlevel%==0 (
  timeout /t 8 >nul
  goto :open
)
set /a _thu=0
:wait
set /a _thu+=1
if %_thu% gtr 45 goto :open
timeout /t 1 >nul
curl -sf -m 2 -o nul %URL%/health 2>nul
if not %errorlevel%==0 goto :wait

:open
REM Uu tien cua so app (khong thanh dia chi). Edge co san tren moi Windows 10/11;
REM khong thay thi thu Chrome; cung khong co thi mo trinh duyet mac dinh.
set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" ( start "" "%EDGE%" --app=%URL% & goto :eof )
set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" ( start "" "%EDGE%" --app=%URL% & goto :eof )
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" ( start "" "%CHROME%" --app=%URL% & goto :eof )
set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" ( start "" "%CHROME%" --app=%URL% & goto :eof )
start "" %URL%
