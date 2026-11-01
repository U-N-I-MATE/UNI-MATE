@echo off
chcp 65001 >nul
title Tu khoi dong UNI MATE
REM Tu khoi dong UNI MATE cung Windows. Dung: unimate-autostart.bat install | uninstall | status
REM Logic nam trong unimate-autostart.ps1 (ghi/xoa muc UniMateOS trong HKCU Run, khong can quyen
REM admin). Bat roi thi dang nhap may la server tu chay nen va tu mo dashboard (0.306.0).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0unimate-autostart.ps1" %1
