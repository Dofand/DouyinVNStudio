# DouyinVN Studio - Check Environment
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       DOUYINVN STUDIO - KIEM TRA MOI TRUONG HE THONG     " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$AllOk = $true

# 1. He dieu hanh
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "[1/6] He dieu hanh: " -NoNewline
Write-Host "$($os.Caption) ($($os.Version))" -ForegroundColor Green

# 2. Python
Write-Host "[2/6] Kiem tra Python 3.12: " -NoNewline
if (Test-Path ".venv\Scripts\python.exe") {
    $ver = & ".venv\Scripts\python.exe" --version
    Write-Host "Moi truong ao (.venv) san sang: $ver" -ForegroundColor Green
} else {
    $sysPy = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPy) {
        $ver = & python --version
        Write-Host "Python he thong: $ver" -ForegroundColor Yellow
    } else {
        Write-Host "Chua tim thay Python! Can cai dat Python 3.12." -ForegroundColor Red
        $AllOk = $false
    }
}

# 3. FFmpeg & FFprobe
Write-Host "[3/6] Kiem tra FFmpeg & FFprobe: " -NoNewline
$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobeCmd = Get-Command ffprobe -ErrorAction SilentlyContinue

if ($ffmpegCmd -and $ffprobeCmd) {
    Write-Host "San sang trong PATH: $($ffmpegCmd.Source)" -ForegroundColor Green
} else {
    Write-Host "Chua tim thay FFmpeg trong PATH. Hay kiem tra settings.json hoac winget install Gyan.FFmpeg." -ForegroundColor Yellow
}

# 4. GPU NVIDIA & CUDA
Write-Host "[4/6] Kiem tra Card do hoa (GPU): " -NoNewline
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    $gpuName = & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    Write-Host "GPU: $gpuName" -ForegroundColor Green
} else {
    Write-Host "Khong co GPU NVIDIA. Ung dung se chay che do CPU INT8 toi uu." -ForegroundColor Gray
}

# 5. VSR (Video-Subtitle-Remover)
Write-Host "[5/6] Kiem tra VSR: " -NoNewline
Write-Host "Ho tro tich hop VSR, lam mo FFmpeg hoac bo qua xoa nen." -ForegroundColor Yellow

# 6. Cache Mo hinh AI
Write-Host "[6/6] Kiem tra Models AI Offline: " -NoNewline
if (Test-Path "models\models--Systran--faster-whisper-tiny") {
    Write-Host "Da co cache model Whisper & Translation trong models/." -ForegroundColor Green
} else {
    Write-Host "Chua co cache model. Ung dung se tu dong tai khi bat dau." -ForegroundColor Yellow
}

Write-Host ""
if ($AllOk) {
    Write-Host "===> MOI TRUONG DA SAN SANG DE CHAY DOUYINVN STUDIO! <===" -ForegroundColor Green
} else {
    Write-Host "===> VUI LONG KIEM TRA CAC CANH BAO O TREN. <===" -ForegroundColor Red
}
Write-Host ""
