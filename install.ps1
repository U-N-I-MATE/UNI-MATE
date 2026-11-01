# ============================================================
# UNI MATE - CAI MOT LAN TREN WINDOWS
#
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# Cai het trong mot luot: Python deps (venv) + BON bo nao CLI chay bang goi thue bao
# (claude, codex, agy, grok) + .env + giai phong port 7777, roi bat server.
#
# Vi sao co file nay: truoc day nguoi dung Windows phai tu di bon duong khac nhau (setup.bat
# chi cai claude + codex; agy va grok phai tu mo PowerShell go tung lenh cua nha cung cap),
# nen ai khong quen ky thuat thi dung o man Models voi hai the bao "CLI chua cai".
#
# HAI CHO DE SAI, ca hai da xu ly trong file nay:
#   1. `pip install` HONG ma khong ai kiem ma loi -> server bat len roi moi chet vi thieu
#      claude-agent-sdk. Buoc [2] duoi day dung han va noi ro neu pip hong.
#   2. Cai CLI xong ma PATH cua PHIEN HIEN TAI chua co -> buoc tong ket bao "chua cai" cho
#      mot CLI vua cai xong. Refresh-Path doc lai PATH tu registry sau moi lan cai.
#
# QUAN TRONG: UNI MATE doc PATH LUC NO BAT. Cai them CLI sau khi server dang chay thi phai
# khoi dong lai UNI MATE moi thay (stop-unimate.bat roi start-unimate.vbs).
#
# KHONG dung ky tu co dau trong file .ps1: PowerShell tren Windows doc file khong BOM bang
# ANSI codepage, chu co dau se thanh rac ngay tren man hinh nguoi dung.
# ============================================================
param(
  [switch]$NoStart,      # cai xong khong tu bat server
  [switch]$NoAutostart,  # khong bat tu khoi dong cung Windows (mac dinh BAT tu 0.306.0)
  [switch]$SkipCli,      # bo qua buoc cai 4 CLI (chi cai Python deps)
  [int]$Port = 0         # cong chay UNI MATE (ghi vao .env); bo trong = giu .env, mac dinh 7777
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Line($t) { Write-Host $t }
function Step($n, $t) { Write-Host "" ; Write-Host "[$n] $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "    OK  $t" -ForegroundColor Green }
function Warn($t) { Write-Host "    [!] $t" -ForegroundColor Yellow }
function Err($t) { Write-Host "    [LOI] $t" -ForegroundColor Red }

# PATH cua phien hien tai KHONG tu cap nhat sau khi mot installer ghi vao registry. Doc lai
# ca Machine + User de buoc tong ket noi dung su that, va de `npm` vua cai bang winget dung
# duoc ngay trong cung mot luot chay.
function Refresh-Path {
  $m = [Environment]::GetEnvironmentVariable("Path", "Machine")
  $u = [Environment]::GetEnvironmentVariable("Path", "User")
  $env:PATH = (@($m, $u) | Where-Object { $_ }) -join ";"
}

function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Line ""
Line " =========================================="
Line "  UNI MATE - cai dat tren Windows"
Line " =========================================="

# ---------------------------------------------------------------- [1] Python
Step 1 "Kiem tra Python"
# "python" co the chi la LOI TAT cua Microsoft Store (WindowsApps\python.exe): Get-Command thay no,
# nhung chay thi in "Python was not found..." va tao .venv that bai (chu repo gap 01/11/2026 tren may
# cai Python 3.14 bang Python install manager, khong them vao PATH). Vi vay phai CHAY thu de biet that,
# roi tim tiep qua lenh py va cac thu muc cai Python quen thuoc; thay thi them vao PATH cua phien nay.
function Test-Py($exe) {
  try { $v = (& $exe --version 2>&1 | Out-String).Trim() } catch { return $false }
  return ($v -match '^Python 3\.\d+')
}
function Find-Python {
  if ((Have "python") -and (Test-Py "python")) { return $true }
  $cands = @()
  if (Have "py") {
    try { $e = (& py -3 -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim(); if ($e) { $cands += $e } } catch {}
  }
  foreach ($g in @("$env:LOCALAPPDATA\Python\pythoncore-3*\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                   "$env:ProgramFiles\Python3*\python.exe")) {
    $cands += @(Get-ChildItem -Path $g -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
  }
  foreach ($c in $cands) {
    if ($c -and (Test-Path $c) -and (Test-Py $c)) {
      $d = Split-Path -Parent $c
      $env:PATH = "$d;$d\Scripts;$env:PATH"
      Ok "Dung Python tai $d"
      return $true
    }
  }
  return $false
}
if (-not (Find-Python)) {
  if (Have "winget") {
    Line "    Chua co Python, dang cai bang winget..."
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements | Out-Null
    Refresh-Path
  }
}
if (-not (Find-Python)) {
  Err "Chua co Python. Tai Python 3.12 o python.org, tick 'Add python.exe to PATH', roi chay lai file nay."
  exit 1
}
$pyv = (python --version 2>&1)
Ok "$pyv"

# ---------------------------------------------------------------- [2] venv + deps
Step 2 "Cai thu vien Python (venv)"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
  if ($LASTEXITCODE -ne 0) { Err "Khong tao duoc .venv"; exit 1 }
}
$vpy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) { Err "Thieu .venv\Scripts\python.exe - xoa thu muc .venv roi chay lai."; exit 1 }
& $vpy -m pip install --upgrade pip -q
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
  Err "pip install THAT BAI. Server se bao 'thieu claude-agent-sdk' neu bo qua buoc nay."
  Line "    Thu lai: .venv\Scripts\python.exe -m pip install -r requirements.txt"
  Line "    Hay gap loi UnicodeDecodeError thi may dang thieu Visual C++ Build Tools / mang chan pypi."
  exit 1
}
Ok "Da cai xong thu vien (gom claude-agent-sdk)"

# ---------------------------------------------------------------- [3] Node + 4 CLI
if ($SkipCli) {
  Step 3 "Bo qua buoc cai CLI (-SkipCli)"
} else {
  Step 3 "Cai 4 bo nao CLI (chay bang goi thue bao, khong can mua API key)"
  if (-not (Have "npm")) {
    if (Have "winget") {
      Line "    Chua co Node.js, dang cai bang winget..."
      winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements | Out-Null
      Refresh-Path
    }
  }
  if (Have "npm") {
    foreach ($it in @(
      @{ pkg = "@anthropic-ai/claude-code"; bin = "claude"; ten = "Claude Code" },
      @{ pkg = "@openai/codex"; bin = "codex"; ten = "Codex - goi ChatGPT" }
    )) {
      if (Have $it.bin) { Ok "$($it.ten): da co san"; continue }
      Line "    $($it.ten): dang cai (npm install -g $($it.pkg))..."
      cmd /c "npm install -g $($it.pkg)" | Out-Null
      Refresh-Path
      if (Have $it.bin) { Ok "$($it.ten)" } else { Warn "$($it.ten) cai chua duoc. Cai tay: npm install -g $($it.pkg)" }
    }
  } else {
    Warn "Chua co Node.js nen bo qua Claude Code + Codex. Cai Node LTS o nodejs.org roi chay lai file nay."
  }

  # agy va grok KHONG cai bang npm: moi nha mot script cai rieng. Best-effort tung cai -
  # mot cai hong khong duoc chan ba cai con lai.
  foreach ($it in @(
    @{ bin = "agy"; ten = "Antigravity CLI (Google)"; url = "https://antigravity.google/cli/install.ps1" },
    @{ bin = "grok"; ten = "Grok Build (xAI)"; url = "https://x.ai/cli/install.ps1" }
  )) {
    if (Have $it.bin) { Ok "$($it.ten): da co san"; continue }
    Line "    $($it.ten): dang cai tu $($it.url) ..."
    try {
      $sc = (Invoke-RestMethod -Uri $it.url -UseBasicParsing -TimeoutSec 60)
      Invoke-Expression $sc
      Refresh-Path
      if (Have $it.bin) { Ok "$($it.ten)" } else { Warn "$($it.ten): script chay xong nhung chua thay binary. Mo PowerShell moi roi thu: irm $($it.url) | iex" }
    } catch {
      Warn "$($it.ten) cai chua duoc ($($_.Exception.Message)). Cai tay: irm $($it.url) | iex"
    }
  }
}

# ---------------------------------------------------------------- [4] .env
Step 4 "Kiem tra .env"
if ((-not (Test-Path ".env")) -and (Test-Path "env.example")) {
  Copy-Item "env.example" ".env"
  Ok "Da tao .env tu env.example"
} else {
  Ok ".env da co"
}

# CONG CHAY: mac dinh 7777. Doi cong (vi du chay song song voi mot ban khac dang giu 7777) bang dong
# UNIMATE_PORT=... trong .env; bien moi truong UNIMATE_PORT neu co thi thang (giong server: load_dotenv
# khong ghi de bien da co). Moi buoc ben duoi chi dung $Port, khong viet cung 7777.
function Get-UniPort($root) {
  if ($env:UNIMATE_PORT -match '^\d+$') { return [int]$env:UNIMATE_PORT }
  $f = Join-Path $root ".env"
  if (Test-Path $f) {
    $m = Select-String -Path $f -Pattern '^\s*UNIMATE_PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($m) { return [int]$m.Matches[0].Groups[1].Value }
  }
  return 7777
}
if ($Port -gt 0) {
  $envf = Join-Path $Root ".env"
  # Doc/ghi bang UTF-8 khong BOM: .env co the co chu tieng Viet, Get-Content/Set-Content cua
  # PowerShell 5 doc ANSI va ghi kem BOM se lam hong no.
  $dong = @()
  if (Test-Path $envf) { $dong = @([IO.File]::ReadAllLines($envf) | Where-Object { $_ -notmatch '^\s*UNIMATE_PORT\s*=' }) }
  [IO.File]::WriteAllLines($envf, [string[]]($dong + "UNIMATE_PORT=$Port"), (New-Object Text.UTF8Encoding $false))
  Ok "Ghi UNIMATE_PORT=$Port vao .env"
}
$Port = Get-UniPort $Root

# ---------------------------------------------------------------- [5] port
Step 5 "Giai phong port $Port"
$conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conns) {
  foreach ($c in $conns) {
    try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop; Ok "Da tat tien trinh cu PID $($c.OwningProcess)" }
    catch { Warn "Khong tat duoc PID $($c.OwningProcess) - dong tay roi chay lai." }
  }
} else {
  Ok "Port $Port dang trong"
}

# ---------------------------------------------------------------- tong ket
Refresh-Path
Line ""
Line " =========================================="
Line "  BO NAO SAN SANG (chon o trang Models)"
Line " =========================================="
foreach ($it in @(
  @{ bin = "claude"; ten = "Claude Code    " },
  @{ bin = "codex"; ten = "Codex (ChatGPT)" },
  @{ bin = "agy"; ten = "Antigravity CLI" },
  @{ bin = "grok"; ten = "Grok Build     " }
)) {
  if (Have $it.bin) {
    $p = (Get-Command $it.bin).Source
    Write-Host "  [x] $($it.ten)  $p" -ForegroundColor Green
  } else {
    Write-Host "  [ ] $($it.ten)  chua cai" -ForegroundColor Yellow
  }
}
Line ""
Line "  Dang nhap tung bo nao NGAY TRONG trang Models cua dashboard - khong can go lenh."
Line "  Cai them CLI sau nay thi phai KHOI DONG LAI UNI MATE (stop-unimate.bat roi start-unimate.vbs),"
Line "  vi tien trinh dang chay giu PATH cua luc no bat."
Line ""

# ---------------------------------------------------------------- [5b] tu khoi dong
# 0.306.0, chu repo 24/10/2026: "mac dinh cai unimate tren win hoac mac thi cai khoi dong cung trinh duyet".
# Dang nhap may la UNI MATE tu chay nen roi tu mo dashboard. Tat: -NoAutostart, unimate-autostart.bat uninstall,
# hoac nut trong trang Cai dat.
if (-not $NoAutostart) {
  $as = Join-Path $Root "unimate-autostart.ps1"
  if (Test-Path $as) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $as install | Out-Null
    if ($LASTEXITCODE -eq 0) { Ok "Tu khoi dong cung Windows: BAT (dang nhap may la UNI MATE tu mo)" }
    else { Warn "Chua bat duoc tu khoi dong. Bat sau: unimate-autostart.bat install" }
  }
}

# ---------------------------------------------------------------- [6] bat server
if ($NoStart) {
  Line "  Cai xong. Bat server: start-unimate.vbs (chay nen) hoac setup.bat (hien cua so)."
  exit 0
}
Step 6 "Bat UNI MATE"
$vbs = Join-Path $Root "start-unimate.vbs"
if (Test-Path $vbs) {
  # /open: cho server len roi mo dashboard luon (0.306.0).
  Start-Process "wscript.exe" -ArgumentList "//nologo `"$vbs`" /open" -WorkingDirectory $Root
  Ok "Server dang chay nen, dashboard se tu mo. Log: server\unimate.log"
} else {
  Start-Process $vpy -ArgumentList "main.py" -WorkingDirectory (Join-Path $Root "server")
  Ok "Server dang chay"
}
Line ""
Line "  Mo: http://localhost:$Port"
Line ""
