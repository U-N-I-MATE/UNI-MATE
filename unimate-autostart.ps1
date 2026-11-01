# ============================================================
# UNI MATE - tu khoi dong cung Windows (ban sao cua bin/unimate-autostart.sh ben Mac).
# Goi qua unimate-autostart.bat, dung goi truc tiep tru khi biet minh dang lam gi.
#
# Cach lam (0.306.0): ghi DUNG muc ma dashboard bat/tat (HKCU\...\Run, ten "UniMateOS",
# khong can quyen admin), tro vao `wscript start-unimate.vbs /open`: dang nhap may la server
# tu chay NEN roi tu mo dashboard trong cua so rieng. install.ps1 goi file nay mac dinh.
# Truoc 0.306.0 file nay dat shortcut trong thu muc Startup, con dashboard ghi Run key: hai
# muc cung bat thi luc dang nhap hai ban UNI MATE gianh nhau cong 8688. Gio chi con Run key,
# shortcut cu bi xoa khi install/uninstall.
# ============================================================
param([string]$Action = "status")

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Startup = [Environment]::GetFolderPath("Startup")
$Lnk = Join-Path $Startup "UNI MATE.lnk"          # muc cu (truoc 0.306.0), chi de don
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$Approved = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
$Name = "UniMateOS"                                  # khop _AUTOSTART_NAME trong server/main.py

switch ($Action.ToLower()) {
  "install" {
    $vbs = Join-Path $Root "start-unimate.vbs"
    if (-not (Test-Path $vbs)) {
      Write-Host "Khong thay start-unimate.vbs canh script nay - dat unimate-autostart.ps1 o goc thu muc UNI MATE."
      exit 1
    }
    # Cung chuoi voi _autostart_command() trong server/main.py, de dashboard bao "Bat" chu khong bao "duong dan cu".
    $cmd = "wscript.exe //nologo `"$vbs`" /open"
    if (-not (Test-Path $RunKey)) { New-Item -Path $RunKey -Force | Out-Null }
    Set-ItemProperty -Path $RunKey -Name $Name -Value $cmd
    # Task Manager tat muc nay bang mot co rieng; bat lai thi go co do (giong nut trong dashboard).
    try {
      $raw = (Get-ItemProperty -Path $Approved -Name $Name -ErrorAction Stop).$Name
      if ($raw -and ($raw[0] -band 1)) {
        Set-ItemProperty -Path $Approved -Name $Name -Value ([byte[]](2,0,0,0,0,0,0,0,0,0,0,0))
      }
    } catch { }
    if (Test-Path $Lnk) { Remove-Item $Lnk -Force }
    Write-Host "Da bat tu khoi dong cung Windows: dang nhap may la UNI MATE tu chay va tu mo dashboard."
    Write-Host "Tat: unimate-autostart.bat uninstall (hoac nut trong dashboard, trang Cai dat)."
  }
  "uninstall" {
    Remove-ItemProperty -Path $RunKey -Name $Name -ErrorAction SilentlyContinue
    if (Test-Path $Lnk) { Remove-Item $Lnk -Force }
    Write-Host "Da tat tu khoi dong cung Windows."
  }
  default {
    $val = (Get-ItemProperty -Path $RunKey -Name $Name -ErrorAction SilentlyContinue).$Name
    if ($val) {
      Write-Host "DANG bat tu khoi dong: $val"
    } elseif (Test-Path $Lnk) {
      Write-Host "DANG bat theo kieu cu (shortcut $Lnk). Chay unimate-autostart.bat install de len kieu moi."
    } else {
      Write-Host "CHUA bat tu khoi dong. Bat bang: unimate-autostart.bat install"
    }
  }
}
