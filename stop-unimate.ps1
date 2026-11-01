# Dung UNI MATE - giet theo DUNG python cua venv nay (moi tien trinh cha/con), khong dua vao port/tieu de.
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
# CONG CHAY: mac dinh 8688. Doi cong (vi du chay song song voi mot ban khac dang giu 8688) bang dong
# UNIMATE_PORT=... trong .env; bien moi truong UNIMATE_PORT neu co thi thang (giong server: load_dotenv
# khong ghi de bien da co). Moi buoc ben duoi chi dung $Port, khong viet cung 8688.
function Get-UniPort($root) {
  if ($env:UNIMATE_PORT -match '^\d+$') { return [int]$env:UNIMATE_PORT }
  $f = Join-Path $root ".env"
  if (Test-Path $f) {
    $m = Select-String -Path $f -Pattern '^\s*UNIMATE_PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($m) { return [int]$m.Matches[0].Groups[1].Value }
  }
  return 8688
}
$Port = Get-UniPort $Root
$killed = $false
# LUU Y: python cua venv chi la LAUNCHER - no re-exec Python goc lam tien trinh CON
# (con nay moi giu port). Vi vay loc theo COMMANDLINE chu khong theo duong dan exe.
# CHI GIET CUA BAN NAY: may co the chay mot ban UNI MATE (hoac JAVIS) khac cung goi "server\main.py".
# Launcher cua ban nay co exe nam trong $Root\.venv; tien trinh con nhan ra qua ParentProcessId.
$tatCa = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
  $_.CommandLine -like '*server\main.py*'
})
$venv = (Join-Path $Root ".venv").ToLower()
$cha = @($tatCa | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLower().StartsWith($venv) } | ForEach-Object { $_.ProcessId })
$tatCa | Where-Object { ($cha -contains $_.ProcessId) -or ($cha -contains $_.ParentProcessId) } | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  Write-Host "  - Da tat python PID $($_.ProcessId)"
  $killed = $true
}
# Phong ho: ai dang giu cong cua ban nay (truong hop chay bang python khac / cai dat khac)
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
  Write-Host "  - Da tat PID $($_.OwningProcess) (chu port $Port)"
  $killed = $true
}
if (-not $killed) { Write-Host '  (Khong thay server nao dang chay)' }
exit 0
