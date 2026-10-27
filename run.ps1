# DouyinVN Studio - Application Launcher Script
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Host.UI.RawUI.WindowTitle = "DouyinVN Studio"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Chua tim thay moi truong ao .venv!" -ForegroundColor Red
    Write-Host "Vui long chay .\\install.ps1 de cai dat truoc." -ForegroundColor Yellow
    exit 1
}

$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "Dang khoi dong DouyinVN Studio..." -ForegroundColor Cyan
& .venv\Scripts\python.exe app.py
