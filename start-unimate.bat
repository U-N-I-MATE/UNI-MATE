@echo off
chcp 65001 >nul
title Khoi dong UNI MATE
cd /d "%~dp0"
REM Cong chay: bien UNIMATE_PORT neu co, khong thi dong UNIMATE_PORT=... trong .env, khong thi 8688.
if "%UNIMATE_PORT%"=="" for /f "tokens=1,* delims==" %%a in ('findstr /r /b /c:"UNIMATE_PORT=[0-9]" ".env" 2^>nul') do set "UNIMATE_PORT=%%b"
if "%UNIMATE_PORT%"=="" set UNIMATE_PORT=8688

echo Bat UNI MATE chay NEN - khong con cua so den (port %UNIMATE_PORT%)...
REM Viec tat instance cu + chay server AN giao het cho start-unimate.vbs (cua so an hoan toan).
REM Log ghi vao server\unimate.log (mo file do neu can xem loi). Tat server: stop-unimate.bat.
wscript //nologo start-unimate.vbs

echo.
echo Da bat. Cho ~10 giay roi mo http://localhost:%UNIMATE_PORT% va bam Ctrl+Shift+R.
echo (Tat server: chay stop-unimate.bat. Xem loi: mo file server\unimate.log)
timeout /t 4 >nul
