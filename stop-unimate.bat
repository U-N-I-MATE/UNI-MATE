@echo off
chcp 65001 >nul
title Dung UNI MATE
echo Dang tim va tat UNI MATE...
REM Logic giet nam trong stop-unimate.ps1 (giet theo dung python cua venv + chu port 8688).
REM KHONG dung timeout o day: chay an qua VBS se loi "Input redirection is not supported".
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-unimate.ps1"
REM Don cua so CMD den "UNI MATE" kieu cu con sot (flow moi chay an, khong tao cua so nay).
taskkill /F /FI "IMAGENAME eq cmd.exe" /FI "WINDOWTITLE eq UNI MATE*" >nul 2>&1
echo Xong.
exit /b 0
