# DouyinVN Studio - Automated Setup & Installation Script
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         DOUYINVN STUDIO - CAI DAT HE THONG (SETUP)       " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

try {
    # 1. Kiem tra Python hoac uv
    Write-Host "[1/4] Kiem tra cong cu cai dat Python..." -ForegroundColor Cyan
    $hasUv = Get-Command uv -ErrorAction SilentlyContinue

    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Dang tao moi truong ao Python 3.12 (.venv)..." -ForegroundColor Yellow
        if ($hasUv) {
            & uv venv .venv --python 3.12
        } else {
            & py -3.12 -m venv .venv
        }
    } else {
        Write-Host "Moi truong ao .venv da ton tai." -ForegroundColor Green
    }

    # 2. Cai dat dependencies
    Write-Host "[2/4] Cai dat cac thu vien can thiet tu requirements.txt..." -ForegroundColor Cyan
    if ($hasUv) {
        & uv pip install --python .venv\Scripts\python.exe -r requirements.txt
    } else {
        & .venv\Scripts\python.exe -m pip install -r requirements.txt
    }

    # 3. Khoi tao thu muc
    Write-Host "[3/4] Khoi tao thu muc lam viec..." -ForegroundColor Cyan
    @("config", "ui", "core", "workers", "storage", "workspace", "models", "output", "logs", "data") | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
        }
    }

    # 4. Kiem tra moi truong sau cai dat
    Write-Host "[4/4] Kiem tra moi truong..." -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File .\check_environment.ps1

    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "     CAI DAT THANH CONG! Khoi chay ung dung: .\\run.ps1   " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "Loi trong qua trinh cai dat: $_" -ForegroundColor Red
    Write-Host "Vui long kiem tra ket noi mang va thu lai." -ForegroundColor Yellow
    exit 1
}
