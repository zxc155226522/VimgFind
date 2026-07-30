param(
    [switch]$Auto
)

# ============================================
# 搜图编译发布.ps1
# 功能：编译 VimgFind 并发布到「发布」目录
# 产物：发布/yyyy年M月d日H时m分s秒/
# ============================================

# 编码设置（解决中文路径/文件名乱码）
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

# 项目根目录
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

# 配置
$AppName   = "VimgFind"
$ExeName   = "VimgFind.exe"
$Python    = "python"

# 检测虚拟环境
if (Test-Path "env\Scripts\python.exe") {
    $Python = "env\Scripts\python.exe"
} elseif (Test-Path ".venv\Scripts\python.exe") {
    $Python = ".venv\Scripts\python.exe"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VimgFind 编译发布脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------
# [1/6] 终止旧进程
# ----------------------------------------
Write-Host "[1/6] 终止旧进程: $ExeName" -ForegroundColor Yellow
Stop-Process -Name "VimgFind" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Write-Host "  -> 完成" -ForegroundColor Green
Write-Host ""

# ----------------------------------------
# [2/6] 清理旧构建产物
# ----------------------------------------
Write-Host "[2/6] 清理旧构建产物" -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Path "build" -Recurse -Force }
if (Test-Path "dist")  { Remove-Item -Path "dist"  -Recurse -Force }
Write-Host "  -> 完成" -ForegroundColor Green
Write-Host ""

# ----------------------------------------
# [3/6] 编译
# ----------------------------------------
Write-Host "[3/6] 编译 $ExeName" -ForegroundColor Yellow
& $Python -m PyInstaller --noconfirm VimgFind.spec
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> 编译失败！" -ForegroundColor Red
    if (-not $Auto) { Read-Host "按回车键退出" }
    exit 1
}

# 验证输出文件
$ExePath = "dist\$AppName\$ExeName"
if (-not (Test-Path $ExePath)) {
    Write-Host "  -> 未找到输出文件: $ExePath" -ForegroundColor Red
    if (-not $Auto) { Read-Host "按回车键退出" }
    exit 1
}
Write-Host "  -> 完成" -ForegroundColor Green
Write-Host ""

# ----------------------------------------
# [4/6] 创建发布目录
# ----------------------------------------
$Timestamp  = Get-Date -Format "yyyy年M月d日H时m分s秒"
$PublishDir = Join-Path $ProjectRoot "发布\$Timestamp"
Write-Host "[4/6] 创建发布目录: 发布\$Timestamp" -ForegroundColor Yellow
New-Item -ItemType Directory -Path $PublishDir -Force | Out-Null
Write-Host "  -> 完成" -ForegroundColor Green
Write-Host ""

# ----------------------------------------
# [5/6] 复制编译产物
# ----------------------------------------
Write-Host "[5/6] 复制编译产物" -ForegroundColor Yellow
Copy-Item -Path "dist\$AppName" -Destination $PublishDir -Recurse -Force
Write-Host "  -> 完成" -ForegroundColor Green
Write-Host ""

# ----------------------------------------
# [6/6] 复制配置文件
#     复制到 VimgFind/ 内部（与 EXE 同级），排除 backups/ 和 error.log
# ----------------------------------------
Write-Host "[6/6] 复制配置文件" -ForegroundColor Yellow
$ConfigDest = Join-Path $PublishDir "$AppName\config"
New-Item -ItemType Directory -Path $ConfigDest -Force | Out-Null

Get-ChildItem -Path "config" -Exclude "backups", "error.log" | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $ConfigDest -Recurse -Force
}
Write-Host "  -> 完成" -ForegroundColor Green
Write-Host ""

# ----------------------------------------
# 完成
# ----------------------------------------
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  发布完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  发布目录: $PublishDir"
Write-Host ""

if (-not $Auto) {
    Read-Host "按回车键退出"
}
