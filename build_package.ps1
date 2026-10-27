# DouyinVN Studio - Package Build Script (PyInstaller)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       DOUYINVN STUDIO - DONG GOI WINDOWS (BUILD EXE)     " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".venv\Scripts\pyinstaller.exe")) {
    Write-Host "Chua tim thay PyInstaller trong .venv!" -ForegroundColor Red
    Write-Host "Vui long chay .\\install.ps1 de cai dat." -ForegroundColor Yellow
    exit 1
}

Write-Host "Dang chay PyInstaller dong goi ung dung..." -ForegroundColor Cyan
& .venv\Scripts\pyinstaller.exe --noconfirm DouyinVNStudio.spec

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Tao thu muc can thiet trong thu muc ban giao dist/DouyinVNStudio..." -ForegroundColor Cyan
    @("models", "workspace", "output", "logs", "data", "config") | ForEach-Object {
        $p = "dist\DouyinVNStudio\$_"
        if (-not (Test-Path $p)) {
            New-Item -ItemType Directory -Path $p -Force | Out-Null
        }
    }

    # Copy config
    if (Test-Path "config\settings.json") {
        Copy-Item "config\settings.json" "dist\DouyinVNStudio\config\settings.json" -Force
    }

    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "     DONG GOI THANH CONG! File chay: dist\\DouyinVNStudio\\DouyinVNStudio.exe" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Host "Dong goi that bai. Kiem tra log PyInstaller o tren." -ForegroundColor Red
    exit 1
}
