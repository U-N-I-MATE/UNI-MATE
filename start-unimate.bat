@echo off
chcp 65001 >nul
title Khoi dong UNI MATE
cd /d "%~dp0"

echo Bat UNI MATE chay NEN - khong con cua so den (port 7777)...
REM Viec tat instance cu + chay server AN giao het cho start-unimate.vbs (cua so an hoan toan).
REM Log ghi vao server\unimate.log (mo file do neu can xem loi). Tat server: stop-unimate.bat.
wscript //nologo start-unimate.vbs

echo.
echo Da bat. Cho ~10 giay roi mo http://localhost:7777 va bam Ctrl+Shift+R.
echo (Tat server: chay stop-unimate.bat. Xem loi: mo file server\unimate.log)
timeout /t 4 >nul
